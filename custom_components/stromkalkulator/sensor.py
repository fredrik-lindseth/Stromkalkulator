"""Sensor platform for Strømkalkulator."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import (
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_DSO,
    DOMAIN,
    DSO_LIST,
    ENOVA_AVGIFT,
    STROMSTOTTE_LEVEL,
    get_forbruksavgift,
    get_mva_sats,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .dso import DSOEntry

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
        MarginNesteTrinnSensor(coordinator, entry),
        KapasitetVarselSensor(coordinator, entry),
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
        StromprisPerKwhSensor(coordinator, entry),
        # Strømstøtte
        StromstotteSensor(coordinator, entry),
        SpotprisEtterStotteSensor(coordinator, entry),
        TotalPrisEtterStotteSensor(coordinator, entry),
        TotalPrisInklAvgifterSensor(coordinator, entry),
        StromstotteKwhSensor(coordinator, entry),
        StromstotteGjenstaaendeSensor(coordinator, entry),
        StromprisPerKwhEtterStotteSensor(coordinator, entry),
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
        MaanedligNorgesprisDifferanseSensor(coordinator, entry),
        MaanedligNorgesprisKompensasjonSensor(coordinator, entry),
        DagskostnadSensor(coordinator, entry),
        EstimertMaanedskostnadSensor(coordinator, entry),
        # Forrige måned sensors
        ForrigeMaanedForbrukDagSensor(coordinator, entry),
        ForrigeMaanedForbrukNattSensor(coordinator, entry),
        ForrigeMaanedForbrukTotalSensor(coordinator, entry),
        ForrigeMaanedNettleieSensor(coordinator, entry),
        ForrigeMaanedToppforbrukSensor(coordinator, entry),
        ForrigeMaanedNorgesprisKompensasjonSensor(coordinator, entry),
    ]

    async_add_entities(entities)


class NettleieBaseSensor(CoordinatorEntity, SensorEntity):  # type: ignore[misc]
    """Base class for Strømkalkulator sensors."""

    _attr_has_entity_name = True
    _device_group: str = DEVICE_NETTLEIE
    _attr_unique_id: str
    _attr_translation_key: str
    _entry: ConfigEntry
    _dso: DSOEntry

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

        # Get DSO name for device info
        dso_id = entry.data.get(CONF_DSO, "bkk")
        self._dso = DSO_LIST.get(dso_id, DSO_LIST["bkk"])

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info."""
        device_names: dict[str, str] = {
            DEVICE_NETTLEIE: f"Nettleie ({self._dso['name']})",
            DEVICE_STROMSTOTTE: "Strømstøtte",
            DEVICE_NORGESPRIS: "Norgespris",
        }
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": device_names.get(self._device_group, f"Nettleie ({self._dso['name']})"),
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }


class EnergileddSensor(NettleieBaseSensor):
    """Sensor for energiledd."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:currency-usd"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd", "energiledd")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
                "dso": self.coordinator.data.get("dso"),
            }
        return None


class KapasitetstrinnSensor(NettleieBaseSensor):
    """Sensor for kapasitetstrinn."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr/mnd"
    _attr_icon: str = "mdi:transmission-tower"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitetstrinn", "kapasitetstrinn")
        self._attr_native_unit_of_measurement = "kr/mnd"
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
                "dso": self.coordinator.data.get("dso"),
            }
            for i, (date, entry) in enumerate(top_3.items(), 1):
                attrs[f"maks_{i}_dato"] = date
                attrs[f"maks_{i}_kw"] = round(entry["kw"], 2)
                attrs[f"maks_{i}_time"] = entry.get("hour")
            return attrs
        return None


class MarginNesteTrinnSensor(NettleieBaseSensor):
    """Sensor for margin to next capacity tier."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement: str = "kW"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:arrow-up-bold"
    _attr_suggested_display_precision: int = 1

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "margin_neste_trinn", "margin_neste_trinn")
        self._attr_native_unit_of_measurement = "kW"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:arrow-up-bold"
        self._attr_suggested_display_precision = 1

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("margin_neste_trinn_kw"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "naavarende_trinn_pris": self.coordinator.data.get("kapasitetsledd"),
                "neste_trinn_pris": self.coordinator.data.get("neste_trinn_pris"),
            }
        return None


class KapasitetVarselSensor(NettleieBaseSensor):
    """Binary-like sensor that warns when close to next capacity tier."""

    _attr_icon: str = "mdi:alert"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "kapasitet_varsel", "kapasitet_varsel")
        self._attr_icon = "mdi:alert"

    @property
    def native_value(self) -> str | None:
        """Return the state."""
        if self.coordinator.data:
            varsel = self.coordinator.data.get("kapasitet_varsel", False)
            return "on" if varsel else "off"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "margin_kw": self.coordinator.data.get("margin_neste_trinn_kw"),
            }
        return None


class TotalPriceSensor(NettleieBaseSensor):
    """Sensor for total electricity price (without strømstøtte)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:cash"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_price", "total_price")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
                "dso": self.coordinator.data.get("dso"),
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
                entries = list(top_3.values())
                return round(cast("float", entries[self._rank - 1]["kw"]), 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            top_3 = self.coordinator.data.get("top_3_days", {})
            if len(top_3) >= self._rank:
                dates = list(top_3.keys())
                entries = list(top_3.values())
                return {
                    "dato": dates[self._rank - 1],
                    "time": entries[self._rank - 1].get("hour"),
                }
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
                "dso": self.coordinator.data.get("dso"),
            }
        return None


class TrinnNummerSensor(NettleieBaseSensor):
    """Sensor for capacity tier number."""

    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
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
    _attr_entity_registry_enabled_default: bool = False
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
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:bank"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "offentlige_avgifter", "offentlige_avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_icon = "mdi:bank"
        self._attr_suggested_display_precision = 2

    def _get_forbruksavgift(self) -> float:
        """Get forbruksavgift based on avgiftssone and current month."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        month = dt_util.now().month
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
        month = dt_util.now().month
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

    _attr_entity_registry_enabled_default: bool = False
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:cash-plus"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "electricity_company_total", "electricity_company_total")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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


class StromprisPerKwhSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh (without capacity fee)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:flash"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_per_kwh", "strompris_per_kwh")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_icon = "mdi:flash"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("strompris_per_kwh"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spot_price": self.coordinator.data.get("spot_price"),
                "energiledd": self.coordinator.data.get("energiledd"),
            }
        return None


class StromstotteSensor(NettleieBaseSensor):
    """Sensor for strømstøtte per kWh."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:cash-refund"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte", "stromstotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
                "tak_naadd": self.coordinator.data.get("stromstotte_tak_naadd", False),
                "boligtype": self.coordinator.data.get("boligtype", "bolig"),
            }
        return None


class SpotprisEtterStotteSensor(NettleieBaseSensor):
    """Sensor for spot price after strømstøtte."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:currency-usd-off"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "spotpris_etter_stotte", "spotpris_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
    _attr_icon: str = "mdi:cash-check"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_etter_stotte", "total_pris_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
    _attr_icon: str = "mdi:receipt-text-check"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_inkl_avgifter", "total_pris_inkl_avgifter")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
                "bruk": "Marginalkostnad per kWh for Energy Dashboard. Månedlig sum avviker fra faktura pga. kapasitetsledd-fordeling.",
            }
        return None


class TotalPrisNorgesprisSensor(NettleieBaseSensor):
    """Sensor for totalpris med norgespris."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:map-marker"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "total_pris_norgespris", "total_pris_norgespris")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
                "norgespris_over_tak": self.coordinator.data.get("norgespris_over_tak", False),
                "boligtype": self.coordinator.data.get("boligtype", "bolig"),
            }
        return None


class PrisforskjellNorgesprisSensor(NettleieBaseSensor):
    """Sensor for prisforskjell mellom norgespris og vanlig pris."""

    _device_group: str = DEVICE_NORGESPRIS
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:cash-minus"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "prisforskjell_norgespris", "prisforskjell_norgespris")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
            has_norgespris = self.coordinator.data.get("har_norgespris", False)
            return "Ja" if has_norgespris else "Nei"
        return None


# =============================================================================
# Fakturasammenligning - Separate sensorer for hver fakturalinje
# =============================================================================


class EnergileddDagSensor(NettleieBaseSensor):
    """Sensor for energiledd dag-sats (eks. avgifter, for fakturasammenligning)."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_entity_category: EntityCategory = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:weather-sunny"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_dag", "energiledd_dag")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
            forbruksavgift = get_forbruksavgift(avgiftssone, dt_util.now().month)
            energiledd_eks_avgifter = energiledd_dag / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
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
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:weather-night"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "energiledd_natt", "energiledd_natt")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
            forbruksavgift = get_forbruksavgift(avgiftssone, dt_util.now().month)
            energiledd_eks_avgifter = energiledd_natt / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT
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
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:lightning-bolt"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "forbruksavgift", "forbruksavgift")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_suggested_display_precision = 2

    def _get_forbruksavgift(self) -> float:
        """Get forbruksavgift based on avgiftssone."""
        avgiftssone = self._entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        month = dt_util.now().month
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
    _attr_entity_registry_enabled_default: bool = False
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:leaf"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "enovaavgift", "enovaavgift")
        self._attr_native_unit_of_measurement = "NOK/kWh"
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
            boligtype = self.coordinator.data.get("boligtype", "bolig")
            return {
                "spotpris": spot_price,
                "terskel": STROMSTOTTE_LEVEL,
                "over_terskel": spot_price > STROMSTOTTE_LEVEL,
                "stromstotte_per_kwh": stromstotte,
                "boligtype": boligtype,
                "note": f"Timer hvor spotpris > {STROMSTOTTE_LEVEL * 100:.2f} øre/kWh gir strømstøtte på fakturaen",
            }
        return None


class StromstotteGjenstaaendeSensor(NettleieBaseSensor):
    """Sensor for remaining kWh before strømstøtte cap."""

    _device_group: str = DEVICE_STROMSTOTTE
    _attr_native_unit_of_measurement: str = "kWh"
    _attr_state_class: SensorStateClass = SensorStateClass.MEASUREMENT
    _attr_icon: str = "mdi:gauge"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "stromstotte_gjenstaaende", "stromstotte_gjenstaaende")
        self._attr_native_unit_of_measurement = "kWh"
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:gauge"

    @property
    def native_value(self) -> float | None:
        """Return remaining kWh before cap is reached."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("stromstotte_gjenstaaende_kwh"))
        return None


class StromprisPerKwhEtterStotteSensor(NettleieBaseSensor):
    """Sensor for electricity price per kWh after subsidy (without capacity fee)."""

    _attr_entity_registry_enabled_default: bool = False
    _device_group: str = DEVICE_STROMSTOTTE
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "NOK/kWh"
    _attr_icon: str = "mdi:flash-outline"
    _attr_suggested_display_precision: int = 2

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, entry, "strompris_per_kwh_etter_stotte", "strompris_per_kwh_etter_stotte")
        self._attr_native_unit_of_measurement = "NOK/kWh"
        self._attr_icon = "mdi:flash-outline"
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("strompris_per_kwh_etter_stotte"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "spotpris": self.coordinator.data.get("spot_price"),
                "stromstotte": self.coordinator.data.get("stromstotte"),
                "energiledd": self.coordinator.data.get("energiledd"),
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
            dag = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            total = self.coordinator.data.get("monthly_consumption_total_kwh", 0)
            return {
                "dag_kwh": dag,
                "natt_kwh": natt,
                "dag_pct": round(dag / total * 100, 1) if total > 0 else 0.0,
                "natt_pct": round(natt / total * 100, 1) if total > 0 else 0.0,
            }
        return None


class MaanedligNettleieSensor(MaanedligBaseSensor):
    """Sensor for monthly grid rent cost (energiledd + kapasitetsledd)."""

    _attr_entity_registry_enabled_default: bool = False
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

    _attr_entity_registry_enabled_default: bool = False
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
            month = dt_util.now().month
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
            month = dt_util.now().month
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

    _attr_entity_registry_enabled_default: bool = False
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
        """Calculate total monthly cost.

        energiledd_dag/natt fra dso.py inkluderer allerede forbruksavgift og
        Enova-avgift, så nettleie-beløpet er komplett. Avgifter legges IKKE
        til separat — det ville dobbelttelle dem.
        """
        if self.coordinator.data:
            dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
            total_kwh = dag_kwh + natt_kwh
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
            stromstotte = self.coordinator.data.get("stromstotte", 0)

            # Nettleie (energiledd inkl. avgifter + kapasitetsledd)
            nettleie = (
                (cast("float", dag_kwh) * cast("float", dag_pris))
                + (cast("float", natt_kwh) * cast("float", natt_pris))
                + cast("float", kapasitet)
            )

            # Strømstøtte (fratrekk)
            stotte = cast("float", total_kwh) * cast("float", stromstotte)

            return round(nettleie - stotte, 2)
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

            nettleie = (dag_kwh * dag_pris) + (natt_kwh * natt_pris) + kapasitet
            stotte = total_kwh * stromstotte
            total_kostnad = nettleie - stotte

            return {
                "nettleie_kr": round(nettleie, 2),
                "stromstotte_kr": round(stotte, 2),
                "forbruk_dag_kwh": round(dag_kwh, 1),
                "forbruk_natt_kwh": round(natt_kwh, 1),
                "forbruk_total_kwh": round(total_kwh, 1),
                "vektet_snittpris_kr_per_kwh": round(total_kostnad / total_kwh, 4) if total_kwh > 0 else None,
            }
        return None


class MaanedligNorgesprisDifferanseSensor(NettleieBaseSensor):
    """Sensor for accumulated monthly Norgespris savings/loss."""

    _device_group: str = DEVICE_MAANEDLIG
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:scale-balance"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "maanedlig_norgespris_diff", "maanedlig_norgespris_diff")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:scale-balance"
        self._attr_suggested_display_precision = 0

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for Månedlig device."""
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": "Månedlig forbruk",
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_norgespris_diff_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            har_norgespris = self.coordinator.data.get("har_norgespris", False)
            return {
                "sammenligner_med": "spotpris" if har_norgespris else "Norgespris",
                "positiv_betyr": "du sparer med nåværende avtale",
            }
        return None


class MaanedligNorgesprisKompensasjonSensor(NettleieBaseSensor):
    """Sensor for accumulated monthly Norgespris compensation (norgespris - spot) * kWh."""

    _device_group: str = DEVICE_MAANEDLIG
    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:cash-sync"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "maanedlig_norgespris_kompensasjon", "maanedlig_norgespris_kompensasjon")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:cash-sync"
        self._attr_suggested_display_precision = 0

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device info for Maanedlig device."""
        return {
            "identifiers": {(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            "name": "Månedlig forbruk",
            "manufacturer": "Fredrik Lindseth",
            "model": "Strømkalkulator",
        }

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("monthly_norgespris_compensation_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.coordinator.data:
            return {
                "formel": "(norgespris - spotpris) * kWh, akkumulert per time",
                "negativ_betyr": "spot dyrere enn norgespris",
            }
        return None


class DagskostnadSensor(MaanedligBaseSensor):
    """Sensor for today's accumulated cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:calendar-today"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "daily_cost", "dagskostnad")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:calendar-today"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("daily_cost_kr"))
        return None


class EstimertMaanedskostnadSensor(MaanedligBaseSensor):
    """Sensor for estimated total monthly cost."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_icon: str = "mdi:crystal-ball"
    _attr_suggested_display_precision: int = 0
    _avgiftssone: str

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "estimated_monthly_cost", "estimert_maanedskostnad")
        self._attr_native_unit_of_measurement = "kr"
        self._attr_icon = "mdi:crystal-ball"
        self._attr_suggested_display_precision = 0
        self._avgiftssone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None

        now = dt_util.now()
        day_of_month = now.day
        # Calculate days in current month
        if now.month == 12:
            days_in_month = 31
        else:
            days_in_month = (now.replace(month=now.month + 1, day=1) - timedelta(days=1)).day

        dag_kwh = self.coordinator.data.get("monthly_consumption_dag_kwh", 0)
        natt_kwh = self.coordinator.data.get("monthly_consumption_natt_kwh", 0)
        total_kwh = dag_kwh + natt_kwh
        dag_pris = self.coordinator.data.get("energiledd_dag", 0)
        natt_pris = self.coordinator.data.get("energiledd_natt", 0)
        kapasitet = self.coordinator.data.get("kapasitetsledd", 0)
        stromstotte = self.coordinator.data.get("stromstotte", 0)

        # energiledd_dag/natt inkluderer allerede forbruksavgift + enova
        nettleie_variable = (dag_kwh * dag_pris) + (natt_kwh * natt_pris)
        stotte = total_kwh * stromstotte
        variable_cost = nettleie_variable - stotte

        if day_of_month == 0:
            return None

        estimated_variable = (variable_cost / day_of_month) * days_in_month
        return round(estimated_variable + kapasitet, 0)


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
            return {"maaned": self.coordinator.data.get("previous_month_name")}
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
            return {"maaned": self.coordinator.data.get("previous_month_name")}
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
                "maaned": self.coordinator.data.get("previous_month_name"),
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
            kapasitet = self.coordinator.data.get("previous_month_kapasitetsledd", 0)

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
            dag_kwh = self.coordinator.data.get("previous_month_consumption_dag_kwh", 0)
            natt_kwh = self.coordinator.data.get("previous_month_consumption_natt_kwh", 0)
            dag_pris = self.coordinator.data.get("energiledd_dag", 0)
            natt_pris = self.coordinator.data.get("energiledd_natt", 0)
            kapasitet = self.coordinator.data.get("previous_month_kapasitetsledd", 0)
            kapasitetstrinn = self.coordinator.data.get("previous_month_kapasitetstrinn", "")

            return {
                "maaned": self.coordinator.data.get("previous_month_name"),
                "energiledd_dag_kr": round(dag_kwh * dag_pris, 2),
                "energiledd_natt_kr": round(natt_kwh * natt_pris, 2),
                "kapasitetsledd_kr": kapasitet,
                "kapasitetstrinn": kapasitetstrinn,
                "snitt_topp_3_kw": self.coordinator.data.get("previous_month_avg_top_3_kw", 0.0),
                "norgespris_differanse_kr": self.coordinator.data.get(
                    "previous_month_norgespris_diff_kr", 0.0
                ),
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
            attrs: dict[str, Any] = {"maaned": self.coordinator.data.get("previous_month_name")}
            sorted_entries = sorted(top_3.items(), key=lambda x: x[1]["kw"], reverse=True)
            for i, (date, entry) in enumerate(sorted_entries, 1):
                attrs[f"topp_{i}_dato"] = date
                attrs[f"topp_{i}_kw"] = round(entry["kw"], 2)
                attrs[f"topp_{i}_time"] = entry.get("hour")
            return attrs
        return None


class ForrigeMaanedNorgesprisKompensasjonSensor(ForrigeMaanedBaseSensor):
    """Sensor for previous month Norgespris compensation."""

    _attr_device_class: SensorDeviceClass = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement: str = "kr"
    _attr_state_class: SensorStateClass = SensorStateClass.TOTAL
    _attr_icon: str = "mdi:cash-sync"
    _attr_suggested_display_precision: int = 0

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator, entry, "forrige_maaned_norgespris_kompensasjon", "forrige_maaned_norgespris_kompensasjon"
        )
        self._attr_native_unit_of_measurement = "kr"
        self._attr_state_class = SensorStateClass.TOTAL
        self._attr_icon = "mdi:cash-sync"
        self._attr_suggested_display_precision = 0

    @property
    def native_value(self) -> float | None:
        """Return previous month Norgespris compensation."""
        if self.coordinator.data:
            return cast("float | None", self.coordinator.data.get("previous_month_norgespris_compensation_kr"))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the month name."""
        if self.coordinator.data:
            return {
                "maaned": self.coordinator.data.get("previous_month_name"),
                "formel": "(norgespris - spotpris) * kWh, akkumulert per time",
            }
        return None
