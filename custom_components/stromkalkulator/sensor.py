"""Sensor platform for Strømkalkulator."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_TSO,
    DOMAIN,
    ENOVA_AVGIFT,
    STROMSTOTTE_LEVEL,
    TSO_LIST,
    get_forbruksavgift,
    get_mva_sats,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .tso import TSOEntry

# Device group constants
DEVICE_NETTLEIE = "stromkalkulator"
DEVICE_STROMSTOTTE = "stromstotte"
DEVICE_NORGESPRIS = "norgespris"
DEVICE_MAANEDLIG = "maanedlig"
DEVICE_FORRIGE_MAANED = "forrige_maaned"

# Silver requirement: limit parallel updates
PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Strømkalkulator sensors."""
    coordinator: NettleieCoordinator = entry.runtime_data

    entities: list[NettleieBaseSensor] = [
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
        EnergileddDagSensor(coordinator, entry),
        EnergileddNattSensor(coordinator, entry),
        TariffSensor(coordinator, entry),
        # Nettleie - Avgifter
        OffentligeAvgifterSensor(coordinator, entry),
        ForbruksavgiftSensor(coordinator, entry),
        EnovaavgiftSensor(coordinator, entry),
        # Strømpriser
        TotalPriceSensor(coordinator, entry),
        ElectricityCompanyTotalSensor(coordinator, entry),
        # Strømstøtte
        StromstotteSensor(coordinator, entry),
        SpotprisEtterStotteSensor(coordinator, entry),
        TotalPrisEtterStotteSensor(coordinator, entry),
        TotalPrisInklAvgifterSensor(coordinator, entry),
        StromstotteKwhSensor(coordinator, entry),
        # Norgespris
        TotalPrisNorgesprisSensor(coordinator, entry),
        PrisforskjellNorgesprisSensor(coordinator, entry),
        NorgesprisAktivSensor(coordinator, entry),
        # Månedlig forbruk og kostnad
        MaanedligForbrukDagSensor(coordinator, entry),
        MaanedligForbrukNattSensor(coordinator, entry),
        MaanedligForbrukTotalSensor(coordinator, entry),
        MaanedligNettleieSensor(coordinator, entry),
        MaanedligAvgifterSensor(coordinator, entry),
        MaanedligStromstotteSensor(coordinator, entry),
        MaanedligTotalSensor(coordinator, entry),
        # Forrige måned sensors
        ForrigeMaanedForbrukDagSensor(coordinator, entry),
        ForrigeMaanedForbrukNattSensor(coordinator, entry),
        ForrigeMaanedForbrukTotalSensor(coordinator, entry),
        ForrigeMaanedNettleieSensor(coordinator, entry),
        ForrigeMaanedToppforbrukSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NettleieBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Strømkalkulator sensors."""

    _attr_has_entity_name = True
    _device_group: str = DEVICE_NETTLEIE
    _attr_unique_id: str
    _attr_translation_key: str
    _entry: ConfigEntry
    _tso: TSOEntry

    def __init__(
        self,
        coordinator: NettleieCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        translation_key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"
        self._attr_translation_key = translation_key
        self._entry = entry

        # Get TSO name for device info
        tso_id = entry.data.get(CONF_TSO, "bkk")
        self._tso = TSO_LIST.get(tso_id, TSO_LIST["bkk"])

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        device_names: dict[str, str] = {
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

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:currency-usd"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd", "energiledd")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr/mnd"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:transmission-tower"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitetstrinn", "kapasitetstrinn")
        self._attr_native_unit_of_measurement = "kr/mnd"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:transmission-tower"

    @property
    def native_value(self) -> float | int | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | int | None", self.coordinator.data.get("kapasitetsledd"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            attrs: dict[str, Any] = {
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

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:cash"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_price", "total_price")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("total_price_uten_stotte"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:lightning-bolt"
    _rank: int

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry, rank: int) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, f"maks_forbruk_{rank}", "maks_forbruk")
        self._rank = rank
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                values = list(top_3.values())
                return round(cast("float", values[self._rank - 1]), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                dates = list(top_3.keys())
                return {"dato": dates[self._rank - 1]}
        return None


class GjsForbrukSensor(NettleieBaseSensor):
    """Sensor for average of top 3 power consumption days."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:chart-line"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "gjennomsnitt_forbruk", "gjs_forbruk")
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:chart-line"

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            avg = self.coordinator.data.get("avg_top_3_kw")
            if avg is not None:
                return round(cast("float", avg), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "kapasitetstrinn": self.coordinator.data.get("kapasitetsledd"),
                "tso": self.coordinator.data.get("tso"),
            }
        return None


class TrinnNummerSensor(NettleieBaseSensor):
    """Sensor for capacity tier number."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_icon: str = "mdi:numeric"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_nummer", "trinn_nummer")
        self._attr_icon = "mdi:numeric"

    @property
    def native_value(self) -> int | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("int | None", self.coordinator.data.get("kapasitetstrinn_nummer"))
        return None


class TrinnIntervallSensor(NettleieBaseSensor):
    """Sensor for capacity tier interval."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_icon: str = "mdi:arrow-expand-horizontal"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "trinn_intervall", "trinn_intervall")
        self._attr_icon = "mdi:arrow-expand-horizontal"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("str | None", self.coordinator.data.get("kapasitetstrinn_intervall"))
        return None


class OffentligeAvgifterSensor(NettleieBaseSensor):
    """Sensor for offentlige avgifter (forbruksavgift, Enova, mva)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:bank"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "offentlige_avgifter", "offentlige_avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:bank"
        self._attr_suggested_display_precision = 2

    def _get_forbruksavgift(self) -> float:
        """Get forbruksavgift based on avgiftssone and current month."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        month = datetime.now().month
        return get_forbruksavgift(avgiftssone, month)

    def _get_mva_sats(self) -> float:
        """Get MVA rate based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return get_mva_sats(avgiftssone)

    @property
    def native_value(self) -> float:
        """Return total avgifter inkl. mva."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        total_eks_mva = forbruksavgift + ENOVA_AVGIFT
        return round(total_eks_mva * (1 + mva_sats), 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown of fees."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        month = datetime.now().month
        sesong = "vinter" if month <= 3 else "sommer"

        forbruksavgift_inkl_mva = round(forbruksavgift * (1 + mva_sats), 4)
        enova_inkl_mva = round(ENOVA_AVGIFT * (1 + mva_sats), 4)
        return {
            "avgiftssone": avgiftssone,
            "sesong": sesong,
            "forbruksavgift_eks_mva": forbruksavgift,
            "forbruksavgift_inkl_mva": forbruksavgift_inkl_mva,
            "enova_avgift_eks_mva": ENOVA_AVGIFT,
            "enova_avgift_inkl_mva": enova_inkl_mva,
            "mva_sats": f"{int(mva_sats * 100)}%",
            "note": "Disse avgiftene er inkludert i energileddet fra nettselskapet",
        }


class ElectricityCompanyTotalSensor(NettleieBaseSensor):
    """Sensor for total price with electricity company + nettleie."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:cash-plus"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "electricity_company_total", "electricity_company_total")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-plus"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            electricity_company_total = self.coordinator.data.get("electricity_company_total")
            if electricity_company_total is not None:
                return round(cast("float", electricity_company_total), 4)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:cash-refund"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte", "stromstotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-refund"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("stromstotte"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "terskel": STROMSTOTTE_LEVEL,
                "dekningsgrad": "90%",
            }
        return None


class SpotprisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for spot price after strømstøtte."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:currency-usd-off"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "spotpris_etter_stotte", "spotpris_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:currency-usd-off"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("spotpris_etter_stotte"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
            }
        return None


class TotalPrisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for total price after strømstøtte (spot + nettleie - støtte)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:cash-check"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_etter_stotte", "total_pris_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-check"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("total_price"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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


class TotalPrisInklAvgifterSensor(NettleieBaseSensor):
    """Sensor for total price including all taxes (for Energy Dashboard)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:receipt-text-check"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_inkl_avgifter", "total_pris_inkl_avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:receipt-text-check"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("total_price_inkl_avgifter"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes with breakdown."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "spotpris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
                "kapasitetsledd_per_kwh": self.coordinator.data.get("kapasitetsledd_per_kwh"),
                "forbruksavgift_inkl_mva": self.coordinator.data.get("forbruksavgift_inkl_mva"),
                "enova_inkl_mva": self.coordinator.data.get("enova_inkl_mva"),
                "offentlige_avgifter": self.coordinator.data.get("offentlige_avgifter"),
                "bruk": "Bruk denne sensoren i Energy Dashboard for korrekt totalpris",
            }
        return None


class TotalPrisNorgesprisSensor(NettleieBaseSensor):
    """Sensor for totalpris med norgespris."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:map-marker"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_norgespris", "total_pris_norgespris")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:map-marker"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("total_pris_norgespris"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
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

    _device_group: str = DEVICE_NORGESPRIS
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:cash-minus"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "prisforskjell_norgespris", "prisforskjell_norgespris")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:cash-minus"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("kroner_spart_per_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            norgespris = self.coordinator.data.get("norgespris")
            norgespris_stromstotte = self.coordinator.data.get("norgespris_stromstotte")
            norgespris_etter_stotte: float | None = None
            if norgespris is not None and norgespris_stromstotte is not None:
                norgespris_etter_stotte = norgespris - norgespris_stromstotte
            return {
                "din_pris_etter_stotte": self.coordinator.data.get("spotpris_etter_stotte"),
                "norgespris_etter_stotte": norgespris_etter_stotte,
                "differens_per_kwh": self.coordinator.data.get("kroner_spart_per_kwh"),
                "note": "Norgespris er fast 50 øre/kWh fra Elhub",
            }
        return None


class NorgesprisAktivSensor(NettleieBaseSensor):
    """Sensor showing if Norgespris is active."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_icon: str = "mdi:check-circle"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "norgespris_aktiv", "norgespris_aktiv")
        self._attr_icon = "mdi:check-circle"

    @property
    def native_value(self) -> str | None:
        """Return 'Ja' if Norgespris is active, 'Nei' otherwise."""
        if self.coordinator.data:
            has_norgespris = self.coordinator.data.get("has_norgespris", False)
            return "Ja" if has_norgespris else "Nei"
        return None


# =============================================================================
# Fakturasammenligning - Separate sensorer for hver fakturalinje
# =============================================================================


class EnergileddDagSensor(NettleieBaseSensor):
    """Sensor for energiledd dag-sats (eks. avgifter, for fakturasammenligning)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:weather-sunny"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_dag", "energiledd_dag")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:weather-sunny"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd_dag"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
            mva_sats = get_mva_sats(avgiftssone)
            energiledd_dag = self.coordinator.data.get("energiledd_dag", 0)
            # Beregn pris eks. avgifter for fakturasammenligning
            forbruksavgift = get_forbruksavgift(avgiftssone, datetime.now().month)
            energiledd_eks_avgifter = energiledd_dag - forbruksavgift - ENOVA_AVGIFT
            if mva_sats > 0:
                energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)
            return {
                "inkl_avgifter_mva": energiledd_dag,
                "eks_avgifter_mva": round(energiledd_eks_avgifter, 4),
                "note": "Fakturaen viser pris eks. avgifter. Sammenlign med eks_avgifter_mva.",
            }
        return None


class EnergileddNattSensor(NettleieBaseSensor):
    """Sensor for energiledd natt/helg-sats (eks. avgifter, for fakturasammenligning)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:weather-night"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_natt", "energiledd_natt")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:weather-night"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("energiledd_natt"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
            mva_sats = get_mva_sats(avgiftssone)
            energiledd_natt = self.coordinator.data.get("energiledd_natt", 0)
            # Beregn pris eks. avgifter for fakturasammenligning
            forbruksavgift = get_forbruksavgift(avgiftssone, datetime.now().month)
            energiledd_eks_avgifter = energiledd_natt - forbruksavgift - ENOVA_AVGIFT
            if mva_sats > 0:
                energiledd_eks_avgifter = energiledd_eks_avgifter / (1 + mva_sats)
            return {
                "inkl_avgifter_mva": energiledd_natt,
                "eks_avgifter_mva": round(energiledd_eks_avgifter, 4),
                "note": "Fakturaen viser pris eks. avgifter. Sammenlign med eks_avgifter_mva.",
            }
        return None


class ForbruksavgiftSensor(NettleieBaseSensor):
    """Sensor for forbruksavgift (elavgift) per kWh."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:lightning-bolt"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forbruksavgift", "forbruksavgift")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 2

    def _get_forbruksavgift(self) -> float:
        """Get forbruksavgift based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        month = datetime.now().month
        return get_forbruksavgift(avgiftssone, month)

    def _get_mva_sats(self) -> float:
        """Get MVA rate based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return get_mva_sats(avgiftssone)

    @property
    def native_value(self) -> float:
        """Return forbruksavgift inkl. mva."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        return round(forbruksavgift * (1 + mva_sats), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown."""
        forbruksavgift = self._get_forbruksavgift()
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return {
            "eks_mva": forbruksavgift,
            "inkl_mva": round(forbruksavgift * (1 + mva_sats), 4),
            "mva_sats": f"{int(mva_sats * 100)}%",
            "avgiftssone": avgiftssone,
            "ore_per_kwh_eks_mva": round(forbruksavgift * 100, 2),
            "note": "Fakturaen viser forbruksavgift eks. mva",
        }


class EnovaavgiftSensor(NettleieBaseSensor):
    """Sensor for Enova-avgift per kWh."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:leaf"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "enovaavgift", "enovaavgift")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:leaf"
        self._attr_suggested_display_precision = 2

    def _get_mva_sats(self) -> float:
        """Get MVA rate based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return get_mva_sats(avgiftssone)

    @property
    def native_value(self) -> float:
        """Return Enova-avgift inkl. mva."""
        mva_sats = self._get_mva_sats()
        return round(ENOVA_AVGIFT * (1 + mva_sats), 4)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return breakdown."""
        mva_sats = self._get_mva_sats()
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        return {
            "eks_mva": ENOVA_AVGIFT,
            "inkl_mva": round(ENOVA_AVGIFT * (1 + mva_sats), 4),
            "mva_sats": f"{int(mva_sats * 100)}%",
            "avgiftssone": avgiftssone,
            "ore_per_kwh_eks_mva": round(ENOVA_AVGIFT * 100, 2),
            "note": "Fakturaen viser Enova-avgift eks. mva (1,0 øre/kWh)",
        }


class StromstotteKwhSensor(NettleieBaseSensor):
    """Sensor for strømstøtte-berettiget forbruk (kWh over terskel)."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_icon: str = "mdi:cash-check"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte_aktiv", "stromstotte_kwh")
        self._attr_icon = "mdi:cash-check"

    @property
    def native_value(self) -> str | None:
        """Return 'Ja' if strømstøtte is active, 'Nei' otherwise."""
        if self.coordinator.data:
            stromstotte = self.coordinator.data.get("stromstotte", 0)
            return "Ja" if stromstotte > 0 else "Nei"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes."""
        if self.coordinator.data:
            spot_price = self.coordinator.data.get("spot_price", 0)
            stromstotte = self.coordinator.data.get("stromstotte", 0)
            return {
                "spotpris": spot_price,
                "terskel": STROMSTOTTE_LEVEL,
                "over_terskel": spot_price > STROMSTOTTE_LEVEL,
                "stromstotte_per_kwh": stromstotte,
                "note": f"Timer hvor spotpris > {STROMSTOTTE_LEVEL * 100:.2f} øre/kWh gir strømstøtte på fakturaen",
            }
        return None


class TariffSensor(NettleieBaseSensor):
    """Sensor for current tariff period (dag/natt) - for use with utility_meter."""

    _attr_icon: str = "mdi:clock-outline"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "tariff", "tariff")
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> str | None:
        """Return current tariff: 'dag' or 'natt'."""
        if self.coordinator.data:
            is_day = self.coordinator.data.get("is_day_rate")
            return "dag" if is_day else "natt"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes with schedule info."""
        if self.coordinator.data:
            return {
                "is_day_rate": self.coordinator.data.get("is_day_rate"),
                "dag_periode": "Hverdager 06:00-22:00 (ikke helligdager)",
                "natt_periode": "22:00-06:00, helger og helligdager",
                "bruk": "Bruk denne sensoren til å styre utility_meter tariff-bytte",
            }
        return None


# =============================================================================
# MÅNEDLIG FORBRUK OG KOSTNAD - Device: "Månedlig"
# =============================================================================


class MaanedligBaseSensor(NettleieBaseSensor):
    """Base class for monthly consumption/cost sensors."""

    _device_group: str = DEVICE_MAANEDLIG

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for Månedlig device."""
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": "Månedlig forbruk",
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }


class MaanedligForbrukDagSensor(MaanedligBaseSensor):
    """Sensor for monthly day tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_icon: str = "mdi:weather-sunny"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_dag", "maanedlig_forbruk_dag")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:weather-sunny"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return monthly day consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_dag_kwh"))
        return None


class MaanedligForbrukNattSensor(MaanedligBaseSensor):
    """Sensor for monthly night tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_icon: str = "mdi:weather-night"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_natt", "maanedlig_forbruk_natt")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:weather-night"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return monthly night consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_natt_kwh"))
        return None


class MaanedligForbrukTotalSensor(MaanedligBaseSensor):
    """Sensor for total monthly consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL_INCREASING
    _attr_icon: str = "mdi:lightning-bolt"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_forbruk_total", "maanedlig_forbruk_total")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return total monthly consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_consumption_total_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return consumption breakdown."""
        if self.coordinator.data:
            return {
                "dag_kwh": self.coordinator.data.get("monthly_consumption_dag_kwh"),
                "natt_kwh": self.coordinator.data.get("monthly_consumption_natt_kwh"),
            }
        return None


class MaanedligNettleieSensor(MaanedligBaseSensor):
    """Sensor for monthly grid rent cost (energiledd + kapasitetsledd)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:transmission-tower"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_nettleie", "maanedlig_nettleie")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:transmission-tower"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Calculate monthly grid rent cost."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
            return round(
                (cast("float", dag_kwh) * cast("float", dag_pris))
                + (cast("float", natt_kwh) * cast("float", natt_pris))
                + cast("float", kapasitet),
                2,
            )
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
            return {
                "energiledd_dag_kr": round(dag_kwh * dag_pris, 2),
                "energiledd_natt_kr": round(natt_kwh * natt_pris, 2),
                "kapasitetsledd_kr": kapasitet,
            }
        return None


class MaanedligAvgifterSensor(MaanedligBaseSensor):
    """Sensor for monthly public fees (forbruksavgift + Enova)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:bank"
    _attr_suggested_display_precision: int = 0
    _avgiftssone: str

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_avgifter", "maanedlig_avgifter")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:bank"
        self._attr_suggested_display_precision = 0
        self._avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    @property
    def native_value(self) -> float | None:
        """Calculate monthly public fees."""
        if self.coordinator.data:
            total_kwh = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
            month = datetime.now().month
            forbruksavgift = get_forbruksavgift(self._avgiftssone, month)
            mva_sats = get_mva_sats(self._avgiftssone)

            # Avgifter inkl. mva
            forbruksavgift_inkl = forbruksavgift * (1 + mva_sats)
            enova_inkl = ENOVA_AVGIFT * (1 + mva_sats)

            return round(cast("float", total_kwh) * (forbruksavgift_inkl + enova_inkl), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return fee breakdown."""
        if self.coordinator.data:
            total_kwh = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
            month = datetime.now().month
            forbruksavgift = get_forbruksavgift(self._avgiftssone, month)
            mva_sats = get_mva_sats(self._avgiftssone)

            forbruksavgift_inkl = forbruksavgift * (1 + mva_sats)
            enova_inkl = ENOVA_AVGIFT * (1 + mva_sats)

            return {
                "forbruksavgift_kr": round(total_kwh * forbruksavgift_inkl, 2),
                "enovaavgift_kr": round(total_kwh * enova_inkl, 2),
                "avgiftssone": self._avgiftssone,
            }
        return None


class MaanedligStromstotteSensor(MaanedligBaseSensor):
    """Sensor for estimated monthly electricity subsidy.

    Note: This is an estimate based on current subsidy rate.
    Actual subsidy is calculated hourly by grid company.
    """

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:cash-plus"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_stromstotte", "maanedlig_stromstotte")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:cash-plus"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Estimate monthly subsidy (rough calculation)."""
        if self.coordinator.data:
            total_kwh = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
            stromstotte_per_kwh = self.coordinator.data.get("stromstotte", 0)
            return round(cast("float", total_kwh) * cast("float", stromstotte_per_kwh), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return subsidy info."""
        if self.coordinator.data:
            return {
                "merknad": "Estimat basert på gjeldende strømstøtte-sats. Faktisk støtte beregnes time-for-time.",
                "stromstotte_per_kwh": self.coordinator.data.get("stromstotte"),
                "har_norgespris": self.coordinator.data.get("har_norgespris"),
            }
        return None


class MaanedligTotalSensor(MaanedligBaseSensor):
    """Sensor for total monthly cost (nettleie + avgifter - strømstøtte)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:receipt-text"
    _attr_suggested_display_precision: int = 0
    _avgiftssone: str

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "maanedlig_total", "maanedlig_total")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:receipt-text"
        self._attr_suggested_display_precision = 0
        self._avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    @property
    def native_value(self) -> float | None:
        """Calculate total monthly cost."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            total_kwh = dag_kwh + natt_kwh
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
            stromstotte = self.coordinator.data.get("stromstotte", 0)

            month = datetime.now().month
            forbruksavgift = get_forbruksavgift(self._avgiftssone, month)
            mva_sats = get_mva_sats(self._avgiftssone)

            # Nettleie
            nettleie = (
                (cast("float", dag_kwh) * cast("float", dag_pris))
                + (cast("float", natt_kwh) * cast("float", natt_pris))
                + cast("float", kapasitet)
            )

            # Avgifter inkl. mva
            avgifter = cast("float", total_kwh) * ((forbruksavgift + ENOVA_AVGIFT) * (1 + mva_sats))

            # Strømstøtte (fratrekk)
            stotte = cast("float", total_kwh) * cast("float", stromstotte)

            return round(nettleie + avgifter - stotte, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            total_kwh = dag_kwh + natt_kwh
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
            stromstotte = self.coordinator.data.get("stromstotte", 0)

            month = datetime.now().month
            forbruksavgift = get_forbruksavgift(self._avgiftssone, month)
            mva_sats = get_mva_sats(self._avgiftssone)

            nettleie = (dag_kwh * dag_pris) + (natt_kwh * natt_pris) + kapasitet
            avgifter = total_kwh * ((forbruksavgift + ENOVA_AVGIFT) * (1 + mva_sats))
            stotte = total_kwh * stromstotte

            return {
                "nettleie_kr": round(nettleie, 2),
                "avgifter_kr": round(avgifter, 2),
                "stromstotte_kr": round(stotte, 2),
                "forbruk_dag_kwh": round(dag_kwh, 1),
                "forbruk_natt_kwh": round(natt_kwh, 1),
                "forbruk_total_kwh": round(total_kwh, 1),
            }
        return None


# =============================================================================
# FORRIGE MÅNED - Device: "Forrige måned"
# =============================================================================


class ForrigeMaanedBaseSensor(NettleieBaseSensor):
    """Base class for previous month sensors."""

    _device_group: str = DEVICE_FORRIGE_MAANED

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for Forrige måned device."""
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": "Forrige måned",
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }


class ForrigeMaanedForbrukDagSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month day tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:weather-sunny"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_dag", "forrige_maaned_forbruk_dag")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:weather-sunny"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return previous month day consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_dag_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {"måned": self.coordinator.data.get("previous_month_name")}
        return None


class ForrigeMaanedForbrukNattSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month night tariff consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:weather-night"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_natt", "forrige_maaned_forbruk_natt")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:weather-night"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return previous month night consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_natt_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {"måned": self.coordinator.data.get("previous_month_name")}
        return None


class ForrigeMaanedForbrukTotalSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month total consumption."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:lightning-bolt"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_forbruk_total", "forrige_maaned_forbruk_total")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return previous month total consumption."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_consumption_total_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return consumption breakdown."""
        if self.coordinator.data:
            return {
                "måned": self.coordinator.data.get("previous_month_name"),
                "dag_kwh": self.coordinator.data.get("previous_month_consumption_dag_kwh"),
                "natt_kwh": self.coordinator.data.get("previous_month_consumption_natt_kwh"),
            }
        return None


class ForrigeMaanedNettleieSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month grid rent cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:transmission-tower"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_nettleie", "forrige_maaned_nettleie")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:transmission-tower"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Calculate previous month grid rent cost."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("previous_month_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("previous_month_consumption_natt_kwh", 0)
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)

            # Get kapasitetsledd from previous month's top 3
            top_3 = self.coordinator.data.get("previous_month_top_3", {})
            if top_3:
                avg_power = sum(top_3.values()) / len(top_3)
                kapasitet = self._get_kapasitetsledd_for_avg(avg_power)
            else:
                kapasitet = 0

            return round(
                (cast("float", dag_kwh) * cast("float", dag_pris))
                + (cast("float", natt_kwh) * cast("float", natt_pris))
                + cast("float", kapasitet),
                2,
            )
        return None

    def _get_kapasitetsledd_for_avg(self, avg_power: float) -> int:
        """Get kapasitetsledd based on average power."""
        kapasitetstrinn = self.coordinator.kapasitetstrinn
        for threshold, price in kapasitetstrinn:
            if avg_power <= threshold:
                return cast("int", price)
        return cast("int", kapasitetstrinn[-1][1]) if kapasitetstrinn else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return cost breakdown."""
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("previous_month_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("previous_month_consumption_natt_kwh", 0)
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)

            top_3 = self.coordinator.data.get("previous_month_top_3", {})
            if top_3:
                avg_power = sum(top_3.values()) / len(top_3)
                kapasitet = self._get_kapasitetsledd_for_avg(avg_power)
            else:
                avg_power = 0
                kapasitet = 0

            return {
                "måned": self.coordinator.data.get("previous_month_name"),
                "energiledd_dag_kr": round(dag_kwh * dag_pris, 2),
                "energiledd_natt_kr": round(natt_kwh * natt_pris, 2),
                "kapasitetsledd_kr": kapasitet,
                "snitt_topp_3_kw": round(avg_power, 2),
            }
        return None


class ForrigeMaanedToppforbrukSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month top 3 power consumption average."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:arrow-up-bold"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forrige_maaned_toppforbruk", "forrige_maaned_toppforbruk")
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:arrow-up-bold"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return previous month average top 3 power."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_avg_top_3_kw"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return top 3 days breakdown."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("previous_month_top_3", {})
            attrs: dict[str, Any] = {"måned": self.coordinator.data.get("previous_month_name")}
            for i, (date, kw) in enumerate(sorted(top_3.items(), key=lambda x: x[1], reverse=True), 1):
                attrs[f"topp_{i}_dato"] = date
                attrs[f"topp_{i}_kw"] = round(kw, 2)
            return attrs
        return None
