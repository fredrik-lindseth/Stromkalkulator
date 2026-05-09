"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant import data_entry_flow
from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir

from .const import (
    AVGIFTSSONE_NORD_NORGE,
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_DSO,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_SPOTPRIS_INKL_MVA,
    DEFAULT_DSO,
    DOMAIN,
    ENOVA_AVGIFT,
    get_forbruksavgift,
    get_mva_sats,
    resolve_avgiftssone,
)
from .coordinator import NettleieCoordinator
from .dso import DSO_LIST, DSO_MIGRATIONS, DSOFusjon

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]

type StromkalkulatorConfigEntry = ConfigEntry[NettleieCoordinator]

_MIGRATION_INDEX: dict[str, DSOFusjon] = {m.gammel: m for m in DSO_MIGRATIONS}


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

    try:
        old_path.rename(new_path)
    except OSError as err:
        _LOGGER.warning("Failed to migrate storage file %s: %s", old_path.name, err)
        return
    _LOGGER.info("Migrated storage file: %s -> %s", old_path.name, new_path.name)


async def _migrate_storage_file(
    hass: HomeAssistant, storage_dir: str, old_dso: str, new_dso: str
) -> None:
    """Migrate storage file in executor to avoid blocking the event loop."""
    await hass.async_add_executor_job(_migrate_storage_file_sync, storage_dir, old_dso, new_dso)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to current schema.

    v1 -> v2: Energiledd-overrides lagret som inkl-mva-verdier konverteres til
    eks-mva. Reverserer formelen `inkl = (eks + forbruksavgift + Enova) * (1+mva)`
    basert på avgiftssonen som er lagret på entry-en.

    v2 -> v3: Setter `spotpris_inkl_mva = True` for å bevare gjeldende oppførsel
    (kode antok inkl. mva fra spotpris-sensor). Nye konfigurasjoner får default
    False (riktig for HA-core nordpool). Se incident 004.
    """
    if entry.version >= 3:
        return True

    if entry.version == 1:
        new_data = {**entry.data}
        sone = entry.data.get(CONF_AVGIFTSSONE) or resolve_avgiftssone(
            DSO_LIST.get(entry.data.get(CONF_DSO, DEFAULT_DSO), {})
        )
        forbruksavgift = get_forbruksavgift(sone)
        mva_sats = get_mva_sats(sone)

        def inkl_to_eks(value: object) -> float | None:
            try:
                v = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            return v / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT

        for key in (CONF_ENERGILEDD_DAG, CONF_ENERGILEDD_NATT):
            raw = entry.data.get(key)
            if raw is None:
                continue
            converted = inkl_to_eks(raw)
            if converted is None or converted <= 0:
                # Sannsynlig feil/korrupt verdi; la coordinator falle tilbake
                # til DSO-default ved å fjerne overstyringen.
                new_data.pop(key, None)
                continue
            new_data[key] = round(converted, 5)

        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrerte config entry %s fra v1 til v2 (energiledd inkl→eks mva, avgiftssone=%s)",
            entry.entry_id,
            sone,
        )

    if entry.version == 2:
        # Auto-fix incident 004: HA-core nordpool leverer eks. mva. Sett False
        # for alle eksisterende konfig (riktig for ~alle brukere). Repair-issue
        # informerer om endringen i tilfelle brukeren har en custom-sensor som
        # inkluderer mva (egendefinert template, eldre custom_components/nordpool
        # med VAT=true). Trigges kun for Sør-Norge der mva-håndteringen utgjør
        # en forskjell.
        new_data = {**entry.data, CONF_SPOTPRIS_INKL_MVA: False}
        hass.config_entries.async_update_entry(entry, data=new_data, version=3)
        sone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        if sone == AVGIFTSSONE_STANDARD:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"spotpris_mva_check_{entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="spotpris_mva_check",
            )
        _LOGGER.info(
            "Migrerte config entry %s fra v2 til v3 (spotpris_inkl_mva=False, sone=%s)",
            entry.entry_id,
            sone,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Set up Nettleie from a config entry."""
    # Check for DSO migration (merger)
    dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
    migration = _MIGRATION_INDEX.get(dso_id)

    if migration is not None:
        new_dso = DSO_LIST.get(migration.ny)
        if new_dso is None:
            _LOGGER.error("DSO migration target %s not found in DSO_LIST", migration.ny)
            return False
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

    # Migrer avgiftssone for NO3-DSO-er (incident 003)
    # NO3 ble feil mappet til nord_norge (mva-fritak), men de fleste NO3-selskap
    # er i Trøndelag/Møre og Romsdal som betaler 25% mva.
    current_avgiftssone = entry.data.get(CONF_AVGIFTSSONE)
    if current_avgiftssone == AVGIFTSSONE_NORD_NORGE:
        resolved_dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        current_dso = DSO_LIST.get(resolved_dso_id)
        if current_dso and current_dso["prisomrade"] == "NO3":
            dso_avgiftssone = current_dso.get("avgiftssone")
            if dso_avgiftssone != AVGIFTSSONE_NORD_NORGE:
                new_data = {**entry.data, CONF_AVGIFTSSONE: AVGIFTSSONE_STANDARD}
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.info(
                    "Migrerte avgiftssone for %s fra nord_norge til standard (NO3, mva-pliktig)",
                    current_dso["name"],
                )

    coordinator: NettleieCoordinator = NettleieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
