"""Sensor platform for Nettleie."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TSO, DOMAIN, TSO_LIST
from .coordinator import NettleieCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Nettleie sensors."""
    coordinator: NettleieCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        EnergileggSensor(coordinator, entry),
        KapasitetstrinnSensor(coordinator, entry),
        TotalPriceSensor(coordinator, entry),
        MaksForbrukSensor(coordinator, entry, 1),
        MaksForbrukSensor(coordinator, entry, 2),
        MaksForbrukSensor(coordinator, entry, 3),
        GjsForbrukSensor(coordinator, entry),
        TrinnNummerSensor(coordinator, entry),
        TrinnIntervallSensor(coordinator, entry),
        TibberTotalSensor(coordinator, entry),
        StromstotteSensor(coordinator, entry),
        SpotprisEtterStotteSensor(coordinator, entry),
        TotalPrisEtterStotteSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NettleieBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Nettleie sensors."""

    def __init__(
        self,
        coordinator: NettleieCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_name = name
        self._entry = entry
        
        # Get TSO name for device info
        tso_id = entry.data.get(CONF_TSO, "bkk")
        self._tso = TSO_LIST.get(tso_id, TSO_LIST["bkk"])

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": f"Nettleie ({self._tso['name']})",
            "manufacturer": "Fredrik Lindseth",
            "model": "Nettleiekalkulator",
        }


class EnergileggSensor(NettleieBaseSensor):
    """Sensor for energiledd."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd", "Energiledd")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("energiledd")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "is_day_rate": self.coordinator.data.get("is_day_rate"),
                "rate_type": "dag" if self.coordinator.data.get("is_day_rate") else "natt/helg",
                "energiledd_dag": self.coordinator.data.get("energiledd_dag"),
                "energiledd_natt": self.coordinator.data.get("energiledd_natt"),
                "tso": self.coordinator.data.get("tso"),
            }
        return None


class KapasitetstrinnSensor(NettleieBaseSensor):
    """Sensor for kapasitetstrinn."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitetstrinn", "Kapasitetstrinn")
        self._attr_native_unit_of_measurement = "kr/mnd"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:transmission-tower"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kapasitetsledd")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            attrs = {
                "trinn": self.coordinator.data.get("kapasitetstrinn_nummer"),
                "intervall": self.coordinator.data.get("kapasitetstrinn_intervall"),
                "gjennomsnitt_kw": self.coordinator.data.get("avg_top_3_kw"),
                "current_power_kw": self.coordinator.data.get("current_power_kw"),
                "tso": self.coordinator.data.get("tso"),
            }
            for i, (date, power) in enumerate(top_3.items(), 1):
                attrs[f"maks_{i}_dato"] = date
                attrs[f"maks_{i}_kw"] = round(power, 2)
            return attrs
        return None


class TotalPriceSensor(NettleieBaseSensor):
    """Sensor for total electricity price."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_price", "Strømpris ink. avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_price")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spot_price": self.coordinator.data.get("spot_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "tso": self.coordinator.data.get("tso"),
            }
        return None


class MaksForbrukSensor(NettleieBaseSensor):
    """Sensor for max power consumption on a specific day."""

    def __init__(
        self, coordinator: NettleieCoordinator, entry: ConfigEntry, rank: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, f"maks_forbruk_{rank}", f"Maks forbruk #{rank}"
        )
        self._rank = rank
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                values = list(top_3.values())
                return round(values[self._rank - 1], 2)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                dates = list(top_3.keys())
                return {"dato": dates[self._rank - 1]}
        return None


class GjsForbrukSensor(NettleieBaseSensor):
    """Sensor for average of top 3 power consumption days."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, "gjennomsnitt_forbruk", "Gjennomsnitt maks forbruk"
        )
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            avg = self.coordinator.data.get("avg_top_3_kw")
            if avg is not None:
                return round(avg, 2)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "kapasitetstrinn": self.coordinator.data.get("kapasitetsledd"),
                "tso": self.coordinator.data.get("tso"),
            }
        return None


class TrinnNummerSensor(NettleieBaseSensor):
    """Sensor for capacity tier number."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_nummer", "Kapasitetstrinn nummer")
        self._attr_icon = "mdi:numeric"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kapasitetstrinn_nummer")
        return None


class TrinnIntervallSensor(NettleieBaseSensor):
    """Sensor for capacity tier interval."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_intervall", "Kapasitetstrinn intervall")
        self._attr_icon = "mdi:arrow-expand-horizontal"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kapasitetstrinn_intervall")
        return None


class TibberTotalSensor(NettleieBaseSensor):
    """Sensor for total price with Tibber + nettleie."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "tibber_total", "Strømpris Tibber + nettleie")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-plus"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            tibber_total = self.coordinator.data.get("tibber_total")
            if tibber_total is not None:
                return round(tibber_total, 4)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "tibber_pris": self.coordinator.data.get("tibber_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
            }
        return None


class StromstotteSensor(NettleieBaseSensor):
    """Sensor for strømstøtte per kWh."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte", "Strømstøtte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-refund"
        self._attr_suggested_display_precision = 4

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("stromstotte")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "terskel": 0.70,
                "dekningsgrad": "90%",
            }
        return None


class SpotprisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for spot price after strømstøtte."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "spotpris_etter_stotte", "Spotpris etter støtte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd-off"
        self._attr_suggested_display_precision = 4

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("spotpris_etter_stotte")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
            }
        return None


class TotalPrisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for total price after strømstøtte (spot + nettleie - støtte)."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_etter_stotte", "Total strømpris etter støtte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-check"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_price")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "spotpris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
            }
        return None
