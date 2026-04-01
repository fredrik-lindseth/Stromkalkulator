# Fix Multi-Instance Storage Bug

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix bug where two config entries with the same DSO share storage, causing data to bleed between instances.

**Architecture:** Change storage key from `stromkalkulator_{dso_id}` to `stromkalkulator_{entry_id}` so each config entry has isolated persistent storage. Add migration fallback from DSO-based key for existing users.

**Tech Stack:** Python, Home Assistant helpers.storage.Store

---

## Background

**Bug:** When a user sets up two config entries with the same nettselskap (e.g., two Tibber pulses in the same BKK area), both coordinators create `Store(hass, 1, "stromkalkulator_bkk")` — the same storage key. Data from one instance overwrites the other.

**Root cause:** `coordinator.py:115` uses `dso_id` in storage key instead of `entry.entry_id`.

**Migration concern:** Existing users have files named `stromkalkulator_{dso_id}`. The fix must migrate data from the old key on first load.

---

### Task 1: Write test for storage key isolation

**Files:**

- Create: `tests/test_storage_key.py`

**Step 1: Write the test**

```python
"""Tests for storage key isolation between config entries."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_store():
    """Patch Store to capture instantiation args."""
    with patch("stromkalkulator.coordinator.Store") as mock:
        mock.return_value = MagicMock()
        yield mock


@pytest.fixture
def mock_hass():
    """Minimal hass mock."""
    hass = MagicMock()
    return hass


def _make_entry(entry_id: str, dso_id: str = "bkk") -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": f"sensor.power_{entry_id}",
    }
    return entry


def test_storage_key_uses_entry_id(mock_store, mock_hass):
    """Storage key must include entry_id, not just dso_id."""
    from stromkalkulator.coordinator import NettleieCoordinator

    entry = _make_entry("entry_abc123", dso_id="bkk")
    NettleieCoordinator(mock_hass, entry)

    mock_store.assert_called_once()
    store_key = mock_store.call_args[0][2]
    assert "entry_abc123" in store_key, f"Storage key should contain entry_id, got: {store_key}"


def test_two_entries_same_dso_get_different_storage(mock_store, mock_hass):
    """Two entries with same DSO must get different storage keys."""
    from stromkalkulator.coordinator import NettleieCoordinator

    entry1 = _make_entry("entry_111", dso_id="bkk")
    entry2 = _make_entry("entry_222", dso_id="bkk")

    NettleieCoordinator(mock_hass, entry1)
    NettleieCoordinator(mock_hass, entry2)

    assert mock_store.call_count == 2
    key1 = mock_store.call_args_list[0][0][2]
    key2 = mock_store.call_args_list[1][0][2]
    assert key1 != key2, f"Two entries got same storage key: {key1}"
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_storage_key.py -v`
Expected: FAIL — storage key currently uses `dso_id`, not `entry_id`

---

### Task 2: Fix storage key in coordinator

**Files:**

- Modify: `custom_components/stromkalkulator/coordinator.py:115`

**Step 1: Change storage key to use entry_id**

In `coordinator.py`, change line 115 from:

```python
self._store = Store(hass, 1, f"{DOMAIN}_{dso_id}")
```

to:

```python
self._store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
```

**Step 2: Run test to verify it passes**

Run: `pipx run pytest tests/test_storage_key.py -v`
Expected: PASS

**Step 3: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All tests pass

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py tests/test_storage_key.py
git commit -m "fix: use entry_id for storage key to support multiple instances

Two config entries with the same DSO (e.g. two meters in same grid area)
now get separate storage files instead of sharing one."
```

---

### Task 3: Update migration to fall back from DSO-based storage

**Files:**

- Modify: `custom_components/stromkalkulator/coordinator.py:375-399`

**Step 1: Write migration test**

Add to `tests/test_storage_key.py`:

```python
@pytest.mark.asyncio
async def test_migration_from_dso_storage(mock_hass):
    """Loading data falls back to DSO-based storage key for migration."""
    from stromkalkulator.coordinator import NettleieCoordinator

    stored_data = {
        "daily_max_power": {"2026-03-01": 5.5},
        "monthly_consumption": {"dag": 100.0, "natt": 50.0},
        "current_month": 3,
        "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
        "previous_month_top_3": {},
        "previous_month_name": None,
    }

    # Track Store instances by key
    stores = {}

    def make_store(hass, version, key):
        store = MagicMock()
        stores[key] = store
        if key == "stromkalkulator_bkk":
            # Old DSO-based store has data
            store.async_load = MagicMock(return_value=stored_data)
        else:
            # New entry_id-based store is empty
            store.async_load = MagicMock(return_value=None)
        return store

    with patch("stromkalkulator.coordinator.Store", side_effect=make_store):
        entry = _make_entry("entry_new", dso_id="bkk")
        coordinator = NettleieCoordinator(mock_hass, entry)
        await coordinator._load_stored_data()

    # Should have loaded data from DSO-based fallback
    assert coordinator._daily_max_power == {"2026-03-01": 5.5}
    assert coordinator._monthly_consumption == {"dag": 100.0, "natt": 50.0}

    # Should have saved to new entry_id-based store
    entry_store = stores["stromkalkulator_entry_new"]
    entry_store.async_save.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `pipx run pytest tests/test_storage_key.py::test_migration_from_dso_storage -v`
Expected: FAIL — current migration code tries entry_id as fallback (which is now primary)

**Step 3: Update migration logic**

Replace `_load_stored_data` in `coordinator.py` (lines 375-399):

```python
async def _load_stored_data(self) -> None:
    """Load stored data from disk."""
    data: dict[str, Any] | None = await self._store.async_load()

    # Migration: try to load from old DSO-based storage if new storage is empty
    if not data:
        old_store: Store[dict[str, Any]] = Store(self.hass, 1, f"{DOMAIN}_{self._dso_id}")
        data = await old_store.async_load()
        if data:
            _LOGGER.info("Migrated data from DSO-based storage to entry-based storage")
            # Save to new location immediately
            await self._store.async_save(data)

    if data:
        self._daily_max_power = data.get("daily_max_power", {})
        self._monthly_consumption = data.get("monthly_consumption", {"dag": 0.0, "natt": 0.0})
        self._previous_month_consumption = data.get("previous_month_consumption", {"dag": 0.0, "natt": 0.0})
        self._previous_month_top_3 = data.get("previous_month_top_3", {})
        self._previous_month_name = data.get("previous_month_name")
        stored_month = data.get("current_month")
        # If stored month is different, clear data
        if stored_month and stored_month != self._current_month:
            self._daily_max_power = {}
            self._monthly_consumption = {"dag": 0.0, "natt": 0.0}
        _LOGGER.debug("Loaded stored data: %s", self._daily_max_power)
```

**Step 4: Run tests**

Run: `pipx run pytest tests/test_storage_key.py -v`
Expected: All PASS

**Step 5: Run full test suite**

Run: `pipx run pytest tests/ -v`
Expected: All tests pass

**Step 6: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py tests/test_storage_key.py
git commit -m "fix: migrate existing data from DSO-based to entry-based storage

Existing users with stromkalkulator_{dso_id} files will have data
automatically migrated to stromkalkulator_{entry_id} on first load."
```

---

### Task 4: Update storage comment and bump version

**Files:**

- Modify: `custom_components/stromkalkulator/coordinator.py:114` (comment)
- Modify: `custom_components/stromkalkulator/manifest.json` (version bump)

**Step 1: Update the comment on line 114**

Change:

```python
# Persistent storage - use DSO id for stable storage across reinstalls
```

to:

```python
# Persistent storage - keyed by entry_id for multi-instance isolation
```

**Step 2: Bump version in manifest.json**

Bump the patch version (check current version first).

**Step 3: Run full test suite**

Run: `pipx run pytest tests/ -v && ruff check custom_components/stromkalkulator/ tests/`
Expected: All pass, no lint errors

**Step 4: Commit**

```bash
git add custom_components/stromkalkulator/coordinator.py custom_components/stromkalkulator/manifest.json
git commit -m "chore: update storage comment, bump version for multi-instance fix"
```

---

## Migration Path Summary

| User scenario                   | What happens                                                                                          |
| ------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Fresh install                   | Storage key is `stromkalkulator_{entry_id}` — just works                                              |
| Single entry, upgrading         | Loads empty from entry_id key → falls back to DSO key → migrates                                      |
| Two entries same DSO, upgrading | First to load gets the shared data, second starts fresh (best possible outcome for corrupted state)   |
| DSO merger + upgrade            | `__init__.py` renames old DSO file → coordinator falls back to new DSO key → migrates to entry_id key |
