# TSO-migrering Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatisk migrere brukere til nye nettselskaper ved fusjoner, uten tap av data.

**Architecture:** En `TSO_MIGRATIONS`-liste i `tso.py` definerer fusjoner som `TSOFusjon(gammel, ny)`. Ved oppstart sjekker `async_setup_entry` om brukerens TSO er migrert, oppdaterer config entry, flytter storage-fil, og oppretter en HA repair issue.

**Tech Stack:** Python dataclasses, Home Assistant config entries, HA issue registry, HA storage

---

### Task 1: TSOFusjon dataclass og TSO_MIGRATIONS

**Files:**
- Modify: `custom_components/stromkalkulator/tso.py:12` (imports) og etter linje 48 (før TSO_LIST)
- Test: `tests/test_tso_migration.py`

**Step 1: Write the failing test**

```python
"""Tests for TSO migration data structures."""

from __future__ import annotations

from stromkalkulator.tso import TSO_LIST, TSO_MIGRATIONS, TSOFusjon


def test_tso_fusjon_dataclass():
    """TSOFusjon has gammel and ny fields."""
    fusjon = TSOFusjon(gammel="old_tso", ny="new_tso")
    assert fusjon.gammel == "old_tso"
    assert fusjon.ny == "new_tso"


def test_tso_fusjon_is_frozen():
    """TSOFusjon is immutable."""
    import pytest

    fusjon = TSOFusjon(gammel="old_tso", ny="new_tso")
    with pytest.raises(AttributeError):
        fusjon.gammel = "other"  # type: ignore[misc]


def test_tso_migrations_exist():
    """TSO_MIGRATIONS contains known mergers."""
    gammel_keys = [m.gammel for m in TSO_MIGRATIONS]
    assert "skiakernett" in gammel_keys
    assert "norgesnett" in gammel_keys


def test_tso_migrations_targets_exist_in_tso_list():
    """Every migration target must exist in TSO_LIST."""
    for migration in TSO_MIGRATIONS:
        assert migration.ny in TSO_LIST, (
            f"Migration target '{migration.ny}' not found in TSO_LIST"
        )


def test_tso_migrations_sources_not_in_tso_list():
    """Migrated TSO keys should be removed from TSO_LIST."""
    for migration in TSO_MIGRATIONS:
        assert migration.gammel not in TSO_LIST, (
            f"Migrated key '{migration.gammel}' should be removed from TSO_LIST"
        )
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tso_migration.py -v`
Expected: FAIL — `TSOFusjon` og `TSO_MIGRATIONS` finnes ikke ennå

**Step 3: Write minimal implementation**

I `custom_components/stromkalkulator/tso.py`, legg til etter imports (linje 12):

```python
from dataclasses import dataclass
```

Legg til etter `TSOEntry` class (etter linje 37, før TSO_LIST):

```python
@dataclass(frozen=True)
class TSOFusjon:
    """Represents a TSO merger: gammel (old key) → ny (new key)."""

    gammel: str
    ny: str


TSO_MIGRATIONS: Final[list[TSOFusjon]] = [
    TSOFusjon(gammel="skiakernett", ny="vevig"),
    TSOFusjon(gammel="norgesnett", ny="glitre"),
]
```

Fjern `"norgesnett"` entry fra `TSO_LIST` (linje 195-214). `skiakernett` er allerede fjernet.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tso_migration.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/tso.py tests/test_tso_migration.py
git commit -m "feat(tso): add TSOFusjon dataclass and TSO_MIGRATIONS list"
```

---

### Task 2: Migreringsfunksjon

**Files:**
- Modify: `custom_components/stromkalkulator/__init__.py`
- Test: `tests/test_tso_migration.py` (legg til)

**Step 1: Write the failing test**

Legg til i `tests/test_tso_migration.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stromkalkulator.tso import TSO_LIST, TSO_MIGRATIONS, TSOFusjon


def _build_migration_index():
    """Build migration lookup dict from TSO_MIGRATIONS list."""
    from stromkalkulator.__init__ import _build_migration_index
    return _build_migration_index()


def test_build_migration_index():
    """_build_migration_index returns dict mapping gammel → TSOFusjon."""
    from stromkalkulator.__init__ import _build_migration_index

    index = _build_migration_index()
    assert isinstance(index, dict)
    assert "skiakernett" in index
    assert index["skiakernett"].ny == "vevig"
    assert "norgesnett" in index
    assert index["norgesnett"].ny == "glitre"


def test_migrate_tso_returns_new_key():
    """_check_tso_migration returns new TSO key when migration exists."""
    from stromkalkulator.__init__ import _check_tso_migration

    result = _check_tso_migration("skiakernett")
    assert result is not None
    assert result.ny == "vevig"


def test_migrate_tso_returns_none_for_current():
    """_check_tso_migration returns None when no migration needed."""
    from stromkalkulator.__init__ import _check_tso_migration

    result = _check_tso_migration("bkk")
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tso_migration.py -v -k "build_migration or migrate_tso"`
Expected: FAIL — functions don't exist

**Step 3: Write minimal implementation**

I `custom_components/stromkalkulator/__init__.py`, legg til:

```python
"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.const import Platform

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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tso_migration.py -v -k "build_migration or migrate_tso"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/__init__.py tests/test_tso_migration.py
git commit -m "feat: add TSO migration lookup functions"
```

---

### Task 3: Storage-migrering

**Files:**
- Modify: `custom_components/stromkalkulator/__init__.py`
- Test: `tests/test_tso_migration.py` (legg til)

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_migrate_storage_file_renames(tmp_path):
    """Storage file is renamed from old to new TSO key."""
    from stromkalkulator.__init__ import _migrate_storage_file

    # Create a fake old storage file
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "test"}')

    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    new_file = storage_dir / "stromkalkulator_glitre"
    assert new_file.exists()
    assert not old_file.exists()
    assert new_file.read_text() == '{"data": "test"}'


@pytest.mark.asyncio
async def test_migrate_storage_file_no_old_file(tmp_path):
    """No error when old storage file doesn't exist."""
    from stromkalkulator.__init__ import _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()

    # Should not raise
    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")


@pytest.mark.asyncio
async def test_migrate_storage_file_target_exists(tmp_path):
    """Don't overwrite if target storage file already exists."""
    from stromkalkulator.__init__ import _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "old"}')
    new_file = storage_dir / "stromkalkulator_glitre"
    new_file.write_text('{"data": "existing"}')

    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    # Existing file should not be overwritten
    assert new_file.read_text() == '{"data": "existing"}'
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_tso_migration.py -v -k "storage"`
Expected: FAIL — `_migrate_storage_file` doesn't exist

**Step 3: Write minimal implementation**

Legg til i `__init__.py`:

```python
from pathlib import Path


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
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_tso_migration.py -v -k "storage"`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add custom_components/stromkalkulator/__init__.py tests/test_tso_migration.py
git commit -m "feat: add storage file migration for TSO mergers"
```

---

### Task 4: Integrer migrering i async_setup_entry

**Files:**
- Modify: `custom_components/stromkalkulator/__init__.py`
- Modify: `custom_components/stromkalkulator/strings.json` (repair issue tekst)

**Step 1: Write the implementation**

Oppdater `async_setup_entry` i `__init__.py`:

```python
async def async_setup_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Set up Nettleie from a config entry."""
    # Check for TSO migration (merger)
    tso_id = entry.data.get(CONF_TSO, "bkk")
    migration = _check_tso_migration(tso_id)

    if migration is not None:
        old_name = migration.gammel
        new_tso = TSO_LIST[migration.ny]
        new_name = new_tso["name"]

        _LOGGER.info(
            "Migrerer nettselskap: %s → %s (%s)",
            old_name,
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
                "old_name": old_name,
                "new_name": new_name,
            },
        )

    coordinator: NettleieCoordinator = NettleieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
```

Legg til import øverst:

```python
from homeassistant.helpers import issue_registry as ir
```

**Step 2: Legg til repair issue tekst i strings.json**

Legg til ny seksjon `"issues"` i `strings.json`:

```json
{
  "config": { ... },
  "options": { ... },
  "entity": { ... },
  "issues": {
    "tso_migrated": {
      "title": "Nettselskapet ditt har fusjonert",
      "fix_flow": {
        "step": {
          "confirm": {
            "title": "Nettselskapet ditt har fusjonert",
            "description": "{old_name} er nå en del av {new_name}. Integrasjonen er automatisk oppdatert, og forbruksdata og historikk er bevart."
          }
        }
      }
    }
  }
}
```

**Merk:** Fixable repair issues i HA krever en repair flow handler. Legg til i `__init__.py`:

```python
from homeassistant import data_entry_flow
from homeassistant.helpers import issue_registry as ir


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
```

**Step 3: Run all existing tests to verify nothing breaks**

Run: `pytest tests/ -v`
Expected: ALL PASS (eksisterende tester skal ikke påvirkes)

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/__init__.py custom_components/stromkalkulator/strings.json
git commit -m "feat: integrate TSO migration into async_setup_entry with repair issue"
```

---

### Task 5: Fjern norgesnett fra TSO_LIST

**Files:**
- Modify: `custom_components/stromkalkulator/tso.py` (fjern norgesnett-oppføring)
- Test: Allerede dekket av `test_tso_migrations_sources_not_in_tso_list` fra Task 1

**Step 1: Fjern norgesnett entry**

Fjern linjene 195-214 (`"norgesnett": { ... },`) fra `tso.py`.

**Step 2: Run tests**

Run: `pytest tests/test_tso_migration.py -v`
Expected: ALL PASS — `test_tso_migrations_sources_not_in_tso_list` bekrefter at norgesnett er borte

**Step 3: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/tso.py
git commit -m "refactor(tso): remove norgesnett from TSO_LIST (migrated to glitre)"
```

---

### Task 6: Oppdater config flow (fjern norgesnett fra dropdown)

**Files:**
- Modify: `custom_components/stromkalkulator/config_flow.py` — sjekk om TSO-listen bygges dynamisk fra `TSO_LIST`

**Step 1: Verifiser at config flow bruker TSO_LIST dynamisk**

Les `config_flow.py` og sjekk om dropdown-listen bygges fra `TSO_LIST.keys()`. Hvis ja, er dette allerede løst av Task 5. Hvis manuell liste, oppdater den.

**Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit (bare hvis endringer trengs)**

```bash
git add custom_components/stromkalkulator/config_flow.py
git commit -m "fix: update config flow TSO list after norgesnett removal"
```

---

### Task 7: End-to-end verifisering

**Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL 185+ tests PASS

**Step 2: Verifiser at integrasjonen laster**

Sjekk at imports fungerer uten feil:

```bash
python3 -c "import sys; sys.path.insert(0, 'custom_components'); from stromkalkulator.tso import TSO_LIST, TSO_MIGRATIONS; print(f'{len(TSO_LIST)} TSOs, {len(TSO_MIGRATIONS)} migrations')"
```

Expected: `71 TSOs, 2 migrations` (72 minus norgesnett)

**Step 3: Oppdater dogcat issue**

```bash
dcat update hacs-strømkalkulator-qsp --status in_review
```
