"""Den eneste veien inn til en sensorverdi.

Kontrakten står i `docs/kontrakter/input-og-konfig.md`. Setup, options,
reconfigure og runtime går alle gjennom denne modulen, slik at det bare finnes
ett sted som avgjør hva et gyldig input er og hva verdien betyr.

Bakgrunnen er at coordinatoren leste `state.state` som et tall og aldri så på
`unit_of_measurement`. En kW-sensor ble lest som W, en NOK/MWh-sensor som
NOK/kWh, og begge deler er tusen ganger feil. Config-flyten hadde en halv vakt
for spotprisen som avviste øre/kWh den kunne regnet om, og slapp gjennom EUR.

To regler skiller seg fra det som sto før:

- Et ikke-gyldig resultat blir aldri 0. En 0 er en måling som sier at du ikke
  bruker noe, og det er en annen påstand enn at målingen uteble.
- At entiteten mangler er `Utilgjengelig`, ikke `Ugyldig`. En slettet sensor er
  ikke en feilkonfigurasjon vi skal avvise, det er data som ikke kommer inn.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from homeassistant.helpers import entity_registry as er

from .const import (
    INPUT_ROLLE_EFFEKT,
    INPUT_ROLLE_EKSPORT,
    INPUT_ROLLE_ENERGI,
    INPUT_ROLLE_LEVERANDORPRIS,
    INPUT_ROLLE_SPOTPRIS,
)

# --------------------------------------------------------------------------
# Grunner (§1). Faste strenger: diagnostikken og oversettelsene slår opp på dem.
# --------------------------------------------------------------------------

GRUNN_FINNES_IKKE: Final[str] = "finnes_ikke"
GRUNN_UTILGJENGELIG: Final[str] = "utilgjengelig"
GRUNN_UKJENT: Final[str] = "ukjent"
GRUNN_IKKE_KONFIGURERT: Final[str] = "ikke_konfigurert"

GRUNN_IKKE_TALL: Final[str] = "ikke_tall"
GRUNN_IKKE_ENDELIG: Final[str] = "ikke_endelig"
GRUNN_UKJENT_ENHET: Final[str] = "ukjent_enhet"
GRUNN_FEIL_DIMENSJON: Final[str] = "feil_dimensjon"
GRUNN_FEIL_VALUTA: Final[str] = "feil_valuta"
GRUNN_IKKE_KUMULATIV: Final[str] = "ikke_kumulativ"
GRUNN_URIMELIG_VERDI: Final[str] = "urimelig_verdi"

#: Grunner som skyldes enheten. Ved runtime gir de vakthold-problemtypen `enhet`
#: og et repair, for en sensor som bytter enhet under drift er en ekte feil.
ENHETSGRUNNER: Final[frozenset[str]] = frozenset(
    {GRUNN_UKJENT_ENHET, GRUNN_FEIL_DIMENSJON, GRUNN_FEIL_VALUTA}
)

# --------------------------------------------------------------------------
# Dimensjoner og enhetstabell (§2)
# --------------------------------------------------------------------------

DIM_EFFEKT: Final[str] = "effekt"
DIM_ENERGI: Final[str] = "energi"
DIM_PRIS: Final[str] = "pris"
#: Rene pengebeløp. Ingen rolle ber om dem, men `kr` og `NOK` er de vanligste
#: feilvalgene (en totalkostnad i stedet for en pris), og de fortjener
#: `feil_dimensjon` framfor `ukjent_enhet`.
DIM_PENGER: Final[str] = "penger"

ROLLE_DIMENSJON: Final[dict[str, str]] = {
    INPUT_ROLLE_EFFEKT: DIM_EFFEKT,
    INPUT_ROLLE_EKSPORT: DIM_EFFEKT,
    INPUT_ROLLE_ENERGI: DIM_ENERGI,
    INPUT_ROLLE_SPOTPRIS: DIM_PRIS,
    INPUT_ROLLE_LEVERANDORPRIS: DIM_PRIS,
}

#: Enheten hver dimensjon normaliseres til.
NORMALISERT_ENHET: Final[dict[str, str]] = {
    DIM_EFFEKT: "W",
    DIM_ENERGI: "kWh",
    DIM_PRIS: "NOK/kWh",
}


@dataclass(frozen=True, slots=True)
class Enhetsregel:
    """Én rad i enhetstabellen."""

    dimensjon: str
    normalisert: str
    faktor: float


#: Nøklene er kanoniserte enhetsstrenger (se `kanoniser_enhet`).
ENHETSTABELL: Final[dict[str, Enhetsregel]] = {
    "w": Enhetsregel(DIM_EFFEKT, "W", 1.0),
    "kw": Enhetsregel(DIM_EFFEKT, "W", 1000.0),
    "mw": Enhetsregel(DIM_EFFEKT, "W", 1_000_000.0),
    "wh": Enhetsregel(DIM_ENERGI, "kWh", 0.001),
    "kwh": Enhetsregel(DIM_ENERGI, "kWh", 1.0),
    "mwh": Enhetsregel(DIM_ENERGI, "kWh", 1000.0),
    "nok/kwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 1.0),
    "kr/kwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 1.0),
    "øre/kwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 0.01),
    "nok/mwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 0.001),
    "kr/mwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 0.001),
    "øre/mwh": Enhetsregel(DIM_PRIS, "NOK/kWh", 0.00001),
    "kr": Enhetsregel(DIM_PENGER, "NOK", 1.0),
    "nok": Enhetsregel(DIM_PENGER, "NOK", 1.0),
    "øre": Enhetsregel(DIM_PENGER, "NOK", 0.01),
}

#: Valutaene vi kan regne på. Alt annet foran en energinevner er `feil_valuta`:
#: integrasjonen har ingen valutakurs, og å lese euro som kroner er verre enn
#: å si nei.
NORSKE_VALUTAER: Final[frozenset[str]] = frozenset({"nok", "kr", "øre"})
_ENERGINEVNERE: Final[frozenset[str]] = frozenset({"wh", "kwh", "mwh"})
_VALUTATEGN: Final[dict[str, str]] = {"€": "eur", "$": "usd", "£": "gbp"}

#: Grense for en prisverdi etter normalisering til NOK/kWh (§1). Norske
#: timespriser har toppet seg i størrelsesorden ti kroner, så 100 ligger en
#: størrelsesorden over ekte data og fanger fortsatt en sensor som leverer noe
#: helt annet enn en pris. Regnes på absoluttverdien: negative spotpriser er
#: gyldige.
MAKS_RIMELIG_PRIS_NOK_KWH: Final[float] = 100.0

#: `state_class` en energisensor må ha. Vi leser differansen mellom
#: avlesninger, så alt annet enn en teller gir meningsløse deltaer.
KUMULATIVE_STATE_CLASS: Final[frozenset[str]] = frozenset({"total_increasing", "total"})

#: Store-skjemaet baselinen lagres i (§5).
BASELINE_SKJEMA: Final[int] = 2
#: Nøkkelen baselinen ligger under i Store-filen.
BASELINE_NOKKEL: Final[str] = "energi_baseline"


# --------------------------------------------------------------------------
# Resultattypene (§1)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Gyldig:
    """Entiteten finnes og leverer et endelig tall i en enhet vi kan regne om.

    `observed_at` og `avlest_kl` er to ulike tider og begge trengs: energien
    bokføres etter observasjonstiden, mens en prisprøve hører til prisruten
    avlesningen faller i. Adapteren leverer begge og velger ikke mellom dem.

    `raa_enhet` er `None` når sensoren ikke oppgir noen enhet. Da har vi antatt
    rollens egen enhet, og for prissensorer skal det si fra (§4).
    """

    verdi: float
    enhet_normalisert: str
    observed_at: datetime
    avlest_kl: datetime
    raa_enhet: str | None
    entity_id: str | None = None

    @property
    def enhet_antatt(self) -> bool:
        """Om enheten ble antatt fordi sensoren ikke oppgir noen."""
        return self.raa_enhet is None


@dataclass(frozen=True, slots=True)
class Utilgjengelig:
    """Entiteten leverer ikke akkurat nå, men oppsettet er i orden."""

    grunn: str
    entity_id: str | None = None


@dataclass(frozen=True, slots=True)
class Ugyldig:
    """Entiteten leverer noe vi ikke har lov til å regne på."""

    grunn: str
    entity_id: str | None = None
    raa_enhet: str | None = None


Inputresultat = Gyldig | Utilgjengelig | Ugyldig


# --------------------------------------------------------------------------
# Enhetsoppslag
# --------------------------------------------------------------------------

_MELLOMROM = re.compile(r"\s+")


def kanoniser_enhet(raa: str) -> str:
    """Enhetsstrengen slik tabellen slår opp på den.

    Sammenligningen er whitespace-trimmet og case-insensitiv, og `ore` godtas
    som skrivemåte for `øre`.
    """
    tekst = _MELLOMROM.sub("", raa).lower()
    for tegn, navn in _VALUTATEGN.items():
        tekst = tekst.replace(tegn, navn)
    return tekst.replace("ore", "øre")


def _brok(kanonisk: str) -> tuple[str, str] | None:
    """(teller, nevner) hvis enheten har formen `noe/noe`."""
    if kanonisk.count("/") != 1:
        return None
    teller, nevner = kanonisk.split("/")
    if not teller or not nevner:
        return None
    return teller, nevner


def vurder_enhet(raa_enhet: str | None, rolle: str) -> tuple[str, float] | str:
    """(normalisert enhet, faktor) for rollen, eller en `Ugyldig`-grunn.

    En sensor uten enhet får rollens egen enhet antatt med faktor 1. Det er
    dagens oppførsel for effekt og energi, og for pris er det §4: sensoren
    godtas som NOK/kWh, men det sies fra med et repair-varsel.
    """
    dimensjon = ROLLE_DIMENSJON[rolle]
    if raa_enhet is None or not raa_enhet.strip():
        return NORMALISERT_ENHET[dimensjon], 1.0

    kanonisk = kanoniser_enhet(raa_enhet)
    regel = ENHETSTABELL.get(kanonisk)
    if regel is not None:
        if regel.dimensjon != dimensjon:
            return GRUNN_FEIL_DIMENSJON
        return regel.normalisert, regel.faktor

    brok = _brok(kanonisk)
    if brok is not None and brok[1] in _ENERGINEVNERE:
        # Pris per energi, men med en teller vi ikke kjenner igjen. Er det en
        # valuta, er det valutaen som er problemet.
        if brok[0] not in NORSKE_VALUTAER:
            return GRUNN_FEIL_VALUTA if dimensjon == DIM_PRIS else GRUNN_FEIL_DIMENSJON
        return GRUNN_UKJENT_ENHET
    if brok is not None and brok[0] in NORSKE_VALUTAER:
        # NOK/noe-annet-enn-energi, for eksempel kr/mnd på et fastledd.
        return GRUNN_FEIL_DIMENSJON
    return GRUNN_UKJENT_ENHET


# --------------------------------------------------------------------------
# Lesing
# --------------------------------------------------------------------------


def _attributt(state: Any, navn: str) -> str | None:
    """Et strengattributt fra staten, eller None.

    `isinstance`-sjekken er ikke paranoia: HA lover `str | None`, men
    attributtene kommer fra en hvilken som helst integrasjon, og testenes
    mock-states svarer med objekter på alt.
    """
    attributter = getattr(state, "attributes", None)
    if attributter is None:
        return None
    try:
        verdi = attributter.get(navn)
    except (AttributeError, TypeError):
        return None
    return verdi if isinstance(verdi, str) else None


def _observasjonstid(state: Any, naa: datetime) -> datetime:
    """Statens `last_updated`, eller avlesningstiden om den mangler."""
    sett = getattr(state, "last_updated", None)
    return sett if isinstance(sett, datetime) else naa


def vurder_state(state: Any, rolle: str, *, entity_id: str | None = None, naa: datetime) -> Inputresultat:
    """Vurder en state vi allerede har hentet.

    Skilt fra `les_input` fordi config-flyten har staten i hånden og ikke skal
    slå opp entiteten en gang til.
    """
    raa_enhet = _attributt(state, "unit_of_measurement")

    enhet = vurder_enhet(raa_enhet, rolle)
    if isinstance(enhet, str):
        return Ugyldig(enhet, entity_id, raa_enhet)
    normalisert, faktor = enhet

    if ROLLE_DIMENSJON[rolle] == DIM_ENERGI:
        state_class = _attributt(state, "state_class")
        if state_class not in KUMULATIVE_STATE_CLASS:
            return Ugyldig(GRUNN_IKKE_KUMULATIV, entity_id, raa_enhet)

    try:
        raa_verdi = float(state.state)
    except (ValueError, TypeError):
        return Ugyldig(GRUNN_IKKE_TALL, entity_id, raa_enhet)
    if not math.isfinite(raa_verdi):
        return Ugyldig(GRUNN_IKKE_ENDELIG, entity_id, raa_enhet)

    verdi = raa_verdi * faktor

    if ROLLE_DIMENSJON[rolle] == DIM_PRIS and abs(verdi) > MAKS_RIMELIG_PRIS_NOK_KWH:
        return Ugyldig(GRUNN_URIMELIG_VERDI, entity_id, raa_enhet)

    return Gyldig(
        verdi=verdi,
        enhet_normalisert=normalisert,
        observed_at=_observasjonstid(state, naa),
        avlest_kl=naa,
        raa_enhet=raa_enhet,
        entity_id=entity_id,
    )


def les_input(hass: Any, entity_id: str | None, rolle: str, *, naa: datetime) -> Inputresultat:
    """Les én rolle fra HA og gi det typede resultatet."""
    if not entity_id:
        return Utilgjengelig(GRUNN_IKKE_KONFIGURERT, None)

    state = hass.states.get(entity_id)
    if state is None:
        return Utilgjengelig(GRUNN_FINNES_IKKE, entity_id)

    raa_state = getattr(state, "state", None)
    if raa_state == "unavailable":
        return Utilgjengelig(GRUNN_UTILGJENGELIG, entity_id)
    if raa_state == "unknown":
        return Utilgjengelig(GRUNN_UKJENT, entity_id)

    return vurder_state(state, rolle, entity_id=entity_id, naa=naa)


def kildeidentitet(hass: Any, entity_id: str | None) -> str | None:
    """Entitetens `unique_id` fra entity-registeret.

    Entity-id alene er ikke fysisk identitet: den følger med ved omdøping, og
    to ulike målere kan arve samme entity-id. Mangler registeroppføringen, er
    det ingen identitet å binde baselinen til, og da faller sammenligningen
    tilbake på entity-id-en i `Baseline.samme_kilde`.
    """
    if not entity_id:
        return None
    try:
        register = er.async_get(hass)
        oppforing = register.async_get(entity_id)
    except (AttributeError, TypeError, KeyError):
        return None
    unique_id = getattr(oppforing, "unique_id", None)
    return unique_id if isinstance(unique_id, str) else None


# --------------------------------------------------------------------------
# Energibaseline (§5)
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Baseline:
    """Den forrige avlesningen vi måler delta fra, bundet til kilden sin.

    Uten kildebinding tolkes et målerbytte som forbruk: en ny teller som står
    på 1020 der den gamle sto på 1000 ga 20 kWh falskt månedsforbruk.
    """

    source_identity: str | None
    entity_id: str
    value_kwh: float
    observed_at: datetime

    def samme_kilde(self, source_identity: str | None, entity_id: str) -> bool:
        """Om en avlesning kommer fra samme fysiske kilde som baselinen.

        `unique_id` er fasiten. Mangler den på begge sider, er entity-id-en det
        eneste vi har, og den er bedre enn å anta at alt er samme måler.
        """
        if self.source_identity is not None or source_identity is not None:
            return self.source_identity == source_identity
        return self.entity_id == entity_id

    def som_lagret(self) -> dict[str, Any]:
        """Baselinen på Store-form."""
        return {
            "schema_version": BASELINE_SKJEMA,
            "source_identity": self.source_identity,
            "entity_id": self.entity_id,
            "value_kwh": self.value_kwh,
            "observed_at": _iso_utc(self.observed_at),
        }

    @classmethod
    def fra_lagret(cls, data: Any) -> Baseline | None:
        """Les en lagret baseline, eller None om den ikke er brukbar.

        Alt som ligger lagret fra før er v1: en rå sensorverdi uten kilde og
        uten enhet. Den forkastes én gang, for vi vet verken hvilken måler den
        kom fra eller hvilken enhet den var i.
        """
        if not isinstance(data, dict):
            return None
        if data.get("schema_version") != BASELINE_SKJEMA:
            return None
        try:
            value_kwh = float(data["value_kwh"])
        except (KeyError, ValueError, TypeError):
            return None
        if not math.isfinite(value_kwh) or value_kwh <= 0:
            return None
        entity_id = data.get("entity_id")
        if not isinstance(entity_id, str):
            return None
        observed = data.get("observed_at")
        if not isinstance(observed, str):
            return None
        try:
            observed_at = datetime.fromisoformat(observed)
        except ValueError:
            return None
        source_identity = data.get("source_identity")
        if source_identity is not None and not isinstance(source_identity, str):
            return None
        return cls(source_identity, entity_id, value_kwh, observed_at)


def _iso_utc(tidspunkt: datetime) -> str:
    """ISO 8601 i UTC, slik resten av Store-filen skriver tidsstempler.

    Lagres det med lokal sone, kommer det tilbake med samme ZoneInfo-objekt som
    `dt_util.now()`, og da måler en rett subtraksjon veggklokke over et
    sommertidsskifte.
    """
    if tidspunkt.tzinfo is None:
        return tidspunkt.isoformat()
    return tidspunkt.astimezone(UTC).isoformat()


__all__ = [
    "BASELINE_NOKKEL",
    "BASELINE_SKJEMA",
    "ENHETSGRUNNER",
    "ENHETSTABELL",
    "Baseline",
    "Gyldig",
    "Inputresultat",
    "Ugyldig",
    "Utilgjengelig",
    "kanoniser_enhet",
    "kildeidentitet",
    "les_input",
    "vurder_enhet",
    "vurder_state",
]
