"""Data coordinator for Nettleie."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
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
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    DAY_RATE_END_HOUR,
    DAY_RATE_START_HOUR,
    DEFAULT_DSO,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DOMAIN,
    DSO_LIST,
    ENOVA_AVGIFT,
    HELLIGDAGER_FASTE,
    MAX_ELAPSED_HOURS,
    MAX_POWER_CLAMP_W,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    UPDATE_INTERVAL_MINUTES,
    WEEKEND_WEEKDAY_START,
    _bevegelige_helligdager,
    get_forbruksavgift,
    get_mva_sats,
    get_norgespris_inkl_mva,
    get_norgespris_max_kwh,
    get_stromstotte_max_kwh,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .dso import DSOEntry

_LOGGER = logging.getLogger(__name__)


@dataclass
class DailyMaxEntry:
    """One day's maximum hourly average power."""

    kw: float
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


class NettleieCoordinator(DataUpdateCoordinator[dict[str, Any]]):  # type: ignore[misc]
    """Coordinator for Nettleie data."""

    entry: ConfigEntry
    power_sensor: str | None
    spot_price_sensor: str | None
    electricity_company_price_sensor: str | None
    export_power_sensor: str | None
    dso: DSOEntry
    _dso_id: str
    avgiftssone: str
    har_norgespris: bool
    boligtype: str
    energiledd_dag: float
    energiledd_natt: float
    kapasitetstrinn: list[tuple[float, int]]
    kapasitet_varsel_terskel: float
    _daily_max_power: dict[str, DailyMaxEntry]
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

        # Get DSO config
        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self.dso = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])
        self._dso_id = dso_id

        # Get avgiftssone from config
        self.avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

        # Get Norgespris setting from config
        self.har_norgespris = entry.data.get(CONF_HAR_NORGESPRIS, False)

        # Get boligtype from config (default: bolig for backward compatibility)
        self.boligtype = entry.data.get(CONF_BOLIGTYPE, BOLIGTYPE_BOLIG)

        # Get energiledd from config (allows override)
        try:
            self.energiledd_dag = float(entry.data.get(CONF_ENERGILEDD_DAG, self.dso["energiledd_dag"]))
        except (ValueError, TypeError):
            self.energiledd_dag = float(self.dso["energiledd_dag"])
        try:
            self.energiledd_natt = float(entry.data.get(CONF_ENERGILEDD_NATT, self.dso["energiledd_natt"]))
        except (ValueError, TypeError):
            self.energiledd_natt = float(self.dso["energiledd_natt"])

        # Get kapasitetstrinn from DSO
        # Normalize: some DSOs (e.g. Barents Nett) use dict format {"min", "max", "pris"}
        # Convert to standard tuple format (kW_threshold, NOK_per_month)
        raw_trinn = self.dso["kapasitetstrinn"]
        if raw_trinn and isinstance(raw_trinn[0], dict):
            self.kapasitetstrinn = [(entry["max"], entry["pris"]) for entry in raw_trinn]
        else:
            self.kapasitetstrinn = cast("list[tuple[float, int]]", raw_trinn)

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
        self._current_hour_energy: float = 0.0
        self._current_hour: int = dt_util.now().hour
        self._current_month = dt_util.now().strftime("%Y-%m")

        # Track energy consumption for monthly utility meter
        self._monthly_consumption = ConsumptionData()
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._last_update = None

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

        # Cache last known prices (survives brief sensor outages)
        self._last_electricity_company_price: float | None = None
        self._last_spot_price: float | None = None

        # Persistent storage - keyed by entry_id for multi-instance isolation
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self._store_loaded = False

    def _read_sensor_float(
        self, entity_id: str | None, *, clamp_max: int | None = MAX_POWER_CLAMP_W
    ) -> float:
        """Read a HA sensor state as a finite float, returning 0 if unavailable."""
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
        return value

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

    async def _handle_month_rollover(self, now: datetime) -> None:
        """Archive previous month's data and reset accumulators."""
        self._previous_month_consumption = self._monthly_consumption.copy()
        prev_month_date = now.replace(day=1) - timedelta(days=1)
        self._previous_month_name = self._format_month_name(prev_month_date)

        self._previous_month_norgespris_diff = self._monthly_norgespris_diff
        self._previous_month_norgespris_compensation = self._monthly_norgespris_compensation

        self._previous_month_export_kwh = self._monthly_export_kwh
        self._previous_month_export_revenue = self._monthly_export_revenue
        self._previous_month_cost = self._monthly_cost

        # Archive energiledd rates for accurate previous-month calculations
        self._previous_month_energiledd_dag = self.energiledd_dag
        self._previous_month_energiledd_natt = self.energiledd_natt

        # Flush siste times akkumulator til daily_max_power før arkivering
        if self._current_hour_energy > 0:
            yesterday = (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
            old_entry = self._daily_max_power.get(yesterday)
            old_max = old_entry.kw if old_entry else 0
            if self._current_hour_energy > old_max:
                self._daily_max_power[yesterday] = DailyMaxEntry(
                    kw=round(self._current_hour_energy, 3), hour=self._current_hour
                )

        # Compute kapasitetsledd for previous month from top_3 before reset
        prev_top_3 = self._get_top_3_days()
        self._previous_month_top_3 = prev_top_3
        if prev_top_3:
            kw_values = [entry.kw for entry in prev_top_3.values()]
            prev_avg = sum(kw_values) / len(kw_values)
            prev_kap, _, prev_trinn = self._get_kapasitetsledd(prev_avg)
            self._previous_month_kapasitetsledd = prev_kap
            self._previous_month_kapasitetstrinn = prev_trinn
        else:
            self._previous_month_kapasitetsledd = 0
            self._previous_month_kapasitetstrinn = ""

        # Reset current month data
        self._daily_max_power = {}
        self._current_hour_energy = 0.0
        self._current_hour = now.hour
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
    def _calculate_stromstotte(spot_price: float, monthly_total_kwh: float, boligtype: str) -> float:
        """Calculate strømstøtte per kWh.

        Forskrift § 5: 90% av spotpris over 96,25 øre inkl. mva (2026).
        Norgespris-kunder mottar ikke strømstøtte, men vi beregner den
        alltid slik at sammenligning mellom Norgespris og spot+støtte fungerer.
        """
        stromstotte_max = get_stromstotte_max_kwh(boligtype)
        if stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max:
            return 0.0
        if spot_price > STROMSTOTTE_LEVEL:
            return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
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

        # Reset at new month
        current_month_str = now.strftime("%Y-%m")
        if current_month_str != self._current_month:
            await self._handle_month_rollover(now)

        # Read sensor values
        current_power_w = self._read_sensor_float(self.power_sensor)
        current_power_kw = current_power_w / 1000

        # Beregn tid siden forrige oppdatering (felles for forbruk og eksport)
        elapsed_hours = 0.0
        if self._last_update is not None:
            elapsed_hours = (now - self._last_update).total_seconds() / 3600
            elapsed_hours = max(0.0, min(elapsed_hours, MAX_ELAPSED_HOURS))

        # Calculate energy consumption since last update (riemann sum)
        energy_kwh = 0.0
        dirty = False
        if elapsed_hours > 0 and current_power_kw > 0:
            energy_kwh = current_power_kw * elapsed_hours
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
        previous_hour = self._current_hour
        if current_hour != self._current_hour:
            # Timen har endret seg -- den forrige timen er komplett.
            # _current_hour_energy (kWh over 1 time) = gjennomsnittlig kW for den timen.
            if self._current_hour_energy > 0:
                prev_date = self._current_date if current_hour != 0 else (
                    (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
                )
                old_entry = self._daily_max_power.get(prev_date)
                old_max = old_entry.kw if old_entry else 0
                if self._current_hour_energy > old_max:
                    self._daily_max_power[prev_date] = DailyMaxEntry(
                        kw=round(self._current_hour_energy, 3), hour=previous_hour
                    )
                    dirty = True
            self._current_hour_energy = 0.0
            self._current_hour = current_hour

        # Legg til denne oppdateringens energi i timens akkumulator
        self._current_hour_energy += energy_kwh

        # Get top 3 days
        top_3 = self._get_top_3_days()
        top_3_kw_values = [entry.kw for entry in top_3.values()]
        avg_power = sum(top_3_kw_values) / 3 if len(top_3) >= 3 else sum(top_3_kw_values) / max(len(top_3), 1)

        # Calculate capacity tier
        kapasitetsledd, trinn_nummer, trinn_intervall = self._get_kapasitetsledd(avg_power)

        # Calculate margin to next tier
        margin_neste_trinn = 0.0
        neste_trinn_pris = kapasitetsledd
        for i, (threshold, _price) in enumerate(self.kapasitetstrinn):
            if avg_power <= threshold:
                if i + 1 < len(self.kapasitetstrinn):
                    margin_neste_trinn = round(threshold - avg_power, 2)
                    neste_trinn_pris = self.kapasitetstrinn[i + 1][1]
                break

        # If in the highest tier (no next tier), don't warn
        if margin_neste_trinn == 0.0 and neste_trinn_pris == kapasitetsledd:
            kapasitet_varsel = False
        else:
            kapasitet_varsel = margin_neste_trinn < self.kapasitet_varsel_terskel

        # Calculate energiledd
        energiledd = self._get_energiledd(now)

        # Get spot price (cache last known value to survive brief sensor outages)
        raw_spot = self._read_price_sensor(self.spot_price_sensor)
        if raw_spot is not None:
            spot_price = raw_spot
            self._last_spot_price = spot_price
        elif self._last_spot_price is not None:
            spot_price = self._last_spot_price
        else:
            spot_price = 0.0

        # Calculate strømstøtte
        monthly_total_kwh = self._monthly_consumption.total
        stromstotte = self._calculate_stromstotte(spot_price, monthly_total_kwh, self.boligtype)
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
        if norgespris_over_tak:
            total_pris_norgespris = spot_price + energiledd + fastledd_per_kwh
        else:
            total_pris_norgespris = norgespris + energiledd + fastledd_per_kwh

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
        forbruksavgift = get_forbruksavgift(self.avgiftssone, now.month)
        forbruksavgift_inkl_mva = forbruksavgift * (1 + mva_sats)
        enova_inkl_mva = ENOVA_AVGIFT * (1 + mva_sats)
        offentlige_avgifter = forbruksavgift_inkl_mva + enova_inkl_mva

        # NB: energiledd fra dso.py inkluderer allerede forbruksavgift + enova
        total_price_inkl_avgifter = total_price

        # Kroner spart/tapt per kWh (sammenligning)
        if self.har_norgespris:
            spot_total_etter_stotte = spot_price - stromstotte + energiledd + fastledd_per_kwh
            kroner_spart_per_kwh = total_price - spot_total_etter_stotte
        else:
            kroner_spart_per_kwh = total_price - total_pris_norgespris

        # Accumulate monthly comparisons and costs
        if energy_kwh > 0:
            if self.har_norgespris:
                diff_per_kwh = spot_total_etter_stotte - total_price
            else:
                diff_per_kwh = total_pris_norgespris - total_price
            self._monthly_norgespris_diff += diff_per_kwh * energy_kwh
            self._monthly_norgespris_compensation += (norgespris - spot_price) * energy_kwh
            self._daily_cost += total_price * energy_kwh
            self._monthly_cost += total_price * energy_kwh

        # Akkumuler kostnad for Energy Dashboard (stat_cost)
        elapsed_seconds = elapsed_hours * 3600
        if energy_kwh > 0:
            if self.har_norgespris and not norgespris_over_tak:
                strom_pris = norgespris
            else:
                strom_pris = spot_price - stromstotte
            self._monthly_accumulated_cost_strom += energy_kwh * strom_pris
            self._monthly_accumulated_cost_energiledd += energy_kwh * energiledd

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

        # Akkumuler eksportinntekt
        if export_energy_kwh > 0:
            self._monthly_export_revenue += spot_price * export_energy_kwh

        # Get electricity company price if configured
        electricity_company_price = None
        electricity_company_total = None
        if self.electricity_company_price_sensor:
            raw_ec = self._read_price_sensor(self.electricity_company_price_sensor)
            if raw_ec is not None:
                electricity_company_price = raw_ec
                self._last_electricity_company_price = raw_ec
            elif self._last_electricity_company_price is not None:
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
            stromstotte=stromstotte,
            spotpris_etter_stotte=spotpris_etter_stotte,
            norgespris=norgespris,
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

        return {
            "energiledd": round(kw["energiledd"], 4),
            "energiledd_dag": self.energiledd_dag,
            "energiledd_natt": self.energiledd_natt,
            "kapasitetsledd": kw["kapasitetsledd"],
            "kapasitetstrinn_nummer": kw["trinn_nummer"],
            "kapasitetstrinn_intervall": kw["trinn_intervall"],
            "kapasitetsledd_per_kwh": round(kw["fastledd_per_kwh"], 4),
            "spot_price": round(kw["spot_price"], 4),
            "stromstotte": round(kw["stromstotte"], 4),
            "spotpris_etter_stotte": round(kw["spotpris_etter_stotte"], 4),
            "norgespris": round(kw["norgespris"], 4),
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

    def _get_kapasitetsledd(self, avg_power: float) -> tuple[int, int, str]:
        """Get kapasitetsledd based on average power.

        Returns: (price, tier_number, tier_range)
        """
        for i, (threshold, price) in enumerate(self.kapasitetstrinn, 1):
            if avg_power <= threshold:
                prev_threshold = self.kapasitetstrinn[i - 2][0] if i > 1 else 0.0
                if threshold == float("inf"):
                    tier_range = f">{prev_threshold:.0f} kW"
                else:
                    tier_range = f"{prev_threshold:.0f}-{threshold:.0f} kW"
                return price, i, tier_range
        last_idx = len(self.kapasitetstrinn)
        prev = self.kapasitetstrinn[-2][0] if last_idx > 1 else 0.0
        last_price = self.kapasitetstrinn[-1][1]
        return last_price, last_idx, f">{prev:.0f} kW"

    def _get_energiledd(self, now: datetime) -> float:
        """Get energiledd based on time of day."""
        if self._is_day_rate(now):
            return self.energiledd_dag
        return self.energiledd_natt

    def _is_day_rate(self, now: datetime) -> bool:
        """Check if current time is day rate."""
        date_mm_dd = now.strftime("%m-%d")
        date_yyyy_mm_dd = now.strftime("%Y-%m-%d")

        is_fixed_holiday = date_mm_dd in HELLIGDAGER_FASTE
        # Compute moving holidays dynamically for the current year
        bevegelige = _bevegelige_helligdager(now.year)
        is_moving_holiday = date_yyyy_mm_dd in bevegelige
        is_weekend = now.weekday() >= WEEKEND_WEEKDAY_START
        is_night = now.hour < DAY_RATE_START_HOUR or now.hour >= DAY_RATE_END_HOUR

        return not (is_fixed_holiday or is_moving_holiday or is_weekend or is_night)

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
        }
        try:
            await self._store.async_save(data)
        except OSError:
            _LOGGER.warning("Failed to save storage data (disk full?)")
            return
        _LOGGER.debug("Saved data: %s", data)
