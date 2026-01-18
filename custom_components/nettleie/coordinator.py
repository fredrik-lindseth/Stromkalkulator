"""Data coordinator for Nettleie."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_TSO,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    DEFAULT_ENERGILEDD_DAG,
    DEFAULT_ENERGILEDD_NATT,
    DOMAIN,
    TSO_LIST,
    HELLIGDAGER_FASTE,
    HELLIGDAGER_BEVEGELIGE,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
)

_LOGGER = logging.getLogger(__name__)


class NettleieCoordinator(DataUpdateCoordinator):
    """Coordinator for Nettleie data."""

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
        
        # Get TSO config
        tso_id = entry.data.get(CONF_TSO, "bkk")
        self.tso = TSO_LIST.get(tso_id, TSO_LIST["bkk"])
        
        # Get energiledd from config (allows override)
        self.energiledd_dag = entry.data.get(CONF_ENERGILEDD_DAG, self.tso["energiledd_dag"])
        self.energiledd_natt = entry.data.get(CONF_ENERGILEDD_NATT, self.tso["energiledd_natt"])
        
        # Get kapasitetstrinn from TSO
        self.kapasitetstrinn = self.tso["kapasitetstrinn"]
        
        # Track max power for capacity calculation
        # Format: {date_str: max_power_kw}
        self._daily_max_power: dict[str, float] = {}
        self._current_month: int = datetime.now().month

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors and calculate values."""
        now = datetime.now()
        
        # Reset at new month
        if now.month != self._current_month:
            self._daily_max_power = {}
            self._current_month = now.month

        # Get current power consumption
        power_state = self.hass.states.get(self.power_sensor)
        current_power_w = float(power_state.state) if power_state and power_state.state not in ("unknown", "unavailable") else 0
        current_power_kw = current_power_w / 1000

        # Update daily max
        today_str = now.strftime("%Y-%m-%d")
        if today_str not in self._daily_max_power:
            self._daily_max_power[today_str] = current_power_kw
        else:
            self._daily_max_power[today_str] = max(self._daily_max_power[today_str], current_power_kw)

        # Get top 3 days
        top_3 = self._get_top_3_days()
        avg_power = sum(top_3.values()) / 3 if len(top_3) >= 3 else sum(top_3.values()) / max(len(top_3), 1)

        # Calculate capacity tier
        kapasitetsledd, trinn_nummer, trinn_intervall = self._get_kapasitetsledd(avg_power)

        # Calculate energiledd
        energiledd = self._get_energiledd(now)

        # Get spot price
        spot_state = self.hass.states.get(self.spot_price_sensor)
        spot_price = float(spot_state.state) if spot_state and spot_state.state not in ("unknown", "unavailable") else 0

        # Calculate strømstøtte
        if spot_price > STROMSTOTTE_LEVEL:
            stromstotte = (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        else:
            stromstotte = 0

        # Calculate fastledd per kWh
        days_in_month = self._days_in_month(now)
        fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24

        # Total price
        total_price = spot_price - stromstotte + energiledd + fastledd_per_kwh

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
            "total_price": round(total_price, 2),
            "current_power_kw": round(current_power_kw, 2),
            "avg_top_3_kw": round(avg_power, 2),
            "top_3_days": top_3,
            "is_day_rate": self._is_day_rate(now),
            "tso": self.tso["name"],
        }

    def _get_top_3_days(self) -> dict[str, float]:
        """Get the top 3 days with highest power consumption."""
        sorted_days = sorted(self._daily_max_power.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_days[:3])

    def _get_kapasitetsledd(self, avg_power: float) -> tuple[int, int, str]:
        """Get kapasitetsledd based on average power.
        
        Returns: (price, tier_number, tier_range)
        """
        for i, (threshold, price) in enumerate(self.kapasitetstrinn, 1):
            if avg_power <= threshold:
                prev_threshold = self.kapasitetstrinn[i-2][0] if i > 1 else 0
                if threshold == float("inf"):
                    tier_range = f">{prev_threshold} kW"
                else:
                    tier_range = f"{prev_threshold}-{threshold} kW"
                return price, i, tier_range
        last_idx = len(self.kapasitetstrinn)
        prev = self.kapasitetstrinn[-2][0] if last_idx > 1 else 0
        return self.kapasitetstrinn[-1][1], last_idx, f">{prev} kW"

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
        is_moving_holiday = date_yyyy_mm_dd in HELLIGDAGER_BEVEGELIGE
        is_weekend = now.weekday() >= 5
        is_night = now.hour < 6 or now.hour >= 22

        return not (is_fixed_holiday or is_moving_holiday or is_weekend or is_night)

    def _days_in_month(self, now: datetime) -> int:
        """Get number of days in current month."""
        next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        return (next_month - now.replace(day=1)).days
