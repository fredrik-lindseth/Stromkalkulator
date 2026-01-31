"""Diagnostics support for Strømkalkulator."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from .coordinator import NettleieCoordinator

from .const import (
    CONF_AVGIFTSSONE,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_HAR_NORGESPRIS,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_TSO,
)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    This includes integration version, configuration, sensor entity IDs,
    TSO data, and coordinator data (sanitized).
    """
    coordinator: NettleieCoordinator = entry.runtime_data

    return {
        "integration": {
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
        },
        "config_entry": {
            "entry_id": entry.entry_id,
            "data": {
                "tso": entry.data.get(CONF_TSO),
                "avgiftssone": entry.data.get(CONF_AVGIFTSSONE),
                "har_norgespris": entry.data.get(CONF_HAR_NORGESPRIS),
                "energiledd_dag_override": entry.data.get(CONF_ENERGILEDD_DAG),
                "energiledd_natt_override": entry.data.get(CONF_ENERGILEDD_NATT),
            },
        },
        "sensor_entity_ids": {
            "power_sensor": entry.data.get(CONF_POWER_SENSOR),
            "spot_price_sensor": entry.data.get(CONF_SPOT_PRICE_SENSOR),
            "electricity_provider_price_sensor": entry.data.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR),
        },
        "tso_info": {
            "id": coordinator._tso_id,
            "name": coordinator.tso.get("name"),
            "energiledd_dag": coordinator.energiledd_dag,
            "energiledd_natt": coordinator.energiledd_natt,
            "kapasitetstrinn_count": len(coordinator.kapasitetstrinn),
        },
        "coordinator_data": coordinator.data if coordinator.data else {},
    }
