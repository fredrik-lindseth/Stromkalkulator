"""Binary sensor platform for Strømkalkulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DSO, DEFAULT_DSO, DEFAULT_NAME, DOMAIN, MANUFACTURER
from .dso import DSO_LIST

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .dso import DSOEntry

# Silver requirement: limit parallel updates
PARALLEL_UPDATES = 1

# Samme device-gruppe som nettleie-sensorene i sensor.py (DEVICE_NETTLEIE).
_DEVICE_NETTLEIE = "stromkalkulator"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: NettleieCoordinator = entry.runtime_data
    async_add_entities([KapasitetVarselBinarySensor(coordinator, entry)])


class KapasitetVarselBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Varsler når effekten nærmer seg neste kapasitetstrinn."""

    _attr_has_entity_name = True
    _attr_translation_key = "kapasitet_varsel"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_kapasitet_varsel"
        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self._dso: DSOEntry = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (samme Nettleie-enhet som nettleie-sensorene)."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{_DEVICE_NETTLEIE}")},
            name=f"Nettleie ({self._dso['name']})",
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )

    @property
    def is_on(self) -> bool | None:
        """True når margin til neste kapasitetstrinn er under terskelen."""
        if self.coordinator.data:
            return bool(self.coordinator.data.get("kapasitet_varsel", False))
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data:
            return {
                "margin_kw": self.coordinator.data.get("margin_neste_trinn_kw"),
            }
        return None
