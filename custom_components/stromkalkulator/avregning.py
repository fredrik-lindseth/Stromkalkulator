"""Avregningskjernen: intervaller, energifordeling og prisadapter.

Modulen er ren. Den importerer ingenting fra Home Assistant og kan kjøres og
testes uten at HA er installert. Coordinatoren (L3a) kobler seg på den; her
finnes verken entiteter, Store eller kroner.

Alt er skrevet mot [avregningskontrakten](../../docs/kontrakter/avregning.md).
Paragrafhenvisningene i docstringene under peker dit, og der kontrakten og
koden er uenige, er det kontrakten som har rett.

De tre reglene som styrer resten:

- Energi bokføres etter avlesningens observasjonstid, ikke etter polltiden
  (invarianten øverst i kontrakten).
- Intervallene er halvåpne og lagres i UTC. Europe/Oslo brukes kun til å
  avgjøre tariff, fakturamåned og avgiftsår, og alltid fra intervallets start
  (A1, C3).
- En pris gjelder for en prisrute, ikke for et øyeblikk. Prisprøven er paret
  `(rutestart, verdi)`, og timeprisen er det uvektede snittet av rutene som
  fikk prøve (A2, A2.1).

Varighet regnes alltid som differansen mellom to `timestamp()`, aldri som
veggklokke-aritmetikk. Det er det som gjør at sommertidsskiftene ikke er et
spesialtilfelle her (C3).
"""

from __future__ import annotations

import math
from bisect import bisect_left
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

from .const import (
    DAY_RATE_END_HOUR,
    DAY_RATE_START_HOUR,
    HELLIGDAGER_FASTE,
    MAX_ELAPSED_HOURS,
    MAX_ENERGY_DELTA_KWH,
    WEEKEND_WEEKDAY_START,
    _bevegelige_helligdager,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

OSLO: Final[ZoneInfo] = ZoneInfo("Europe/Oslo")

#: Lengden på et avregningsintervall (A1). 60 i v1; bryteren til kvarters-
#: avregning er dette tallet, ikke en ny regel (A5).
AVREGNINGSINTERVALL_MINUTTER: Final[int] = 60
AVREGNINGSINTERVALL: Final[timedelta] = timedelta(minutes=AVREGNINGSINTERVALL_MINUTTER)

#: Lengden på en prisrute (A2.1). 15 uansett prissensor: en kvartersnativ
#: sensor gir fire ulike verdier som snittes, en timesoppløst gir fire like,
#: og snittet av fire like tall er timesprisen selv.
PRISRUTE_MINUTTER: Final[int] = 15

#: Hvor lenge etter rutestart en prisprøve må være tatt for å telle (A2.1
#: punkt 2). Seks ganger etterslepet som er målt på en Nord Pool-sensor i
#: drift. Kontrakten oppgir tallet, og `tests/test_avregningskontrakt.py`
#: leser det ut av dokumentet.
PRIS_SETTLE_SEKUNDER: Final[int] = 60

#: Store-skjemaet denne serien skriver (D).
SKJEMA_VERSJON: Final[int] = 3

#: Hvor langt bakover `til_lagring` tar med intervaller og prisruter når den
#: får vite hva klokken er. Det åpne intervallet pluss tre timer: nok til at en
#: omstart med et kort gap foran seg gjenopptar med prisene sine, og lite nok
#: til at lagringen er noen kilobyte og ikke noen hundre.
LAGRINGSVINDU: Final[timedelta] = timedelta(hours=3)

#: Flyttallsslakken i bevaringsinvarianten (C2.1).
BEVARING_SLAKK_KWH: Final[float] = 1e-9


# ---------------------------------------------------------------------------
# Enums


class Tariff(StrEnum):
    """Dag- eller natt-tariff, avgjort av intervallets start i Europe/Oslo."""

    DAG = "dag"
    NATT = "natt"


class Energikvalitet(StrEnum):
    """Kvaliteten på en energiavlesning (B1).

    `ESTIMERT` er stien for brukere uten energisensor: energien er ikke
    observert, den er regnet ut fra effekt over et pollvindu, og da gjelder
    ikke polltidsuavhengigheten (C2.6).
    """

    MALT = "malt"
    ESTIMERT = "estimert"
    AVVIST = "avvist"


class Intervallkvalitet(StrEnum):
    """Kvaliteten på et avregnet intervall (B3, C4)."""

    KOMPLETT = "komplett"
    DELVIS_PRIS = "delvis_pris"
    UTEN_PRIS = "uten_pris"
    UFULLSTENDIG = "ufullstendig"


class Priskilde(StrEnum):
    """Hvor prisen kom fra (B2)."""

    SENSOR = "sensor"
    ARKIV = "arkiv"
    MANUELL = "manuell"


class Revisjon(StrEnum):
    """Prisårgangen intervallet ble avregnet med (A4, B2)."""

    FORELOPIG = "forelopig"
    FINAL = "final"
    UKJENT = "ukjent"


class Utfall(StrEnum):
    """Hva som skjedde med en avlesning som ble lagt fram for boken."""

    BOKFORT = "bokfort"
    BASELINE = "baseline"
    DUPLIKAT = "duplikat"
    FORSINKET = "forsinket"
    AVVIST_NULLVINDU = "avvist_nullvindu"
    AVVIST_NEGATIV = "avvist_negativ"
    AVVIST_SPRANG = "avvist_sprang"
    AVVIST_FOR_LANGT_VINDU = "avvist_for_langt_vindu"
    AVVIST_ARKIVERT = "avvist_arkivert"


# ---------------------------------------------------------------------------
# Tid


def krev_aware(tidspunkt: datetime, hva: str = "tidspunkt") -> datetime:
    """Krev en tidssoneklar datetime og gi den tilbake i UTC.

    B1: en naiv datetime er en programmeringsfeil og skal kaste, ikke tolkes
    som lokal tid. Å gjette lokal tid her er nøyaktig den feilen som gjør at
    en time forsvinner eller kommer to ganger i sommertidsskiftene.
    """
    if tidspunkt.tzinfo is None or tidspunkt.tzinfo.utcoffset(tidspunkt) is None:
        raise ValueError(f"{hva} må være tidssoneklar")
    return tidspunkt.astimezone(UTC)


def varighet_sekunder(fra: datetime, til: datetime) -> float:
    """Absolutt tid mellom to tidspunkt, regnet via `timestamp()`.

    C3: UTC-tidslinjen er sammenhengende gjennom begge sommertidsskiftene, og
    denne funksjonen er stedet det håndheves. Veggklokke-aritmetikk hører ikke
    hjemme i avregningskjernen.
    """
    return krev_aware(til, "slutt").timestamp() - krev_aware(fra, "start").timestamp()


def intervallstart(tidspunkt: datetime) -> datetime:
    """Starten på avregningsintervallet tidspunktet faller i (A1, halvåpent)."""
    return krev_aware(tidspunkt).replace(minute=0, second=0, microsecond=0)


def prisrutestart(tidspunkt: datetime, opplosning_minutter: int = PRISRUTE_MINUTTER) -> datetime:
    """Starten på prisruten tidspunktet faller i (A2.1, forankret i klokketimen)."""
    if opplosning_minutter <= 0 or 60 % opplosning_minutter:
        raise ValueError("prisruten må gå opp i en hel time")
    i_utc = krev_aware(tidspunkt, "polltid")
    minutt = (i_utc.minute // opplosning_minutter) * opplosning_minutter
    return i_utc.replace(minute=minutt, second=0, microsecond=0)


def lokal_maned(start_utc: datetime) -> str:
    """Fakturamåneden intervallet hører til, `YYYY-MM` i Europe/Oslo (A1, C3)."""
    return f"{krev_aware(start_utc, 'intervallstart').astimezone(OSLO):%Y-%m}"


def lokal_dato(start_utc: datetime) -> str:
    """Lokal dato, `YYYY-MM-DD` i Europe/Oslo. Brukes av døgnbøkene i L3b."""
    return f"{krev_aware(start_utc, 'intervallstart').astimezone(OSLO):%Y-%m-%d}"


def lokal_time(start_utc: datetime) -> int:
    """Lokal klokketime, 0 til 23 i Europe/Oslo (B3).

    Merkelappen er ikke entydig: 25.10.2026 har to intervaller med `2`. Det er
    `start_utc` som skiller dem, aldri veggklokken (C3).
    """
    return krev_aware(start_utc, "intervallstart").astimezone(OSLO).hour


def avgiftsaar(start_utc: datetime) -> int:
    """Avgiftsåret intervallet avregnes med, året i Europe/Oslo (C3 D6)."""
    return krev_aware(start_utc, "intervallstart").astimezone(OSLO).year


def regelkilde(tariffmodus: str, dso_id: str, start_utc: datetime) -> str:
    """`{tariffmodus}:{dso_id}:{avgiftsaar}` (B3).

    Alle tre leddene avgjøres av `start_utc`, så et intervall som bokføres
    etter nyttår, men hører til gammelt år, beholder gammelt avgiftsår.
    """
    return f"{tariffmodus}:{dso_id}:{avgiftsaar(start_utc)}"


# ---------------------------------------------------------------------------
# Fordelingsregelen


def fordel_delta(fra: datetime, til: datetime, delta_kwh: float) -> dict[datetime, float]:
    """Fordel et godkjent målerdelta jevnt over tid (C1).

    Vinduet er `(fra, til]`, og deltaet fordeles prorata på sekunder i hvert
    avregningsintervall vinduet dekker. Svaret er `{intervallstart: kWh}`.

    Jevn fordeling er valgt framfor snapping fordi den er kontinuerlig i
    polltid: en poll som flytter seg ett sekund flytter en promille av
    energien, ikke et helt delta over en intervallgrense. Målingen som avgjorde
    står i C1.

    Et vindu uten lengde kan ikke fordeles. To avlesninger med samme
    observasjonstid og ulik teller er en avvist avlesning, ikke en bokføring.
    """
    fra_utc = krev_aware(fra, "vindusstart")
    til_utc = krev_aware(til, "vindusslutt")
    varighet = varighet_sekunder(fra_utc, til_utc)
    if varighet <= 0:
        raise ValueError("vinduet må ha positiv lengde")

    fordeling: dict[datetime, float] = {}
    naa = fra_utc
    while naa < til_utc:
        start = intervallstart(naa)
        neste = min(til_utc, start + AVREGNINGSINTERVALL)
        andel = varighet_sekunder(naa, neste) / varighet
        fordeling[start] = fordeling.get(start, 0.0) + delta_kwh * andel
        naa = neste
    return fordeling


# ---------------------------------------------------------------------------
# Tariff


@dataclass(frozen=True, slots=True)
class Tariffregel:
    """Regelen som avgjør dag eller natt for et intervall.

    Klokkeslettene er globale (`DAY_RATE_START_HOUR`/`DAY_RATE_END_HOUR`),
    mens `helg_som_natt` og `helligdager_ekstra` kommer fra nettselskapet.
    `helligdager_ekstra` er `MM-DD`-strenger og skal bare settes når en ekte
    faktura bekrefter at hele dagen behandles som natt (se AGENTS.md).
    """

    helg_som_natt: bool = True
    helligdager_ekstra: tuple[str, ...] = ()
    dag_start_time: int = DAY_RATE_START_HOUR
    dag_slutt_time: int = DAY_RATE_END_HOUR

    def tariff(self, start_utc: datetime) -> Tariff:
        """Tariffen for intervallet som starter `start_utc` (A1, B3).

        Merkelappen hentes fra `zoneinfo` ved å regne om starten til
        Europe/Oslo. Det er ikke veggklokke-aritmetikk: vi spør om hvilken
        lokal time et absolutt tidspunkt falt i, og regner ikke i den.
        """
        lokal = krev_aware(start_utc, "intervallstart").astimezone(OSLO)
        er_natt_time = lokal.hour < self.dag_start_time or lokal.hour >= self.dag_slutt_time
        if er_natt_time:
            return Tariff.NATT
        if not self.helg_som_natt:
            return Tariff.DAG
        if lokal.weekday() >= WEEKEND_WEEKDAY_START:
            return Tariff.NATT
        if f"{lokal:%m-%d}" in HELLIGDAGER_FASTE or f"{lokal:%m-%d}" in self.helligdager_ekstra:
            return Tariff.NATT
        if f"{lokal:%Y-%m-%d}" in _bevegelige_helligdager(lokal.year):
            return Tariff.NATT
        return Tariff.DAG


# ---------------------------------------------------------------------------
# Datatypene i B


@dataclass(frozen=True, slots=True)
class Avlesning:
    """En observasjon av energikilden (B1).

    For en teller er `value_kwh` tellerstanden og `observed_at` entitetens
    `last_updated`. For den syntetiske stien uten energisensor er `value_kwh`
    energien i pollvinduet og `observed_at` polltiden, og `kvalitet` er
    `ESTIMERT`. De to blandes aldri: stien velges av konfigurasjonen, ikke av
    tilstanden.
    """

    source_identity: str
    value_kwh: float
    observed_at: datetime
    entity_id: str = ""
    kvalitet: Energikvalitet = Energikvalitet.MALT
    schema_version: int = SKJEMA_VERSJON

    def __post_init__(self) -> None:
        object.__setattr__(self, "observed_at", krev_aware(self.observed_at, "observed_at"))
        if not math.isfinite(self.value_kwh):
            raise ValueError("value_kwh må være et endelig tall")

    @property
    def er_estimert(self) -> bool:
        """Energien er regnet ut fra effekt, ikke lest av en teller (B1)."""
        return self.kvalitet is Energikvalitet.ESTIMERT

    def er_samme_som(self, annen: Avlesning | None) -> bool:
        """C2.2: identiteten er (`source_identity`, `observed_at`, `value_kwh`)."""
        if annen is None:
            return False
        return (
            self.source_identity == annen.source_identity
            and self.observed_at == annen.observed_at
            and self.value_kwh == annen.value_kwh
        )

    def til_lagring(self) -> dict[str, Any]:
        return {
            "source_identity": self.source_identity,
            "entity_id": self.entity_id,
            "value_kwh": self.value_kwh,
            "observed_at": self.observed_at.isoformat(),
            "kvalitet": str(self.kvalitet),
            "schema_version": self.schema_version,
        }

    @classmethod
    def fra_lagring(cls, raa: Mapping[str, Any]) -> Avlesning:
        return cls(
            source_identity=str(raa["source_identity"]),
            value_kwh=float(raa["value_kwh"]),
            observed_at=datetime.fromisoformat(str(raa["observed_at"])),
            entity_id=str(raa.get("entity_id", "")),
            kvalitet=Energikvalitet(raa.get("kvalitet", Energikvalitet.MALT)),
            schema_version=int(raa.get("schema_version", SKJEMA_VERSJON)),
        )


@dataclass(frozen=True, slots=True)
class Prisintervall:
    """Prisen for ett avregningsintervall (B2).

    `nok_per_kwh_eks_mva` er `None` når ingen prisrute fikk prøve. Den er aldri
    0 som erstatning, og aldri et annet intervalls pris (C2.5).
    """

    start_utc: datetime
    slutt_utc: datetime
    nok_per_kwh_eks_mva: float | None
    omrade: str = ""
    opplosning_minutter: int = PRISRUTE_MINUTTER
    kilde: Priskilde = Priskilde.SENSOR
    revisjon: Revisjon = Revisjon.UKJENT
    pris_prover: int = 0
    pris_prover_ventet: int = AVREGNINGSINTERVALL_MINUTTER // PRISRUTE_MINUTTER

    def __post_init__(self) -> None:
        object.__setattr__(self, "start_utc", krev_aware(self.start_utc, "start_utc"))
        object.__setattr__(self, "slutt_utc", krev_aware(self.slutt_utc, "slutt_utc"))
        if self.slutt_utc <= self.start_utc:
            raise ValueError("prisintervallet må ha positiv lengde")
        if self.pris_prover == 0 and self.nok_per_kwh_eks_mva is not None:
            raise ValueError("uten prøver finnes ingen pris (C2.5)")
        if self.pris_prover > 0 and self.nok_per_kwh_eks_mva is None:
            raise ValueError("med prøver skal prisen finnes")

    @property
    def kvalitet(self) -> Intervallkvalitet:
        """Priskvaliteten alene: komplett, delvis eller uten pris (A2.1, C4)."""
        if self.pris_prover == 0:
            return Intervallkvalitet.UTEN_PRIS
        if self.pris_prover < self.pris_prover_ventet:
            return Intervallkvalitet.DELVIS_PRIS
        return Intervallkvalitet.KOMPLETT

    def til_lagring(self) -> dict[str, Any]:
        return {
            "start_utc": self.start_utc.isoformat(),
            "slutt_utc": self.slutt_utc.isoformat(),
            "nok_per_kwh_eks_mva": self.nok_per_kwh_eks_mva,
            "omrade": self.omrade,
            "opplosning_minutter": self.opplosning_minutter,
            "kilde": str(self.kilde),
            "revisjon": str(self.revisjon),
            "pris_prover": self.pris_prover,
            "pris_prover_ventet": self.pris_prover_ventet,
        }


@dataclass(frozen=True, slots=True)
class AvregnetIntervall:
    """Ett ferdig avregnet intervall (B3).

    `kvalitet` er overskriften: står boken i en måned som krysset migreringen,
    er den `UFULLSTENDIG` (D), ellers er den priskvaliteten fra A2.1.
    `pris.kvalitet` gir priskvaliteten uansett.

    `energikvalitet` er ikke i B3s tabell. Den står her fordi et intervall som
    er fylt fra den syntetiske stien (B1) ikke er polltidsuavhengig, og det er
    ikke noe annet felt som sier fra om det. Ingen kroner her; de kommer i L3b.
    """

    start_utc: datetime
    slutt_utc: datetime
    kwh: float
    lokal_maned: str
    lokal_time: int
    tariff: Tariff
    pris: Prisintervall | None
    regelkilde: str
    kvalitet: Intervallkvalitet
    apen: bool
    energikvalitet: Energikvalitet = Energikvalitet.MALT

    @property
    def nok_per_kwh_eks_mva(self) -> float | None:
        """Prisen, eller `None`. Aldri 0 som erstatning (C2.5)."""
        return None if self.pris is None else self.pris.nok_per_kwh_eks_mva

    @property
    def har_pris(self) -> bool:
        return self.nok_per_kwh_eks_mva is not None

    @property
    def varighet_i_sekunder(self) -> float:
        """Alltid 3600 i v1, også over sommertidsskiftene (A1, C3)."""
        return varighet_sekunder(self.start_utc, self.slutt_utc)


@dataclass(frozen=True, slots=True)
class Manedssum:
    """Sum over en fakturamåneds avregnede intervaller.

    Kroner er ikke med. Dette er grunnlaget L3b regner kroner fra, og feltene
    svarer til `monthly_consumption_*`, `kwh_uten_pris` og `kwh_delvis_pris` i
    felttabellen.
    """

    maned: str
    kwh_total: float = 0.0
    kwh_dag: float = 0.0
    kwh_natt: float = 0.0
    kwh_uten_pris: float = 0.0
    kwh_delvis_pris: float = 0.0
    avvist_kwh: float = 0.0
    intervaller: int = 0


@dataclass(frozen=True, slots=True)
class Bokforing:
    """Hva boken gjorde med en avlesning.

    Coordinatoren trenger utfallet for diagnostikk og varsling; boken selv har
    alt gjort det som skal gjøres når dette kommer tilbake.
    """

    utfall: Utfall
    bokfort_kwh: float = 0.0
    avvist_kwh: float = 0.0
    fordeling: Mapping[datetime, float] = field(default_factory=dict)
    arkiverte_maneder: tuple[str, ...] = ()

    @property
    def ble_bokfort(self) -> bool:
        return self.utfall is Utfall.BOKFORT


# ---------------------------------------------------------------------------
# Prisadapteren


@dataclass(slots=True)
class _Ruteprove:
    polltid: datetime
    verdi: float


class Prisadapter:
    """Samler prisprøver i ruter og setter dem sammen til en timepris (A2.1).

    En prisprøve er paret `(rutestart, verdi)`. Ruten er den polltiden faller
    i, prøven godtas først når polltiden ligger minst `PRIS_SETTLE_SEKUNDER`
    etter rutestart, og innenfor en rute gjelder den seneste godkjente prøven.
    En prøve bæres aldri inn i en annen rute.

    Adapteren er rekkefølgeuavhengig med vilje: hvilken prøve som vinner en
    rute avgjøres av polltiden, ikke av når `registrer` ble kalt. To
    avspillinger av de samme prøvene i ulik rekkefølge gir derfor samme pris.
    """

    def __init__(
        self,
        *,
        omrade: str = "",
        opplosning_minutter: int = PRISRUTE_MINUTTER,
        settle_sekunder: int = PRIS_SETTLE_SEKUNDER,
        kilde: Priskilde = Priskilde.SENSOR,
        revisjon: Revisjon = Revisjon.UKJENT,
    ) -> None:
        if opplosning_minutter <= 0 or 60 % opplosning_minutter:
            raise ValueError("prisruten må gå opp i en hel time")
        self.omrade = omrade
        self.opplosning_minutter = opplosning_minutter
        self.settle_sekunder = settle_sekunder
        self.kilde = kilde
        self.revisjon = revisjon
        self._ruter: dict[datetime, _Ruteprove] = {}

    @property
    def prover_ventet(self) -> int:
        """`60 / opplosning_minutter` (B2)."""
        return AVREGNINGSINTERVALL_MINUTTER // self.opplosning_minutter

    def registrer(self, avlest_kl: datetime, verdi: float) -> datetime | None:
        """Ta imot en prisprøve. Gir rutestarten den landet i, eller `None`.

        `avlest_kl` er polltiden fra inputadapteren, ikke prissensorens
        `last_updated`: prissensoren er en trinnfunksjon som viser prisen for
        ruten som gjelder nå, og det er den egenskapen vi leser. To like
        priser på rad er to prøver, ikke én (A2.1, C8 P2).
        """
        if not math.isfinite(verdi):
            raise ValueError("prisprøven må være et endelig tall")
        polltid = krev_aware(avlest_kl, "avlest_kl")
        start = prisrutestart(polltid, self.opplosning_minutter)
        if varighet_sekunder(start, polltid) < self.settle_sekunder:
            return None
        staaende = self._ruter.get(start)
        if staaende is None or (staaende.polltid, staaende.verdi) < (polltid, verdi):
            self._ruter[start] = _Ruteprove(polltid, verdi)
        return start

    def ruter_i(self, start_utc: datetime) -> dict[datetime, float]:
        """Rutene med godkjent prøve i avregningsintervallet som starter her.

        Rutene ligger på gridet (`prisrutestart`) og oppløsningen går opp i en
        hel time, så de fire mulige rutestartene kan regnes ut og slås opp
        direkte. Å gå gjennom hele rutetabellen ga samme svar, men koster en
        månedslang tabell ved hvert oppslag, og coordinatoren slår opp ved hver
        poll.
        """
        start = krev_aware(start_utc, "intervallstart")
        steg = timedelta(minutes=self.opplosning_minutter)
        ut: dict[datetime, float] = {}
        for n in range(self.prover_ventet):
            rutestart = start + n * steg
            prove = self._ruter.get(rutestart)
            if prove is not None:
                ut[rutestart] = prove.verdi
        return ut

    def prisintervall(self, start_utc: datetime) -> Prisintervall:
        """Prisen for avregningsintervallet: uvektet snitt av rutene med prøve.

        Ingen tidsvekting. En rute teller likt uansett hvor i ruten prøven ble
        tatt og hvor mange polls som traff den. Det er samme regning som
        `scripts/research/verify_norgespris_eksakt.py` gjør mot kvarterarkivet,
        så drift og etterkontroll regner likt (A2).
        """
        start = krev_aware(start_utc, "intervallstart")
        ruter = self.ruter_i(start)
        pris = sum(ruter.values()) / len(ruter) if ruter else None
        return Prisintervall(
            start_utc=start,
            slutt_utc=start + AVREGNINGSINTERVALL,
            nok_per_kwh_eks_mva=pris,
            omrade=self.omrade,
            opplosning_minutter=self.opplosning_minutter,
            kilde=self.kilde,
            revisjon=self.revisjon,
            pris_prover=len(ruter),
            pris_prover_ventet=self.prover_ventet,
        )

    def glem_for(self, grense: datetime) -> None:
        """Slipp ruter som starter før `grense`.

        Prisen står fast ved lukking, og et lukket intervall får aldri en ny
        prøve (C6). Rutene til en arkivert måned har derfor ingen jobb igjen.
        """
        skille = krev_aware(grense, "grense")
        self._ruter = {start: prove for start, prove in self._ruter.items() if start >= skille}

    def til_lagring(self, fra: datetime | None = None) -> dict[str, Any]:
        """Adapteren på Store-form, eventuelt bare rutene fra `fra` og utover.

        Prisen på et lukket intervall står fast (C6), så rutene bak vinduet
        boken lagrer har ingen jobb igjen.
        """
        return {
            "omrade": self.omrade,
            "opplosning_minutter": self.opplosning_minutter,
            "settle_sekunder": self.settle_sekunder,
            "kilde": str(self.kilde),
            "revisjon": str(self.revisjon),
            "ruter": [
                {"rutestart": start.isoformat(), "polltid": prove.polltid.isoformat(), "verdi": prove.verdi}
                for start, prove in sorted(par for par in self._ruter.items() if fra is None or par[0] >= fra)
            ],
        }

    @classmethod
    def fra_lagring(cls, raa: Mapping[str, Any]) -> Prisadapter:
        """Les adapteren tilbake, godkjente ruteprøver og alt (C5).

        Uten prøvene ville en omstart midt i timen gjort et `komplett`
        intervall til `delvis_pris`, og restartlikheten i C2.7 ville brutt.
        """
        adapter = cls(
            omrade=str(raa.get("omrade", "")),
            opplosning_minutter=int(raa.get("opplosning_minutter", PRISRUTE_MINUTTER)),
            settle_sekunder=int(raa.get("settle_sekunder", PRIS_SETTLE_SEKUNDER)),
            kilde=Priskilde(raa.get("kilde", Priskilde.SENSOR)),
            revisjon=Revisjon(raa.get("revisjon", Revisjon.UKJENT)),
        )
        for rad in raa.get("ruter", []):
            adapter._ruter[datetime.fromisoformat(str(rad["rutestart"]))] = _Ruteprove(
                polltid=datetime.fromisoformat(str(rad["polltid"])),
                verdi=float(rad["verdi"]),
            )
        return adapter


# ---------------------------------------------------------------------------
# Boken


@dataclass(slots=True)
class _Post:
    """Energien bokført i ett intervall, før pris og merkelapper legges på."""

    kwh: float = 0.0
    energikvalitet: Energikvalitet = Energikvalitet.MALT


class Avregningsbok:
    """Avlesninger inn, avregnede intervaller ut.

    Boken eier tre ting: energien per intervall, prisrutene, og baselinen for
    neste delta. Den eier ingen kroner og ingen klokke: alt som trenger «nå»
    tar det som argument, slik at en replay kan styre tiden selv.

    Månedsrulleringen skjer inne i bokføringen av den første avlesningen med
    observasjonstid i den nye måneden, ikke ved et klokkeslett (C6). Vinduet
    deles ved månedsgrensen, delen før grensen bokføres i den gamle måneden,
    måneden arkiveres, og resten bokføres i den nye.
    """

    def __init__(
        self,
        *,
        tariffregel: Tariffregel | None = None,
        tariffmodus: str = "catalog",
        dso_id: str = "",
        prisadapter: Prisadapter | None = None,
        maks_delta_kwh: float = MAX_ENERGY_DELTA_KWH,
        maks_estimert_vindu_timer: float = MAX_ELAPSED_HOURS,
        ufullstendig: bool = False,
    ) -> None:
        self.tariffregel = tariffregel or Tariffregel()
        self.tariffmodus = tariffmodus
        self.dso_id = dso_id
        self.pris = prisadapter or Prisadapter()
        self.maks_delta_kwh = maks_delta_kwh
        self.maks_estimert_vindu_timer = maks_estimert_vindu_timer
        self.ufullstendig = ufullstendig
        self._poster: dict[datetime, _Post] = {}
        # Ferdig bygde intervaller, alltid med `apen = False`. Coordinatoren
        # spør om månedens status ved hver poll, og uten denne ville hver poll
        # bygget hele måneden på nytt. Oppføringen kastes når intervallet får
        # mer energi eller en ny prisprøve, altså av de to tingene som kan
        # endre den.
        self._bygget: dict[datetime, AvregnetIntervall] = {}
        #: Startene i `_poster`, sortert. Kastes når et nytt intervall kommer
        #: til, ikke når et kjent får mer energi.
        self._sorterte: list[datetime] | None = None
        #: Månedssummen holdes løpende. Coordinatoren spør ved hver poll, og
        #: en poll rører ett eller to intervaller, så summen rettes med
        #: differansen for dem framfor å regnes opp av hele måneden.
        self._skitne: set[datetime] = set()
        self._bidrag: dict[datetime, tuple[float, Tariff, Intervallkvalitet]] = {}
        self._sum_total = 0.0
        self._sum_dag = 0.0
        self._sum_natt = 0.0
        self._sum_uten = 0.0
        self._sum_delvis = 0.0
        self._sist_observert: Avlesning | None = None
        self._aktiv_maned: str | None = None
        self._arkiv: dict[str, Manedssum] = {}
        self._avvist_kwh: float = 0.0

    # -- tilstand ----------------------------------------------------------

    @property
    def sist_observert(self) -> Avlesning | None:
        """Siste behandlede avlesning. Baseline for neste delta (C5)."""
        return self._sist_observert

    @property
    def aktiv_maned(self) -> str | None:
        """Fakturamåneden boken fører nå, eller `None` før første bokføring."""
        return self._aktiv_maned

    @property
    def avvist_kwh(self) -> float:
        """kWh forkastet denne måneden: sprang, målerreset, duplikat (C1)."""
        return self._avvist_kwh

    def arkiverte_maneder(self) -> dict[str, Manedssum]:
        """Månedene boken har rullert forbi, med sine summer."""
        return dict(self._arkiv)

    def sett_baseline(self, avlesning: Avlesning | None) -> None:
        """Sett siste behandlede observasjon uten å bokføre noe (C5).

        Brukes når baselinen kommer fra et eldre lagringsskjema, der den lå
        utenfor boken. Det er en flytting av utgangspunktet for neste delta,
        ikke en avlesning, så ingen intervaller får energi.
        """
        self._sist_observert = avlesning

    # -- pris --------------------------------------------------------------

    def registrer_prisprove(self, avlest_kl: datetime, verdi: float) -> datetime | None:
        """Send en prisprøve videre til adapteren (A2.1)."""
        rutestart = self.pris.registrer(avlest_kl, verdi)
        if rutestart is not None:
            berort = intervallstart(rutestart)
            self._bygget.pop(berort, None)
            if berort in self._poster:
                self._skitne.add(berort)
        return rutestart

    # -- energi ------------------------------------------------------------

    def bokfor(self, avlesning: Avlesning) -> Bokforing:
        """Bokfør en avlesning etter C1, C2 og C6.

        Rekkefølgen på sjekkene er kontraktens: duplikat og forsinket først
        (C2.2 og C2.3), så randtilfellene i C1, så fordelingen.
        """
        if avlesning.kvalitet is Energikvalitet.AVVIST:
            return Bokforing(Utfall.AVVIST_NULLVINDU)

        forrige = self._sist_observert
        if forrige is None or forrige.source_identity != avlesning.source_identity:
            # Ny bok eller ny kilde: deltaet er 0 og baselinen flyttes (C5, K1).
            self._sist_observert = avlesning
            return Bokforing(Utfall.BASELINE)

        if avlesning.er_samme_som(forrige):
            return Bokforing(Utfall.DUPLIKAT)
        if avlesning.observed_at < forrige.observed_at:
            return Bokforing(Utfall.FORSINKET)
        if avlesning.observed_at == forrige.observed_at:
            # Samme observasjonstid, ulik verdi: vinduet har lengde null og kan
            # ikke fordeles (C1). Baselinen står, så neste avlesning måles fra
            # den samme kjente standen.
            return Bokforing(Utfall.AVVIST_NULLVINDU)

        if avlesning.er_estimert:
            return self._bokfor_estimert(forrige, avlesning)
        return self._bokfor_teller(forrige, avlesning)

    def _bokfor_teller(self, forrige: Avlesning, avlesning: Avlesning) -> Bokforing:
        delta = avlesning.value_kwh - forrige.value_kwh
        if delta < 0:
            # Målerreset eller kildebytte: ikke bokført, baselinen flyttes (C1).
            self._sist_observert = avlesning
            return Bokforing(Utfall.AVVIST_NEGATIV)
        if delta > self.maks_delta_kwh:
            # Baselinen flyttes her også. Uten det ville hver senere avlesning
            # også ligget over grensen, og boken stått stille for godt (C1).
            self._sist_observert = avlesning
            self._avvist_kwh += delta
            return Bokforing(Utfall.AVVIST_SPRANG, avvist_kwh=delta)
        return self._fordel(forrige.observed_at, avlesning, delta)

    def _bokfor_estimert(self, forrige: Avlesning, avlesning: Avlesning) -> Bokforing:
        """Den syntetiske stien: `value_kwh` er energien i vinduet, ikke en stand (B1)."""
        timer = varighet_sekunder(forrige.observed_at, avlesning.observed_at) / 3600
        if timer > self.maks_estimert_vindu_timer:
            # Antakelsen om konstant effekt gjennom vinduet holder ikke. Energien
            # forkastes framfor å gjettes, og intervallene i gapet får ingen
            # energi: de er «uten data», ikke null forbruk (B1, C4).
            self._sist_observert = avlesning
            return Bokforing(Utfall.AVVIST_FOR_LANGT_VINDU)
        delta = avlesning.value_kwh
        if delta < 0:
            self._sist_observert = avlesning
            return Bokforing(Utfall.AVVIST_NEGATIV)
        if delta > self.maks_delta_kwh:
            self._sist_observert = avlesning
            self._avvist_kwh += delta
            return Bokforing(Utfall.AVVIST_SPRANG, avvist_kwh=delta)
        return self._fordel(forrige.observed_at, avlesning, delta)

    def _fordel(self, fra: datetime, avlesning: Avlesning, delta: float) -> Bokforing:
        fordeling = fordel_delta(fra, avlesning.observed_at, delta)
        arkivert: list[str] = []
        bokfort = 0.0
        avvist = 0.0
        landet: dict[datetime, float] = {}

        for start in sorted(fordeling):
            kwh = fordeling[start]
            maned = lokal_maned(start)
            if self._aktiv_maned is None:
                self._aktiv_maned = maned
            elif maned > self._aktiv_maned:
                arkivert.append(self._arkiver(naa_maned=maned))
            elif maned < self._aktiv_maned:
                # Et arkivert månedsskifte tar ikke imot mer energi (C6). I
                # praksis kommer vi ikke hit, for vinduene er sammenhengende og
                # forsinkede avlesninger er alt avvist av C2.3.
                avvist += kwh
                continue
            if start not in self._poster:
                self._poster[start] = _Post()
                self._sorterte = None
            post = self._poster[start]
            self._bygget.pop(start, None)
            self._skitne.add(start)
            post.kwh += kwh
            if avlesning.er_estimert:
                post.energikvalitet = Energikvalitet.ESTIMERT
            bokfort += kwh
            landet[start] = landet.get(start, 0.0) + kwh

        self._sist_observert = avlesning
        if avvist:
            self._avvist_kwh += avvist
        utfall = Utfall.BOKFORT if landet else Utfall.AVVIST_ARKIVERT
        return Bokforing(
            utfall=utfall,
            bokfort_kwh=bokfort,
            avvist_kwh=avvist,
            fordeling=landet,
            arkiverte_maneder=tuple(arkivert),
        )

    def _arkiver(self, *, naa_maned: str) -> str:
        """Lukk den aktive måneden og gjør den uforanderlig (C6)."""
        gammel = self._aktiv_maned
        assert gammel is not None
        self._arkiv[gammel] = self.maanedssum()
        self._poster.clear()
        self._bygget.clear()
        self._sorterte = None
        self._skitne.clear()
        self._bidrag.clear()
        self._sum_total = self._sum_dag = self._sum_natt = 0.0
        self._sum_uten = self._sum_delvis = 0.0
        self._avvist_kwh = 0.0
        self._aktiv_maned = naa_maned
        self.ufullstendig = False  # flagget fjernes ved første månedsskifte (D)
        self.pris.glem_for(_maanedsstart_utc(naa_maned))
        return gammel

    # -- utdata ------------------------------------------------------------

    def _starter(self) -> list[datetime]:
        """Intervallstartene i den aktive måneden, sortert og cachet."""
        if self._sorterte is None:
            self._sorterte = sorted(self._poster)
        return self._sorterte

    def intervaller(self, naa: datetime | None = None) -> list[AvregnetIntervall]:
        """Den aktive månedens intervaller, sortert på `start_utc`.

        `naa` avgjør bare `apen`: et intervall er åpent til klokken i UTC har
        passert `slutt_utc`, og lukkingen skjer av tiden alene, ikke av en poll
        (C6). Uten `naa` regnes alle som lukkede.
        """
        grense = krev_aware(naa, "naa") if naa is not None else None
        return [self._bygg(start, self._poster[start], grense) for start in self._starter()]

    def intervall(self, start_utc: datetime, naa: datetime | None = None) -> AvregnetIntervall | None:
        """Ett intervall, eller `None` om det ikke finnes energi i det.

        Et hull i boken er ikke null forbruk og skal ikke vises som det (C4).
        """
        start = intervallstart(start_utc)
        post = self._poster.get(start)
        if post is None:
            return None
        return self._bygg(start, post, krev_aware(naa, "naa") if naa is not None else None)

    def _bygg(self, start: datetime, post: _Post, naa: datetime | None) -> AvregnetIntervall:
        """Bygg intervallet, eller hent det ferdige fra cachen.

        `apen` er det eneste som avhenger av klokken, og det avgjøres til
        slutt. Alt annet er avgjort av intervallets egen start, energien og
        prisrutene, og de tre kastes cachen på.
        """
        lukket = self._bygget.get(start)
        if lukket is None:
            slutt = start + AVREGNINGSINTERVALL
            pris = self.pris.prisintervall(start)
            kvalitet = Intervallkvalitet.UFULLSTENDIG if self.ufullstendig else pris.kvalitet
            lukket = AvregnetIntervall(
                start_utc=start,
                slutt_utc=slutt,
                kwh=post.kwh,
                lokal_maned=lokal_maned(start),
                lokal_time=lokal_time(start),
                tariff=self.tariffregel.tariff(start),
                pris=pris,
                regelkilde=regelkilde(self.tariffmodus, self.dso_id, start),
                kvalitet=kvalitet,
                apen=False,
                energikvalitet=post.energikvalitet,
            )
            self._bygget[start] = lukket
        if naa is not None and naa < lukket.slutt_utc:
            return replace(lukket, apen=True)
        return lukket

    def apne_intervaller(self, naa: datetime) -> list[AvregnetIntervall]:
        """Intervallene som ennå ikke er lukket (`avregning_apne_intervaller`)."""
        return [i for i in self.intervaller(naa) if i.apen]

    def siste_lukkede(self, naa: datetime) -> AvregnetIntervall | None:
        """Siste lukkede intervall (`avregning_siste_intervall`)."""
        lukkede = [i for i in self.intervaller(naa) if not i.apen]
        return lukkede[-1] if lukkede else None

    def maanedssum(self, naa: datetime | None = None) -> Manedssum:
        """Summene for den aktive måneden (felttabellen).

        `naa` er med for symmetrien med `intervaller`; summene er de samme
        uansett, for et åpent intervall teller like fullt det som er bokført i
        det.
        """
        del naa
        for start in self._skitne:
            self._trekk_bidrag(start)
            self._legg_til_bidrag(start)
        self._skitne.clear()
        return Manedssum(
            maned=self._aktiv_maned or "",
            kwh_total=self._sum_total,
            kwh_dag=self._sum_dag,
            kwh_natt=self._sum_natt,
            kwh_uten_pris=self._sum_uten,
            kwh_delvis_pris=self._sum_delvis,
            avvist_kwh=self._avvist_kwh,
            intervaller=len(self._poster),
        )

    def _trekk_bidrag(self, start: datetime) -> None:
        """Ta ut det intervallet bidro med sist. Samme tall som ble lagt til."""
        gammelt = self._bidrag.pop(start, None)
        if gammelt is None:
            return
        kwh, tariff, priskvalitet = gammelt
        self._sum_total -= kwh
        if tariff is Tariff.DAG:
            self._sum_dag -= kwh
        else:
            self._sum_natt -= kwh
        if priskvalitet is Intervallkvalitet.UTEN_PRIS:
            self._sum_uten -= kwh
        elif priskvalitet is Intervallkvalitet.DELVIS_PRIS:
            self._sum_delvis -= kwh

    def _legg_til_bidrag(self, start: datetime) -> None:
        post = self._poster.get(start)
        if post is None:
            return
        i = self._bygg(start, post, None)
        priskvalitet = i.pris.kvalitet if i.pris is not None else Intervallkvalitet.UTEN_PRIS
        self._bidrag[start] = (i.kwh, i.tariff, priskvalitet)
        self._sum_total += i.kwh
        if i.tariff is Tariff.DAG:
            self._sum_dag += i.kwh
        else:
            self._sum_natt += i.kwh
        if priskvalitet is Intervallkvalitet.UTEN_PRIS:
            self._sum_uten += i.kwh
        elif priskvalitet is Intervallkvalitet.DELVIS_PRIS:
            self._sum_delvis += i.kwh

    def statusfelt(self, naa: datetime) -> dict[str, Any]:
        """De nye feltene i felttabellen, klare til å legges i data-dicten.

        Kroner er ikke med. L3b fyller resten fra de samme intervallene.
        """
        grense = krev_aware(naa, "naa")
        starter = self._starter()
        # Startene er sorterte, så de åpne er en hale: så snart et intervall er
        # lukket, er alle foran det også lukket.
        apne = 0
        while apne < len(starter) and starter[-1 - apne] + AVREGNINGSINTERVALL > grense:
            apne += 1
        sist_lukket = starter[-1 - apne] if apne < len(starter) else None
        siste = self.intervall(sist_lukket, grense) if sist_lukket is not None else None
        sum_ = self.maanedssum()
        return {
            "avregning_skjema": SKJEMA_VERSJON,
            "avregning_ufullstendig": self.ufullstendig,
            "avregning_sist_observert": (
                self._sist_observert.observed_at.isoformat() if self._sist_observert else None
            ),
            "avregning_kilde": (self._sist_observert.source_identity if self._sist_observert else None),
            "avregning_siste_intervall": siste.start_utc.isoformat() if siste else None,
            "avregning_apne_intervaller": apne,
            "avregning_avvist_kwh": sum_.avvist_kwh,
            "kwh_uten_pris": sum_.kwh_uten_pris,
            "kwh_delvis_pris": sum_.kwh_delvis_pris,
        }

    # -- persistens --------------------------------------------------------

    def til_lagring(self, naa: datetime | None = None) -> dict[str, Any]:
        """Bokens del av Store-filen, skjema 3 (D).

        D krever de åpne intervallene og prisrutene deres. `naa` er klokken
        lagringen skjer på, og med den skrives bare vinduet som fortsatt kan
        endre seg: det åpne intervallet og timene rett før det.

        Uten `naa` skrives hele den aktive måneden. Det er riktigere på papiret
        og umulig i drift: lagringen skjer ved hver poll, og en måned med
        prisruter er et par hundre kilobyte å skrive hvert minutt på et
        SD-kort. Det som faller utenfor vinduet er ferdig avregnet, og summen
        av det ligger i månedsfeltene coordinatoren bærer.
        """
        beholde = intervallstart(naa) - LAGRINGSVINDU if naa is not None else None
        return {
            "skjema_versjon": SKJEMA_VERSJON,
            "aktiv_maned": self._aktiv_maned,
            "ufullstendig": self.ufullstendig,
            "avvist_kwh": self._avvist_kwh,
            "sist_observert": self._sist_observert.til_lagring() if self._sist_observert else None,
            "pris": self.pris.til_lagring(fra=beholde),
            "intervaller": [
                {
                    "start_utc": start.isoformat(),
                    "kwh": self._poster[start].kwh,
                    "energikvalitet": str(self._poster[start].energikvalitet),
                }
                for start in (
                    self._starter()
                    if beholde is None
                    else self._starter()[bisect_left(self._starter(), beholde) :]
                )
            ],
            "arkiv": {
                maned: {
                    "kwh_total": sum_.kwh_total,
                    "kwh_dag": sum_.kwh_dag,
                    "kwh_natt": sum_.kwh_natt,
                    "kwh_uten_pris": sum_.kwh_uten_pris,
                    "kwh_delvis_pris": sum_.kwh_delvis_pris,
                    "avvist_kwh": sum_.avvist_kwh,
                    "intervaller": sum_.intervaller,
                }
                for maned, sum_ in sorted(self._arkiv.items())
            },
        }

    @classmethod
    def fra_lagring(cls, raa: Mapping[str, Any] | None, **kwargs: Any) -> Avregningsbok:
        """Gjenoppta boken fra Store (C5, D).

        `raa` fra et eldre skjema gir en tom bok merket `ufullstendig`:
        månedssummene fra v1 og v2 kan ikke gjøres om til intervallhistorikk,
        og første avlesning etter migreringen blir baseline. Ingen intervaller
        bokføres bakover.
        """
        migrert = migrer_lagring(raa)
        bok = cls(**kwargs)
        bok.ufullstendig = bool(migrert["ufullstendig"])
        bok._aktiv_maned = migrert["aktiv_maned"]
        bok._avvist_kwh = float(migrert["avvist_kwh"])
        if migrert["sist_observert"]:
            bok._sist_observert = Avlesning.fra_lagring(migrert["sist_observert"])
        if migrert["pris"] and kwargs.get("prisadapter") is None:
            bok.pris = Prisadapter.fra_lagring(migrert["pris"])
        for rad in migrert["intervaller"]:
            bok._poster[datetime.fromisoformat(str(rad["start_utc"]))] = _Post(
                kwh=float(rad["kwh"]),
                energikvalitet=Energikvalitet(rad.get("energikvalitet", Energikvalitet.MALT)),
            )
        bok._skitne.update(bok._poster)
        for maned, sum_ in migrert["arkiv"].items():
            bok._arkiv[maned] = Manedssum(
                maned=maned,
                kwh_total=float(sum_["kwh_total"]),
                kwh_dag=float(sum_["kwh_dag"]),
                kwh_natt=float(sum_["kwh_natt"]),
                kwh_uten_pris=float(sum_["kwh_uten_pris"]),
                kwh_delvis_pris=float(sum_["kwh_delvis_pris"]),
                avvist_kwh=float(sum_["avvist_kwh"]),
                intervaller=int(sum_["intervaller"]),
            )
        return bok


def migrer_lagring(raa: Mapping[str, Any] | None) -> dict[str, Any]:
    """Gjør en lagret bok om til skjema 3 (D).

    Migreringen er enveis. Fra v1 og v2 finnes det ingen intervallhistorikk å
    rekonstruere, så resultatet er en tom bok med `ufullstendig: true`. Flagget
    fjernes ved første månedsskifte etter migreringen. Feltene fra det gamle
    skjemaet følger med uendret under `ovrige`, slik at den som eier Store-filen
    kan skrive dem videre og en nedgradering ikke mister månedsdata.
    """
    kjente = {
        "skjema_versjon",
        "aktiv_maned",
        "ufullstendig",
        "avvist_kwh",
        "sist_observert",
        "pris",
        "intervaller",
        "arkiv",
        "ovrige",
    }
    tom: dict[str, Any] = {
        "skjema_versjon": SKJEMA_VERSJON,
        "aktiv_maned": None,
        "ufullstendig": True,
        "avvist_kwh": 0.0,
        "sist_observert": None,
        "pris": None,
        "intervaller": [],
        "arkiv": {},
        "ovrige": {},
    }
    if not raa:
        # Fersk installasjon, ikke en migrering: ingenting mangler.
        tom["ufullstendig"] = False
        return tom

    versjon = int(raa.get("skjema_versjon", 0))
    ovrige = {k: v for k, v in raa.items() if k not in kjente}
    if versjon < SKJEMA_VERSJON:
        tom["ovrige"] = ovrige
        return tom

    return {
        "skjema_versjon": versjon,
        "aktiv_maned": raa.get("aktiv_maned"),
        "ufullstendig": bool(raa.get("ufullstendig", False)),
        "avvist_kwh": float(raa.get("avvist_kwh", 0.0)),
        "sist_observert": raa.get("sist_observert"),
        "pris": raa.get("pris"),
        "intervaller": list(raa.get("intervaller", [])),
        "arkiv": dict(raa.get("arkiv", {})),
        "ovrige": {**ovrige, **dict(raa.get("ovrige", {}))},
    }


def _maanedsstart_utc(maned: str) -> datetime:
    """Første øyeblikk i fakturamåneden, i UTC.

    Lokal midnatt, ikke UTC-midnatt: 31.03 kl. 22 UTC er allerede april lokalt
    (C3 D5).
    """
    aar, mnd = (int(del_) for del_ in maned.split("-"))
    return datetime(aar, mnd, 1, tzinfo=OSLO).astimezone(UTC)


def summer_intervaller(intervaller: Iterable[AvregnetIntervall]) -> float:
    """Sum kWh over en samling intervaller. Ingen avrunding (A3)."""
    return sum(i.kwh for i in intervaller)


def med_pris(intervall: AvregnetIntervall, pris: Prisintervall | None) -> AvregnetIntervall:
    """Sett en annen pris på et intervall, for replay og etterkontroll (L2).

    Drift bruker den ikke: i drift kommer prisen fra adapteren, og et lukket
    intervall får aldri en ny prøve (C6).
    """
    kvalitet = (
        Intervallkvalitet.UFULLSTENDIG
        if intervall.kvalitet is Intervallkvalitet.UFULLSTENDIG
        else (pris.kvalitet if pris is not None else Intervallkvalitet.UTEN_PRIS)
    )
    return replace(intervall, pris=pris, kvalitet=kvalitet)
