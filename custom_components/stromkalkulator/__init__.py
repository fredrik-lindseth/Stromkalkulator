"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .const import DOMAIN
from .coordinator import NettleieCoordinator
from .tso import TSO_MIGRATIONS, TSOFusjon

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type StromkalkulatorConfigEntry = ConfigEntry[NettleieCoordinator]

# Build migration lookup once at import time
_MIGRATION_INDEX: dict[str, TSOFusjon] = {m.gammel: m for m in TSO_MIGRATIONS}


def _build_migration_index() -> dict[str, TSOFusjon]:
    """Return the migration index (for testing)."""
    return _MIGRATION_INDEX


def _check_tso_migration(tso_id: str) -> TSOFusjon | None:
    """Check if a TSO key needs migration. Returns TSOFusjon or None."""
    return _MIGRATION_INDEX.get(tso_id)


async def _migrate_storage_file(storage_dir: str, old_tso: str, new_tso: str) -> None:
    """Rename storage file from old TSO key to new TSO key."""
    old_path = Path(storage_dir) / f"{DOMAIN}_{old_tso}"
    new_path = Path(storage_dir) / f"{DOMAIN}_{new_tso}"

    if not old_path.exists():
        _LOGGER.debug("No storage file to migrate: %s", old_path)
        return

    if new_path.exists():
        _LOGGER.warning(
            "Storage file already exists for %s, skipping migration from %s",
            new_tso,
            old_tso,
        )
        return

    old_path.rename(new_path)
    _LOGGER.info("Migrated storage file: %s → %s", old_path.name, new_path.name)


async def async_setup_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Set up Nettleie from a config entry."""
    coordinator: NettleieCoordinator = NettleieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok
