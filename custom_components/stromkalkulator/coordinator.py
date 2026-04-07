"""Data coordinator for Nettleie."""

from __future__ import annotations

import logging
import math
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
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DOMAIN,
    DSO_LIST,
    ENOVA_AVGIFT,
    HELLIGDAGER_FASTE,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
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
    _daily_max_power: dict[str, dict[str, Any]]
    _current_month: str  # "YYYY-MM" format for year-aware month tracking
    _monthly_consumption: dict[str, float]
    _last_update: datetime | None
    _previous_month_consumption: dict[str, float]
    _previous_month_top_3: dict[str, dict[str, Any]]
    _previous_month_name: str | None
    _monthly_norgespris_diff: float
    _previous_month_norgespris_diff: float
    _monthly_norgespris_compensation: float
    _previous_month_norgespris_compensation: float
    _previous_month_kapasitetsledd: int
    _previous_month_kapasitetstrinn: str
    _monthly_export_kwh: float
    _monthly_export_revenue: float
    _monthly_cost: float
    _previous_month_export_kwh: float
    _previous_month_export_revenue: float
    _previous_month_cost: float
    _store: Store[dict[str, Any]]
    _store_loaded: bool

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=1),
        )
        self.entry = entry
        self.power_sensor = entry.data.get(CONF_POWER_SENSOR)
        self.spot_price_sensor = entry.data.get(CONF_SPOT_PRICE_SENSOR)
        self.electricity_company_price_sensor = entry.data.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR)
        self.export_power_sensor = entry.data.get(CONF_EXPORT_POWER_SENSOR)

        # Get DSO config
        dso_id = entry.data.get(CONF_DSO, "bkk")
        self.dso = DSO_LIST.get(dso_id, DSO_LIST["bkk"])
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
        # Format: {date_str: {"kw": max_hourly_avg_kw, "hour": hour_of_day}}
        # Nettselskapet bruker maks timesforbruk (kWh/time = snitt-kW per klokke-time),
        # ikke instantan effekt. Vi akkumulerer energi per klokke-time og bruker den
        # høyeste timen som dagens topp.
        self._daily_max_power: dict[str, dict[str, Any]] = {}
        self._current_hour_energy: float = 0.0  # kWh akkumulert i inneværende klokke-time
        self._current_hour: int = dt_util.now().hour  # 0-23
        self._current_month = dt_util.now().strftime("%Y-%m")

        # Track energy consumption for monthly utility meter
        # Format: {"dag": kwh, "natt": kwh}
        self._monthly_consumption = {"dag": 0.0, "natt": 0.0}
        self._monthly_norgespris_diff = 0.0
        self._monthly_norgespris_compensation = 0.0
        self._last_update = None

        # Track previous month's data for invoice verification
        self._previous_month_consumption = {"dag": 0.0, "natt": 0.0}
        self._previous_month_top_3: dict[str, dict[str, Any]] = {}
        self._previous_month_name = None  # e.g., "januar 2026"
        self._previous_month_norgespris_diff = 0.0
        self._previous_month_norgespris_compensation = 0.0
        self._previous_month_kapasitetsledd = 0
        self._previous_month_kapasitetstrinn = ""

        # Eksport-akkumulering (plusskunder med solceller)
        self._monthly_export_kwh = 0.0
        self._monthly_export_revenue = 0.0
        self._monthly_cost = 0.0
        self._previous_month_export_kwh = 0.0
        self._previous_month_export_revenue = 0.0
        self._previous_month_cost = 0.0

        # Daily cost accumulation
        self._daily_cost = 0.0
        self._current_date = dt_util.now().strftime("%Y-%m-%d")

        # Cache last known prices (survives brief sensor outages)
        self._last_electricity_company_price: float | None = None
        self._last_spot_price: float | None = None

        # Persistent storage - keyed by entry_id for multi-instance isolation
        self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
        self._store_loaded = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate values."""
        now = dt_util.now()

        # Load stored data on first run
        if not self._store_loaded:
            await self._load_stored_data()
            self._store_loaded = True

        # Reset at new month
        current_month_str = now.strftime("%Y-%m")
        if current_month_str != self._current_month:
            # Save previous month's data before reset
            self._previous_month_consumption = self._monthly_consumption.copy()
            # Format: "januar 2026" (Norwegian month name)
            prev_month_date = now.replace(day=1) - timedelta(days=1)
            self._previous_month_name = self._format_month_name(prev_month_date)

            # Archive Norgespris diff and compensation before reset
            self._previous_month_norgespris_diff = self._monthly_norgespris_diff
            self._previous_month_norgespris_compensation = self._monthly_norgespris_compensation

            # Archive export data before reset
            self._previous_month_export_kwh = self._monthly_export_kwh
            self._previous_month_export_revenue = self._monthly_export_revenue
            self._previous_month_cost = self._monthly_cost

            # Flush siste times akkumulator til daily_max_power før arkivering
            if self._current_hour_energy > 0:
                yesterday = (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
                old_max = self._daily_max_power.get(yesterday, {}).get("kw", 0)
                if self._current_hour_energy > old_max:
                    self._daily_max_power[yesterday] = {"kw": round(self._current_hour_energy, 3), "hour": self._current_hour}

            # Compute kapasitetsledd for previous month from top_3 before reset
            prev_top_3 = self._get_top_3_days()
            self._previous_month_top_3 = prev_top_3
            if prev_top_3:
                kw_values = [entry["kw"] for entry in prev_top_3.values()]
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
            self._monthly_consumption = {"dag": 0.0, "natt": 0.0}
            self._monthly_norgespris_diff = 0.0
            self._monthly_norgespris_compensation = 0.0
            self._monthly_export_kwh = 0.0
            self._monthly_export_revenue = 0.0
            self._monthly_cost = 0.0
            self._current_month = current_month_str
            await self._save_stored_data()

        # Get current power consumption
        power_state = self.hass.states.get(self.power_sensor)
        try:
            current_power_w = (
                float(power_state.state) if power_state and power_state.state not in ("unknown", "unavailable") else 0
            )
        except (ValueError, TypeError):
            current_power_w = 0
        if not math.isfinite(current_power_w):
            current_power_w = 0
        # Clamp to reasonable residential range (0-500 kW = 500,000 W)
        if current_power_w > 500_000:
            _LOGGER.warning("Power reading %s W exceeds 500 kW, clamping", current_power_w)
            current_power_w = 0
        current_power_kw = current_power_w / 1000

        # Beregn tid siden forrige oppdatering (felles for forbruk og eksport)
        elapsed_hours = 0.0
        if self._last_update is not None:
            elapsed_hours = (now - self._last_update).total_seconds() / 3600
            # Clamp to 0-6 minutes: reject negative (clock jump back) and spikes (clock jump forward)
            elapsed_hours = max(0.0, min(elapsed_hours, 0.1))

        # Calculate energy consumption since last update (riemann sum)
        energy_kwh = 0.0
        consumption_updated = False
        if elapsed_hours > 0 and current_power_kw > 0:
            energy_kwh = current_power_kw * elapsed_hours
            # Add to appropriate tariff bucket
            tariff = "dag" if self._is_day_rate(now) else "natt"
            self._monthly_consumption[tariff] += energy_kwh
            consumption_updated = True

        # Eksport-akkumulering (plusskunder med solceller)
        export_energy_kwh = 0.0
        export_updated = False
        if self.export_power_sensor and elapsed_hours > 0:
            export_state = self.hass.states.get(self.export_power_sensor)
            try:
                export_power_w = (
                    float(export_state.state)
                    if export_state and export_state.state not in ("unknown", "unavailable")
                    else 0
                )
            except (ValueError, TypeError):
                export_power_w = 0
            if not math.isfinite(export_power_w):
                export_power_w = 0
            if export_power_w > 500_000:
                export_power_w = 0
            export_power_kw = export_power_w / 1000
            if export_power_kw > 0:
                export_energy_kwh = export_power_kw * elapsed_hours
                self._monthly_export_kwh += export_energy_kwh
                export_updated = True

        self._last_update = now

        # Update daily max (basert på timessnitt, ikke instantan effekt)
        today_str = now.strftime("%Y-%m-%d")

        # Reset daily cost at date change
        if today_str != self._current_date:
            self._daily_cost = 0.0
            self._current_date = today_str

        # Akkumuler energi i inneværende klokke-time
        current_hour = now.hour
        hourly_max_updated = False
        previous_hour = self._current_hour
        if current_hour != self._current_hour:
            # Timen har endret seg — den forrige timen er komplett.
            # _current_hour_energy (kWh over 1 time) = gjennomsnittlig kW for den timen.
            if self._current_hour_energy > 0:
                prev_date = self._current_date if current_hour != 0 else (
                    (now.replace(hour=0, minute=0, second=0) - timedelta(seconds=1)).strftime("%Y-%m-%d")
                )
                old_max = self._daily_max_power.get(prev_date, {}).get("kw", 0)
                if self._current_hour_energy > old_max:
                    self._daily_max_power[prev_date] = {"kw": round(self._current_hour_energy, 3), "hour": previous_hour}
                    hourly_max_updated = True
            self._current_hour_energy = 0.0
            self._current_hour = current_hour

        # Legg til denne oppdateringens energi i timens akkumulator
        self._current_hour_energy += energy_kwh

        # Save if anything changed
        if hourly_max_updated or consumption_updated or export_updated:
            await self._save_stored_data()

        # Get top 3 days
        top_3 = self._get_top_3_days()
        top_3_kw_values = [entry["kw"] for entry in top_3.values()]
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
        spot_state = self.hass.states.get(self.spot_price_sensor)
        spot_price: float = 0
        if spot_state and spot_state.state not in ("unknown", "unavailable"):
            try:
                raw_spot = float(spot_state.state)
            except (ValueError, TypeError):
                raw_spot = None
            if raw_spot is not None and math.isfinite(raw_spot):
                spot_price = raw_spot
                self._last_spot_price = spot_price
            elif self._last_spot_price is not None:
                spot_price = self._last_spot_price
        elif self._last_spot_price is not None:
            spot_price = self._last_spot_price

        # Raise if either sensor entity is completely missing (not registered)
        if power_state is None:
            raise UpdateFailed(f"Power sensor entity not found: {self.power_sensor}")
        if spot_state is None:
            raise UpdateFailed(f"Spot price sensor entity not found: {self.spot_price_sensor}")

        # Calculate strømstøtte (always from spot price, for comparison)
        # Forskrift § 5: 90% av spotpris over 77 øre/kWh eks. mva (96,25 øre inkl. mva) i 2026
        # kWh-tak avhenger av boligtype:
        # - Bolig / Fritidsbolig fast bosted: 5000 kWh/mnd (Forskrift § 5)
        # - Fritidsbolig: Ingen rett på strømstøtte (Forskrift § 3)
        # Kilde: https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791
        # NB: Norgespris-kunder mottar ikke strømstøtte, men vi beregner den
        # alltid slik at sammenligning mellom Norgespris og spot+støtte fungerer.
        monthly_total_kwh = self._monthly_consumption["dag"] + self._monthly_consumption["natt"]
        stromstotte_max = get_stromstotte_max_kwh(self.boligtype)
        stromstotte: float
        if stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max:
            stromstotte = 0.0
        elif spot_price > STROMSTOTTE_LEVEL:
            stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        else:
            stromstotte = 0.0

        stromstotte_gjenstaaende = max(0.0, stromstotte_max - monthly_total_kwh)

        # Spotpris etter strømstøtte
        spotpris_etter_stotte = spot_price - stromstotte

        # Calculate fastledd per kWh
        days_in_month = self._days_in_month(now)
        fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24

        # Norgespris - fast pris basert på avgiftssone
        # Kilde: https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
        # Sør-Norge: 40 øre + 25% mva = 50 øre/kWh
        # Nord-Norge/Tiltakssonen: 40 øre (mva-fritak)
        norgespris = get_norgespris_inkl_mva(self.avgiftssone)

        # Norgespris har ingen strømstøtte
        norgespris_stromstotte = 0

        # Total price calculation depends on whether user has Norgespris
        # Norgespris kWh-tak: Bolig=5000, Fritidsbolig=1000. Over taket betaler man spotpris.
        norgespris_max = get_norgespris_max_kwh(self.boligtype)
        norgespris_over_tak = monthly_total_kwh >= norgespris_max

        if self.har_norgespris:
            if norgespris_over_tak:
                # Over Norgespris-taket: betaler spotpris (ingen Norgespris-rabatt)
                total_price = spot_price + energiledd + fastledd_per_kwh
                total_price_uten_stotte = spot_price + energiledd + fastledd_per_kwh
            else:
                # Under taket: fast Norgespris
                total_price = norgespris + energiledd + fastledd_per_kwh
                total_price_uten_stotte = norgespris + energiledd + fastledd_per_kwh
        else:
            # Standard: spotpris minus strømstøtte
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
        # Forbruksavgift og Enova-avgift inkl. mva
        mva_sats = get_mva_sats(self.avgiftssone)
        forbruksavgift = get_forbruksavgift(self.avgiftssone, now.month)
        forbruksavgift_inkl_mva = forbruksavgift * (1 + mva_sats)
        enova_inkl_mva = ENOVA_AVGIFT * (1 + mva_sats)
        offentlige_avgifter = forbruksavgift_inkl_mva + enova_inkl_mva

        # Totalpris inkl. alle avgifter (for Energy Dashboard)
        # NB: energiledd fra dso.py inkluderer allerede forbruksavgift + enova,
        # så total_price har avgiftene bakt inn. Ikke legg dem til på nytt.
        total_price_inkl_avgifter = total_price

        # Kroner spart/tapt per kWh (sammenligning)
        # Positiv = du betaler mer enn alternativet
        # Negativ = du betaler mindre enn alternativet
        kroner_spart_per_kwh: float
        if self.har_norgespris:
            # Sammenlign Norgespris med hva spot etter støtte ville kostet
            spot_total_etter_stotte = spot_price - stromstotte + energiledd + fastledd_per_kwh
            kroner_spart_per_kwh = total_price - spot_total_etter_stotte
        else:
            kroner_spart_per_kwh = total_price - total_pris_norgespris

        # Accumulate monthly Norgespris comparison
        # Positiv = du sparer med nåværende avtale
        if energy_kwh > 0:
            if self.har_norgespris:
                # Sammenlign med spot etter støtte
                diff_per_kwh = spot_total_etter_stotte - total_price
            else:
                diff_per_kwh = total_pris_norgespris - total_price
            self._monthly_norgespris_diff += diff_per_kwh * energy_kwh

        # Accumulate Norgespris compensation: (norgespris_fast - spotpris) * kWh
        # Beregnes alltid, uavhengig av har_norgespris (spot-kunder kan sammenligne)
        if energy_kwh > 0:
            self._monthly_norgespris_compensation += (norgespris - spot_price) * energy_kwh

        # Accumulate daily cost
        # total_price inkluderer allerede energiledd (med avgifter) og strømstøtte-fradrag
        if energy_kwh > 0:
            self._daily_cost += total_price * energy_kwh
            self._monthly_cost += total_price * energy_kwh

        # Akkumuler eksportinntekt — kun spotpris, ingen avgifter
        if export_energy_kwh > 0:
            self._monthly_export_revenue += spot_price * export_energy_kwh

        # Get electricity company price if configured
        # Caches last known price to survive brief API outages (price changes max once per hour)
        electricity_company_price = None
        electricity_company_total = None
        if self.electricity_company_price_sensor:
            electricity_company_state = self.hass.states.get(self.electricity_company_price_sensor)
            if electricity_company_state and electricity_company_state.state not in ("unknown", "unavailable"):
                try:
                    raw_price = float(electricity_company_state.state)
                except (ValueError, TypeError):
                    raw_price = None
                if raw_price is not None and math.isfinite(raw_price):
                    electricity_company_price = raw_price
                    self._last_electricity_company_price = electricity_company_price
            elif self._last_electricity_company_price is not None:
                electricity_company_price = self._last_electricity_company_price
            if electricity_company_price is not None:
                # Electricity company total = strømpris + nettleie (energiledd + kapasitetsledd per kWh)
                electricity_company_total = electricity_company_price + energiledd + fastledd_per_kwh

        return {
            "energiledd": round(energiledd, 4),
            "energiledd_dag": self.energiledd_dag,
            "energiledd_natt": self.energiledd_natt,
            "kapasitetsledd": kapasitetsledd,
            "kapasitetstrinn_nummer": trinn_nummer,
            "kapasitetstrinn_intervall": trinn_intervall,
            "kapasitetsledd_per_kwh": round(fastledd_per_kwh, 4),
            "spot_price": round(spot_price, 4),
            "stromstotte": round(stromstotte, 4),
            "spotpris_etter_stotte": round(spotpris_etter_stotte, 4),
            "norgespris": round(norgespris, 4),
            "norgespris_stromstotte": norgespris_stromstotte,
            "total_pris_norgespris": round(total_pris_norgespris, 4),
            "kroner_spart_per_kwh": round(kroner_spart_per_kwh, 4),
            "total_price": round(total_price, 4),
            "total_price_uten_stotte": round(total_price_uten_stotte, 4),
            "total_price_inkl_avgifter": round(total_price_inkl_avgifter, 4),
            "strompris_per_kwh": round(strompris_per_kwh, 4),
            "strompris_per_kwh_etter_stotte": round(strompris_per_kwh_etter_stotte, 4),
            "forbruksavgift_inkl_mva": round(forbruksavgift_inkl_mva, 4),
            "enova_inkl_mva": round(enova_inkl_mva, 4),
            "offentlige_avgifter": round(offentlige_avgifter, 4),
            "electricity_company_price": round(electricity_company_price, 4)
            if electricity_company_price is not None
            else None,
            "electricity_company_total": round(electricity_company_total, 4)
            if electricity_company_total is not None
            else None,
            "current_power_kw": round(current_power_kw, 2),
            "avg_top_3_kw": round(avg_power, 2),
            "top_3_days": top_3,
            "is_day_rate": self._is_day_rate(now),
            "dso": self.dso["name"],
            "har_norgespris": self.har_norgespris,
            "avgiftssone": self.avgiftssone,
            # Monthly consumption tracking
            "monthly_consumption_dag_kwh": round(self._monthly_consumption["dag"], 3),
            "monthly_consumption_natt_kwh": round(self._monthly_consumption["natt"], 3),
            "monthly_consumption_total_kwh": round(
                self._monthly_consumption["dag"] + self._monthly_consumption["natt"], 3
            ),
            # Previous month data for invoice verification
            "previous_month_consumption_dag_kwh": round(self._previous_month_consumption["dag"], 3),
            "previous_month_consumption_natt_kwh": round(self._previous_month_consumption["natt"], 3),
            "previous_month_consumption_total_kwh": round(
                self._previous_month_consumption["dag"] + self._previous_month_consumption["natt"], 3
            ),
            "previous_month_top_3": self._previous_month_top_3,
            "previous_month_avg_top_3_kw": round(
                sum(e["kw"] for e in self._previous_month_top_3.values())
                / max(len(self._previous_month_top_3), 1),
                2,
            )
            if self._previous_month_top_3
            else 0.0,
            "previous_month_name": self._previous_month_name,
            "previous_month_kapasitetsledd": self._previous_month_kapasitetsledd,
            "previous_month_kapasitetstrinn": self._previous_month_kapasitetstrinn,
            "stromstotte_tak_naadd": stromstotte_max == 0 or monthly_total_kwh >= stromstotte_max,
            "norgespris_over_tak": norgespris_over_tak,
            "boligtype": self.boligtype,
            "stromstotte_gjenstaaende_kwh": round(stromstotte_gjenstaaende, 1),
            "margin_neste_trinn_kw": margin_neste_trinn,
            "neste_trinn_pris": neste_trinn_pris,
            "kapasitet_varsel": kapasitet_varsel,
            "monthly_norgespris_diff_kr": round(self._monthly_norgespris_diff, 2),
            "previous_month_norgespris_diff_kr": round(self._previous_month_norgespris_diff, 2),
            "monthly_norgespris_compensation_kr": round(self._monthly_norgespris_compensation, 2),
            "previous_month_norgespris_compensation_kr": round(self._previous_month_norgespris_compensation, 2),
            "daily_cost_kr": round(self._daily_cost, 2),
            # Eksport (plusskunder)
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

    def _get_top_3_days(self) -> dict[str, dict[str, Any]]:
        """Get the top 3 days with highest power consumption."""
        sorted_days = sorted(self._daily_max_power.items(), key=lambda x: x[1]["kw"], reverse=True)
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
        is_weekend = now.weekday() >= 5
        is_night = now.hour < 6 or now.hour >= 22

        return not (is_fixed_holiday or is_moving_holiday or is_weekend or is_night)

    def _days_in_month(self, now: datetime) -> int:
        """Get number of days in current month."""
        next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        return (next_month - now.replace(day=1)).days

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
                # Save to new location immediately
                await self._store.async_save(data)
                # Remove old DSO-based storage to prevent a second instance
                # with the same DSO from loading the same data (issue #1)
                await old_store.async_remove()

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
    def _validate_daily_max_power(data: Any) -> dict[str, dict[str, Any]]:
        """Validate daily max power dict, migrating old float format to new dict format."""
        if not isinstance(data, dict):
            return {}
        result: dict[str, dict[str, Any]] = {}
        for key, val in data.items():
            if isinstance(val, dict):
                # New format: {"kw": float, "hour": int|None}
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
                    result[str(key)] = {"kw": fval, "hour": hour}
            else:
                # Old format: bare float — migrer til dict
                try:
                    fval = float(val)
                except (ValueError, TypeError):
                    continue
                if math.isfinite(fval) and fval >= 0:
                    result[str(key)] = {"kw": fval, "hour": None}
        return result

    @staticmethod
    def _validate_consumption(data: Any) -> dict[str, float]:
        """Validate consumption dict has dag/natt keys with finite floats."""
        if not isinstance(data, dict):
            return {"dag": 0.0, "natt": 0.0}
        result: dict[str, float] = {"dag": 0.0, "natt": 0.0}
        for key in ("dag", "natt"):
            try:
                val = float(data.get(key, 0.0))
            except (ValueError, TypeError):
                val = 0.0
            if not math.isfinite(val) or val < 0:
                val = 0.0
            result[key] = val
        return result

    async def _save_stored_data(self) -> None:
        """Save data to disk."""
        data: dict[str, Any] = {
            "daily_max_power": dict(self._daily_max_power),
            "monthly_consumption": dict(self._monthly_consumption),
            "current_month": self._current_month,
            "previous_month_consumption": dict(self._previous_month_consumption),
            "previous_month_top_3": dict(self._previous_month_top_3),
            "previous_month_name": self._previous_month_name,
            "monthly_norgespris_diff": self._monthly_norgespris_diff,
            "previous_month_norgespris_diff": self._previous_month_norgespris_diff,
            "monthly_norgespris_compensation": self._monthly_norgespris_compensation,
            "previous_month_norgespris_compensation": self._previous_month_norgespris_compensation,
            "previous_month_kapasitetsledd": self._previous_month_kapasitetsledd,
            "previous_month_kapasitetstrinn": self._previous_month_kapasitetstrinn,
            "daily_cost": self._daily_cost,
            "current_date": self._current_date,
            "current_hour_energy": self._current_hour_energy,
            "current_hour": self._current_hour,
            "monthly_export_kwh": self._monthly_export_kwh,
            "monthly_export_revenue": self._monthly_export_revenue,
            "monthly_cost": self._monthly_cost,
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
