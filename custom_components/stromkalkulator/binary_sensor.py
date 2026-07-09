"""Binary sensor platform for Strømkalkulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DSO,
    DEFAULT_DSO,
    DEFAULT_NAME,
    DOMAIN,
    MANUFACTURER,
    STROMSTOTTE_LEVEL,
)
from .dso import DSO_LIST

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import NettleieCoordinator
    from .dso import DSOEntry

# Coordinator-basert plattform uten egen I/O ved oppdatering: 0 er HA-
# konvensjonen for coordinator-entiteter (ubegrenset parallellitet).
PARALLEL_UPDATES = 0

# Device-grupper (matcher DEVICE_*-konstantene i sensor.py) slik at binary
# sensors havner under samme enhet som de tilhørende sensorene.
_DEVICE_NETTLEIE = "stromkalkulator"
_DEVICE_STROMSTOTTE = "stromstotte"
_DEVICE_NORGESPRIS = "norgespris"

_DEVICE_NAMES = {
    _DEVICE_STROMSTOTTE: "Strømstøtte",
    _DEVICE_NORGESPRIS: "Norgespris",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: NettleieCoordinator = entry.runtime_data
    async_add_entities(
        [
            KapasitetVarselBinarySensor(coordinator, entry),
            NorgesprisAktivBinarySensor(coordinator, entry),
            StromstotteAktivBinarySensor(coordinator, entry),
        ]
    )


class StromkalkulatorBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Base class for Strømkalkulator binary sensors."""

    _attr_has_entity_name = True
    _device_group: str = _DEVICE_NETTLEIE

    def __init__(
        self,
        coordinator: NettleieCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        self._dso: DSOEntry = DSO_LIST.get(dso_id, DSO_LIST[DEFAULT_DSO])

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the sensor's device group."""
        name = _DEVICE_NAMES.get(self._device_group, f"Nettleie ({self._dso['name']})")
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._entry.entry_id}_{self._device_group}")},
            name=name,
            manufacturer=MANUFACTURER,
            model=DEFAULT_NAME,
        )

    def _spot_price_valid(self) -> bool:
        """True hvis coordinator har gyldig spotpris (ikke kaldstart/bortfall).

        Mangler nøkkelen (eldre data eller test-stub) antas spot gyldig, slik at
        gatingen ikke gjør en ellers fungerende sensor utilgjengelig.
        """
        return bool(self.coordinator.data and self.coordinator.data.get("spot_price_valid", True))


class KapasitetVarselBinarySensor(StromkalkulatorBinarySensor):
    """Varsler når effekten nærmer seg neste kapasitetstrinn."""

    _attr_translation_key = "kapasitet_varsel"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:alert"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "kapasitet_varsel")

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


class NorgesprisAktivBinarySensor(StromkalkulatorBinarySensor):
    """Viser om Norgespris er aktiv for kontoen.

    Ren av/på-status uten device_class: dette er ikke et problem eller en
    varsel, bare en indikator på hvilken prismodell som gjelder.
    """

    _device_group = _DEVICE_NORGESPRIS
    _attr_translation_key = "norgespris_aktiv"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:check-circle"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "norgespris_aktiv")

    @property
    def is_on(self) -> bool | None:
        """True når Norgespris er aktiv."""
        if self.coordinator.data:
            return bool(self.coordinator.data.get("har_norgespris", False))
        return None


class StromstotteAktivBinarySensor(StromkalkulatorBinarySensor):
    """Viser om strømstøtte er aktiv nå (spotpris over terskel).

    Ingen device_class: «på» betyr at timen gir strømstøtte, ikke et problem.
    Spot-gatet: uten gyldig spotpris kan vi ikke avgjøre støtten, så is_on er
    None (unavailable) i stedet for en misvisende «av».
    """

    _device_group = _DEVICE_STROMSTOTTE
    _attr_translation_key = "stromstotte_aktiv"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:cash-check"

    def __init__(self, coordinator: NettleieCoordinator, entry: ConfigEntry) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry, "stromstotte_aktiv")

    @property
    def is_on(self) -> bool | None:
        """True når strømstøtte er aktiv (None ved manglende/ugyldig spotdata)."""
        if self.coordinator.data and self._spot_price_valid():
            return bool(self.coordinator.data.get("stromstotte", 0) > 0)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return attributes."""
        if self.coordinator.data:
            spot_price = self.coordinator.data.get("spot_price", 0)
            terskel = self.coordinator.data.get("stromstotte_terskel", STROMSTOTTE_LEVEL)
            stromstotte = self.coordinator.data.get("stromstotte", 0)
            boligtype = self.coordinator.data.get("boligtype", "bolig")
            return {
                "spotpris": spot_price,
                "terskel": terskel,
                "over_terskel": spot_price > terskel,
                "stromstotte_per_kwh": stromstotte,
                "boligtype": boligtype,
                "note": f"Timer hvor spotpris > {terskel * 100:.2f} øre/kWh gir strømstøtte på fakturaen",
            }
        return None
