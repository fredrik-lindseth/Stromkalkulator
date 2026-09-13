"""Data coordinator for Nettleie."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .avregning import (
    OSLO,
    Avlesning,
    Avregningsbok,
    Bokforing,
    Energikvalitet,
    Tariff,
    Tariffregel,
    Utfall,
    intervallstart,
    lokal_dato,
    lokal_maned,
    lokal_time,
)
from .const import (
    AVGIFTSSONE_STANDARD,
    BOLIGTYPE_BOLIG,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_EGENDEFINERT_KAPASITETSTRINN,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGI_FROSSEN_TIMER,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_PRISENHET_BEKREFTET,
    CONF_SIKRINGSTRINN,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DEFAULT_DSO,
    DEFAULT_ENERGI_FROSSEN_TIMER,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DOMAIN,
    DSO_EGENDEFINERT,
    DSO_LIST,
    ENOVA_AVGIFT,
    INPUT_ROLLE_EFFEKT,
    INPUT_ROLLE_EKSPORT,
    INPUT_ROLLE_ENERGI,
    INPUT_ROLLE_LEVERANDORPRIS,
    INPUT_ROLLE_SPOTPRIS,
    INPUT_UTFALL_GRACE_MINUTTER,
    MAX_ELAPSED_HOURS,
    MAX_ENERGI_FROSSEN_TIMER,
    MAX_ENERGY_DELTA_KWH,
    MAX_POWER_CLAMP_W,
    MIN_ENERGI_FROSSEN_TIMER,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    TARIFFMODUS_MANUAL,
    UPDATE_INTERVAL_MINUTES,
    VAKTHOLD_ENHET,
    VAKTHOLD_FROSSEN,
    VAKTHOLD_SPOT_UTLOPT,
    VAKTHOLD_UTFALL,
    compute_energiledd_inkl_mva,
    get_forbruksavgift,
    get_mva_sats,
    get_norgespris_inkl_mva,
    get_norgespris_max_kwh,
    get_stromstotte_max_kwh,
    get_stromstotte_terskel,
    les_tariffmodus,
)
from .dso import (
    FASTLEDD_FEM_VEKTET_AR,
    FASTLEDD_MND_MAX,
    FASTLEDD_OV_TREFASE,
    FASTLEDD_TRINNBASERTE,
    finn_kapasitetstrinn,
    finn_sikringstrinn,
    grunnlag_i_lavere_trinn,
    hent_fastledd_metode,
    parse_kapasitetstrinn,
)
from .inputadapter import (
    BASELINE_NOKKEL,
    ENHETSGRUNNER,
    GRUNN_FINNES_IKKE,
    Baseline,
    Gyldig,
    Inputresultat,
    Ugyldig,
    Utilgjengelig,
    kildeidentitet,
    les_input,
)
from .kostnad import (
    INGEN_KRONER,
    Kroner,
    Satser,
    andel_av_maaned,
    fastledd_belop,
    forlopt_andel_av_maaned,
    kroner_for_intervall,
    sekunder_forlopt_i_dogn,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .avregning import AvregnetIntervall
    from .dso import DSOEntry, EnergileddPeriode, FastleddLineaer, KapasitetstrinnDict

_LOGGER = logging.getLogger(__name__)

# FEM_VEKTET_ÅR ser tolv måneder bakover. Fjellnett skriver «løpende siste 12
# mnd», ikke 52 uker, så vinduet regnes i kalendermåneder mot toppens egen dato.
FEM_VEKTET_VINDU_MAANEDER = 12
FEM_VEKTET_ANTALL_TOPPER = 5


@dataclass
class DailyMaxEntry:
    """One day's maximum hourly average power."""

    kw: float
    hour: int | None = None


@dataclass
class WeeklyMaxEntry:
    """Én ukes høyeste timessnitt, for nettselskap som avregner årstopper.

    `dato` er dagen toppen falt på, og avgjør når toppen faller ut av
    tolvmånedersvinduet. Sesongvekten følger derimot mandagen i uken toppen
    ligger i, ikke toppens egen måned: Fjellnetts fellesbestemmelser sier at en
    uke som krysser et månedsskifte vektes med mandagens måned hele veien.
    Uken identifiseres av mandagens dato, som sorterer kronologisk.
    """

    kw: float
    dato: str
    hour: int | None = None


@dataclass
class ConsumptionData:
    """Day/night energy consumption accumulator."""

    dag: float = 0.0
    natt: float = 0.0

    @property
    def total(self) -> float:
        return self.dag + self.natt

    def copy(self) -> ConsumptionData:
        return ConsumptionData(dag=self.dag, natt=self.natt)


def days_in_month(now: datetime) -> int:
    """Get number of days in the month of the given datetime."""
    next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    return (next_month - now.replace(day=1)).days


_SPOT_CACHE_MAX_AGE = timedelta(hours=2)


def _tolv_maaneder_tilbake(dag: date) -> date:
    """Samme dato tolv kalendermåneder tidligere.

    29. februar finnes ikke året før, og klemmes til 28. Det gjør vinduet ett
    døgn lengre det ene året, aldri kortere, så ingen topp dør for tidlig.
    """
    aar = dag.year - FEM_VEKTET_VINDU_MAANEDER // 12
    try:
        return dag.replace(year=aar)
    except ValueError:
        return dag.replace(year=aar, day=28)


def _toppdato(nokkel: str, entry: WeeklyMaxEntry) -> date:
    """Datoen ukestoppen falt på.

    Faller tilbake til ukenøkkelen om `dato` er ubrukelig, og til date.min om
    begge er det. En post ingen kan datere hører ikke hjemme i vinduet.
    """
    for kandidat in (entry.dato, nokkel):
        try:
            return date.fromisoformat(kandidat)
        except ValueError:
            continue
    return date.min


def _som_sats(raa: object, fallback: float) -> float:
    """Lagret energiledd som tall, med katalogens sats for noe uleselig.

    En overstyring som ikke er et tall er ikke en sats, og da er katalogen det
    beste vi har. Alternativet, å la entryet regne med 0, ville gitt en
    nettleie som ser billig og riktig ut.
    """
    try:
        return float(raa)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def sekunder_mellom(fra: datetime, til: datetime) -> float:
    """Ekte tid mellom to tidspunkt, i sekunder.

    Python hopper over utcoffset når begge datetimes har samme tzinfo-objekt,
    og dt_util.now() gir nettopp det. En rett subtraksjon måler derfor
    veggklokke: ved sommertidsskiftet blir ett ekte minutt til 61, og to ekte
    timer til tre. timestamp() går veien om UTC og måler tiden som faktisk gikk.
    Alt vaktholdet sammenligner skal gjennom her.
    """
    return til.timestamp() - fra.timestamp()


def trekk_fra_sekunder(tidspunkt: datetime, sekunder: float) -> datetime:
    """Tidspunktet så mange ekte sekunder tidligere.

    Motstykket til sekunder_mellom(). Å trekke fra en timedelta flytter
    veggklokken, så over et sommertidsskifte bommer den med en time. Veien om
    timestamp() treffer øyeblikket som faktisk ligger så mange sekunder tilbake.
    """
    if tidspunkt.tzinfo is None:
        return tidspunkt - timedelta(seconds=sekunder)
    return datetime.fromtimestamp(tidspunkt.timestamp() - sekunder, tz=tidspunkt.tzinfo)


def _aware(tidspunkt: datetime) -> datetime:
    """Tidssoneklar utgave av et tidspunkt, tolket som Europe/Oslo om nødvendig.

    Avregningskjernen krever tidssoneklar tid og kaster ellers (B1), og det er
    riktig av den: en naiv tid er nettopp det som gjør at en time forsvinner
    eller kommer to ganger over sommertidsskiftene. I drift er `dt_util.now()`
    alltid klar. Dette er grensen mot alt som ikke er det, og den gjetter på
    Europe/Oslo framfor å la en avlesning falle ut.
    """
    return tidspunkt if tidspunkt.tzinfo is not None else tidspunkt.replace(tzinfo=OSLO)


def _uten_kildeidentitet(data: Any) -> Any:
    """Store-filen slik den kan stå i en logg (kontrakt §10.1).

    `source_identity` er `unique_id` fra entity-registeret, og hos AMS- og
    Elhub-integrasjoner er det målepunkt-ID eller målerserienummer, altså noe
    som peker på én husstand. Home Assistant har en knapp som slår på DEBUG og
    laster ned loggen for innliming i et offentlig issue, så en debuglinje er
    like offentlig som diagnostikkdumpen. Entity-id-en står igjen: den er et
    navn brukeren har valgt selv, og uten den vet han ikke hvilken sensor
    linjen gjelder.

    Redigeringen er rekursiv fordi nøkkelen ligger både på baselinen og på
    bokens siste observasjon.
    """
    if isinstance(data, Mapping):
        return {
            nokkel: ("<redigert>" if nokkel == "source_identity" else _uten_kildeidentitet(verdi))
            for nokkel, verdi in data.items()
        }
    return data


def _som_lokal(tidspunkt: datetime | None) -> datetime | None:
    """Lagret tidsstempel tilbake til lokal tid.

    _iso_utc() skriver UTC til Store, og fromisoformat gir det tilbake i UTC.
    Alt annet i minnet er lokal tid fra dt_util.now(), og et tidsstempel som
    vises til brukeren eller havner i diagnostikken skal vise klokken på veggen.
    Naive tidsstempel har ingen sone å regne om fra og slippes gjennom.
    """
    if tidspunkt is None or tidspunkt.tzinfo is None:
        return tidspunkt
    lokal: datetime = dt_util.as_local(tidspunkt)
    return lokal


def _iso_utc(tidspunkt: datetime | None) -> str | None:
    """Tidsstempel til lagring, i UTC når det er tidssonebevisst.

    Lagres det med lokal sone, kommer det tilbake med samme ZoneInfo-objekt som
    dt_util.now() og havner i veggklokke-fellen over.
    """
    if tidspunkt is None:
        return None
    if tidspunkt.tzinfo is None:
        return tidspunkt.isoformat()
    return tidspunkt.astimezone(UTC).isoformat()


# Repair-issue-id per problemtype. Id-en suffikses med entry_id (incident 001),
# så to instanser aldri deler varsel.
_VAKTHOLD_ISSUE_PREFIX: dict[str, str] = {
    VAKTHOLD_UTFALL: "input_utfall",
    VAKTHOLD_FROSSEN: "energi_frossen",
    VAKTHOLD_SPOT_UTLOPT: "spot_utfall",
    VAKTHOLD_ENHET: "input_enhet",
}


def _vakthold_varighet(timer: float) -> str:
    """Varigheten slik varselet viser den, kvantisert så teksten ikke blafrer.

    Varselet skrives om hver gang innholdet endrer seg, og polles hvert
    minutt. Et tall med desimal ville skrevet om issuen hvert sjette minutt,
    altså rundt 2400 ganger gjennom et utfall som det på 237 timer i juli.
    Over en time vises derfor hele timer. Under en time beholdes desimalen,
    ellers ville det første varselet (som kommer etter 30 minutters grace)
    meldt null timer.
    """
    if timer < 1:
        return f"{timer:.1f}"
    return f"{float(int(timer)):.1f}"


# Resultattypene slik diagnostikken navngir dem.
_RESULTATTYPE: dict[type, str] = {
    Gyldig: "gyldig",
    Utilgjengelig: "utilgjengelig",
    Ugyldig: "ugyldig",
}

# Rollenavnene slik de vises i repair-teksten. Attributtene bruker
# maskinnavnene, varselet leses av et menneske.
_ROLLE_TEKST: dict[str, str] = {
    INPUT_ROLLE_EFFEKT: "effektmåleren",
    INPUT_ROLLE_ENERGI: "energimåleren",
    INPUT_ROLLE_SPOTPRIS: "spotpris-sensoren",
    INPUT_ROLLE_EKSPORT: "eksportmåleren",
    INPUT_ROLLE_LEVERANDORPRIS: "strømleverandør-sensoren",
}


class NettleieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Nettleie data."""

    entry: ConfigEntry
    power_sensor: str | None
    spot_price_sensor: str | None
    electricity_company_price_sensor: str | None
    export_power_sensor: str | None
    energy_sensor: str | None
    _baseline: Baseline | None
    _baseline_forkastet: bool
    _input_resultater: dict[str, Inputresultat]
    _input_sist_gyldig_avlest: dict[str, datetime]
    dso: DSOEntry
    _dso_id: str
    avgiftssone: str
    har_norgespris: bool
    boligtype: str
    energiledd_dag_eks_mva: float
    energiledd_natt_eks_mva: float
    energiledd_dag: float  # inkl. forbruksavgift, Enova og mva (aktiv sats, oppdateres ved sesongbytte)
    energiledd_natt: float
    _energiledd_perioder_inkl: list[tuple[str, str, float, float]]  # (fra, til, dag_inkl, natt_inkl)
    _energiledd_perioder_eks: list[tuple[str, str, float, float]]  # samme, uten avgifter og mva
    kapasitetstrinn: list[tuple[float, int]]
    fastledd_metode: str
    fastledd_lineaer: FastleddLineaer | None
    fastledd_sesongfaktor: dict[int, float]
    sikringstrinn_valg: str | None
    kapasitet_varsel_terskel: float
    _daily_max_power: dict[str, DailyMaxEntry]
    _weekly_max_power: dict[str, WeeklyMaxEntry]
    _current_month: str  # "YYYY-MM" format for year-aware month tracking
    _monthly_consumption: ConsumptionData
    _last_update: datetime | None
    _previous_month_consumption: ConsumptionData
    _previous_month_top_3: dict[str, DailyMaxEntry]
    _previous_month_name: str | None
    _monthly_norgespris_diff: float
    _previous_month_norgespris_diff: float
    _monthly_norgespris_compensation: float
    _previous_month_norgespris_compensation: float
    _previous_month_kapasitetsledd: int
    _previous_month_kapasitetstrinn: str
    _previous_month_energiledd_dag: float
    _previous_month_energiledd_natt: float
    _monthly_export_kwh: float
    _monthly_export_revenue: float
    _previous_month_export_kwh: float
    _previous_month_export_revenue: float
    _previous_month_cost: float
    _monthly_accumulated_cost_strom: float
    _monthly_stromstotte: float
    _monthly_energiledd_dag: float
    _monthly_energiledd_natt: float
    _monthly_avgifter: float
    _monthly_energiledd_apning: float
    _monthly_accumulated_cost_kapasitetsledd: float
    _store: Store[dict[str, Any]]
    _store_loaded: bool
    energi_frossen_terskel_timer: float
    _input_sist_gyldig: dict[str, datetime]
    _input_utfall_aktiv: set[str]
    _last_energy_increase: datetime | None
    _vakthold_issues: dict[str, dict[str, str]]
    _vakthold_issues_synket: bool

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=UPDATE_INTERVAL_MINUTES),
        )
        self.entry = entry
        self.power_sensor = entry.data.get(CONF_POWER_SENSOR)
        self.spot_price_sensor = entry.data.get(CONF_SPOT_PRICE_SENSOR)
        self.electricity_company_price_sensor = entry.data.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR)
        self.export_power_sensor = entry.data.get(CONF_EXPORT_POWER_SENSOR)
        # Valgfri kumulativ energi-sensor (kWh, OBIS 1.8.0 fra AMS-måler).
        # Når satt: brukes som primær kilde via delta-akkumulasjon i stedet for
        # p * elapsed-Riemann-sum. Eksakt mot faktura. Tom string -> ingen sensor.
        energy_sensor_raw = entry.data.get(CONF_ENERGY_SENSOR)
        self.energy_sensor = energy_sensor_raw if energy_sensor_raw else None

        # Get DSO config
        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self.dso = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])
        self._dso_id = dso_id
        self._helg_som_natt = self.dso.get("helg_som_natt", True)
        self._terskel_inkludert = self.dso.get("terskel_inkludert", True)
        self._helligdager_ekstra = self.dso.get("helligdager_ekstra", [])

        # Get avgiftssone from config
        self.avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

        # Get Norgespris setting from config
        self.har_norgespris = entry.data.get(CONF_HAR_NORGESPRIS, False)

        # Get boligtype from config (default: bolig for backward compatibility)
        self.boligtype = entry.data.get(CONF_BOLIGTYPE, BOLIGTYPE_BOLIG)

        # Spotpris-sensor leverer eks. mva som default (HA-core nordpool).
        # Eldre konfig ble migrert til True i v3 for å bevare oppførsel.
        self.spotpris_inkl_mva = entry.data.get(CONF_SPOTPRIS_INKL_MVA, False)

        # Energiledd lagres i DSO som ren nettleie eks. mva og avgifter, og
        # hvor satsen kommer fra avgjøres av tariffmodusen (kontrakt §6), ikke
        # av om det tilfeldigvis ligger et tall på entryet. Den gamle regelen,
        # «lagret verdi vinner», var grunnen til at en satsoppdatering i dso.py
        # aldri nådde fram til noen som allerede hadde satt opp anlegget sitt.
        #
        # catalog og legacy_unconfirmed regner begge med katalogen. Bare manual
        # leser entryets egne tall, og heller ikke den på et nettselskap med
        # sesongperioder: der styrer periodene hele året, og en fast dag- og
        # nattsats gir ikke mening. At den ble ignorert er synlig i attributtet
        # `manual_ignorert` framfor å skje i stillhet.
        self.tariffmodus = les_tariffmodus(entry.data)
        raw_perioder: list[EnergileddPeriode] = self.dso.get("energiledd_perioder", [])
        self.sesong_styrer = bool(raw_perioder)
        self.manual_ignorert = self.tariffmodus == TARIFFMODUS_MANUAL and self.sesong_styrer

        katalog_dag_eks = float(self.dso["energiledd_dag_eks_mva"])
        katalog_natt_eks = float(self.dso["energiledd_natt_eks_mva"])
        if self.tariffmodus == TARIFFMODUS_MANUAL and not self.sesong_styrer:
            self.energiledd_dag_eks_mva = _som_sats(entry.data.get(CONF_ENERGILEDD_DAG), katalog_dag_eks)
            self.energiledd_natt_eks_mva = _som_sats(entry.data.get(CONF_ENERGILEDD_NATT), katalog_natt_eks)
        else:
            self.energiledd_dag_eks_mva = katalog_dag_eks
            self.energiledd_natt_eks_mva = katalog_natt_eks

        self.energiledd_dag = compute_energiledd_inkl_mva(self.energiledd_dag_eks_mva, self.avgiftssone)
        self.energiledd_natt = compute_energiledd_inkl_mva(self.energiledd_natt_eks_mva, self.avgiftssone)
        self._energiledd_perioder_eks = [
            (p["fra"], p["til"], float(p["dag_eks_mva"]), float(p["natt_eks_mva"])) for p in raw_perioder
        ]
        self._energiledd_perioder_inkl = [
            (
                fra,
                til,
                compute_energiledd_inkl_mva(dag, self.avgiftssone),
                compute_energiledd_inkl_mva(natt, self.avgiftssone),
            )
            for fra, til, dag, natt in self._energiledd_perioder_eks
        ]

        # Get kapasitetstrinn from DSO
        # Normalize: some DSOs (e.g. Barents Nett) use dict format {"min", "max", "pris"}
        # Convert to standard tuple format (kW_threshold, NOK_per_month)
        raw_trinn = self.dso["kapasitetstrinn"]
        if raw_trinn and isinstance(raw_trinn[0], dict):
            dict_trinn = cast("list[KapasitetstrinnDict]", raw_trinn)
            self.kapasitetstrinn = [(entry["max"], entry["pris"]) for entry in dict_trinn]
        else:
            self.kapasitetstrinn = cast("list[tuple[float, int]]", raw_trinn)

        # Egendefinert har ingen prisliste, så trinnene er brukerens egne eller
        # ingen. En ulesbar tabell behandles som ingen: config-flowen avviser
        # den, og et entry som likevel bærer en (håndredigert .storage) skal gi
        # ukjent fastledd, ikke halve trinn.
        egne_trinn = entry.data.get(CONF_EGENDEFINERT_KAPASITETSTRINN)
        if egne_trinn and dso_id == DSO_EGENDEFINERT:
            try:
                self.kapasitetstrinn = parse_kapasitetstrinn(str(egne_trinn))
            except ValueError:
                _LOGGER.warning(
                    "Kunne ikke lese egendefinerte kapasitetstrinn (%s). Fastleddet står som ukjent.",
                    egne_trinn,
                )
                self.kapasitetstrinn = []

        # Fastledd-metode. Nettselskap uten `fastledd_metode` bruker NVE-modellen
        # (snitt av tre døgnmakser) og er upåvirket av alt under.
        self.fastledd_metode = hent_fastledd_metode(self.dso)
        self.fastledd_lineaer = self.dso.get("fastledd_lineaer")
        self.fastledd_sesongfaktor = self.dso.get("fastledd_sesongfaktor", {})
        # Sikringsstørrelse er brukerdata og kan ikke leses av effektsensoren.
        # Tom verdi holdes som None, slik at manglende valg blir synlig i stedet
        # for å bli tolket som det billigste trinnet.
        sikring_raw = entry.data.get(CONF_SIKRINGSTRINN)
        self.sikringstrinn_valg = str(sikring_raw) if sikring_raw else None

        try:
            self.kapasitet_varsel_terskel = float(
                entry.data.get(CONF_KAPASITET_VARSEL_TERSKEL, DEFAULT_KAPASITET_VARSEL_TERSKEL)
            )
        except (ValueError, TypeError):
            self.kapasitet_varsel_terskel = float(DEFAULT_KAPASITET_VARSEL_TERSKEL)

        # Track max hourly average power for capacity calculation
        # Nettselskapet bruker maks timesforbruk (kWh/time = snitt-kW per
        # klokke-time), ikke instantan effekt. Timene kommer fra
        # avregningsboken, som er den eneste som vet hvilken time en
        # kilowattime hører til; her ligger bare toppen per dato.
        self._daily_max_power: dict[str, DailyMaxEntry] = {}
        # Ukestopper over løpende tolv måneder. Vedlikeholdes kun for
        # nettselskap som avregner årstopper; ellers ville 72 av 73 brukere
        # lagre data ingen leser.
        self._weekly_max_power: dict[str, WeeklyMaxEntry] = {}
        # Speil av det åpne intervallet, satt ved hver poll. Lagres fordi
        # Store-filen har båret den siden v1, og fordi diagnostikken viser den.
        self._current_hour_energy: float = 0.0
        self._current_hour: int = dt_util.now().hour
        self._current_month = dt_util.now().strftime("%Y-%m")

        # Track energy consumption for monthly utility meter
        self._monthly_consumption = ConsumptionData()
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._last_update = None
        # Baselinen vi måler energidelta fra, bundet til kilden sin.
        # None = ingen avlesning å måle fra ennå.
        self._baseline = None
        # Om den lagrede baselinen ble forkastet ved siste lasting. Eksponeres
        # til diagnostikken, slik at et uventet nullforbruk kan forklares.
        self._baseline_forkastet = False

        # Track previous month's data for invoice verification
        self._previous_month_consumption = ConsumptionData()
        self._previous_month_top_3: dict[str, DailyMaxEntry] = {}
        self._previous_month_name = None
        self._previous_month_norgespris_diff = 0.0
        self._previous_month_norgespris_compensation = 0.0
        self._previous_month_kapasitetsledd = 0
        self._previous_month_kapasitetstrinn = ""
        self._previous_month_energiledd_dag = self.energiledd_dag
        self._previous_month_energiledd_natt = self.energiledd_natt

        # Eksport-akkumulering (plusskunder med solceller)
        self._monthly_export_kwh = 0.0
        self._monthly_export_revenue = 0.0
        self._previous_month_export_kwh = 0.0
        self._previous_month_export_revenue = 0.0
        self._previous_month_cost = 0.0

        # Akkumulert kostnad for Energy Dashboard (stat_cost). Alt utenom
        # fastleddet bokføres per avregnet intervall; fastleddet er et
        # periodebeløp og regnes på nytt ved hver poll (kostnad.py).
        self._monthly_accumulated_cost_strom = 0.0
        self._monthly_stromstotte = 0.0
        self._monthly_energiledd_dag = 0.0
        self._monthly_energiledd_natt = 0.0
        self._monthly_avgifter = 0.0
        # Energiledd fra før oppgraderingen til intervallbokføring. Beløpet
        # finnes bare som én sum og lar seg ikke splitte i dag, natt og
        # avgifter i ettertid, så det bæres som en åpningsbalanse og faller
        # bort ved første månedsskifte.
        self._monthly_energiledd_apning = 0.0
        self._monthly_accumulated_cost_kapasitetsledd = 0.0

        # Daily cost accumulation
        self._daily_cost = 0.0
        self._current_date = dt_util.now().strftime("%Y-%m-%d")

        # Cache last known prices (survives brief sensor outages, max 2 timer)
        self._last_electricity_company_price: float | None = None
        self._last_electricity_company_price_time: datetime | None = None
        self._last_spot_price: float | None = None
        self._last_spot_price_time: datetime | None = None

        # Vakthold på input-sensorene. Per rolle: siste gang entiteten leverte et
        # tall. Utfallet måles fra det tidspunktet, ikke fra første poll som ser
        # feilen, slik at et hull mellom to polls ikke nullstiller klokken.
        try:
            terskel = float(entry.data.get(CONF_ENERGI_FROSSEN_TIMER, DEFAULT_ENERGI_FROSSEN_TIMER))
        except (ValueError, TypeError):
            terskel = DEFAULT_ENERGI_FROSSEN_TIMER
        if not math.isfinite(terskel):
            terskel = DEFAULT_ENERGI_FROSSEN_TIMER
        self.energi_frossen_terskel_timer = min(
            max(terskel, MIN_ENERGI_FROSSEN_TIMER), MAX_ENERGI_FROSSEN_TIMER
        )
        self._input_sist_gyldig = {}
        self._input_utfall_aktiv = set()
        # Siste typede resultat per rolle, fylt av _les_inputer ved hver poll.
        # Tomt før første poll, og da er det ingenting å rapportere ennå.
        self._input_resultater = {}
        self._input_sist_gyldig_avlest = {}
        # Varselet om prissensor uten enhet reises ved overgang, ikke ved hver
        # poll, og bare for de rollene som faktisk er ubekreftede nå.
        self._prisenhet_issue_aktiv = False
        self._prisenhet_issue_roller: list[str] = []
        self._prisenhet_issue_synket = False
        # Settes fra Store ved oppstart, ellers på første poll. None betyr
        # "vet ikke ennå", og da kan telleren ikke meldes frossen.
        self._last_energy_increase = None
        self._vakthold_issues = {}
        self._vakthold_issues_synket = False

        # Avregningsboken (L1). Den er eneste kilde til hvilken time en
        # kilowattime hører til, hvilken tariff den har og hvilken pris som
        # gjelder for den. Coordinatoren leser av den; den regner ikke det
        # samme selv ved siden av.
        self._tariffregel = Tariffregel(
            helg_som_natt=self._helg_som_natt,
            helligdager_ekstra=tuple(self._helligdager_ekstra),
        )
        self._bok = self._ny_bok()
        # Kronene hvert intervall alt har bidratt med, slik at et intervall som
        # får mer energi eller en ny prisrute bare bidrar med differansen. Uten
        # den ville en time blitt bokført på nytt ved hver poll.
        self._kr_bokfort: dict[datetime, Kroner] = {}
        # kWh hvert lukkede intervall alt er registrert i døgnmaks med, slik at
        # en forsinket avlesning inn i en ferdig time oppdaterer toppen, mens
        # en uendret time ikke regnes om ved hver poll.
        self._timesmaks_bokfort: dict[datetime, float] = {}

        # Persistent storage - keyed by entry_id for multi-instance isolation
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self._store_loaded = False

    def _ny_bok(self, raa: Any = None) -> Avregningsbok:
        """Bygg boken, eventuelt fra en lagret Store-fil (kontrakt D).

        En fil som ikke er et oppslagsverk i det hele tatt behandles som ingen
        fil. Det er samme regel som resten av lastingen følger: en ødelagt
        lagring gir standardverdier, ikke en exception i oppstarten.
        """
        return Avregningsbok.fra_lagring(
            raa if isinstance(raa, Mapping) else None,
            tariffregel=self._tariffregel,
            tariffmodus=self.tariffmodus,
            dso_id=self._dso_id,
        )

    def _input_entiteter(self) -> list[tuple[str, str | None]]:
        """(rolle, entity_id) for alle fem rollene, også de som ikke er satt."""
        return [
            (INPUT_ROLLE_EFFEKT, self.power_sensor),
            (INPUT_ROLLE_SPOTPRIS, self.spot_price_sensor),
            (INPUT_ROLLE_ENERGI, self.energy_sensor),
            (INPUT_ROLLE_EKSPORT, self.export_power_sensor),
            (INPUT_ROLLE_LEVERANDORPRIS, self.electricity_company_price_sensor),
        ]

    def _les_inputer(self, now: datetime) -> dict[str, Inputresultat]:
        """Les alle fem rollene én gang, gjennom adapteren.

        Alt i denne oppdateringen leser fra det samme oppslaget, slik at
        vaktholdet, beregningene og diagnostikken aldri ser hver sin poll.
        """
        resultater = {
            rolle: les_input(self.hass, entity_id, rolle, naa=now)
            for rolle, entity_id in self._input_entiteter()
        }
        self._input_resultater = resultater
        for rolle, resultat in resultater.items():
            if isinstance(resultat, Gyldig):
                self._input_sist_gyldig_avlest[rolle] = resultat.avlest_kl
        return resultater

    def _effekt_watt(self, rolle: str) -> float | None:
        """Watt fra en effektrolle, eller None når det ikke kom noen måling.

        None og ikke 0: en 0 er en måling som sier at anlegget ikke bruker noe,
        og det er en annen påstand enn at målingen uteble.

        Negative avlesninger klippes til 0. power_sensor er unidireksjonell
        import (OBIS 1.7.0), eksport går via export_power_sensor, så en negativ
        effektverdi er sensorstøy eller feilkonfig og skal ikke telle.

        Clampen mot MAX_POWER_CLAMP_W står igjen etter enhetsnormaliseringen
        fordi den fanger noe annet enn feil enhet: en sensor som leverer et tall
        ingen husinstallasjon kan produsere.
        """
        resultat = self._input_resultater.get(rolle)
        if not isinstance(resultat, Gyldig):
            return None
        verdi = resultat.verdi
        if verdi > MAX_POWER_CLAMP_W:
            _LOGGER.warning(
                "Sensor %s leser %s W, over grensen %s. Avvist.",
                resultat.entity_id,
                verdi,
                MAX_POWER_CLAMP_W,
            )
            return None
        return max(verdi, 0.0)

    def _avg_in_lower_tier(self, avg_power: float, threshold: float) -> bool:
        """Om avg_power hører til trinnet under denne terskelen."""
        return grunnlag_i_lavere_trinn(avg_power, threshold, self._terskel_inkludert)

    def _read_price_sensor(self, rolle: str) -> float | None:
        """Prisen i NOK/kWh for en prisrolle, eller None når den uteble.

        Cachen av forrige verdi ligger hos kalleren: den er til for
        prissensorene i denne integrasjonen, og et ikke-gyldig resultat skal
        aldri overskrive den.
        """
        resultat = self._input_resultater.get(rolle)
        return resultat.verdi if isinstance(resultat, Gyldig) else None

    def _kildeidentitet(self, entity_id: str) -> str:
        """Identiteten boken binder avlesningene sine til (kontrakt §5).

        `unique_id` er fasiten. Mangler den, er entity-id-en det eneste vi har,
        og den merkes som sådan slik at en sensor som senere får en unique_id
        blir en ny kilde og ikke en fortsettelse av den gamle. Det er samme
        regel som `Baseline.samme_kilde`, uttrykt som én streng fordi boken
        sammenligner identiteter og ikke kjenner fallbacken.
        """
        identitet = kildeidentitet(self.hass, entity_id)
        return identitet if identitet is not None else f"entity:{entity_id}"

    def _les_avlesning(
        self, now: datetime, effekt_kw: float | None, elapsed_hours: float
    ) -> Avlesning | None:
        """Gjør denne pollens input om til en avlesning boken kan ta imot (B1).

        Med energisensor er avlesningen tellerstanden med sensorens egen
        observasjonstid. Uten er den den syntetiske avlesningen i B1: energien
        i pollvinduet, med polltiden som observasjonstid og `estimert` som
        kvalitet. Stien velges av konfigurasjonen, aldri av tilstanden.
        """
        if self.energy_sensor:
            resultat = self._input_resultater.get(INPUT_ROLLE_ENERGI)
            if not isinstance(resultat, Gyldig) or resultat.verdi <= 0:
                # En teller på 0 er enten et blankt oppstartstall eller en
                # sensor som ikke har lest ennå. Begge duger dårlig som
                # baseline, og et ikke-gyldig resultat rører ingenting.
                return None
            return Avlesning(
                source_identity=self._kildeidentitet(self.energy_sensor),
                entity_id=self.energy_sensor,
                value_kwh=resultat.verdi,
                observed_at=_aware(resultat.observed_at),
            )
        if not self.power_sensor or effekt_kw is None:
            return None
        # Null energi er også en avlesning. Den første pollen har ikke noe
        # vindu bak seg, og uten en avlesning der ville boken stått uten
        # utgangspunkt og den neste pollen bokført null i stedet for vinduet
        # sitt. En effekt på null er dessuten en måling som sier at anlegget
        # ikke brukte noe, ikke at målingen uteble.
        energi = effekt_kw * elapsed_hours if elapsed_hours > 0 and effekt_kw > 0 else 0.0
        return Avlesning(
            source_identity=self._kildeidentitet(self.power_sensor),
            entity_id=self.power_sensor,
            value_kwh=energi,
            observed_at=_aware(now),
            kvalitet=Energikvalitet.ESTIMERT,
        )

    def _compute_energy_delta(self, now: datetime | None = None) -> float:
        """Bokfør energisensorens avlesning og gi kilowattimene som ble bokført.

        Fordelingen over avregningsintervallene, tariffen og prisen eies av
        `Avregningsbok` (docs/kontrakter/avregning.md). Her ligger bare det som
        hører Home Assistant til: logglinjene, repair-varselet og klokken
        vaktholdet måler frossen teller med.

        Baselinen er bundet til kilden sin (docs/kontrakter/input-og-konfig.md
        §5). Et målerbytte, altså en ny fysisk kilde, gir delta 0 og ny baseline
        med en gang; uten den bindingen ble en ny teller som sto på 1020 der den
        gamle sto på 1000 til 20 kWh falskt månedsforbruk.

        Et ikke-gyldig resultat rører ikke baselinen. Neste avlesning måler
        derfor fra den siste vi faktisk stolte på, ikke fra et hull.

        Et forkastet delta er ikke bare en loggelinje: det er kWh som forsvinner
        fra månedsforbruket, så det reises et fiksbart repair-varsel med tallet
        slik at brukeren kan korrigere mot fakturaen.
        """
        if not self.energy_sensor:
            return 0.0
        tidspunkt = now if now is not None else dt_util.now()
        avlesning = self._les_avlesning(tidspunkt, None, 0.0)
        if avlesning is None:
            return 0.0
        return self._bokfor(avlesning, tidspunkt).bokfort_kwh

    def _bokfor(self, avlesning: Avlesning, now: datetime) -> Bokforing:
        """Send avlesningen til boken og følg opp utfallet mot brukeren."""
        forrige = self._bok.sist_observert
        bokforing = self._bok.bokfor(avlesning)
        utfall = bokforing.utfall

        if utfall is Utfall.BASELINE and forrige is not None:
            # Kildeidentiteten er unique_id fra entity-registeret, og hos
            # AMS- og Elhub-integrasjoner er den målepunkt-ID eller
            # målerserienummer, altså noe som peker på én husstand.
            # home-assistant.log limes inn i offentlige issues like ofte som
            # diagnostikkdumpen, og dumpen aliaserer den nettopp derfor
            # (diagnostikk.py). Loggen sier at kilden er en annen, ikke hvilken.
            _LOGGER.info(
                "%s er en ny kilde. Ny baseline på %.3f kWh, delta 0.",
                avlesning.entity_id,
                avlesning.value_kwh,
            )
        elif utfall is Utfall.AVVIST_NEGATIV:
            _LOGGER.warning(
                "%s gikk nedover (%.3f -> %.3f). Counter reset? Ignorerer delta.",
                avlesning.entity_id,
                forrige.value_kwh if forrige else 0.0,
                avlesning.value_kwh,
            )
            self._meld_forkastet_delta(
                now, avlesning.value_kwh - (forrige.value_kwh if forrige else 0.0), forrige
            )
        elif utfall is Utfall.AVVIST_SPRANG:
            _LOGGER.warning(
                "%s delta %.1f kWh > %.0f kWh. Ignorerer som outlier.",
                avlesning.entity_id,
                bokforing.avvist_kwh,
                MAX_ENERGY_DELTA_KWH,
            )
            self._meld_forkastet_delta(now, bokforing.avvist_kwh, forrige)
        elif utfall is Utfall.AVVIST_FOR_LANGT_VINDU:
            _LOGGER.debug(
                "Pollvinduet var lengre enn %s timer. Estimert energi forkastet.",
                MAX_ELAPSED_HOURS,
            )

        if bokforing.bokfort_kwh > 0 and not avlesning.er_estimert:
            # Klokken vaktholdet måler frossen teller med. Den syntetiske stien
            # har ingen teller som kan fryse, så den skal ikke stille den.
            self._last_energy_increase = now
        self._speil_baseline()
        return bokforing

    def _fores_av_boken(self) -> bool:
        """Om boken fører den måneden coordinatoren viser.

        Boken rullerer på observasjonstid og coordinatoren på klokken, så de
        kan stå et øyeblikk fra hverandre. I det vinduet er bokens summer en
        annen måneds og skal ikke legges til.
        """
        return self._bok.aktiv_maned in (None, self._current_month)

    def _aapningsbalanse(self) -> ConsumptionData:
        """Månedsforbruket som ikke ligger i boken (kontrakt D).

        Etter migreringen fra v2 er det gamle månedssummer uten
        intervallhistorikk, og etter et månedsskifte er det null. Den regnes ut
        av differansen framfor å bæres som et eget lagret tall, så den kan ikke
        drifte fra boken.
        """
        if not self._fores_av_boken():
            return self._monthly_consumption.copy()
        sum_ = self._bok.maanedssum()
        return ConsumptionData(
            dag=self._monthly_consumption.dag - sum_.kwh_dag,
            natt=self._monthly_consumption.natt - sum_.kwh_natt,
        )

    def _forbruk_fra_boken(self, naa: datetime, balanse: ConsumptionData) -> ConsumptionData:
        """Åpningsbalansen pluss bokens egne intervaller for måneden."""
        if not self._fores_av_boken():
            return balanse.copy()
        sum_ = self._bok.maanedssum(_aware(naa))
        return ConsumptionData(dag=balanse.dag + sum_.kwh_dag, natt=balanse.natt + sum_.kwh_natt)

    def _del_ved_maanedsskifte(self, avlesning: Avlesning | None) -> list[Avlesning]:
        """Del en avlesning som krysser en fakturamåned ved grensen.

        Boken deler vinduet selv når den bokfører (C6), men den arkiverer den
        gamle måneden i samme kall, og da er intervallene borte før kronene for
        dem er gjort opp. Deles avlesningen her, er den gamle måneden ferdig
        bokført når arkiveringen skjer.

        Delingen er ren interpolasjon i tid, den samme `fordel_delta` gjør, så
        to deler gir nøyaktig samme fordeling som én.
        """
        if avlesning is None:
            return []
        forrige = self._bok.sist_observert
        if forrige is None or forrige.source_identity != avlesning.source_identity:
            return [avlesning]
        fra, til = forrige.observed_at, avlesning.observed_at
        if til <= fra or lokal_maned(fra) == lokal_maned(til):
            return [avlesning]
        delta = avlesning.value_kwh if avlesning.er_estimert else avlesning.value_kwh - forrige.value_kwh
        if delta < 0 or delta > MAX_ENERGY_DELTA_KWH:
            # Et sprang eller et målerbytte avvises i sin helhet. Delt i to
            # kunne hver halvdel sluppet under grensen, og da ville avvisningen
            # avhengt av hvor i måneden spranget lå.
            return [avlesning]

        deler: list[Avlesning] = []
        forrige_tid, forrige_verdi = fra, forrige.value_kwh
        for grense in self._maanedsgrenser(fra, til):
            andel = (grense.timestamp() - forrige_tid.timestamp()) / (til.timestamp() - fra.timestamp())
            verdi = delta * andel if avlesning.er_estimert else forrige_verdi + delta * andel
            deler.append(replace(avlesning, value_kwh=verdi, observed_at=grense))
            forrige_tid, forrige_verdi = grense, verdi
        if avlesning.er_estimert:
            rest = delta * (til.timestamp() - forrige_tid.timestamp()) / (til.timestamp() - fra.timestamp())
            deler.append(replace(avlesning, value_kwh=rest))
        else:
            deler.append(avlesning)
        return deler

    @staticmethod
    def _maanedsgrenser(fra: datetime, til: datetime) -> list[datetime]:
        """Fakturamånedenes startpunkt i UTC, strengt mellom `fra` og `til`."""
        grenser: list[datetime] = []
        aar, mnd = (int(del_) for del_ in lokal_maned(fra).split("-"))
        while True:
            aar, mnd = (aar + 1, 1) if mnd == 12 else (aar, mnd + 1)
            grense = datetime(aar, mnd, 1, tzinfo=OSLO).astimezone(UTC)
            if grense >= til:
                return grenser
            if grense > fra:
                grenser.append(grense)

    @property
    def _monthly_accumulated_cost_energiledd(self) -> float:
        """Nettleiens energidel denne måneden, med forbruksavgift og Enova.

        Feltet `monthly_accumulated_cost_energiledd_kr` har alltid ment dette,
        og dommen over K3 hadde rett i at navnet er upresist: satsen som ganges
        er hele `total_nettleie_price`, ikke energileddet alene. Navnet står
        likevel, for brukerne har langtidsstatistikk på sensoren, og et bytte av
        betydning ville rettet navnet og ødelagt tallrekken i samme slengen.
        Splitten ligger i stedet ved siden av som `monthly_energiledd_dag_kr`,
        `monthly_energiledd_natt_kr` og `monthly_avgifter_kr`, som summerer
        nøyaktig hit. Et nytt navn hører til L3c, der sensorattributtene skrives
        om i samme endring.
        """
        return (
            self._monthly_energiledd_dag
            + self._monthly_energiledd_natt
            + self._monthly_avgifter
            + self._monthly_energiledd_apning
        )

    @property
    def _monthly_accumulated_cost(self) -> float:
        """Månedens kostnad: alt som følger energien, pluss fastleddet.

        Én akkumulator, ikke to. `monthly_cost_kr` og
        `monthly_accumulated_cost_kr` var to veier til samme tall og kunne
        svare ulikt; nå er de det samme tallet (33f81xu).
        """
        return (
            self._monthly_accumulated_cost_strom
            + self._monthly_accumulated_cost_energiledd
            + self._monthly_accumulated_cost_kapasitetsledd
        )

    @property
    def _monthly_cost(self) -> float:
        """Samme tall som `_monthly_accumulated_cost`, med det gamle navnet."""
        return self._monthly_accumulated_cost

    def _satser(self, intervall: AvregnetIntervall) -> Satser:
        """Satsene som gjaldt i et avregnet intervall.

        Sesongsatsene slås opp på intervallets egen start, ikke på klokken
        pollen står på, og tariffen kommer fra intervallet (C2.4).
        """
        lokal = intervall.start_utc.astimezone(OSLO)
        dag_sats, natt_sats = self._get_aktive_energileddsatser(lokal)
        mva = get_mva_sats(self.avgiftssone)
        return Satser(
            energiledd_inkl_mva=dag_sats if intervall.tariff is Tariff.DAG else natt_sats,
            avgifter_inkl_mva=(get_forbruksavgift(self.avgiftssone) + ENOVA_AVGIFT) * (1 + mva),
            mva_sats=mva,
            norgespris_inkl_mva=get_norgespris_inkl_mva(self.avgiftssone),
            stromstotte_terskel=get_stromstotte_terskel(self.avgiftssone),
            stromstotte_max_kwh=get_stromstotte_max_kwh(self.boligtype),
            norgespris_max_kwh=get_norgespris_max_kwh(self.boligtype),
            har_norgespris=self.har_norgespris,
        )

    def _kwh_fra_og_med(self, naa: datetime, starter: set[datetime]) -> dict[datetime, float]:
        """kWh i boken fra og med hvert av intervallene i `starter`.

        Tak-splitten trenger å vite hvor mye måneden hadde bak seg da et
        intervall begynte. Månedstotalen er kjent (den bærer også
        åpningsbalansen fra en migrering), og det som ligger foran et intervall
        er totalen minus det som ligger fra og med det.
        """
        if not starter:
            return {}
        tidligst = min(starter)
        etter: dict[datetime, float] = {}
        lopende = 0.0
        for intervall in reversed(self._bok.intervaller(naa)):
            if intervall.start_utc < tidligst:
                break
            lopende += intervall.kwh
            etter[intervall.start_utc] = lopende
        return etter

    def _akkumuler_kroner(self, now: datetime, berorte: Iterable[datetime] = ()) -> None:
        """Bokfør kronene for intervallene denne pollen rørte (C2.4).

        Intervallene regnes opp på nytt, og bare differansen mot det de alt har
        bidratt med legges til. Det er det som gjør at en time som får sin
        fjerde prisrute, eller mer energi etter at den er lukket, ender på
        riktig beløp uten å bli talt to ganger.

        Fastleddet er ikke med. Det er et periodebeløp og regnes av tiden, ikke
        av kilowattimene.
        """
        if not self._fores_av_boken():
            return
        naa = _aware(now)
        starter = set(berorte)
        starter.add(intervallstart(naa))
        etter = self._kwh_fra_og_med(naa, starter)
        total = self._monthly_consumption.total
        for start in sorted(starter):
            intervall = self._bok.intervall(start, naa)
            if intervall is None or intervall.lokal_maned != self._current_month:
                continue
            kwh_for = max(0.0, total - etter.get(start, intervall.kwh))
            nye = kroner_for_intervall(intervall, self._satser(intervall), kwh_for=kwh_for)
            self._legg_til_kroner(nye - self._kr_bokfort.get(start, INGEN_KRONER), lokal_dato(start))
            self._kr_bokfort[start] = nye

    def _legg_til_kroner(self, diff: Kroner, dato: str) -> None:
        """Legg en differanse inn i månedens og dagens bøker."""
        self._monthly_accumulated_cost_strom += diff.strom_kr
        self._monthly_stromstotte += diff.stromstotte_kr
        self._monthly_energiledd_dag += diff.energiledd_dag_kr
        self._monthly_energiledd_natt += diff.energiledd_natt_kr
        self._monthly_avgifter += diff.avgifter_kr
        self._monthly_norgespris_compensation += diff.norgespris_kompensasjon_kr
        self._monthly_norgespris_diff += diff.norgespris_differanse_kr
        if dato == self._current_date:
            # Dagsboken er de samme intervallene, avgrenset av intervallets egen
            # lokale dato. En time som får mer energi i morgen hører fortsatt til
            # i går, og skal ikke dukke opp i morgendagens tall.
            self._daily_cost += diff.energi_kr

    def _oppdater_fastledd(self, now: datetime, kapasitetsledd: int) -> None:
        """Fastleddet som periodebeløp: kr/mnd ganger forløpt andel av måneden.

        Regnet på nytt ved hver poll framfor å summeres opp av små tidsbiter.
        To ting følger av det. Et trinnskifte midt i måneden gjelder hele
        måneden, slik nettselskapet fakturerer, i stedet for å tidsvekte det
        gamle og det nye trinnet mot hverandre. Og en Egendefinert-bruker som
        fyller inn trinntabellen den 20. får hele månedens forløpte andel med en
        gang, i stedet for et stille hull for de nitten dagene før (K3, funn 5).

        Andelen måles i absolutt tid, så mars og oktober er ikke
        spesialtilfeller (3jebp9g).
        """
        belop = None if self._fastledd_ukjent() or self._mangler_sikringsvalg() else kapasitetsledd
        self._monthly_accumulated_cost_kapasitetsledd = fastledd_belop(
            belop, forlopt_andel_av_maaned(_aware(now))
        )

    def _oppdater_fastledd_helmaaned(self, kapasitetsledd: int) -> None:
        """Sett fastleddet til hele månedens beløp, for måneden som lukkes.

        Nettselskapet fakturerer sluttrinnet for hele fakturamåneden, så det er
        det tallet som arkiveres, ikke andelen som var forløpt da siste poll
        kom inn.
        """
        belop = None if self._fastledd_ukjent() or self._mangler_sikringsvalg() else kapasitetsledd
        self._monthly_accumulated_cost_kapasitetsledd = fastledd_belop(belop, 1.0)

    def _fastledd_i_dag(self, now: datetime, kapasitetsledd: int) -> float:
        """Dagens andel av månedens fastledd, i kroner."""
        belop = None if self._fastledd_ukjent() or self._mangler_sikringsvalg() else kapasitetsledd
        naa = _aware(now)
        return fastledd_belop(belop, andel_av_maaned(sekunder_forlopt_i_dogn(naa), naa))

    def _oppdater_timesmaks(self, now: datetime) -> bool:
        """Skriv bokens lukkede intervaller til døgnmaks. True hvis noe endret seg.

        Dette erstatter veggklokke-bøtten som `_current_hour_energy` var.
        Intervallene er de samme timene, men de kommer fra boken, så de er de
        samme kilowattimene som avregningen bruker og de er UTC-forankret.
        Sommertidsskiftene trenger derfor ingen egen kode her: timen som finnes
        to ganger er to intervaller, og timen som ikke finnes er ingen.

        `current_hour_energy` speiles fra det åpne intervallet, slik
        felttabellen sier den skal være.
        """
        naa = _aware(now)
        apen = intervallstart(naa)
        endret = False
        for intervall in self._bok.intervaller(naa):
            start = intervall.start_utc
            if start >= apen or intervall.kwh <= 0:
                continue
            if self._timesmaks_bokfort.get(start) == intervall.kwh:
                continue
            self._timesmaks_bokfort[start] = intervall.kwh
            if self._registrer_timesmaks(lokal_dato(start), intervall.kwh, lokal_time(start)):
                endret = True
        apent = self._bok.intervall(apen, naa)
        self._current_hour_energy = apent.kwh if apent is not None else 0.0
        return endret

    def _speil_baseline(self) -> None:
        """Skriv bokens siste observasjon til v2-baselinen Store-filen bærer.

        Boken er kilden (kontrakt C5). `energi_baseline` står igjen fordi en
        nedgradering til 1.17 skal finne den der den lå, og fordi
        diagnostikken viser den.
        """
        siste = self._bok.sist_observert
        if siste is None or siste.er_estimert:
            self._baseline = None
            return
        identitet = siste.source_identity
        self._baseline = Baseline(
            source_identity=None if identitet.startswith("entity:") else identitet,
            entity_id=siste.entity_id,
            value_kwh=siste.value_kwh,
            observed_at=siste.observed_at,
        )

    def _meld_forkastet_delta(
        self, now: datetime, raw_delta: float, forrige_avlesning: Avlesning | None = None
    ) -> None:
        """Reis et fiksbart repair-varsel om kWh som ble kastet.

        Fiksbart fordi det eneste som skal skje er at brukeren ser tallet og
        bekrefter; integrasjonen kan ikke gjenskape forbruket selv.

        `forrige` er tidspunktet for avlesningen spranget måles fra. Det er
        sjelden forrige poll: hovedtilfellet er comebacket etter et langt
        utfall, der telleren sto på samme tall i flere døgn hos oss mens
        måleren gikk videre.
        """
        baselinetid = _som_lokal(forrige_avlesning.observed_at) if forrige_avlesning else None
        forrige = baselinetid or self._last_update or now
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"energi_delta_forkastet_{self.entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="energi_delta_forkastet",
            translation_placeholders={
                "sensor": self.energy_sensor or "",
                "kwh": f"{raw_delta:.1f}",
                "forrige": forrige.strftime("%d.%m.%Y kl. %H:%M"),
            },
        )

    # ------------------------------------------------------------------
    # Vakthold på input-sensorene
    #
    # Bakgrunn: HAN-leseren lå nede 237 timer sommeren 2026 mens integrasjonen
    # rapporterte videre som om ingenting var galt, og det ble oppdaget ti dager
    # for sent. Tre deteksjoner dekker de tre måtene input dør på: entiteten
    # forsvinner, telleren fryser mens entiteten ser frisk ut, og prisen blir
    # for gammel til å regne kostnad av.
    # ------------------------------------------------------------------

    def _konfigurerte_inputer(self) -> list[tuple[str, str]]:
        """(rolle, entity_id) for hver input brukeren faktisk har satt opp."""
        return [(rolle, eid) for rolle, eid in self._input_entiteter() if eid]

    def _input_er_gyldig(self, rolle: str) -> bool:
        """Om rollen leverte et tall vi kan regne på i denne oppdateringen.

        Manglende entitet, unavailable/unknown, uleselige verdier og enheter vi
        ikke kan regne om er samme sak for utfalls-deteksjonen: det kommer ingen
        brukbar måling inn. Enhetsfeil får i tillegg sitt eget problem, siden en
        sensor som bytter enhet under drift er noe annet enn et utfall.
        """
        return isinstance(self._input_resultater.get(rolle), Gyldig)

    @staticmethod
    def _vakthold_problem(
        type_: str,
        rolle: str,
        entity_id: str,
        siden: datetime,
        now: datetime,
        *,
        resultat: Inputresultat | None = None,
    ) -> dict[str, Any]:
        """Én rad i data["input_problemer"].

        `finnes` skiller en slettet entitet fra en som svarer unavailable. De to
        krever hver sin handling av brukeren: den ene er en entitet som er borte
        fra HA, den andre en integrasjon som ikke leverer.
        """
        minutter = max(0, int(sekunder_mellom(siden, now) // 60))
        grunn = getattr(resultat, "grunn", None)
        return {
            "type": type_,
            "input": rolle,
            "entity_id": entity_id,
            "siden": siden.isoformat(),
            "minutter": minutter,
            "timer": round(minutter / 60, 1),
            "finnes": grunn != GRUNN_FINNES_IKKE,
            "grunn": grunn,
            "raa_enhet": getattr(resultat, "raa_enhet", None),
        }

    def _oppdater_vakthold(self, now: datetime, *, spot_price_valid: bool) -> list[dict[str, Any]]:
        """Vurder alle inputene og returner de aktive problemene.

        Rekkefølgen er stabil (utfall før frossen før spot) slik at attributtene
        ikke blafrer mellom polls.
        """
        grace_sekunder = INPUT_UTFALL_GRACE_MINUTTER * 60
        problemer: list[dict[str, Any]] = []
        gyldig_naa: dict[str, bool] = {}

        for rolle, entity_id in self._konfigurerte_inputer():
            resultat = self._input_resultater.get(rolle)
            gyldig = isinstance(resultat, Gyldig)
            gyldig_naa[rolle] = gyldig
            if gyldig:
                self._input_sist_gyldig[rolle] = now
                if rolle in self._input_utfall_aktiv:
                    self._input_utfall_aktiv.discard(rolle)
                    if rolle == INPUT_ROLLE_ENERGI:
                        # Telleren gikk sin gang mens vi var blinde. Det vi
                        # mistet er alt meldt som utfall, og et sprang som blir
                        # forkastet melder seg selv, så frossen-klokken starter
                        # på nytt her framfor å fyre i det sensoren er tilbake.
                        self._last_energy_increase = now
                continue
            siden = self._input_sist_gyldig.setdefault(rolle, now)
            if isinstance(resultat, Ugyldig) and resultat.grunn in ENHETSGRUNNER:
                # Ingen grace: dette er ikke et utfall som går over av seg selv,
                # det er en sensor som leverer noe vi ikke har lov til å regne
                # på, og hvert minutt den står slik er et minutt uten tall.
                problemer.append(
                    self._vakthold_problem(VAKTHOLD_ENHET, rolle, entity_id, siden, now, resultat=resultat)
                )
                continue
            if rolle == INPUT_ROLLE_LEVERANDORPRIS:
                # Leverandørprisen mater bare sammenligningssensoren, så et
                # utfall der rapporteres som attributt og hever ikke vaktholdet.
                # Enhetsgrenen over gjelder likevel: kontrakt §1 sier at en
                # sensor som bytter enhet under drift er en ekte feil i alle
                # roller, og uten den ville en leverandørpris som gikk til
                # EUR/kWh bare blitt stille.
                continue
            if sekunder_mellom(siden, now) > grace_sekunder:
                self._input_utfall_aktiv.add(rolle)
                problemer.append(
                    self._vakthold_problem(VAKTHOLD_UTFALL, rolle, entity_id, siden, now, resultat=resultat)
                )

        # Rangering, slik at én årsak gir ett varsel: står energisensoren selv i
        # utfall, eier utfalls-deteksjonen hendelsen. Frossen-teksten sier at
        # sensoren rapporterer men telleren står stille, og det er usant når
        # sensoren er borte.
        if self.energy_sensor and gyldig_naa.get(INPUT_ROLLE_ENERGI, False):
            if self._last_energy_increase is None:
                # Fersk installasjon, eller lagret verdi som manglet: start
                # klokken nå framfor å melde frossen på null grunnlag.
                self._last_energy_increase = now
            elif sekunder_mellom(self._last_energy_increase, now) > self.energi_frossen_terskel_timer * 3600:
                problemer.append(
                    self._vakthold_problem(
                        VAKTHOLD_FROSSEN,
                        INPUT_ROLLE_ENERGI,
                        self.energy_sensor,
                        self._last_energy_increase,
                        now,
                        resultat=self._input_resultater.get(INPUT_ROLLE_ENERGI),
                    )
                )

        if not spot_price_valid and self.spot_price_sensor:
            siden = self._input_sist_gyldig.setdefault(INPUT_ROLLE_SPOTPRIS, now)
            # Samme grace som de andre inputene. Cachen er in-memory, så ved
            # første poll etter en HA-omstart er den tom mens Nord Pool ennå
            # ikke har levert. Uten grace varsler vi hver eneste omstart.
            if sekunder_mellom(siden, now) > grace_sekunder:
                problemer.append(
                    self._vakthold_problem(
                        VAKTHOLD_SPOT_UTLOPT,
                        INPUT_ROLLE_SPOTPRIS,
                        self.spot_price_sensor,
                        siden,
                        now,
                        resultat=self._input_resultater.get(INPUT_ROLLE_SPOTPRIS),
                    )
                )
                # Samme rangering igjen: spot_utlopt sier alt utfallet sier, og
                # i tillegg at kostnaden har sluttet å akkumulere.
                problemer = [
                    p
                    for p in problemer
                    if not (p["type"] == VAKTHOLD_UTFALL and p["input"] == INPUT_ROLLE_SPOTPRIS)
                ]

        self._oppdater_vakthold_issues(problemer)
        return problemer

    @staticmethod
    def _vakthold_plassholdere(type_: str, rader: list[dict[str, Any]]) -> dict[str, str]:
        """Teksten varselet vises med, bygget av alle radene av samme sort.

        Ett varsel dekker alle inputene som er nede av samme grunn, så teksten
        må bygges av hele listen. Ble den bygget av den første raden alene,
        sto det effektmåleren i varselet mens det var energimåleren som lå
        nede, og brukeren feilsøkte en sensor som var frisk.

        Rollenavnene er norske også i den engelske teksten, slik `_ROLLE_TEKST`
        alt er. Tallene og enhetene står uten ord i `detaljer`, nettopp fordi
        ordet rundt dem hører hjemme i malen som faktisk oversettes.
        """
        varigheter = [_vakthold_varighet(float(rad["timer"])) for rad in rader]
        enheter = [str(rad.get("raa_enhet") or "uten enhet") for rad in rader]
        verdier = enheter if type_ == VAKTHOLD_ENHET else varigheter
        detaljer = "\n".join(
            f"- {_ROLLE_TEKST.get(rad['input'], rad['input'])} ({rad['entity_id']}): {verdi}"
            for rad, verdi in zip(rader, verdier, strict=True)
        )
        return {
            "input": ", ".join(_ROLLE_TEKST.get(rad["input"], rad["input"]) for rad in rader),
            "entity_id": ", ".join(str(rad["entity_id"]) for rad in rader),
            "timer": _vakthold_varighet(max(float(rad["timer"]) for rad in rader)),
            "enhet": enheter[0],
            "detaljer": detaljer,
        }

    def _oppdater_vakthold_issues(self, problemer: list[dict[str, Any]]) -> None:
        """Hold ett varsel per sort i takt med inputene som faktisk er nede.

        Varselet skrives om når innholdet endrer seg, ikke ved hver poll. Er to
        sensorer nede og den ene frisker til, skal teksten slutte å peke på
        den, men et uendret utfall skal ikke skrive i issue-registeret hvert
        minutt. Varselet forsvinner først når ingen rader av sorten står igjen.
        """
        rader_per_sort: dict[str, list[dict[str, Any]]] = {}
        for problem in problemer:
            rader_per_sort.setdefault(str(problem["type"]), []).append(problem)

        for type_, prefix in _VAKTHOLD_ISSUE_PREFIX.items():
            issue_id = f"{prefix}_{self.entry.entry_id}"
            rader = rader_per_sort.get(type_)
            if rader:
                plassholdere = self._vakthold_plassholdere(type_, rader)
                if self._vakthold_issues.get(type_) == plassholdere:
                    continue
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    issue_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=f"vakthold_{type_}",
                    translation_placeholders=plassholdere,
                )
                self._vakthold_issues[type_] = plassholdere
            elif type_ in self._vakthold_issues or not self._vakthold_issues_synket:
                # Første poll rydder også issues som overlevde en omstart.
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                self._vakthold_issues.pop(type_, None)
        self._vakthold_issues_synket = True

    async def _handle_month_rollover(self, now: datetime) -> None:
        """Archive previous month's data and reset accumulators."""
        prev_month_date = now.replace(day=1) - timedelta(days=1)
        expected_prev = prev_month_date.strftime("%Y-%m")

        # Multi-måned gap: hvis lagret måned er eldre enn forrige måned
        # (f.eks. HA var nede i flere måneder), er dataen foreldet.
        # Nullstill forrige-måned i stedet for å arkivere gammel data med feil label.
        is_multi_month_gap = self._current_month < expected_prev

        if is_multi_month_gap:
            _LOGGER.warning(
                "Multi-måned gap: lagret måned %s, forventet %s. Nullstiller forrige-måned-data.",
                self._current_month,
                expected_prev,
            )
            self._previous_month_consumption = ConsumptionData()
            self._previous_month_name = None
            self._previous_month_norgespris_diff = 0.0
            self._previous_month_norgespris_compensation = 0.0
            self._previous_month_export_kwh = 0.0
            self._previous_month_export_revenue = 0.0
            self._previous_month_cost = 0.0
            self._previous_month_top_3 = {}
            self._previous_month_kapasitetsledd = 0
            self._previous_month_kapasitetstrinn = ""
        else:
            self._previous_month_consumption = self._monthly_consumption.copy()
            self._previous_month_name = self._format_month_name(prev_month_date)
            self._previous_month_norgespris_diff = self._monthly_norgespris_diff
            self._previous_month_norgespris_compensation = self._monthly_norgespris_compensation
            self._previous_month_export_kwh = self._monthly_export_kwh
            self._previous_month_export_revenue = self._monthly_export_revenue
            # Timene i måneden er alt skrevet til døgnmaks fra boken, også den
            # siste: `_oppdater_timesmaks` kjører inne i bokføringen, før boken
            # arkiverer måneden.

            # Compute kapasitetsledd for previous month before reset
            prev_top_3 = self._get_top_3_days()
            self._previous_month_top_3 = prev_top_3
            # TRE_DØGNMAX_MND, MND_MAX og UKJENT leser bare inneværende måned, så
            # uten målinger finnes det ikke noe grunnlag å arkivere. OV_TREFASE og
            # FEM_VEKTET_ÅR har et beløp uansett (sikringsstørrelse, grunnbeløp).
            if not prev_top_3 and self.fastledd_metode in FASTLEDD_TRINNBASERTE:
                self._previous_month_kapasitetsledd = 0
                self._previous_month_kapasitetstrinn = ""
            else:
                prev_kap, _, prev_trinn = self._get_kapasitetsledd(self._fastledd_grunnlag())
                self._previous_month_kapasitetsledd = prev_kap
                self._previous_month_kapasitetstrinn = prev_trinn

            # Måneden som lukkes fakturerer sluttrinnet for hele måneden, ikke
            # en tidsvektet blanding av trinnene den var innom. Fastleddet
            # settes til fullt beløp før kostnaden arkiveres.
            self._oppdater_fastledd_helmaaned(self._previous_month_kapasitetsledd)
            self._previous_month_cost = self._monthly_cost

        # Archive energiledd rates for accurate previous-month calculations.
        # For sesong-DSO-er bruker vi forrige måneds siste dag (now - 1 dag) for å fange
        # satsen som faktisk gjaldt mesteparten av forrige måned. Eksempel: rollover
        # 1. juli kl 00:00: vi vil ha juni-satsen, ikke juli-satsen.
        forrige_dag = now - timedelta(days=1)
        forrige_dag_dag, forrige_dag_natt = self._get_aktive_energileddsatser(forrige_dag)
        self._previous_month_energiledd_dag = forrige_dag_dag
        self._previous_month_energiledd_natt = forrige_dag_natt

        # Reset current month data. _weekly_max_power står bevisst igjen: det er
        # et rullerende tolvmånedersvindu og hører ikke til kalendermåneden.
        self._daily_max_power = {}
        self._timesmaks_bokfort = {}
        self._current_hour_energy = 0.0
        self._current_hour = now.hour
        self._monthly_consumption = ConsumptionData()
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._kr_bokfort = {}
        self._monthly_export_kwh = 0.0
        self._monthly_export_revenue = 0.0
        self._monthly_accumulated_cost_strom = 0.0
        self._monthly_stromstotte = 0.0
        self._monthly_energiledd_dag = 0.0
        self._monthly_energiledd_natt = 0.0
        self._monthly_avgifter = 0.0
        self._monthly_energiledd_apning = 0.0
        self._monthly_accumulated_cost_kapasitetsledd = 0.0
        self._current_month = now.strftime("%Y-%m")
        await self._save_stored_data()

    @staticmethod
    def _calculate_stromstotte(
        spot_price: float,
        monthly_total_kwh: float,
        boligtype: str,
        terskel: float = STROMSTOTTE_LEVEL,
    ) -> float:
        """Calculate strømstøtte per kWh.

        Forskrift § 5: 90 % av spotpris over terskel. Terskelen er sonebevisst
        (se get_stromstotte_terskel / incident 005): 96,25 øre inkl. mva i
        standard-sonen, 77 øre i mva-frie soner. Default holdes på standard-sonens
        verdi for bakoverkompatible kall. Norgespris-kunder mottar ikke
        strømstøtte, men vi beregner den alltid slik at sammenligning mellom
        Norgespris og spot+støtte fungerer.
        """
        stromstotte_max = get_stromstotte_max_kwh(boligtype)
        if stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max:
            return 0.0
        if spot_price > terskel:
            return (spot_price - terskel) * STROMSTOTTE_RATE
        return 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate values."""
        now = dt_util.now()

        # Load stored data on first run
        if not self._store_loaded:
            await self._load_stored_data()
            self._store_loaded = True

        # Alle fem rollene leses én gang, gjennom adapteren, og resten av
        # oppdateringen ser bare normaliserte verdier.
        #
        # En manglende entitet kaster ikke lenger UpdateFailed. Den feilet hele
        # oppdateringen før vaktholdet hadde sagt fra, og stoppet samtidig
        # energi og energiledd som ikke trengte den sensoren i det hele tatt.
        # Nå melder vaktholdet utfallet, og alt som fortsatt har datagrunnlag
        # regnes videre.
        self._les_inputer(now)
        self._meld_prisenhet_ubekreftet()

        current_power_w = self._effekt_watt(INPUT_ROLLE_EFFEKT)
        current_power_kw = current_power_w / 1000 if current_power_w is not None else None

        # Tid siden forrige oppdatering (felles for forbruk og eksport). Målt i
        # absolutt tid: en rett subtraksjon av to tidspunkt med samme
        # tzinfo-objekt måler veggklokke, og da blir ett ekte minutt til seks
        # ved vår-DST og til null ved høst-DST (3jebp9g).
        elapsed_hours = 0.0
        if self._last_update is not None:
            elapsed_hours = sekunder_mellom(self._last_update, now) / 3600
            elapsed_hours = max(0.0, min(elapsed_hours, MAX_ELAPSED_HOURS))

        # Prisen leses før energien bokføres, slik at prisprøven for ruten vi
        # står i er registrert når intervallet leses av.
        #
        # Visningscachen er visningens, ikke avregningens: `spot_price` under
        # kan være inntil to timer gammel, mens boken bare får prøver som
        # faktisk kom inn denne pollen. En time uten prøve blir `uten_pris` og
        # telles i `kwh_uten_pris`, den får ikke naboens pris (C2.5, C4).
        mva_sats_for_spot = get_mva_sats(self.avgiftssone)
        raw_spot = self._read_price_sensor(INPUT_ROLLE_SPOTPRIS)
        if raw_spot is not None:
            prove_eks_mva = (
                raw_spot / (1 + mva_sats_for_spot)
                if self.spotpris_inkl_mva and mva_sats_for_spot > 0
                else raw_spot
            )
            self._bok.registrer_prisprove(_aware(now), prove_eks_mva)
            spot_price_raw = raw_spot
            self._last_spot_price = spot_price_raw
            self._last_spot_price_time = now
            spot_price_valid = True
        elif (
            self._last_spot_price is not None
            and self._last_spot_price_time is not None
            and sekunder_mellom(self._last_spot_price_time, now) < _SPOT_CACHE_MAX_AGE.total_seconds()
        ):
            spot_price_raw = self._last_spot_price
            spot_price_valid = True
        else:
            spot_price_raw = 0.0
            spot_price_valid = False

        # Normaliser til inkl. mva. Resten av kjeden behandler spot_price som inkl. mva,
        # samme enhet som STROMSTOTTE_LEVEL og NORGESPRIS_INKL_MVA. Se incident 004.
        if self.spotpris_inkl_mva:
            spot_price = spot_price_raw
            spot_price_eks_mva = (
                spot_price_raw / (1 + mva_sats_for_spot) if mva_sats_for_spot > 0 else spot_price_raw
            )
        else:
            spot_price_eks_mva = spot_price_raw
            spot_price = spot_price_raw * (1 + mva_sats_for_spot)

        # Dagsboken nullstilles før energien bokføres. Skjedde det etterpå,
        # ville timen etter midnatt blitt bokført mot gårsdagens dato og så
        # strøket av nullstillingen.
        today_str = now.strftime("%Y-%m-%d")
        if today_str != self._current_date:
            self._daily_cost = 0.0
            self._current_date = today_str

        # Akkumuler energi FØRST, slik at siste syklus havner i riktig måned.
        # Avlesningen går i boken, som fordeler den over avregningsintervallene
        # etter observasjonstid (C1). Tariffen kommer fra intervallets egen
        # start, ikke fra klokken pollen står på.
        dirty = False
        energy_kwh = 0.0
        berorte: set[datetime] = set()
        aapningsbalanse = self._aapningsbalanse()
        avlesning = self._les_avlesning(now, current_power_kw, elapsed_hours)
        for del_avlesning in self._del_ved_maanedsskifte(avlesning):
            bokforing = self._bokfor(del_avlesning, now)
            energy_kwh += bokforing.bokfort_kwh
            if bokforing.bokfort_kwh > 0 or bokforing.avvist_kwh:
                dirty = True
            if bokforing.arkiverte_maneder:
                # Boken rullerte inne i denne bokføringen. Månedssummen som
                # skal arkiveres er den boken lukket, ikke det som ligger i den
                # nye måneden nå; rulleringen under plukker den opp herfra.
                arkiv = self._bok.arkiverte_maneder()[bokforing.arkiverte_maneder[-1]]
                self._monthly_consumption = ConsumptionData(
                    dag=aapningsbalanse.dag + arkiv.kwh_dag,
                    natt=aapningsbalanse.natt + arkiv.kwh_natt,
                )
            else:
                self._monthly_consumption = self._forbruk_fra_boken(now, aapningsbalanse)
            berorte |= set(bokforing.fordeling)
            self._akkumuler_kroner(now, bokforing.fordeling)
            # Døgnmaks føres her inne, ikke etter løkken: krysser avlesningen et
            # månedsskifte, arkiverer boken den gamle måneden når den andre
            # delen bokføres, og da er den siste timen i måneden borte.
            if self._oppdater_timesmaks(now):
                dirty = True

        # En poll uten avlesning kjører ikke løkken over, og da ville en time
        # som ble ferdig mens sensoren var borte stått ubokført i døgnmaks til
        # neste avlesning kom. Kallet er idempotent.
        if self._oppdater_timesmaks(now):
            dirty = True

        # Eksport-akkumulering (plusskunder med solceller)
        export_energy_kwh = 0.0
        if self.export_power_sensor and elapsed_hours > 0:
            export_power_w = self._effekt_watt(INPUT_ROLLE_EKSPORT)
            export_power_kw = (export_power_w or 0.0) / 1000
            if export_power_kw > 0:
                export_energy_kwh = export_power_kw * elapsed_hours
                self._monthly_export_kwh += export_energy_kwh
                dirty = True
                # Inntekten bokføres i samme slengen som kilowattimene, og
                # begge deler før månedsskiftet arkiveres. Sto de på hver sin
                # side av rulleringen, ville siste syklus lagt kWh i den gamle
                # måneden og kronene i den nye. Kraftleverandører betaler
                # plusskunder spotpris eks. mva; mva er ikke aktuelt på salg
                # fra privatperson (accountant-funn #1).
                if spot_price_valid:
                    self._monthly_export_revenue += spot_price_eks_mva * export_energy_kwh

        self._last_update = now
        self._current_hour = now.hour

        # Månedsskifte: boken har alt bokført den gamle måneden ferdig over, så
        # arkiveringen skjer her, før noe av nåtidssnapshotet regnes. Uten det
        # kunne første juli-snapshot kombinere null kilowattimer med junis trinn
        # og tak-flagg (2ferkiq).
        current_month_str = now.strftime("%Y-%m")
        if current_month_str != self._current_month:
            await self._handle_month_rollover(now)
            # Etter arkiveringen står måneden på null, og det boken alt har
            # bokført i den nye måneden er det eneste forbruket som finnes.
            self._monthly_consumption = self._forbruk_fra_boken(now, ConsumptionData())
            if self._oppdater_timesmaks(now):
                dirty = True

        # Det åpne intervallet regnes opp uansett: en prisprøve kan ha endret
        # timeprisen uten at noen energi ble bokført. Etter en rullering er det
        # også her den nye månedens intervaller får kronene sine.
        self._akkumuler_kroner(now, berorte)

        if self._trenger_ukesmaks and self._prune_ukesmaks(now):
            dirty = True

        # Get top 3 days
        top_3 = self._get_top_3_days()
        top_3_kw_values = [entry.kw for entry in top_3.values()]
        avg_power = sum(top_3_kw_values) / 3 if len(top_3) >= 3 else sum(top_3_kw_values) / max(len(top_3), 1)

        # Effektgrunnlaget nettselskapets fastledd-metode bruker. Sammenfaller med
        # snittet av topp-3 for NVE-modellen, men ikke for de fem som avviker.
        fastledd_grunnlag = self._fastledd_grunnlag()

        # Calculate capacity tier
        kapasitetsledd, trinn_nummer, trinn_intervall = self._get_kapasitetsledd(fastledd_grunnlag)

        # Calculate margin to next tier. Bare meningsfullt der trinnet følger målt
        # effekt: sikringsbasert og lineært fastledd endrer seg ikke med forbruket.
        margin_neste_trinn = 0.0
        neste_trinn_pris = kapasitetsledd
        if self.fastledd_metode in FASTLEDD_TRINNBASERTE:
            for i, (threshold, _price) in enumerate(self.kapasitetstrinn):
                if self._avg_in_lower_tier(fastledd_grunnlag, threshold):
                    if i + 1 < len(self.kapasitetstrinn):
                        margin_neste_trinn = round(threshold - fastledd_grunnlag, 2)
                        neste_trinn_pris = self.kapasitetstrinn[i + 1][1]
                    break

        # If in the highest tier (no next tier), don't warn
        if margin_neste_trinn == 0.0 and neste_trinn_pris == kapasitetsledd:
            kapasitet_varsel = False
        else:
            kapasitet_varsel = margin_neste_trinn < self.kapasitet_varsel_terskel

        # Vaktholdet vurderes etter at energien er bokført og spot_price_valid
        # er avgjort, og før noen beregning kan skjule at inputen er borte. Det
        # skal se den avlesningen som nettopp kom: en teller som våknet i denne
        # pollen er ikke frossen lenger.
        input_problemer = self._oppdater_vakthold(now, spot_price_valid=spot_price_valid)

        # Calculate energiledd
        energiledd = self._get_energiledd(now)

        # Calculate strømstøtte (sonebevisst terskel, se incident 005)
        monthly_total_kwh = self._monthly_consumption.total
        stromstotte_terskel = get_stromstotte_terskel(self.avgiftssone)
        stromstotte = self._calculate_stromstotte(
            spot_price, monthly_total_kwh, self.boligtype, stromstotte_terskel
        )
        stromstotte_max = get_stromstotte_max_kwh(self.boligtype)
        stromstotte_gjenstaaende = max(0.0, stromstotte_max - monthly_total_kwh)

        # Spotpris etter strømstøtte
        spotpris_etter_stotte = spot_price - stromstotte

        # Fastleddet fordelt utover månedens timer. Dette er en visningssats,
        # den Energy Dashboard trenger for å ha én kr/kWh å gange med, og den
        # eneste bruken den har. Ingen krone i bokføringen kommer herfra:
        # fastledd er et periodebeløp (kostnad.py).
        dim = days_in_month(now)
        fastledd_per_kwh = (kapasitetsledd / dim) / 24

        # Norgespris - fast pris basert på avgiftssone
        norgespris = get_norgespris_inkl_mva(self.avgiftssone)

        # Norgespris kWh-tak
        norgespris_max = get_norgespris_max_kwh(self.boligtype)
        norgespris_over_tak = monthly_total_kwh >= norgespris_max

        if self.har_norgespris:
            if norgespris_over_tak:
                total_price = spot_price + energiledd + fastledd_per_kwh
                total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh
            else:
                total_price = norgespris + energiledd + fastledd_per_kwh
                total_price_uten_stotte = norgespris + energiledd + fastledd_per_kwh
        else:
            total_price = spot_price - stromstotte + energiledd + fastledd_per_kwh
            total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh

        # Norgespris comparison: use Norgespris if under cap, else spotpris
        # strompris_norgespris er ren strømdel uten nettleie (for ApexCharts-sammenligning
        # mot spotpris). Over taket faller man tilbake til spotpris.
        if norgespris_over_tak:
            strompris_norgespris = spot_price
        else:
            strompris_norgespris = norgespris
        total_pris_norgespris = strompris_norgespris + energiledd + fastledd_per_kwh

        # Strømpris per kWh (uten kapasitetsledd)
        if self.har_norgespris:
            if norgespris_over_tak:
                strompris_per_kwh = spot_price + energiledd
                strompris_per_kwh_etter_stotte = spot_price + energiledd
            else:
                strompris_per_kwh = norgespris + energiledd
                strompris_per_kwh_etter_stotte = norgespris + energiledd
        else:
            strompris_per_kwh = spot_price + energiledd
            strompris_per_kwh_etter_stotte = spot_price - stromstotte + energiledd

        # Offentlige avgifter (for Energy Dashboard)
        mva_sats = get_mva_sats(self.avgiftssone)
        forbruksavgift = get_forbruksavgift(self.avgiftssone)
        forbruksavgift_inkl_mva = forbruksavgift * (1 + mva_sats)
        enova_inkl_mva = ENOVA_AVGIFT * (1 + mva_sats)
        offentlige_avgifter = forbruksavgift_inkl_mva + enova_inkl_mva

        # NB: energiledd fra dso.py inkluderer allerede forbruksavgift + enova
        total_price_inkl_avgifter = total_price

        # Kroner spart per kWh: positiv = du sparer med nåværende avtale
        # Samme fortegn som _monthly_norgespris_diff (alternativ - din pris)
        if self.har_norgespris:
            alternativ_pris = spot_price - stromstotte + energiledd + fastledd_per_kwh
        else:
            alternativ_pris = total_pris_norgespris
        kroner_spart_per_kwh = alternativ_pris - total_price

        # Kraft, energiledd, avgifter, strømstøtte og Norgespris-linjen er alt
        # bokført per avregnet intervall over, med intervallets egen pris.
        # Fastleddet er det eneste som gjenstår, og det er et periodebeløp:
        # kr/mnd ganger forløpt andel av måneden, regnet på nytt her.
        self._oppdater_fastledd(now, kapasitetsledd)

        # Get electricity company price if configured
        electricity_company_price = None
        electricity_company_total = None
        if self.electricity_company_price_sensor:
            raw_ec = self._read_price_sensor(INPUT_ROLLE_LEVERANDORPRIS)
            if raw_ec is not None:
                electricity_company_price = raw_ec
                self._last_electricity_company_price = raw_ec
                self._last_electricity_company_price_time = now
            elif (
                self._last_electricity_company_price is not None
                and self._last_electricity_company_price_time is not None
                and sekunder_mellom(self._last_electricity_company_price_time, now)
                < _SPOT_CACHE_MAX_AGE.total_seconds()
            ):
                # Samme maks-alder som spot: en død leverandørsensor skal ikke
                # gi evig gammel pris i electricity_company_total.
                electricity_company_price = self._last_electricity_company_price
            if electricity_company_price is not None:
                electricity_company_total = electricity_company_price + energiledd + fastledd_per_kwh

        # Single save per cycle
        if dirty:
            await self._save_stored_data()

        return self._build_data_dict(
            energiledd=energiledd,
            kapasitetsledd=kapasitetsledd,
            trinn_nummer=trinn_nummer,
            trinn_intervall=trinn_intervall,
            fastledd_per_kwh=fastledd_per_kwh,
            fastledd_i_dag=self._fastledd_i_dag(now, kapasitetsledd),
            spot_price=spot_price,
            spot_price_valid=spot_price_valid,
            stromstotte=stromstotte,
            stromstotte_terskel=stromstotte_terskel,
            spotpris_etter_stotte=spotpris_etter_stotte,
            norgespris=norgespris,
            strompris_norgespris=strompris_norgespris,
            total_pris_norgespris=total_pris_norgespris,
            kroner_spart_per_kwh=kroner_spart_per_kwh,
            total_price=total_price,
            total_price_uten_stotte=total_price_uten_stotte,
            total_price_inkl_avgifter=total_price_inkl_avgifter,
            strompris_per_kwh=strompris_per_kwh,
            strompris_per_kwh_etter_stotte=strompris_per_kwh_etter_stotte,
            forbruksavgift_inkl_mva=forbruksavgift_inkl_mva,
            enova_inkl_mva=enova_inkl_mva,
            offentlige_avgifter=offentlige_avgifter,
            electricity_company_price=electricity_company_price,
            electricity_company_total=electricity_company_total,
            current_power_kw=current_power_kw,
            avg_power=avg_power,
            fastledd_grunnlag=fastledd_grunnlag,
            top_3=top_3,
            now=now,
            stromstotte_max=stromstotte_max,
            monthly_total_kwh=monthly_total_kwh,
            norgespris_over_tak=norgespris_over_tak,
            stromstotte_gjenstaaende=stromstotte_gjenstaaende,
            margin_neste_trinn=margin_neste_trinn,
            neste_trinn_pris=neste_trinn_pris,
            kapasitet_varsel=kapasitet_varsel,
            input_problemer=input_problemer,
        )

    def _build_data_dict(self, **kw: Any) -> dict[str, Any]:
        """Assemble the coordinator data dict from computed values."""
        top_3 = kw["top_3"]
        prev_top_3 = self._previous_month_top_3
        ec_price = kw["electricity_company_price"]
        ec_total = kw["electricity_company_total"]
        now = kw["now"]
        aktiv_dag, aktiv_natt = self._get_aktive_energileddsatser(now)
        perioder_meta = self._serialize_perioder()
        aktiv_periode = self._aktiv_periode_label(now)

        return {
            # Bokens egne statusfelt (felttabellen i avregningskontrakten).
            **self._bok.statusfelt(_aware(now)),
            "energiledd": round(kw["energiledd"], 4),
            "energiledd_dag": aktiv_dag,
            "energiledd_natt": aktiv_natt,
            "energiledd_perioder": perioder_meta,
            "aktiv_energiledd_periode": aktiv_periode,
            "tarifforigin": self._tarifforigin(now, aktiv_dag, aktiv_natt),
            "kapasitetsledd": kw["kapasitetsledd"],
            "kapasitetstrinn_nummer": kw["trinn_nummer"],
            "kapasitetstrinn_intervall": kw["trinn_intervall"],
            "kapasitetsledd_per_kwh": round(kw["fastledd_per_kwh"], 4),
            "fastledd_metode": self.fastledd_metode,
            "fastledd_grunnlag_kw": round(kw["fastledd_grunnlag"], 2),
            "fastledd_mangler_sikringsvalg": self._mangler_sikringsvalg(),
            "fastledd_ukjent": self._fastledd_ukjent(),
            "spot_price": round(kw["spot_price"], 4),
            "spot_price_valid": kw["spot_price_valid"],
            "stromstotte": round(kw["stromstotte"], 4),
            "stromstotte_terskel": round(kw["stromstotte_terskel"], 4),
            "spotpris_etter_stotte": round(kw["spotpris_etter_stotte"], 4),
            "norgespris": round(kw["norgespris"], 4),
            "strompris_norgespris": round(kw["strompris_norgespris"], 4),
            "total_pris_norgespris": round(kw["total_pris_norgespris"], 4),
            "kroner_spart_per_kwh": round(kw["kroner_spart_per_kwh"], 4),
            "total_price": round(kw["total_price"], 4),
            "total_price_uten_stotte": round(kw["total_price_uten_stotte"], 4),
            "total_price_inkl_avgifter": round(kw["total_price_inkl_avgifter"], 4),
            "strompris_per_kwh": round(kw["strompris_per_kwh"], 4),
            "strompris_per_kwh_etter_stotte": round(kw["strompris_per_kwh_etter_stotte"], 4),
            "forbruksavgift_inkl_mva": round(kw["forbruksavgift_inkl_mva"], 4),
            "enova_inkl_mva": round(kw["enova_inkl_mva"], 4),
            "offentlige_avgifter": round(kw["offentlige_avgifter"], 4),
            "electricity_company_price": round(ec_price, 4) if ec_price is not None else None,
            "electricity_company_total": round(ec_total, 4) if ec_total is not None else None,
            "current_power_kw": (
                round(kw["current_power_kw"], 2) if kw["current_power_kw"] is not None else None
            ),
            "avg_top_3_kw": round(kw["avg_power"], 2),
            "top_3_days": top_3,
            "is_day_rate": self._is_day_rate(kw["now"]),
            "dso": self.dso["name"],
            "har_norgespris": self.har_norgespris,
            "avgiftssone": self.avgiftssone,
            # Periodemerkelappene følger med i samme oppdatering som de
            # akkumulerte verdiene, slik at sensorene kan sette last_reset fra
            # nøyaktig den oppdateringen som nullstiller dem.
            "current_month": self._current_month,
            "current_date": self._current_date,
            "monthly_consumption_dag_kwh": round(self._monthly_consumption.dag, 3),
            "monthly_consumption_natt_kwh": round(self._monthly_consumption.natt, 3),
            "monthly_consumption_total_kwh": round(self._monthly_consumption.total, 3),
            "previous_month_consumption_dag_kwh": round(self._previous_month_consumption.dag, 3),
            "previous_month_consumption_natt_kwh": round(self._previous_month_consumption.natt, 3),
            "previous_month_consumption_total_kwh": round(self._previous_month_consumption.total, 3),
            "previous_month_top_3": prev_top_3,
            "previous_month_avg_top_3_kw": round(
                sum(e.kw for e in prev_top_3.values()) / max(len(prev_top_3), 1),
                2,
            )
            if prev_top_3
            else 0.0,
            "previous_month_name": self._previous_month_name,
            "previous_month_kapasitetsledd": self._previous_month_kapasitetsledd,
            "previous_month_kapasitetstrinn": self._previous_month_kapasitetstrinn,
            "previous_month_energiledd_dag": self._previous_month_energiledd_dag,
            "previous_month_energiledd_natt": self._previous_month_energiledd_natt,
            "stromstotte_tak_naadd": kw["stromstotte_max"] == 0
            or kw["monthly_total_kwh"] >= kw["stromstotte_max"],
            "norgespris_over_tak": kw["norgespris_over_tak"],
            "boligtype": self.boligtype,
            "stromstotte_gjenstaaende_kwh": round(kw["stromstotte_gjenstaaende"], 1),
            "margin_neste_trinn_kw": kw["margin_neste_trinn"],
            "neste_trinn_pris": kw["neste_trinn_pris"],
            "kapasitet_varsel": kw["kapasitet_varsel"],
            # Vakthold på input-sensorene. maaledata_problem er sannheten
            # binary_sensoren leser; listen forteller hvilken input og hvor lenge.
            "input_problemer": kw["input_problemer"],
            # Grensesnittet mot diagnostikken (kontrakt §10). Alt kommer fra
            # denne fullførte oppdateringen, så diagnostikken aldri viser en
            # blanding av to polls. Entity-id-er aliaseres av diagnostikklaget.
            "input_resultater": self._input_resultater_rapport(kw["now"]),
            "baseline": self._baseline_rapport(),
            "maaledata_problem": bool(kw["input_problemer"]),
            "sist_energi_okning": (
                self._last_energy_increase.isoformat() if self._last_energy_increase else None
            ),
            "energi_frossen_terskel_timer": self.energi_frossen_terskel_timer,
            "leverandorpris_gyldig": (
                None
                if not self.electricity_company_price_sensor
                else self._input_er_gyldig(INPUT_ROLLE_LEVERANDORPRIS)
            ),
            "monthly_norgespris_diff_kr": round(self._monthly_norgespris_diff, 2),
            "previous_month_norgespris_diff_kr": round(self._previous_month_norgespris_diff, 2),
            "monthly_norgespris_compensation_kr": round(self._monthly_norgespris_compensation, 2),
            "previous_month_norgespris_compensation_kr": round(
                self._previous_month_norgespris_compensation, 2
            ),
            "daily_cost_kr": round(self._daily_cost + kw["fastledd_i_dag"], 2),
            "monthly_stromstotte_kr": round(self._monthly_stromstotte, 4),
            "monthly_energiledd_dag_kr": round(self._monthly_energiledd_dag, 4),
            "monthly_energiledd_natt_kr": round(self._monthly_energiledd_natt, 4),
            "monthly_avgifter_kr": round(self._monthly_avgifter, 4),
            "monthly_accumulated_cost_kr": round(self._monthly_accumulated_cost, 4),
            "monthly_accumulated_cost_strom_kr": round(self._monthly_accumulated_cost_strom, 4),
            "monthly_accumulated_cost_energiledd_kr": round(self._monthly_accumulated_cost_energiledd, 4),
            "monthly_accumulated_cost_kapasitetsledd_kr": round(
                self._monthly_accumulated_cost_kapasitetsledd, 4
            ),
            "eksport_konfigurert": self.export_power_sensor is not None,
            "monthly_export_kwh": round(self._monthly_export_kwh, 3),
            "monthly_export_revenue_kr": round(self._monthly_export_revenue, 2),
            "monthly_cost_kr": round(self._monthly_cost, 2),
            "monthly_net_cost_kr": round(self._monthly_cost - self._monthly_export_revenue, 2),
            "previous_month_export_kwh": round(self._previous_month_export_kwh, 3),
            "previous_month_export_revenue_kr": round(self._previous_month_export_revenue, 2),
            "previous_month_cost_kr": round(self._previous_month_cost, 2),
            "previous_month_net_cost_kr": round(
                self._previous_month_cost - self._previous_month_export_revenue, 2
            ),
        }

    def _get_top_3_days(self) -> dict[str, DailyMaxEntry]:
        """Get the top 3 days with highest power consumption."""
        sorted_days = sorted(self._daily_max_power.items(), key=lambda x: x[1].kw, reverse=True)
        return dict(sorted_days[:3])

    @property
    def _trenger_ukesmaks(self) -> bool:
        """Om nettselskapet avregner ukestopper over et rullerende år."""
        return self.fastledd_metode == FASTLEDD_FEM_VEKTET_AR

    def _sesongvekt(self, maaned: int) -> float:
        """Vektfaktor for en måned. 1,0 når nettselskapet ikke sesongvekter."""
        return self.fastledd_sesongfaktor.get(maaned, 1.0)

    @staticmethod
    def _ukestart(dag: date) -> date:
        """Mandagen i uken dagen ligger i."""
        return dag - timedelta(days=dag.weekday())

    def _registrer_timesmaks(self, dato: str, kwh: float, hour: int | None) -> bool:
        """Bokfør en fullført times snitteffekt. True hvis noe ble endret.

        En fullført klokketimes kWh er samme tall som timens snitt-kW, og er det
        nettselskapene måler. Skrives til døgnmaks alltid, og til ukesmaks for
        nettselskap som avregner årstopper.
        """
        kw = round(kwh, 3)
        endret = False
        forrige = self._daily_max_power.get(dato)
        if kw > (forrige.kw if forrige else 0):
            self._daily_max_power[dato] = DailyMaxEntry(kw=kw, hour=hour)
            endret = True
        if self._trenger_ukesmaks and self._registrer_ukesmaks(dato, kw, hour):
            endret = True
        return endret

    def _registrer_ukesmaks(self, dato: str, kw: float, hour: int | None) -> bool:
        """Hold ukens høyeste time. Nøkkelen er mandagens dato.

        Hele uken vektes med mandagens måned, så alle timene i uken har samme
        vekt og den høyeste rå kW-en er også den høyeste vektede. Derfor
        sammenlignes rå kW her. Vektingen skjer i `_vektet`, før de fem høyeste
        plukkes ut, slik fellesbestemmelsene beskriver rekkefølgen.
        """
        try:
            dag = date.fromisoformat(dato)
        except ValueError:
            _LOGGER.warning("Ugyldig dato for ukesmaks: %s", dato)
            return False
        nokkel = self._ukestart(dag).isoformat()
        forrige = self._weekly_max_power.get(nokkel)
        if forrige is not None and kw <= forrige.kw:
            return False
        self._weekly_max_power[nokkel] = WeeklyMaxEntry(kw=kw, dato=dato, hour=hour)
        return True

    def _vektet(self, entry: WeeklyMaxEntry) -> float:
        """Ukestoppens sesongvektede effekt.

        Vekten følger mandagen i uken, ikke toppens egen måned. Fjellnett:
        «Når ei uke går over et månedsskift, vil det være mandag i starten på
        uka som bestemmer hvilken sesongfaktor som effekten blir vekta med.»
        """
        try:
            dag = date.fromisoformat(entry.dato)
        except ValueError:
            return entry.kw
        return entry.kw * self._sesongvekt(self._ukestart(dag).month)

    def _prune_ukesmaks(self, now: datetime) -> bool:
        """Kast ukestopper som har falt ut av tolvmånedersvinduet.

        Vinduet er halvåpent: en topp datert nøyaktig tolv kalendermåneder
        tilbake er ute, dagen etter er inne. Grensen måles mot toppens egen
        dato, ikke mot mandagsnøkkelen, for det er effekten som skal være
        «løpende siste 12 mnd». En topp på en søndag ville ellers dødd seks
        dager for tidlig.
        """
        grense = _tolv_maaneder_tilbake(now.date())
        utgaatt = [
            nokkel for nokkel, entry in self._weekly_max_power.items() if _toppdato(nokkel, entry) <= grense
        ]
        for nokkel in utgaatt:
            del self._weekly_max_power[nokkel]
        return bool(utgaatt)

    def _fastledd_grunnlag(self) -> float:
        """Effektverdien i kW som nettselskapets fastledd-metode legger til grunn.

        NVE-modellen bruker snittet av de tre høyeste døgnmaksene i måneden. De
        fem nettselskapene som avviker, er dokumentert i docs/beregninger.md.
        """
        if self.fastledd_metode == FASTLEDD_MND_MAX:
            return max((e.kw for e in self._daily_max_power.values()), default=0.0)
        if self.fastledd_metode == FASTLEDD_FEM_VEKTET_AR:
            vektet = sorted((self._vektet(e) for e in self._weekly_max_power.values()), reverse=True)[
                :FEM_VEKTET_ANTALL_TOPPER
            ]
            if not vektet:
                return 0.0
            # Nettselskapet fakturerer effekten med to desimaler.
            return round(sum(vektet) / len(vektet), 2)
        top_3 = [e.kw for e in self._get_top_3_days().values()]
        if not top_3:
            return 0.0
        return sum(top_3) / 3 if len(top_3) >= 3 else sum(top_3) / len(top_3)

    def _fastledd_ukjent(self) -> bool:
        """Om fastleddet er ukjent fordi ingen kjenner trinnene.

        Gjelder Egendefinert uten brukeroppgitt trinntabell. Nettselskapene i
        `dso.py` har enten trinn med kilde eller en annen fastledd-metode, så
        dette er ikke en tilstand et katalogoppsett kan havne i. Kapasitetsledd
        og alt som bygger på det blir ukjent (kontrakt §9), framfor et
        plausibelt beløp uten kilde (incident 006).
        """
        return self.fastledd_metode in FASTLEDD_TRINNBASERTE and not self.kapasitetstrinn

    def _mangler_sikringsvalg(self) -> bool:
        """Om et sikringsbasert fastledd står uten gyldig brukervalg."""
        if self.fastledd_metode != FASTLEDD_OV_TREFASE:
            return False
        return finn_sikringstrinn(self.dso, self.sikringstrinn_valg) is None

    def _lineart_fastledd(self, grunnlag_kw: float) -> int:
        """Fastledd i kr/mnd inkl. mva for grunnbeløp + sats per kW."""
        if self.fastledd_lineaer is None:
            return 0
        aar_eks_mva = (
            self.fastledd_lineaer["grunnbelop_aar_eks_mva"]
            + self.fastledd_lineaer["sats_kw_aar_eks_mva"] * grunnlag_kw
        )
        maaned = aar_eks_mva / 12 * (1 + get_mva_sats(self.avgiftssone))
        # Halve kroner rundes opp, som i dso.py. Innebygd round() gjør bankers
        # rounding og ville gitt 453 der nettselskapet fakturerer 453,75.
        return int(Decimal(maaned).quantize(Decimal(1), ROUND_HALF_UP))

    def _get_kapasitetsledd(self, grunnlag_kw: float) -> tuple[int, int | None, str]:
        """Fastledd i kr/mnd for et effektgrunnlag.

        Returns: (pris, trinnummer, trinnbeskrivelse). Trinnummer er None der
        nettselskapet ikke har trinn, eller der sikringsstørrelsen mangler.
        """
        if self._fastledd_ukjent():
            # Ingen gjetning: uten brukerens egne trinn finnes det ikke noe
            # beløp å slå opp, og 0 her betyr «regnet uten fastledd», ikke
            # «fastleddet er null». Sensorene viser Ukjent.
            return 0, None, "fastledd ukjent"

        if self.fastledd_metode == FASTLEDD_OV_TREFASE:
            valgt = finn_sikringstrinn(self.dso, self.sikringstrinn_valg)
            if valgt is None:
                # Ingen gjetning: sikringsstørrelse kan ikke leses av en
                # effektsensor, og et plausibelt beløp ville skjult feilen.
                return 0, None, "sikringsstørrelse ikke valgt"
            nummer, trinn = valgt
            return trinn["kr_mnd"], nummer, trinn["label"]

        if self.fastledd_metode == FASTLEDD_FEM_VEKTET_AR:
            return (
                self._lineart_fastledd(grunnlag_kw),
                None,
                f"{grunnlag_kw:.2f} kW vektet årstopp",
            )

        return finn_kapasitetstrinn(self.kapasitetstrinn, grunnlag_kw, self._terskel_inkludert)

    def _serialize_perioder(self) -> list[dict[str, Any]] | None:
        """Returner energiledd-periodene som dict-liste for sensor-attributter.

        Returnerer None hvis DSO ikke har sesongprising. Satser er inkl.
        avgifter og mva.
        """
        if not self._energiledd_perioder_inkl:
            return None
        return [
            {"fra": fra, "til": til, "dag": round(dag, 4), "natt": round(natt, 4)}
            for fra, til, dag, natt in self._energiledd_perioder_inkl
        ]

    def _aktiv_periode_label(self, now: datetime) -> str | None:
        """Returner "fra-til" for aktiv periode, eller None ved ikke-sesong DSO."""
        if not self._energiledd_perioder_inkl:
            return None
        mm_dd = now.strftime("%m-%d")
        for fra, til, _dag, _natt in self._energiledd_perioder_inkl:
            if fra <= til:
                if fra <= mm_dd <= til:
                    return f"{fra} til {til}"
            elif mm_dd >= fra or mm_dd <= til:
                return f"{fra} til {til}"
        return None

    def _tarifforigin(self, now: datetime, aktiv_dag: float, aktiv_natt: float) -> dict[str, Any]:
        """Hvor satsene i denne oppdateringen kom fra (kontrakt §10).

        D2 leser dette framfor å tolke `entry.data` på nytt, slik at
        diagnostikken forteller hvilke tall som faktisk ble brukt, ikke hvilke
        som ligger lagret. På en sesong-DSO er det periodens satser.
        """
        aktiv_dag_eks, aktiv_natt_eks = self._slaa_opp_periode(
            now,
            self._energiledd_perioder_eks,
            (self.energiledd_dag_eks_mva, self.energiledd_natt_eks_mva),
        )
        return {
            "modus": self.tariffmodus,
            "dso": self._dso_id,
            "sesongperioder_styrer": self.sesong_styrer,
            "manual_ignorert": self.manual_ignorert,
            "energiledd_dag_eks_mva": round(aktiv_dag_eks, 5),
            "energiledd_natt_eks_mva": round(aktiv_natt_eks, 5),
            "energiledd_dag_inkl_mva": round(aktiv_dag, 5),
            "energiledd_natt_inkl_mva": round(aktiv_natt, 5),
        }

    @staticmethod
    def _slaa_opp_periode(
        now: datetime,
        perioder: list[tuple[str, str, float, float]],
        fallback: tuple[float, float],
    ) -> tuple[float, float]:
        """Periodens (dag, natt) for datoen, eller fallback om ingen treffer.

        En periode som krysser nyttår har `fra` etter `til`, og treffer da alt
        som ligger på eller etter `fra` eller på eller før `til`.
        """
        if not perioder:
            return fallback
        mm_dd = now.strftime("%m-%d")
        for fra, til, dag, natt in perioder:
            if fra <= til:
                if fra <= mm_dd <= til:
                    return dag, natt
            elif mm_dd >= fra or mm_dd <= til:
                return dag, natt
        return fallback

    def _get_aktive_energileddsatser(self, now: datetime) -> tuple[float, float]:
        """Returner (dag, natt) energileddsatser inkl. avgifter for nåværende dato.

        For DSO-er med sesongprising slås det opp i `energiledd_perioder`.
        Faller tilbake til `self.energiledd_dag/natt` hvis ingen periode
        treffer (skal ikke skje hvis periodene dekker hele året, men er en
        trygg fallback).
        """
        return self._slaa_opp_periode(
            now, self._energiledd_perioder_inkl, (self.energiledd_dag, self.energiledd_natt)
        )

    def _get_energiledd(self, now: datetime) -> float:
        """Get energiledd based on time of day."""
        dag, natt = self._get_aktive_energileddsatser(now)
        return dag if self._is_day_rate(now) else natt

    def _is_day_rate(self, now: datetime) -> bool:
        """Om tidspunktet ligger i dagtariffen.

        Regelen bor i `Tariffregel` og leses derfra, ikke av en kopi her.
        Kopien fantes, og den var grunnen til at avregningen og visningen kunne
        svare ulikt på samme time.

        En naiv tid tolkes som Europe/Oslo. Avregningen sender aldri en slik
        inn; den er til for tester og for visningsfelt som ennå ikke er
        tidssoneklare.
        """
        return self._tariffregel.tariff(_aware(now)) is Tariff.DAG

    def _format_month_name(self, dt: datetime) -> str:
        """Format date as Norwegian month name with year."""
        months: list[str] = [
            "januar",
            "februar",
            "mars",
            "april",
            "mai",
            "juni",
            "juli",
            "august",
            "september",
            "oktober",
            "november",
            "desember",
        ]
        return f"{months[dt.month - 1]} {dt.year}"

    def _meld_prisenhet_ubekreftet(self) -> None:
        """Be brukeren bekrefte en prissensor uten enhet (kontrakt §4).

        Sensoren godtas som NOK/kWh, for integrasjonen skal virke fra første
        minutt, men antakelsen skal være synlig. Flagget er per rolle: den som
        bekreftet spotprisen og senere la til en leverandørprissensor uten enhet
        skal få spørsmålet om den òg.

        Varselet reises ikke for en sensor som har enhet. Det er hele poenget:
        den som har en Nord Pool-sensor med NOK/kWh skal ikke se noe.
        """
        issue_id = f"prisenhet_ubekreftet_{self.entry.entry_id}"
        bekreftet = self.entry.data.get(CONF_PRISENHET_BEKREFTET) or []
        if not isinstance(bekreftet, list):
            bekreftet = []

        ubekreftede = [
            rolle
            for rolle in (INPUT_ROLLE_SPOTPRIS, INPUT_ROLLE_LEVERANDORPRIS)
            if rolle not in bekreftet
            and isinstance(resultat := self._input_resultater.get(rolle), Gyldig)
            and resultat.raa_enhet is None
        ]
        if not ubekreftede:
            if self._prisenhet_issue_aktiv or not self._prisenhet_issue_synket:
                # `not synket` er første poll etter oppstart, og den rydder også
                # et varsel som overlevde en omstart. Uten det ble en issue
                # stående for godt hvis sensoren fikk enhet mens HA var nede:
                # minnet sa at ingen issue var aktiv, og da ble den aldri
                # slettet. Samme mønster som `_vakthold_issues_synket`.
                ir.async_delete_issue(self.hass, DOMAIN, issue_id)
                self._prisenhet_issue_aktiv = False
                self._prisenhet_issue_roller = []
            self._prisenhet_issue_synket = True
            return

        if self._prisenhet_issue_roller == ubekreftede:
            return
        entiteter = [
            str(getattr(self._input_resultater.get(rolle), "entity_id", "")) for rolle in ubekreftede
        ]
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            issue_id,
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="prisenhet_ubekreftet",
            translation_placeholders={
                "roller": ", ".join(_ROLLE_TEKST.get(r, r) for r in ubekreftede),
                "entity_id": ", ".join(entiteter),
            },
            data={"entry_id": self.entry.entry_id, "roller": ",".join(ubekreftede)},
        )
        self._prisenhet_issue_aktiv = True
        self._prisenhet_issue_roller = list(ubekreftede)
        self._prisenhet_issue_synket = True

    def _input_resultater_rapport(self, now: datetime) -> dict[str, dict[str, Any]]:
        """Siste resultat per rolle, på formen diagnostikken leser (§10)."""
        rapport: dict[str, dict[str, Any]] = {}
        for rolle, entity_id in self._input_entiteter():
            resultat = self._input_resultater.get(rolle)
            if resultat is None:
                continue
            sist_gyldig = self._input_sist_gyldig_avlest.get(rolle)
            rapport[rolle] = {
                "entity_id": entity_id,
                "type": _RESULTATTYPE[type(resultat)],
                "grunn": getattr(resultat, "grunn", None),
                "raa_enhet": getattr(resultat, "raa_enhet", None),
                "enhet_normalisert": getattr(resultat, "enhet_normalisert", None),
                "alder_sekunder": (
                    round(sekunder_mellom(sist_gyldig, now), 1) if sist_gyldig is not None else None
                ),
            }
        return rapport

    def _baseline_rapport(self) -> dict[str, Any] | None:
        """Energibaselinen slik diagnostikken viser den (§10).

        `forkastet` er med fordi et uventet nullforbruk rett etter en omstart
        skal kunne forklares uten å lese loggen.
        """
        if self._baseline is None:
            return {"forkastet": self._baseline_forkastet} if self._baseline_forkastet else None
        return {
            **self._baseline.som_lagret(),
            "forkastet": self._baseline_forkastet,
        }

    async def _load_stored_data(self) -> None:
        """Load stored data from disk."""
        data: dict[str, Any] | None = await self._store.async_load()

        # Migration: try to load from old DSO-based storage if new storage is empty
        if not data:
            old_store: Store[dict[str, Any]] = Store(self.hass, 1, f"{DOMAIN}_{self._dso_id}")
            data = await old_store.async_load()
            if data:
                _LOGGER.info("Migrated data from DSO-based storage to entry-based storage")
                try:
                    await self._store.async_save(data)
                    await old_store.async_remove()
                except OSError as err:
                    _LOGGER.warning("Storage migration failed: %s", err)

        # Boken leser hele filen, ikke bare sine egne nøkler: en v1- eller
        # v2-fil har ingen intervallhistorikk å gjenskape, og måneden den
        # migreres i merkes `ufullstendig` (kontrakt D).
        self._bok = self._ny_bok(data)

        if data:
            try:
                self._daily_max_power = self._validate_daily_max_power(data.get("daily_max_power", {}))
                self._weekly_max_power = self._validate_weekly_max_power(data.get("weekly_max_power", {}))
                self._monthly_consumption = self._validate_consumption(
                    data.get("monthly_consumption", {"dag": 0.0, "natt": 0.0})
                )
                self._monthly_norgespris_diff = self._validate_float(data.get("monthly_norgespris_diff", 0.0))
                self._previous_month_consumption = self._validate_consumption(
                    data.get("previous_month_consumption", {"dag": 0.0, "natt": 0.0})
                )
                self._previous_month_top_3 = self._validate_daily_max_power(
                    data.get("previous_month_top_3", {})
                )
                self._previous_month_name = data.get("previous_month_name")
                self._previous_month_norgespris_diff = self._validate_float(
                    data.get("previous_month_norgespris_diff", 0.0)
                )
                self._monthly_norgespris_compensation = self._validate_float(
                    data.get("monthly_norgespris_compensation", 0.0)
                )
                self._previous_month_norgespris_compensation = self._validate_float(
                    data.get("previous_month_norgespris_compensation", 0.0)
                )
                prev_kap = data.get("previous_month_kapasitetsledd", 0)
                try:
                    self._previous_month_kapasitetsledd = int(prev_kap)
                except (ValueError, TypeError):
                    self._previous_month_kapasitetsledd = 0
                self._previous_month_kapasitetstrinn = str(data.get("previous_month_kapasitetstrinn", ""))
                self._previous_month_energiledd_dag = self._validate_float(
                    data.get("previous_month_energiledd_dag", self.energiledd_dag)
                )
                self._previous_month_energiledd_natt = self._validate_float(
                    data.get("previous_month_energiledd_natt", self.energiledd_natt)
                )
                self._daily_cost = self._validate_float(data.get("daily_cost", 0.0))
                # Eksport-data
                self._monthly_export_kwh = self._validate_float(data.get("monthly_export_kwh", 0.0))
                self._monthly_export_revenue = self._validate_float(data.get("monthly_export_revenue", 0.0))
                # `monthly_cost` og `monthly_accumulated_cost` leses ikke: de er
                # summer av feltene under, og en lagret sum som kan avvike fra
                # delene sine er nettopp den motstriden 33f81xu handler om.
                self._monthly_accumulated_cost_strom = self._validate_float(
                    data.get("monthly_accumulated_cost_strom", 0.0)
                )
                self._monthly_stromstotte = self._validate_float(data.get("monthly_stromstotte", 0.0))
                if any(
                    nokkel in data
                    for nokkel in ("monthly_energiledd_dag", "monthly_energiledd_natt", "monthly_avgifter")
                ):
                    self._monthly_energiledd_dag = self._validate_float(
                        data.get("monthly_energiledd_dag", 0.0)
                    )
                    self._monthly_energiledd_natt = self._validate_float(
                        data.get("monthly_energiledd_natt", 0.0)
                    )
                    self._monthly_avgifter = self._validate_float(data.get("monthly_avgifter", 0.0))
                    self._monthly_energiledd_apning = self._validate_float(
                        data.get("monthly_energiledd_apning", 0.0)
                    )
                else:
                    # En fil fra før splitten har bare summen. Den kan ikke deles
                    # i dag, natt og avgifter i ettertid, så den bæres som
                    # åpningsbalanse og faller bort ved første månedsskifte.
                    self._monthly_energiledd_apning = self._validate_float(
                        data.get("monthly_accumulated_cost_energiledd", 0.0)
                    )
                # Fastleddet regnes på nytt ved hver poll og lastes ikke. Det
                # lagrede tallet er med for nedgradering og for diagnostikken.
                self._previous_month_export_kwh = self._validate_float(
                    data.get("previous_month_export_kwh", 0.0)
                )
                self._previous_month_export_revenue = self._validate_float(
                    data.get("previous_month_export_revenue", 0.0)
                )
                self._previous_month_cost = self._validate_float(data.get("previous_month_cost", 0.0))
                self._current_date = data.get("current_date", dt_util.now().strftime("%Y-%m-%d"))
                self._current_hour_energy = self._validate_float(data.get("current_hour_energy", 0.0))
                stored_hour = data.get("current_hour")
                if isinstance(stored_hour, int) and 0 <= stored_hour <= 23:
                    self._current_hour = stored_hour
                stored_month = data.get("current_month")
                if stored_month is not None:
                    # Backward compat: old format stored month as integer
                    if isinstance(stored_month, int):
                        # Cannot reconstruct year from int alone; assume current year
                        stored_month = f"{dt_util.now().year}-{stored_month:02d}"
                    if stored_month != self._current_month:
                        # Set to stored month so the normal month-transition in
                        # _async_update_data fires and properly archives previous month data
                        self._current_month = stored_month
                # Additiv nøkkel: mangler den, står vi på None og vaktholdet
                # starter klokken ved første poll i stedet for å melde frossen.
                stored_increase = data.get("last_energy_increase")
                if stored_increase:
                    try:
                        self._last_energy_increase = _som_lokal(datetime.fromisoformat(stored_increase))
                    except (ValueError, TypeError):
                        _LOGGER.warning(
                            "Kunne ikke lese last_energy_increase fra storage: %s", stored_increase
                        )

                stored_last_update = data.get("last_update")
                last_update_age_hours: float | None = None
                naa = dt_util.now()
                if stored_last_update:
                    try:
                        loaded_last_update = datetime.fromisoformat(stored_last_update)
                        # Bare gjenopprett hvis gapet er innenfor MAX_ELAPSED_HOURS.
                        # Lengre gap betyr restart-pause; da vil vi heller starte friskt
                        # (None) enn å akkumulere current_power * hele restart-vinduet.
                        last_update_age_hours = sekunder_mellom(loaded_last_update, naa) / 3600
                        if self._last_energy_increase is not None and last_update_age_hours > 0:
                            # HA var av i gapet, og da kunne ingen se telleren øke.
                            # Frossen-klokken skal bare telle tid vi faktisk så på,
                            # ellers gir et strømbrudd på en natt et frossen-varsel
                            # i det HA kommer opp igjen. Klokken skyves fram med
                            # nedetiden: det som var målt før avstengningen står,
                            # det blinde gapet teller ikke.
                            observert = max(
                                0.0,
                                sekunder_mellom(self._last_energy_increase, loaded_last_update),
                            )
                            self._last_energy_increase = trekk_fra_sekunder(naa, observert)
                        if 0 <= last_update_age_hours <= MAX_ELAPSED_HOURS:
                            self._last_update = loaded_last_update
                    except (ValueError, TypeError) as err:
                        _LOGGER.warning("Kunne ikke lese last_update fra storage: %s", err)

                # Energibaselinen (kontrakt §5). Samme kilde gjenopptar uansett
                # alder: en hytte som sto avslått i en uke skal få forbruket
                # sitt fordelt, ikke slettet. Vernet mot det gigantiske spranget
                # er MAX_ENERGY_DELTA_KWH, som viser brukeren tallet.
                #
                # Alt som ligger lagret fra før 1.17 er en rå sensorverdi uten
                # kilde og uten enhet. Den forkastes én gang, og neste avlesning
                # setter ny baseline med delta 0. Månedsdata beholdes.
                lagret_baseline = data.get(BASELINE_NOKKEL)
                self._baseline = Baseline.fra_lagret(lagret_baseline)
                if self._bok.sist_observert is None and self._baseline is not None:
                    # v2-fil: boken har ingen observasjon, men baselinen i
                    # filen er den samme opplysningen og skal ikke kastes.
                    self._bok.sett_baseline(
                        Avlesning(
                            source_identity=self._baseline.source_identity
                            or f"entity:{self._baseline.entity_id}",
                            entity_id=self._baseline.entity_id,
                            value_kwh=self._baseline.value_kwh,
                            observed_at=_aware(self._baseline.observed_at),
                        )
                    )
                # Forkastet betyr at det faktisk lå en baseline der som ikke lot
                # seg lese. `_save_stored_data` skriver `energi_baseline: None`
                # ved hver lagring uten baseline, så `BASELINE_NOKKEL in data`
                # er sann også hos den som aldri har hatt en, og det ga et
                # forkastet-flagg og en INFO-linje hos hver eneste ny bruker.
                self._baseline_forkastet = self._baseline is None and (
                    lagret_baseline is not None or data.get("last_tpi_kwh") is not None
                )
                if self._baseline is not None and not self.energy_sensor:
                    # Energisensoren er fjernet fra konfigurasjonen. Settes den
                    # inn igjen, er det per definisjon en ny kilde (§5). Det er
                    # ikke en forkastet baseline: den var lesbar, den har bare
                    # ingen sensor å høre til.
                    self._baseline = None
                    self._bok.sett_baseline(None)
                if self._baseline_forkastet:
                    _LOGGER.info(
                        "Energibaselinen i lagringsfilen manglet kildeidentitet og ble forkastet. "
                        "Neste avlesning setter ny baseline; månedsdata er urørt."
                    )

                if self._baseline is None:
                    # Uten baseline vet vi ikke om telleren har stått stille
                    # eller om HA bare har vært av. Å ha vært avslått er ikke en
                    # frossen måler, så klokken starter ved første poll i stedet
                    # for at hytta får varsel i det den slås på igjen.
                    self._last_energy_increase = None
            except (TypeError, KeyError, AttributeError) as err:
                _LOGGER.warning("Corrupt storage data, using defaults: %s", err)
            _LOGGER.debug("Loaded stored data: %s", self._daily_max_power)

        # Kronene hvert lagret intervall alt har bidratt med regnes opp igjen
        # av boken framfor å lagres. Da kan de ikke drifte fra intervallene, og
        # et intervall som ikke endrer seg mer bidrar aldri en gang til.
        self._speil_baseline()
        self._bygg_kronebokforing()

    def _bygg_kronebokforing(self) -> None:
        """Sett `_kr_bokfort` til det bokens intervaller svarer til nå (C5).

        Kronene hvert lagret intervall alt har bidratt med regnes opp igjen av
        boken framfor å lagres. Da kan de ikke drifte fra intervallene, og et
        intervall som ikke endrer seg mer bidrar aldri en gang til.
        """
        self._kr_bokfort = {}
        if not self._fores_av_boken():
            return
        kwh_for = max(0.0, self._monthly_consumption.total - self._bok.maanedssum().kwh_total)
        for intervall in self._bok.intervaller():
            self._kr_bokfort[intervall.start_utc] = kroner_for_intervall(
                intervall, self._satser(intervall), kwh_for=kwh_for
            )
            kwh_for += intervall.kwh

    @staticmethod
    def _validate_float(value: Any) -> float:
        """Validate and return a finite float, defaulting to 0.0."""
        try:
            val = float(value)
        except (ValueError, TypeError):
            return 0.0
        return val if math.isfinite(val) else 0.0

    @staticmethod
    def _validate_daily_max_power(data: Any) -> dict[str, DailyMaxEntry]:
        """Validate daily max power dict, migrating old float format to new dict format."""
        if not isinstance(data, dict):
            return {}
        result: dict[str, DailyMaxEntry] = {}
        for key, val in data.items():
            if isinstance(val, dict):
                try:
                    fval = float(val.get("kw", 0))
                except (ValueError, TypeError):
                    continue
                if math.isfinite(fval) and fval >= 0:
                    hour = val.get("hour")
                    if hour is not None:
                        try:
                            hour = int(hour)
                            if not 0 <= hour <= 23:
                                hour = None
                        except (ValueError, TypeError):
                            hour = None
                    result[str(key)] = DailyMaxEntry(kw=fval, hour=hour)
            else:
                try:
                    fval = float(val)
                except (ValueError, TypeError):
                    continue
                if math.isfinite(fval) and fval >= 0:
                    result[str(key)] = DailyMaxEntry(kw=fval, hour=None)
        return result

    @staticmethod
    def _validate_weekly_max_power(data: Any) -> dict[str, WeeklyMaxEntry]:
        """Valider lagrede ukestopper. Poster uten gyldig dato forkastes.

        Datoen bærer sesongvekten, så en post uten den er ubrukelig og skal ut
        heller enn å bli vektet feil.
        """
        if not isinstance(data, dict):
            return {}
        result: dict[str, WeeklyMaxEntry] = {}
        for key, val in data.items():
            if not isinstance(val, dict):
                continue
            try:
                kw = float(val.get("kw", 0))
            except (ValueError, TypeError):
                continue
            if not math.isfinite(kw) or kw < 0:
                continue
            dato = str(val.get("dato", ""))
            try:
                date.fromisoformat(dato)
            except ValueError:
                continue
            hour = val.get("hour")
            if hour is not None:
                try:
                    hour = int(hour)
                    if not 0 <= hour <= 23:
                        hour = None
                except (ValueError, TypeError):
                    hour = None
            result[str(key)] = WeeklyMaxEntry(kw=kw, dato=dato, hour=hour)
        return result

    @staticmethod
    def _validate_consumption(data: Any) -> ConsumptionData:
        """Validate consumption dict has dag/natt keys with finite floats."""
        if not isinstance(data, dict):
            return ConsumptionData()
        result = ConsumptionData()
        for key in ("dag", "natt"):
            try:
                val = float(data.get(key, 0.0))
            except (ValueError, TypeError):
                val = 0.0
            if not math.isfinite(val) or val < 0:
                val = 0.0
            setattr(result, key, val)
        return result

    @staticmethod
    def _serialize_daily_max(data: dict[str, DailyMaxEntry]) -> dict[str, dict[str, Any]]:
        """Convert DailyMaxEntry dict to JSON-serializable format."""
        return {k: {"kw": v.kw, "hour": v.hour} for k, v in data.items()}

    async def _save_stored_data(self) -> None:
        """Save data to disk."""
        data: dict[str, Any] = {
            # Boken skriver `skjema_versjon` selv, og den er én teller for hele
            # filen (kontrakt D). Den sto på 2 fra K1 og løftes til 3 her.
            # v1- og v2-feltene under skrives uendret, så en nedgradering
            # beholder månedsdataene sine.
            **self._bok.til_lagring(_aware(dt_util.now())),
            "daily_max_power": self._serialize_daily_max(self._daily_max_power),
            "weekly_max_power": {
                k: {"kw": v.kw, "dato": v.dato, "hour": v.hour} for k, v in self._weekly_max_power.items()
            },
            "monthly_consumption": {
                "dag": self._monthly_consumption.dag,
                "natt": self._monthly_consumption.natt,
            },
            "current_month": self._current_month,
            "previous_month_consumption": {
                "dag": self._previous_month_consumption.dag,
                "natt": self._previous_month_consumption.natt,
            },
            "previous_month_top_3": self._serialize_daily_max(self._previous_month_top_3),
            "previous_month_name": self._previous_month_name,
            "monthly_norgespris_diff": self._monthly_norgespris_diff,
            "previous_month_norgespris_diff": self._previous_month_norgespris_diff,
            "monthly_norgespris_compensation": self._monthly_norgespris_compensation,
            "previous_month_norgespris_compensation": self._previous_month_norgespris_compensation,
            "previous_month_kapasitetsledd": self._previous_month_kapasitetsledd,
            "previous_month_kapasitetstrinn": self._previous_month_kapasitetstrinn,
            "previous_month_energiledd_dag": self._previous_month_energiledd_dag,
            "previous_month_energiledd_natt": self._previous_month_energiledd_natt,
            "daily_cost": self._daily_cost,
            "current_date": self._current_date,
            "current_hour_energy": self._current_hour_energy,
            "current_hour": self._current_hour,
            "monthly_export_kwh": self._monthly_export_kwh,
            "monthly_export_revenue": self._monthly_export_revenue,
            "monthly_cost": self._monthly_cost,
            "monthly_accumulated_cost": self._monthly_accumulated_cost,
            "monthly_accumulated_cost_strom": self._monthly_accumulated_cost_strom,
            "monthly_accumulated_cost_energiledd": self._monthly_accumulated_cost_energiledd,
            "monthly_accumulated_cost_kapasitetsledd": self._monthly_accumulated_cost_kapasitetsledd,
            "monthly_stromstotte": self._monthly_stromstotte,
            "monthly_energiledd_dag": self._monthly_energiledd_dag,
            "monthly_energiledd_natt": self._monthly_energiledd_natt,
            "monthly_avgifter": self._monthly_avgifter,
            "monthly_energiledd_apning": self._monthly_energiledd_apning,
            "previous_month_export_kwh": self._previous_month_export_kwh,
            "previous_month_export_revenue": self._previous_month_export_revenue,
            "previous_month_cost": self._previous_month_cost,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            BASELINE_NOKKEL: self._baseline.som_lagret() if self._baseline else None,
            # Additiv nøkkel (v1.17.0). Eldre lagringsfiler mangler den og
            # faller tilbake til "vet ikke" ved oppstart, uten versjonsbump.
            "last_energy_increase": _iso_utc(self._last_energy_increase),
        }
        try:
            await self._store.async_save(data)
        except OSError:
            _LOGGER.warning("Failed to save storage data (disk full?)")
            return
        if _LOGGER.isEnabledFor(logging.DEBUG):
            # Redigeringen går gjennom hele filen, og filen er ikke liten.
            # Den skal bare koste noe når noen faktisk leser loggen.
            _LOGGER.debug("Lagret %s nøkler: %s", len(data), _uten_kildeidentitet(data))
