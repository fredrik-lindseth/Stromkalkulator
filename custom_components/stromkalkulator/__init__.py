"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant import data_entry_flow
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .const import CONF_DSO, DOMAIN
from .coordinator import NettleieCoordinator
from .dso import DSO_LIST, DSO_MIGRATIONS, DSOFusjon

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type StromkalkulatorConfigEntry = ConfigEntry[NettleieCoordinator]

# Build migration lookup once at import time
_MIGRATION_INDEX: dict[str, DSOFusjon] = {m.gammel: m for m in DSO_MIGRATIONS}


def _build_migration_index() -> dict[str, DSOFusjon]:
    """Return the migration index (for testing)."""
    return _MIGRATION_INDEX


def _check_dso_migration(dso_id: str) -> DSOFusjon | None:
    """Check if a DSO key needs migration. Returns DSOFusjon or None."""
    return _MIGRATION_INDEX.get(dso_id)


def _migrate_storage_file_sync(storage_dir: str, old_dso: str, new_dso: str) -> None:
    """Rename storage file from old DSO key to new DSO key (sync, runs in executor).

    NOTE: Since v0.55.0, storage files are keyed by entry_id, not DSO.
    This function only handles transitional migration for users upgrading
    from <=v0.54 who also have a DSO merger. The coordinator's
    _load_stored_data handles the DSO→entry_id migration separately.
    """
    old_path = Path(storage_dir) / f"{DOMAIN}_{old_dso}"
    new_path = Path(storage_dir) / f"{DOMAIN}_{new_dso}"

    if not old_path.exists():
        _LOGGER.debug("No storage file to migrate: %s", old_path)
        return

    if new_path.exists():
        _LOGGER.warning(
            "Storage file already exists for %s, skipping migration from %s",
            new_dso,
            old_dso,
        )
        return

    old_path.rename(new_path)
    _LOGGER.info("Migrated storage file: %s → %s", old_path.name, new_path.name)


async def _migrate_storage_file(
    hass: HomeAssistant, storage_dir: str, old_dso: str, new_dso: str
) -> None:
    """Migrate storage file in executor to avoid blocking the event loop."""
    await hass.async_add_executor_job(_migrate_storage_file_sync, storage_dir, old_dso, new_dso)


async def async_setup_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Set up Nettleie from a config entry."""
    # Check for DSO migration (merger)
    dso_id = entry.data.get(CONF_DSO, "bkk")
    migration = _check_dso_migration(dso_id)

    if migration is not None:
        new_dso = DSO_LIST[migration.ny]
        new_name = new_dso["name"]

        _LOGGER.info(
            "Migrerer nettselskap: %s → %s (%s)",
            migration.gammel,
            migration.ny,
            new_name,
        )

        # Migrate storage file FIRST (before updating config entry)
        storage_dir = hass.config.path(".storage")
        await _migrate_storage_file(hass, storage_dir, migration.gammel, migration.ny)

        # Update config entry with new DSO key
        new_data = {**entry.data, CONF_DSO: migration.ny}
        hass.config_entries.async_update_entry(entry, data=new_data)

        # Create repair issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"dso_migration_{migration.gammel}_{migration.ny}",
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

    # Fix entity names cached before translations were deployed (one-time migration)
    # Remove and re-register entities with wrong names so HA picks up translation_key
    ent_reg = er.async_get(hass)
    for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        if ent.original_name and "Monetary balance" in ent.original_name:
            ent_reg.async_remove(ent.entity_id)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


class DsoMigrationRepairFlow(data_entry_flow.FlowHandler):
    """Handler for DSO migration repair flow."""

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
) -> DsoMigrationRepairFlow:
    """Create flow to fix a repair issue."""
    return DsoMigrationRepairFlow()
