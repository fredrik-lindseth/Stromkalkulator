"""Data coordinator for Nettleie."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING, Any, cast

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AVGIFTSSONE_STANDARD,
    BOLIGTYPE_BOLIG,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SIKRINGSTRINN,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DAY_RATE_END_HOUR,
    DAY_RATE_START_HOUR,
    DEFAULT_DSO,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DOMAIN,
    DSO_LIST,
    ENOVA_AVGIFT,
    HELLIGDAGER_FASTE,
    MAX_ELAPSED_HOURS,
    MAX_ENERGY_DELTA_KWH,
    MAX_POWER_CLAMP_W,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    TPI_STALE_HOURS,
    UPDATE_INTERVAL_MINUTES,
    WEEKEND_WEEKDAY_START,
    _bevegelige_helligdager,
    compute_energiledd_inkl_mva,
    get_forbruksavgift,
    get_mva_sats,
    get_norgespris_inkl_mva,
    get_norgespris_max_kwh,
    get_stromstotte_max_kwh,
    get_stromstotte_terskel,
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
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .dso import DSOEntry, EnergileddPeriode, FastleddLineaer, KapasitetstrinnDict

_LOGGER = logging.getLogger(__name__)

# FEM_VEKTET_ÅR ser tolv måneder bakover. 52 uker holder vinduet i takt med
# ukesnøklene (mandagsdatoer) uten å måtte regne på månedslengder.
FEM_VEKTET_VINDU_DAGER = 364
FEM_VEKTET_ANTALL_TOPPER = 5


@dataclass
class DailyMaxEntry:
    """One day's maximum hourly average power."""

    kw: float
    hour: int | None = None


@dataclass
class WeeklyMaxEntry:
    """Én ukes høyeste timessnitt, for nettselskap som avregner årstopper.

    `dato` er dagen toppen falt på, og avgjør hvilken sesongvekt den får.
    Uken identifiseres av mandagens dato, som både sorterer kronologisk og lar
    oss kutte vinduet uten å regne ISO-uker om til datoer igjen.
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


class NettleieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Nettleie data."""

    entry: ConfigEntry
    power_sensor: str | None
    spot_price_sensor: str | None
    electricity_company_price_sensor: str | None
    export_power_sensor: str | None
    energy_sensor: str | None
    _last_tpi_kwh: float | None
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
    kapasitetstrinn: list[tuple[float, int]]
    fastledd_metode: str
    fastledd_lineaer: FastleddLineaer | None
    fastledd_sesongfaktor: dict[int, float]
    sikringstrinn_valg: str | None
    kapasitet_varsel_terskel: float
    _daily_max_power: dict[str, DailyMaxEntry]
    _weekly_max_power: dict[str, WeeklyMaxEntry]
    _current_hour_utcoffset: timedelta | None
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
    _monthly_cost: float
    _previous_month_export_kwh: float
    _previous_month_export_revenue: float
    _previous_month_cost: float
    _monthly_accumulated_cost: float
    _monthly_accumulated_cost_strom: float
    _monthly_accumulated_cost_energiledd: float
    _monthly_accumulated_cost_kapasitetsledd: float
    _store: Store[dict[str, Any]]
    _store_loaded: bool

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

        # Energiledd lagres i DSO som ren nettleie eks. mva og avgifter.
        # Bruker kan overstyre via config (CONF_ENERGILEDD_*), også eks. mva.
        # Vi beregner inkl-mva-verdier her én gang basert på avgiftssone slik
        # at sensorene kan bruke de ferdige verdiene direkte.
        #
        # Sesongprising: hvis DSO har `energiledd_perioder`, ignoreres CONF-
        # overstyring og periodene driver aktiv sats. CONF-overstyring gir
        # lite mening på en DSO som bytter pris flere ganger i året.
        raw_perioder: list[EnergileddPeriode] = self.dso.get("energiledd_perioder", [])
        if not raw_perioder:
            try:
                self.energiledd_dag_eks_mva = float(
                    entry.data.get(CONF_ENERGILEDD_DAG, self.dso["energiledd_dag_eks_mva"])
                )
            except (ValueError, TypeError):
                self.energiledd_dag_eks_mva = float(self.dso["energiledd_dag_eks_mva"])
            try:
                self.energiledd_natt_eks_mva = float(
                    entry.data.get(CONF_ENERGILEDD_NATT, self.dso["energiledd_natt_eks_mva"])
                )
            except (ValueError, TypeError):
                self.energiledd_natt_eks_mva = float(self.dso["energiledd_natt_eks_mva"])
        else:
            self.energiledd_dag_eks_mva = float(self.dso["energiledd_dag_eks_mva"])
            self.energiledd_natt_eks_mva = float(self.dso["energiledd_natt_eks_mva"])

        self.energiledd_dag = compute_energiledd_inkl_mva(
            self.energiledd_dag_eks_mva, self.avgiftssone
        )
        self.energiledd_natt = compute_energiledd_inkl_mva(
            self.energiledd_natt_eks_mva, self.avgiftssone
        )
        self._energiledd_perioder_inkl = [
            (
                p["fra"],
                p["til"],
                compute_energiledd_inkl_mva(p["dag_eks_mva"], self.avgiftssone),
                compute_energiledd_inkl_mva(p["natt_eks_mva"], self.avgiftssone),
            )
            for p in raw_perioder
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
        # Nettselskapet bruker maks timesforbruk (kWh/time = snitt-kW per klokke-time),
        # ikke instantan effekt. Vi akkumulerer energi per klokke-time og bruker den
        # høyeste timen som dagens topp.
        self._daily_max_power: dict[str, DailyMaxEntry] = {}
        # Ukestopper over løpende tolv måneder. Vedlikeholdes kun for
        # nettselskap som avregner årstopper; ellers ville 72 av 73 brukere
        # lagre data ingen leser.
        self._weekly_max_power: dict[str, WeeklyMaxEntry] = {}
        self._current_hour_energy: float = 0.0
        self._current_hour: int = dt_util.now().hour
        # Sporing av aware-tidssone for hour-bucket: ved høst-DST skjer time
        # 02:xx to ganger fysisk (CEST -> CET). Vi må flushe bucketen mellom
        # passeringene. Hvis now er naiv blir denne None og adferden er som
        # før (kun .hour-sammenligning).
        self._current_hour_utcoffset: timedelta | None = dt_util.now().utcoffset()
        self._current_month = dt_util.now().strftime("%Y-%m")

        # Track energy consumption for monthly utility meter
        self._monthly_consumption = ConsumptionData()
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._last_update = None
        # Siste kumulative tpi-verdi vi har sett, brukt for delta-akkumulasjon
        # når energy_sensor er konfigurert. None = første poll etter oppstart.
        self._last_tpi_kwh = None

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
        self._monthly_cost = 0.0
        self._previous_month_export_kwh = 0.0
        self._previous_month_export_revenue = 0.0
        self._previous_month_cost = 0.0

        # Akkumulert kostnad for Energy Dashboard (stat_cost)
        self._monthly_accumulated_cost = 0.0
        self._monthly_accumulated_cost_strom = 0.0
        self._monthly_accumulated_cost_energiledd = 0.0
        self._monthly_accumulated_cost_kapasitetsledd = 0.0

        # Daily cost accumulation
        self._daily_cost = 0.0
        self._current_date = dt_util.now().strftime("%Y-%m-%d")

        # Cache last known prices (survives brief sensor outages, max 2 timer)
        self._last_electricity_company_price: float | None = None
        self._last_electricity_company_price_time: datetime | None = None
        self._last_spot_price: float | None = None
        self._last_spot_price_time: datetime | None = None

        # Persistent storage - keyed by entry_id for multi-instance isolation
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self._store_loaded = False

    def _read_sensor_float(
        self, entity_id: str | None, *, clamp_max: int | None = MAX_POWER_CLAMP_W, clamp_min: float = 0.0
    ) -> float:
        """Read a HA sensor state as a finite float, returning 0 if unavailable.

        Negative avlesninger klippes til clamp_min (default 0). power_sensor er
        unidireksjonell import (OBIS 1.7.0), eksport skal gå via export_power_sensor,
        så en negativ effektverdi er sensorstøy eller feilkonfig og skal ikke telle.
        """
        if not entity_id:
            return 0.0
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return 0.0
        if not math.isfinite(value):
            return 0.0
        if clamp_max is not None and value > clamp_max:
            _LOGGER.warning("Sensor %s reading %s exceeds clamp %s, rejecting", entity_id, value, clamp_max)
            return 0.0
        if value < clamp_min:
            return clamp_min
        return value

    def _avg_in_lower_tier(self, avg_power: float, threshold: float) -> bool:
        """Om avg_power hører til trinnet under denne terskelen."""
        return grunnlag_i_lavere_trinn(avg_power, threshold, self._terskel_inkludert)

    def _read_price_sensor(self, entity_id: str | None) -> float | None:
        """Read a price sensor, caching last known value. Returns None if never available."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                raw = float(state.state)
            except (ValueError, TypeError):
                raw = None
            if raw is not None and math.isfinite(raw):
                return raw
        return None

    def _compute_energy_delta(self) -> float:
        """Beregn forbruk siden forrige poll fra kumulativ energi-sensor.

        Leser energy_sensor (kWh) og returnerer differansen mot forrige avlesning.
        Negative deltas (counter reset, meter-bytte) og urealistisk store deltas
        ignoreres. Oppdaterer _last_tpi_kwh som side-effekt. Hvis sensoren er
        unavailable beholdes _last_tpi_kwh slik at neste poll kan plukke opp.
        """
        if not self.energy_sensor:
            return 0.0
        state = self.hass.states.get(self.energy_sensor)
        if not state or state.state in ("unknown", "unavailable"):
            return 0.0
        try:
            current_tpi = float(state.state)
        except (ValueError, TypeError):
            return 0.0
        if not math.isfinite(current_tpi) or current_tpi <= 0:
            return 0.0

        delta = 0.0
        if self._last_tpi_kwh is not None and self._last_tpi_kwh > 0:
            raw_delta = current_tpi - self._last_tpi_kwh
            if 0 < raw_delta < MAX_ENERGY_DELTA_KWH:
                delta = raw_delta
            elif raw_delta < 0:
                _LOGGER.warning(
                    "energy_sensor %s gikk nedover (%.3f -> %.3f). Counter reset eller meter-bytte? Ignorerer delta.",
                    self.energy_sensor,
                    self._last_tpi_kwh,
                    current_tpi,
                )
            elif raw_delta >= MAX_ENERGY_DELTA_KWH:
                _LOGGER.warning(
                    "energy_sensor %s delta %.1f kWh > %.0f kWh. Ignorerer som outlier.",
                    self.energy_sensor,
                    raw_delta,
                    MAX_ENERGY_DELTA_KWH,
                )
        self._last_tpi_kwh = current_tpi
        return delta

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
            self._previous_month_cost = self._monthly_cost

            # Flush siste times akkumulator til daily_max_power før arkivering
            if self._current_hour_energy > 0:
                yesterday = (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
                self._registrer_timesmaks(yesterday, self._current_hour_energy, self._current_hour)

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
        self._current_hour_energy = 0.0
        self._current_hour = now.hour
        self._current_hour_utcoffset = now.utcoffset()
        self._monthly_consumption = ConsumptionData()
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._monthly_export_kwh = 0.0
        self._monthly_export_revenue = 0.0
        self._monthly_cost = 0.0
        self._monthly_accumulated_cost = 0.0
        self._monthly_accumulated_cost_strom = 0.0
        self._monthly_accumulated_cost_energiledd = 0.0
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

        # Raise early if sensor entities are completely missing (not registered)
        power_state = self.hass.states.get(self.power_sensor)
        spot_state = self.hass.states.get(self.spot_price_sensor)
        if power_state is None:
            raise UpdateFailed(f"Power sensor entity not found: {self.power_sensor}")
        if spot_state is None:
            raise UpdateFailed(f"Spot price sensor entity not found: {self.spot_price_sensor}")

        # Read sensor values
        current_power_w = self._read_sensor_float(self.power_sensor)
        current_power_kw = current_power_w / 1000

        # Beregn tid siden forrige oppdatering (felles for forbruk og eksport)
        elapsed_hours = 0.0
        if self._last_update is not None:
            elapsed_hours = (now - self._last_update).total_seconds() / 3600
            elapsed_hours = max(0.0, min(elapsed_hours, MAX_ELAPSED_HOURS))

        # Akkumuler energi FØRST, slik at siste syklus havner i riktig måned.
        # Med energy_sensor: bruk delta fra kumulativ kWh-teller (eksakt mot
        # faktura). Uten: fall tilbake til p * elapsed-Riemann-sum.
        energy_kwh = 0.0
        dirty = False
        if self.energy_sensor:
            energy_kwh = self._compute_energy_delta()
        elif elapsed_hours > 0 and current_power_kw > 0:
            energy_kwh = current_power_kw * elapsed_hours

        if energy_kwh > 0:
            tariff = "dag" if self._is_day_rate(now) else "natt"
            if tariff == "dag":
                self._monthly_consumption.dag += energy_kwh
            else:
                self._monthly_consumption.natt += energy_kwh
            dirty = True

        # Eksport-akkumulering (plusskunder med solceller)
        export_energy_kwh = 0.0
        if self.export_power_sensor and elapsed_hours > 0:
            export_power_w = self._read_sensor_float(self.export_power_sensor)
            export_power_kw = export_power_w / 1000
            if export_power_kw > 0:
                export_energy_kwh = export_power_kw * elapsed_hours
                self._monthly_export_kwh += export_energy_kwh
                dirty = True

        self._last_update = now

        # Update daily max (basert på timessnitt, ikke instantan effekt)
        today_str = now.strftime("%Y-%m-%d")

        # Reset daily cost at date change
        if today_str != self._current_date:
            self._daily_cost = 0.0
            self._current_date = today_str

        # Akkumuler energi i inneværende klokke-time
        current_hour = now.hour
        current_utcoffset = now.utcoffset()
        previous_hour = self._current_hour
        # Sammenlign både time og utcoffset for å fange høst-DST: ved
        # gjentatt 02:xx (CEST -> CET) er .hour lik, men utcoffset skifter
        # fra +02:00 til +01:00. Naive datetimes har utcoffset()==None i
        # begge tilfeller, så naive tester beholder eksisterende adferd.
        hour_changed = current_hour != self._current_hour
        offset_changed = (
            current_utcoffset is not None
            and self._current_hour_utcoffset is not None
            and current_utcoffset != self._current_hour_utcoffset
        )
        if hour_changed or offset_changed:
            # Timen har endret seg -- den forrige timen er komplett.
            # _current_hour_energy (kWh over 1 time) = gjennomsnittlig kW for den timen.
            if self._current_hour_energy > 0:
                prev_date = self._current_date if current_hour != 0 else (
                    (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
                )
                if self._registrer_timesmaks(prev_date, self._current_hour_energy, previous_hour):
                    dirty = True
            self._current_hour_energy = 0.0
            self._current_hour = current_hour
            self._current_hour_utcoffset = current_utcoffset

        # Legg til denne oppdateringens energi i timens akkumulator
        self._current_hour_energy += energy_kwh

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

        # Calculate energiledd
        energiledd = self._get_energiledd(now)

        # Get spot price (cache last known value, max 2 timer for kostnadakkumulering)
        raw_spot = self._read_price_sensor(self.spot_price_sensor)
        if raw_spot is not None:
            spot_price_raw = raw_spot
            self._last_spot_price = spot_price_raw
            self._last_spot_price_time = now
            spot_price_valid = True
        elif (
            self._last_spot_price is not None
            and self._last_spot_price_time is not None
            and (now - self._last_spot_price_time) < _SPOT_CACHE_MAX_AGE
        ):
            spot_price_raw = self._last_spot_price
            spot_price_valid = True
        else:
            spot_price_raw = 0.0
            spot_price_valid = False

        # Normaliser til inkl. mva. Resten av kjeden behandler spot_price som inkl. mva,
        # samme enhet som STROMSTOTTE_LEVEL og NORGESPRIS_INKL_MVA. Se incident 004.
        mva_sats_for_spot = get_mva_sats(self.avgiftssone)
        if self.spotpris_inkl_mva:
            spot_price = spot_price_raw
            spot_price_eks_mva = (
                spot_price_raw / (1 + mva_sats_for_spot) if mva_sats_for_spot > 0 else spot_price_raw
            )
        else:
            spot_price_eks_mva = spot_price_raw
            spot_price = spot_price_raw * (1 + mva_sats_for_spot)

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

        # Calculate fastledd per kWh
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

        if energy_kwh > 0 and spot_price_valid:
            self._monthly_norgespris_diff += kroner_spart_per_kwh * energy_kwh
            # Kompensasjons-sensoren reflekterer kun timer under Norgespris-taket.
            # Over taket betaler kunden faktisk spot, så det er ingen kompensasjon
            # å regne på. Samme tak-logikk som total_price (linje 615-624).
            # Kjent begrensning: hvis taket nås midt i en time, telles hele timen
            # i feil bucket. Effekt < 1 min forbruk pga 1-min polling.
            if not norgespris_over_tak:
                self._monthly_norgespris_compensation += (norgespris - spot_price) * energy_kwh
            self._daily_cost += total_price * energy_kwh
            self._monthly_cost += total_price * energy_kwh

        # Akkumuler kostnad for Energy Dashboard (stat_cost)
        elapsed_seconds = elapsed_hours * 3600
        if energy_kwh > 0:
            # Energiledd er kjent uavhengig av spotpris
            self._monthly_accumulated_cost_energiledd += energy_kwh * energiledd
            # Strømdelen er kjent for Norgespris under tak; ellers krever den valid spot
            if self.har_norgespris and not norgespris_over_tak:
                self._monthly_accumulated_cost_strom += energy_kwh * norgespris
            elif spot_price_valid:
                if self.har_norgespris:
                    strom_pris = spot_price
                else:
                    strom_pris = spot_price - stromstotte
                self._monthly_accumulated_cost_strom += energy_kwh * strom_pris

        if elapsed_seconds > 0:
            seconds_in_month = dim * 24 * 3600
            delta_kap = elapsed_seconds * (kapasitetsledd / seconds_in_month)
            self._monthly_accumulated_cost_kapasitetsledd += delta_kap
            dirty = True

        self._monthly_accumulated_cost = (
            self._monthly_accumulated_cost_strom
            + self._monthly_accumulated_cost_energiledd
            + self._monthly_accumulated_cost_kapasitetsledd
        )

        # Eksportinntekt: kraftleverandører betaler plusskunder spotpris eks. mva
        # (mva er ikke aktuelt på salg fra privatperson). Se accountant-funn #1.
        if export_energy_kwh > 0 and spot_price_valid:
            self._monthly_export_revenue += spot_price_eks_mva * export_energy_kwh

        # Månedsskifte: arkiver ETTER at all energi og kostnad er akkumulert,
        # slik at siste syklus havner i riktig måned.
        current_month_str = now.strftime("%Y-%m")
        if current_month_str != self._current_month:
            await self._handle_month_rollover(now)

        # Get electricity company price if configured
        electricity_company_price = None
        electricity_company_total = None
        if self.electricity_company_price_sensor:
            raw_ec = self._read_price_sensor(self.electricity_company_price_sensor)
            if raw_ec is not None:
                electricity_company_price = raw_ec
                self._last_electricity_company_price = raw_ec
                self._last_electricity_company_price_time = now
            elif (
                self._last_electricity_company_price is not None
                and self._last_electricity_company_price_time is not None
                and (now - self._last_electricity_company_price_time) < _SPOT_CACHE_MAX_AGE
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
            "energiledd": round(kw["energiledd"], 4),
            "energiledd_dag": aktiv_dag,
            "energiledd_natt": aktiv_natt,
            "energiledd_perioder": perioder_meta,
            "aktiv_energiledd_periode": aktiv_periode,
            "kapasitetsledd": kw["kapasitetsledd"],
            "kapasitetstrinn_nummer": kw["trinn_nummer"],
            "kapasitetstrinn_intervall": kw["trinn_intervall"],
            "kapasitetsledd_per_kwh": round(kw["fastledd_per_kwh"], 4),
            "fastledd_metode": self.fastledd_metode,
            "fastledd_grunnlag_kw": round(kw["fastledd_grunnlag"], 2),
            "fastledd_mangler_sikringsvalg": self._mangler_sikringsvalg(),
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
            "current_power_kw": round(kw["current_power_kw"], 2),
            "avg_top_3_kw": round(kw["avg_power"], 2),
            "top_3_days": top_3,
            "is_day_rate": self._is_day_rate(kw["now"]),
            "dso": self.dso["name"],
            "har_norgespris": self.har_norgespris,
            "avgiftssone": self.avgiftssone,
            "monthly_consumption_dag_kwh": round(self._monthly_consumption.dag, 3),
            "monthly_consumption_natt_kwh": round(self._monthly_consumption.natt, 3),
            "monthly_consumption_total_kwh": round(self._monthly_consumption.total, 3),
            "previous_month_consumption_dag_kwh": round(self._previous_month_consumption.dag, 3),
            "previous_month_consumption_natt_kwh": round(self._previous_month_consumption.natt, 3),
            "previous_month_consumption_total_kwh": round(self._previous_month_consumption.total, 3),
            "previous_month_top_3": prev_top_3,
            "previous_month_avg_top_3_kw": round(
                sum(e.kw for e in prev_top_3.values()) / max(len(prev_top_3), 1), 2,
            ) if prev_top_3 else 0.0,
            "previous_month_name": self._previous_month_name,
            "previous_month_kapasitetsledd": self._previous_month_kapasitetsledd,
            "previous_month_kapasitetstrinn": self._previous_month_kapasitetstrinn,
            "previous_month_energiledd_dag": self._previous_month_energiledd_dag,
            "previous_month_energiledd_natt": self._previous_month_energiledd_natt,
            "stromstotte_tak_naadd": kw["stromstotte_max"] == 0 or kw["monthly_total_kwh"] >= kw["stromstotte_max"],
            "norgespris_over_tak": kw["norgespris_over_tak"],
            "boligtype": self.boligtype,
            "stromstotte_gjenstaaende_kwh": round(kw["stromstotte_gjenstaaende"], 1),
            "margin_neste_trinn_kw": kw["margin_neste_trinn"],
            "neste_trinn_pris": kw["neste_trinn_pris"],
            "kapasitet_varsel": kw["kapasitet_varsel"],
            "monthly_norgespris_diff_kr": round(self._monthly_norgespris_diff, 2),
            "previous_month_norgespris_diff_kr": round(self._previous_month_norgespris_diff, 2),
            "monthly_norgespris_compensation_kr": round(self._monthly_norgespris_compensation, 2),
            "previous_month_norgespris_compensation_kr": round(self._previous_month_norgespris_compensation, 2),
            "daily_cost_kr": round(self._daily_cost, 2),
            "monthly_accumulated_cost_kr": round(self._monthly_accumulated_cost, 4),
            "monthly_accumulated_cost_strom_kr": round(self._monthly_accumulated_cost_strom, 4),
            "monthly_accumulated_cost_energiledd_kr": round(self._monthly_accumulated_cost_energiledd, 4),
            "monthly_accumulated_cost_kapasitetsledd_kr": round(self._monthly_accumulated_cost_kapasitetsledd, 4),
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
        """Hold ukens høyeste sesongvektede time. Nøkkelen er mandagens dato.

        Sammenligningen skjer på vektet verdi, ikke rå kW, fordi nettselskapet
        vekter før det plukker ukestoppen. Det gir bare utslag i uker som krysser
        et månedsskifte, men det er de ukene som ellers ville blitt feil.
        """
        try:
            dag = date.fromisoformat(dato)
        except ValueError:
            _LOGGER.warning("Ugyldig dato for ukesmaks: %s", dato)
            return False
        nokkel = (dag - timedelta(days=dag.weekday())).isoformat()
        forrige = self._weekly_max_power.get(nokkel)
        if forrige is not None and kw * self._sesongvekt(dag.month) <= self._vektet(forrige):
            return False
        self._weekly_max_power[nokkel] = WeeklyMaxEntry(kw=kw, dato=dato, hour=hour)
        return True

    def _vektet(self, entry: WeeklyMaxEntry) -> float:
        """Ukestoppens sesongvektede effekt."""
        try:
            maaned = date.fromisoformat(entry.dato).month
        except ValueError:
            return entry.kw
        return entry.kw * self._sesongvekt(maaned)

    def _prune_ukesmaks(self, now: datetime) -> bool:
        """Kast ukestopper som har falt ut av tolvmånedersvinduet."""
        grense = (now.date() - timedelta(days=FEM_VEKTET_VINDU_DAGER)).isoformat()
        utgaatt = [nokkel for nokkel in self._weekly_max_power if nokkel < grense]
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
            vektet = sorted(
                (self._vektet(e) for e in self._weekly_max_power.values()), reverse=True
            )[:FEM_VEKTET_ANTALL_TOPPER]
            if not vektet:
                return 0.0
            # Nettselskapet fakturerer effekten med to desimaler.
            return round(sum(vektet) / len(vektet), 2)
        top_3 = [e.kw for e in self._get_top_3_days().values()]
        if not top_3:
            return 0.0
        return sum(top_3) / 3 if len(top_3) >= 3 else sum(top_3) / len(top_3)

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

        return finn_kapasitetstrinn(
            self.kapasitetstrinn, grunnlag_kw, self._terskel_inkludert
        )

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

    def _get_aktive_energileddsatser(self, now: datetime) -> tuple[float, float]:
        """Returner (dag, natt) energileddsatser inkl. avgifter for nåværende dato.

        For DSO-er med sesongprising slås det opp i `energiledd_perioder`.
        Faller tilbake til `self.energiledd_dag/natt` hvis ingen periode
        treffer (skal ikke skje hvis periodene dekker hele året, men er en
        trygg fallback).
        """
        if not self._energiledd_perioder_inkl:
            return self.energiledd_dag, self.energiledd_natt
        mm_dd = now.strftime("%m-%d")
        for fra, til, dag, natt in self._energiledd_perioder_inkl:
            if fra <= til:
                if fra <= mm_dd <= til:
                    return dag, natt
            elif mm_dd >= fra or mm_dd <= til:
                return dag, natt
        return self.energiledd_dag, self.energiledd_natt

    def _get_energiledd(self, now: datetime) -> float:
        """Get energiledd based on time of day."""
        dag, natt = self._get_aktive_energileddsatser(now)
        return dag if self._is_day_rate(now) else natt

    def _is_day_rate(self, now: datetime) -> bool:
        """Check if current time is day rate."""
        is_night = now.hour < DAY_RATE_START_HOUR or now.hour >= DAY_RATE_END_HOUR

        if not self._helg_som_natt:
            return not is_night

        date_mm_dd = now.strftime("%m-%d")
        date_yyyy_mm_dd = now.strftime("%Y-%m-%d")

        is_fixed_holiday = date_mm_dd in HELLIGDAGER_FASTE
        is_dso_extra_holiday = date_mm_dd in self._helligdager_ekstra
        bevegelige = _bevegelige_helligdager(now.year)
        is_moving_holiday = date_yyyy_mm_dd in bevegelige
        is_weekend = now.weekday() >= WEEKEND_WEEKDAY_START

        return not (
            is_fixed_holiday
            or is_dso_extra_holiday
            or is_moving_holiday
            or is_weekend
            or is_night
        )

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

        if data:
            try:
                self._daily_max_power = self._validate_daily_max_power(data.get("daily_max_power", {}))
                self._weekly_max_power = self._validate_weekly_max_power(
                    data.get("weekly_max_power", {})
                )
                self._monthly_consumption = self._validate_consumption(
                    data.get("monthly_consumption", {"dag": 0.0, "natt": 0.0})
                )
                self._monthly_norgespris_diff = self._validate_float(
                    data.get("monthly_norgespris_diff", 0.0)
                )
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
                self._previous_month_kapasitetstrinn = str(
                    data.get("previous_month_kapasitetstrinn", "")
                )
                self._previous_month_energiledd_dag = self._validate_float(
                    data.get("previous_month_energiledd_dag", self.energiledd_dag)
                )
                self._previous_month_energiledd_natt = self._validate_float(
                    data.get("previous_month_energiledd_natt", self.energiledd_natt)
                )
                self._daily_cost = self._validate_float(data.get("daily_cost", 0.0))
                # Eksport-data
                self._monthly_export_kwh = self._validate_float(
                    data.get("monthly_export_kwh", 0.0)
                )
                self._monthly_export_revenue = self._validate_float(
                    data.get("monthly_export_revenue", 0.0)
                )
                self._monthly_cost = self._validate_float(
                    data.get("monthly_cost", 0.0)
                )
                self._monthly_accumulated_cost = self._validate_float(
                    data.get("monthly_accumulated_cost", 0.0)
                )
                self._monthly_accumulated_cost_strom = self._validate_float(
                    data.get("monthly_accumulated_cost_strom", 0.0)
                )
                self._monthly_accumulated_cost_energiledd = self._validate_float(
                    data.get("monthly_accumulated_cost_energiledd", 0.0)
                )
                self._monthly_accumulated_cost_kapasitetsledd = self._validate_float(
                    data.get("monthly_accumulated_cost_kapasitetsledd", 0.0)
                )
                self._previous_month_export_kwh = self._validate_float(
                    data.get("previous_month_export_kwh", 0.0)
                )
                self._previous_month_export_revenue = self._validate_float(
                    data.get("previous_month_export_revenue", 0.0)
                )
                self._previous_month_cost = self._validate_float(
                    data.get("previous_month_cost", 0.0)
                )
                self._current_date = data.get("current_date", dt_util.now().strftime("%Y-%m-%d"))
                self._current_hour_energy = self._validate_float(
                    data.get("current_hour_energy", 0.0)
                )
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
                stored_last_update = data.get("last_update")
                last_update_age_hours: float | None = None
                if stored_last_update:
                    try:
                        loaded_last_update = datetime.fromisoformat(stored_last_update)
                        # Bare gjenopprett hvis gapet er innenfor MAX_ELAPSED_HOURS.
                        # Lengre gap betyr restart-pause; da vil vi heller starte friskt
                        # (None) enn å akkumulere current_power * hele restart-vinduet.
                        last_update_age_hours = (dt_util.now() - loaded_last_update).total_seconds() / 3600
                        if 0 <= last_update_age_hours <= MAX_ELAPSED_HOURS:
                            self._last_update = loaded_last_update
                    except (ValueError, TypeError) as err:
                        _LOGGER.warning(
                            "Kunne ikke lese last_update fra storage: %s", err
                        )

                # _last_tpi_kwh: gjenopprett kun hvis ferskt nok. Eldre verdi gir
                # gigantisk delta ved første poll (alt forbruk siden restart).
                # Uten last_update kan vi ikke bedømme alder -> drop.
                stored_tpi = data.get("last_tpi_kwh")
                if stored_tpi is not None and last_update_age_hours is not None:
                    try:
                        tpi_val = float(stored_tpi)
                    except (ValueError, TypeError):
                        tpi_val = None
                    if (
                        tpi_val is not None
                        and math.isfinite(tpi_val)
                        and tpi_val > 0
                        and last_update_age_hours <= TPI_STALE_HOURS
                    ):
                        self._last_tpi_kwh = tpi_val
            except (TypeError, KeyError, AttributeError) as err:
                _LOGGER.warning("Corrupt storage data, using defaults: %s", err)
            _LOGGER.debug("Loaded stored data: %s", self._daily_max_power)

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
            "daily_max_power": self._serialize_daily_max(self._daily_max_power),
            "weekly_max_power": {
                k: {"kw": v.kw, "dato": v.dato, "hour": v.hour}
                for k, v in self._weekly_max_power.items()
            },
            "monthly_consumption": {"dag": self._monthly_consumption.dag, "natt": self._monthly_consumption.natt},
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
            "previous_month_export_kwh": self._previous_month_export_kwh,
            "previous_month_export_revenue": self._previous_month_export_revenue,
            "previous_month_cost": self._previous_month_cost,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "last_tpi_kwh": self._last_tpi_kwh,
        }
        try:
            await self._store.async_save(data)
        except OSError:
            _LOGGER.warning("Failed to save storage data (disk full?)")
            return
        _LOGGER.debug("Saved data: %s", data)
