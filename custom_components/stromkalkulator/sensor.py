"""Sensor platform for Strømkalkulator."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_TSO, DOMAIN, TSO_LIST, FORBRUKSAVGIFT, ENOVA_AVGIFT, MVA_SATS
from .coordinator import NettleieCoordinator

# Device group constants
DEVICE_NETTLEIE = "stromkalkulator"
DEVICE_STROMSTOTTE = "stromstotte"
DEVICE_NORGESPRIS = "norgespris"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Strømkalkulator sensors."""
    coordinator: NettleieCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = [
        # Nettleie - Kapasitet
        MaksForbrukSensor(coordinator, entry, 1),
        MaksForbrukSensor(coordinator, entry, 2),
        MaksForbrukSensor(coordinator, entry, 3),
        GjsForbrukSensor(coordinator, entry),
        TrinnNummerSensor(coordinator, entry),
        TrinnIntervallSensor(coordinator, entry),
        KapasitetstrinnSensor(coordinator, entry),
        # Nettleie - Energiledd
        EnergileddSensor(coordinator, entry),
        # Nettleie - Avgifter
        OffentligeAvgifterSensor(coordinator, entry),
        # Strømpriser
        TotalPriceSensor(coordinator, entry),
        ElectricityCompanyTotalSensor(coordinator, entry),
        # Strømstøtte
        StromstotteSensor(coordinator, entry),
        SpotprisEtterStotteSensor(coordinator, entry),
        TotalPrisEtterStotteSensor(coordinator, entry),
        # Norgespris
        TotalPrisNorgesprisSensor(coordinator, entry),
        PrisforskjellNorgesprisSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NettleieBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Strømkalkulator sensors."""

    _device_group: str = DEVICE_NETTLEIE

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
        device_names = {
            DEVICE_NETTLEIE: f"Nettleie ({self._tso['name']})",
            DEVICE_STROMSTOTTE: "Strømstøtte",
            DEVICE_NORGESPRIS: "Norgespris",
        }
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": device_names.get(self._device_group, f"Nettleie ({self._tso['name']})"),
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }


class EnergileddSensor(NettleieBaseSensor):
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
    """Sensor for total electricity price (without strømstøtte)."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_price", "Total strømpris (før støtte)")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_price_uten_stotte")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spot_price": self.coordinator.data.get("spot_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                "tso": self.coordinator.data.get("tso"),
            }
        return None


class MaksForbrukSensor(NettleieBaseSensor):
    """Sensor for max power consumption on a specific day."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: NettleieCoordinator, entry: ConfigEntry, rank: int
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, f"maks_forbruk_{rank}", f"Toppforbruk #{rank}"
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

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, "gjennomsnitt_forbruk", "Snitt toppforbruk"
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

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_nummer", "Kapasitetstrinn (nummer)")
        self._attr_icon = "mdi:numeric"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kapasitetstrinn_nummer")
        return None


class TrinnIntervallSensor(NettleieBaseSensor):
    """Sensor for capacity tier interval."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_intervall", "Kapasitetstrinn (intervall)")
        self._attr_icon = "mdi:arrow-expand-horizontal"

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kapasitetstrinn_intervall")
        return None


class OffentligeAvgifterSensor(NettleieBaseSensor):
    """Sensor for offentlige avgifter (forbruksavgift, Enova, mva)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "offentlige_avgifter", "Offentlige avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:bank"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return total avgifter inkl. mva."""
        # Forbruksavgift + Enova, inkl. mva
        total_eks_mva = FORBRUKSAVGIFT + ENOVA_AVGIFT
        return round(total_eks_mva * (1 + MVA_SATS), 2)

    @property
    def extra_state_attributes(self):
        """Return breakdown of fees."""
        forbruksavgift_inkl_mva = round(FORBRUKSAVGIFT * (1 + MVA_SATS), 4)
        enova_inkl_mva = round(ENOVA_AVGIFT * (1 + MVA_SATS), 4)
        return {
            "forbruksavgift_eks_mva": FORBRUKSAVGIFT,
            "forbruksavgift_inkl_mva": forbruksavgift_inkl_mva,
            "enova_avgift_eks_mva": ENOVA_AVGIFT,
            "enova_avgift_inkl_mva": enova_inkl_mva,
            "mva_sats": f"{int(MVA_SATS * 100)}%",
            "note": "Disse avgiftene er inkludert i energileddet fra nettselskapet",
        }


class ElectricityCompanyTotalSensor(NettleieBaseSensor):
    """Sensor for total price with electricity company + nettleie."""

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "electricity_company_total", "Total strømpris (strømavtale)")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-plus"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            electricity_company_total = self.coordinator.data.get("electricity_company_total")
            if electricity_company_total is not None:
                return round(electricity_company_total, 4)
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "electricity_company_pris": self.coordinator.data.get("electricity_company_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
            }
        return None


class StromstotteSensor(NettleieBaseSensor):
    """Sensor for strømstøtte per kWh."""

    _device_group = DEVICE_STROMSTOTTE

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte", "Strømstøtte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-refund"
        self._attr_suggested_display_precision = 2

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

    _device_group = DEVICE_STROMSTOTTE

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "spotpris_etter_stotte", "Spotpris etter støtte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd-off"
        self._attr_suggested_display_precision = 2

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

    _device_group = DEVICE_STROMSTOTTE

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


class TotalPrisNorgesprisSensor(NettleieBaseSensor):
    """Sensor for totalpris med norgespris."""

    _device_group = DEVICE_NORGESPRIS

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_norgespris", "Total strømpris (norgespris)")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:map-marker"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("total_pris_norgespris")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "norgespris": self.coordinator.data.get("norgespris"),
                "norgespris_stromstotte": self.coordinator.data.get("norgespris_stromstotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                "note": "Norgespris er fast 50 øre/kWh fra Elhub",
            }
        return None


class PrisforskjellNorgesprisSensor(NettleieBaseSensor):
    """Sensor for prisforskjell mellom norgespris og vanlig pris."""

    _device_group = DEVICE_NORGESPRIS

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "prisforskjell_norgespris", "Prisforskjell (norgespris)")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-minus"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self):
        """Return the state."""
        if self.coordinator.data:
            return self.coordinator.data.get("kroner_spart_per_kwh")
        return None

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        if self.coordinator.data:
            norgespris = self.coordinator.data.get("norgespris")
            norgespris_stromstotte = self.coordinator.data.get("norgespris_stromstotte")
            norgespris_etter_stotte = None
            if norgespris is not None and norgespris_stromstotte is not None:
                norgespris_etter_stotte = norgespris - norgespris_stromstotte
            return {
                "din_pris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                "norgespris_etter_stotte": norgespris_etter_stotte,
                "differens_per_kwh": self.coordinator.data.get("kroner_spart_per_kwh"),
                "note": "Norgespris er fast 50 øre/kWh fra Elhub",
            }
        return None
