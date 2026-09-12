"""Tidsbevisst hendelsesreplay: kjør coordinatoren slik den kjører i drift.

Den gamle replayen (`tests/test_coordinator_replay.py`) matet én poll per
klokketime, med hele timens energi og timens pris, på naiv lokaltid. Det er
ikke en rytme som finnes i produksjon, og en test i den rytmen kan ikke se de
feilene rytmen skjuler: at energien bokføres i bøtten pollen står i framfor i
timen den ble målt, at prisen som brukes er den som gjaldt da vi spurte, og at
et poll noen sekunder på feil side av et timeskifte flytter kilowattimer.

Her er tiden hendelsenes, ikke testens:

* **Målinger** har en egen observasjonstid (`last_updated` på HA-staten).
  Telleren rapporterer når den vil, ikke når vi poller.
* **Priser** publiseres per prisrute. Sensoren er en trinnfunksjon: den viser
  prisen for ruten som gjelder nå, og verdien er den samme uansett når i ruten
  vi leser den.
* **Poll** skjer hvert minutt med jitter, slik HAs `async_track_time_interval`
  faktisk oppfører seg. Samme historikk skal gi samme avregning uansett hvor
  jitteret lander (C2.6).
* **Omstart** er å bygge coordinatoren på nytt mot den samme lagrede boken.
  Hendelsene fortsetter, og resultatet skal være det samme (C2.7).
* **Tid er alltid tidssoneklar Europe/Oslo.** Sommertidsskiftene er ekte
  skifter, ikke en time som forsvinner fordi noen droppet tzinfo.

Harnesset er med vilje ikke en fasit. Det kjører den ekte coordinatoren og
rapporterer hva den kom fram til; fasiten står i `fasit.py`, og testene
sammenligner de to.
"""

from __future__ import annotations

import asyncio
import random
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

from tests.conftest import _make_entry
from tests.replay.fasit import OSLO, Fasit, Hendelseslogg, Satser, krev_aware, prisrutestart

if TYPE_CHECKING:
    from collections.abc import Iterator

UPDATE_INTERVAL_SEKUNDER = 60


# ---------------------------------------------------------------------------
# HA-etterligninger: bare det coordinatoren faktisk rører ved
# ---------------------------------------------------------------------------


class FalskState:
    """HA-state med både verdi og `last_updated`.

    `tests.conftest._make_state` gir bare `.state`. Den holder for en test som
    ikke bryr seg om når verdien ble satt, men hele denne filen handler om
    nettopp det, så staten her bærer observasjonstiden sin.
    """

    __slots__ = ("attributes", "entity_id", "last_changed", "last_updated", "state")

    def __init__(self, entity_id: str, verdi: Any, last_updated: datetime) -> None:
        self.entity_id = entity_id
        self.state = "unavailable" if verdi is None else str(verdi)
        self.last_updated = last_updated
        self.last_changed = last_updated
        self.attributes: dict[str, Any] = {}

    def __repr__(self) -> str:  # pragma: no cover - kun for feilsøking
        return f"<FalskState {self.entity_id}={self.state} @ {self.last_updated.isoformat()}>"


class FalskDtUtil:
    """`homeassistant.util.dt` med en klokke vi styrer.

    Klokken står stille mellom polls og settes av harnesset. Alt den gir fra
    seg er tidssoneklart, som i produksjon.
    """

    def __init__(self, naa: datetime) -> None:
        self._naa = krev_aware(naa, "naa").astimezone(OSLO)

    def sett(self, naa: datetime) -> None:
        self._naa = krev_aware(naa, "naa").astimezone(OSLO)

    def now(self) -> datetime:
        return self._naa

    def utcnow(self) -> datetime:
        return self._naa.astimezone(UTC)

    @staticmethod
    def as_local(tidspunkt: datetime) -> datetime:
        if tidspunkt.tzinfo is None:
            return tidspunkt.replace(tzinfo=OSLO)
        return tidspunkt.astimezone(OSLO)

    @staticmethod
    def as_utc(tidspunkt: datetime) -> datetime:
        if tidspunkt.tzinfo is None:
            return tidspunkt.replace(tzinfo=OSLO).astimezone(UTC)
        return tidspunkt.astimezone(UTC)

    @staticmethod
    def parse_datetime(verdi: str) -> datetime | None:
        try:
            return datetime.fromisoformat(verdi)
        except (ValueError, TypeError):
            return None


class FalskStore:
    """Store som faktisk husker, slik at en omstart kan lese tilbake.

    `tests.conftest.coord_module` gir en MagicMock som alltid laster `None`.
    Da er enhver omstart en ny installasjon, og C2.7 kan ikke testes i det hele
    tatt. Her ligger dataene i en dict som overlever at coordinatoren bygges på
    nytt, akkurat som filen på disk gjør.
    """

    def __init__(self, disk: dict[str, Any], key: str) -> None:
        self._disk = disk
        self._key = key

    async def async_load(self) -> dict[str, Any] | None:
        return self._disk.get(self._key)

    async def async_save(self, data: dict[str, Any]) -> None:
        # Kopi, ellers ville coordinatoren kunne endre «disken» etterpå.
        self._disk[self._key] = dict(data)

    async def async_remove(self) -> None:
        self._disk.pop(self._key, None)


# ---------------------------------------------------------------------------
# Pollplan
# ---------------------------------------------------------------------------


def pollplan(
    fra: datetime,
    til: datetime,
    *,
    intervall_sekunder: int = UPDATE_INTERVAL_SEKUNDER,
    jitter_sekunder: float = 0.0,
    frø: int = 0,
) -> Iterator[datetime]:
    """Polltidspunkt fra `fra` til `til`, halvåpent, med valgfri jitter.

    Jitteret er den lille forsinkelsen HAs tidsplanlegger har i praksis: hvert
    poll ligger et tilfeldig antall sekunder etter det planlagte. Det er aldri
    negativt, for en timer fyrer ikke for tidlig.

    Regnet på epoch-sekunder, så et sommertidsskifte midt i planen gir like
    mange polls som et vanlig døgn pluss eller minus en time, ikke et hopp.
    """
    fra = krev_aware(fra, "fra")
    til = krev_aware(til, "til")
    rng = random.Random(frø)
    t = fra.timestamp()
    slutt = til.timestamp()
    while t < slutt:
        forsinkelse = rng.uniform(0.0, jitter_sekunder) if jitter_sekunder else 0.0
        kl = datetime.fromtimestamp(t + forsinkelse, tz=UTC).astimezone(OSLO)
        if kl < til:
            yield kl
        t += intervall_sekunder


# ---------------------------------------------------------------------------
# Selve replayen
# ---------------------------------------------------------------------------


@dataclass
class Replay:
    """Spiller en hendelseslogg inn i en ekte NettleieCoordinator.

    Bruk:

        r = Replay(coord_module, hendelser)
        r.start(kl)
        for kl in pollplan(fra, til, jitter_sekunder=8):
            r.poll(kl)
        r.restart(kl)          # bygger coordinatoren på nytt fra lagret bok
        r.poll(...)
    """

    coord_module: Any
    hendelser: Hendelseslogg
    entry_kwargs: dict[str, Any] = field(default_factory=dict)
    power_sensor: str = "sensor.power"
    spot_sensor: str = "sensor.spot_price"
    energy_sensor: str | None = "sensor.tpi"
    opplosning_minutter: int = 15

    coord: Any = field(init=False, default=None)
    hass: Any = field(init=False, default=None)
    disk: dict[str, Any] = field(init=False, default_factory=dict)
    siste_data: dict[str, Any] | None = field(init=False, default=None)
    polls: int = field(init=False, default=0)
    omstarter: int = field(init=False, default=0)
    _loop: Any = field(init=False, default=None)
    _dt: Any = field(init=False, default=None)
    _pris_hull: set[datetime] = field(init=False, default_factory=set)
    _teller_borte: list[tuple[datetime, datetime]] = field(init=False, default_factory=list)

    # Historikken coordinatoren faktisk fikk se. Den er ikke den samme som
    # hendelsesloggen: et poll ser bare siste state, så en måling mellom to
    # polls går tapt for begge parter. Fasiten skal derfor mates med denne,
    # ikke med loggen, ellers måler vi noe annet enn C2.6.
    observerte_malinger: list[tuple[datetime, float]] = field(init=False, default_factory=list)
    observerte_priser: list[tuple[datetime, float]] = field(init=False, default_factory=list)

    # -- oppsett ---------------------------------------------------------

    def start(self, naa: datetime) -> None:
        """Bygg coordinatoren for første gang, med klokken på `naa`."""
        self._loop = asyncio.new_event_loop()
        self._dt = FalskDtUtil(naa)
        self.coord_module.dt_util = self._dt
        self.coord_module.Store = lambda hass, versjon, key: FalskStore(self.disk, key)
        self.hass = MagicMock()
        self.hass.states.get = self._state
        self._bygg()

    def _bygg(self) -> None:
        kwargs = {
            "dso_id": "bkk",
            "har_norgespris": True,
            "avgiftssone": "standard",
            "spotpris_inkl_mva": False,
            "power_sensor": self.power_sensor,
            "spot_price_sensor": self.spot_sensor,
            "energy_sensor": self.energy_sensor,
            **self.entry_kwargs,
        }
        entry = _make_entry(**kwargs)
        self.coord = self.coord_module.NettleieCoordinator(self.hass, entry)

    def lukk(self) -> None:
        if self._loop is not None:
            self._loop.close()
            self._loop = None

    # -- statene coordinatoren leser --------------------------------------

    def pris_hull(self, *rutestarter: datetime) -> None:
        """Merk prisruter der sensoren er `unavailable` (C4)."""
        for r in rutestarter:
            self._pris_hull.add(prisrutestart(r, self.opplosning_minutter))

    def teller_borte(self, fra: datetime, til: datetime) -> None:
        """Merk et vindu der energisensoren er `unavailable`."""
        self._teller_borte.append((krev_aware(fra), krev_aware(til)))

    def _state(self, entity_id: str) -> FalskState | None:
        naa = self._dt.now()
        if entity_id == self.spot_sensor:
            rute = prisrutestart(naa, self.opplosning_minutter)
            if rute in self._pris_hull:
                return FalskState(entity_id, None, rute)
            verdi = self.hendelser.pris_ved(naa)
            if verdi is not None and (
                not self.observerte_priser or self.observerte_priser[-1] != (naa, verdi)
            ):
                self.observerte_priser.append((naa, verdi))
            return FalskState(entity_id, verdi, rute)
        if entity_id == self.energy_sensor:
            if any(fra <= naa < til for fra, til in self._teller_borte):
                return FalskState(entity_id, None, naa)
            treff = self.hendelser.teller_ved(naa)
            if treff is None:
                return FalskState(entity_id, None, naa)
            observert, verdi = treff
            if not self.observerte_malinger or self.observerte_malinger[-1] != treff:
                self.observerte_malinger.append(treff)
            return FalskState(entity_id, verdi, observert)
        if entity_id == self.power_sensor:
            return FalskState(entity_id, self._effekt(naa), naa)
        return None

    def _effekt(self, naa: datetime) -> float:
        """Effekt i watt, utledet av de to siste målingene.

        Med energisensor bruker coordinatoren bare effekten til visning og til
        `current_power_kw`, men den skal likevel være et troverdig tall: en
        sensor som står på null mens telleren går er ikke et oppsett noen har.
        """
        malinger = self.hendelser.malinger
        i = bisect_right(malinger, naa, key=lambda m: m[0])
        if i < 2:
            return 0.0
        forrige_obs, forrige_verdi = malinger[i - 2]
        obs, verdi = malinger[i - 1]
        sekunder = obs.timestamp() - forrige_obs.timestamp()
        if sekunder <= 0:
            return 0.0
        return max(0.0, (verdi - forrige_verdi) / (sekunder / 3600.0) * 1000.0)

    # -- fasit for den historikken coordinatoren faktisk så -----------------

    def fasit(self, satser: Satser | None = None) -> Fasit:
        """Bygg fasiten av de observerte hendelsene, i observert rekkefølge."""
        f = Fasit(satser, opplosning_minutter=self.opplosning_minutter)
        for avlest_kl, verdi in self.observerte_priser:
            f.prisprove(avlest_kl, verdi)
        for observed_at, teller in self.observerte_malinger:
            f.bokfor(observed_at, teller)
        return f

    # -- kjøring ----------------------------------------------------------

    def poll(self, kl: datetime) -> dict[str, Any]:
        """Ett poll på tidspunktet `kl`."""
        self._dt.sett(kl)
        self.siste_data = self._loop.run_until_complete(self.coord._async_update_data())
        self.polls += 1
        return self.siste_data

    def kjor(self, poller: Iterator[datetime]) -> dict[str, Any] | None:
        """Kjør en hel pollplan."""
        for kl in poller:
            self.poll(kl)
        return self.siste_data

    def restart(self, kl: datetime) -> None:
        """Omstart: bygg coordinatoren på nytt mot den samme lagrede boken.

        Den gamle får lagre først, slik en ordentlig avslutning gjør. Vil du
        etterligne et strømbrudd, der ingenting ble lagret, poller du bare til
        hit og kaller `restart` uten å ha pollet siden forrige lagring.
        """
        self._loop.run_until_complete(self.coord._save_stored_data())
        self._dt.sett(kl)
        self._bygg()
        self.omstarter += 1

    # -- avlesning --------------------------------------------------------

    @property
    def data(self) -> dict[str, Any]:
        if self.siste_data is None:
            raise RuntimeError("Ingen polls kjørt ennå")
        return self.siste_data

    def rull_maned(self, kl: datetime) -> dict[str, Any]:
        """Poll én gang inn i neste måned, så `previous_month_*` fylles."""
        return self.poll(kl)


def maned_grenser(maned: str) -> tuple[datetime, datetime]:
    """(start, slutt) i lokal tid for en `YYYY-MM`-måned, halvåpent."""
    aar, mnd = (int(x) for x in maned.split("-"))
    start = datetime(aar, mnd, 1, tzinfo=OSLO)
    if mnd == 12:
        slutt = datetime(aar + 1, 1, 1, tzinfo=OSLO)
    else:
        slutt = datetime(aar, mnd + 1, 1, tzinfo=OSLO)
    return start, slutt


def logg_fra_timesenergi(
    timer: list[tuple[datetime, float]],
    priser: dict[datetime, list[float] | None],
    *,
    start_teller: float = 100_000.0,
    opplosning_minutter: int = 15,
    maler_sekunder: int = 3600,
) -> Hendelseslogg:
    """Bygg en hendelseslogg av intervallenergi og kvarterpriser.

    `maler_sekunder` er hvor ofte telleren rapporterer. 3600 gir én rapport per
    timegrense, som er Elhubs oppløsning. Lavere verdier deler timens energi
    jevnt utover og gir et vindu som krysser timegrensen, som er det en ekte
    HAN-måler gjør, og det er da polltiden i det hele tatt kan flytte
    kilowattimer mellom to timer.

    `observed_at` er rapporttidspunktet selv.
    En ekte HAN-melding kommer noen sekunder etter grensen med verdien som
    gjaldt ved grensen, og det etterslepet er korrigert for i
    `scripts/research/verify_invoice_hourly.py` (`--shift-seconds`). Å legge det
    inn her ville forskjøvet fasiten og coordinatoren like mye og dermed ikke
    bevist noe; det hører hjemme i etterkontrollen mot faktura, ikke i en test
    av fordelingsregelen.

    Prisene publiseres per kvarter. Har måneden bare en timespris (fallback i
    prisarkivet), publiseres den samme verdien i alle fire rutene, som en
    timesoppløst prissensor gjør i drift.
    """
    if 3600 % maler_sekunder:
        raise ValueError(f"maler_sekunder må gå opp i en time, fikk {maler_sekunder}")
    logg = Hendelseslogg()
    teller = start_teller
    if timer:
        logg.mal(timer[0][0], teller)
    per_time = 3600 // maler_sekunder
    for start, kwh in timer:
        for n in range(1, per_time + 1):
            logg.mal(start + timedelta(seconds=maler_sekunder * n), teller + kwh * n / per_time)
        teller += kwh
        kvarter = priser.get(start)
        if kvarter is None:
            continue
        for i, verdi in enumerate(kvarter):
            logg.pris(start + timedelta(minutes=opplosning_minutter * i), verdi)
    logg.sorter()
    return logg
