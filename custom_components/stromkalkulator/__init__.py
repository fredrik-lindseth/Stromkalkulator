"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant import data_entry_flow
from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir

from .const import CONF_TSO, DOMAIN
from .coordinator import NettleieCoordinator
from .tso import TSO_LIST, TSO_MIGRATIONS, TSOFusjon

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
    # Check for TSO migration (merger)
    tso_id = entry.data.get(CONF_TSO, "bkk")
    migration = _check_tso_migration(tso_id)

    if migration is not None:
        new_tso = TSO_LIST[migration.ny]
        new_name = new_tso["name"]

        _LOGGER.info(
            "Migrerer nettselskap: %s → %s (%s)",
            migration.gammel,
            migration.ny,
            new_name,
        )

        # Update config entry with new TSO key
        new_data = {**entry.data, CONF_TSO: migration.ny}
        hass.config_entries.async_update_entry(entry, data=new_data)

        # Migrate storage file
        storage_dir = hass.config.path(".storage")
        await _migrate_storage_file(storage_dir, migration.gammel, migration.ny)

        # Create repair issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"tso_migration_{migration.gammel}_{migration.ny}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="tso_migrated",
            translation_placeholders={
                "old_name": migration.gammel,
                "new_name": new_name,
            },
        )

    coordinator: NettleieCoordinator = NettleieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


class TsoMigrationRepairFlow(data_entry_flow.FlowHandler):
    """Handler for TSO migration repair flow."""

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step."""
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str] | None,
) -> TsoMigrationRepairFlow:
    """Create flow to fix a repair issue."""
    return TsoMigrationRepairFlow()
