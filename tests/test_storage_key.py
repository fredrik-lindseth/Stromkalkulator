"""Tests for storage key isolation between config entries."""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_update_coordinator():
    """Replace the mocked DataUpdateCoordinator with a real base class.

    conftest.py mocks homeassistant.helpers.update_coordinator as a MagicMock.
    Subclassing a MagicMock doesn't invoke the real __init__, so we need a
    minimal real class for NettleieCoordinator to inherit from.
    """

    class FakeDataUpdateCoordinator:
        def __init_subclass__(cls, **kwargs):
            pass

        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval):
            self.hass = hass

    mod = sys.modules["homeassistant.helpers.update_coordinator"]
    original = getattr(mod, "DataUpdateCoordinator", None)
    mod.DataUpdateCoordinator = FakeDataUpdateCoordinator
    yield
    mod.DataUpdateCoordinator = original


@pytest.fixture
def mock_store():
    """Patch Store to capture instantiation args."""
    mock = MagicMock()
    mod = sys.modules["homeassistant.helpers.storage"]
    original = mod.Store
    mod.Store = mock
    # Also patch the already-imported name in the coordinator module
    import stromkalkulator.coordinator as coord

    coord_original = coord.Store
    coord.Store = mock
    yield mock
    mod.Store = original
    coord.Store = coord_original


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
    # Re-import to pick up the patched DataUpdateCoordinator
    import importlib

    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    # Re-apply Store mock after reload
    mock_store.reset_mock()
    coord.Store = mock_store

    entry = _make_entry("entry_abc123", dso_id="bkk")
    coord.NettleieCoordinator(mock_hass, entry)

    mock_store.assert_called_once()
    store_key = mock_store.call_args[0][2]
    assert "entry_abc123" in store_key, f"Storage key should contain entry_id, got: {store_key}"


def test_two_entries_same_dso_get_different_storage(mock_store, mock_hass):
    """Two entries with same DSO must get different storage keys."""
    import importlib

    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    mock_store.reset_mock()
    coord.Store = mock_store

    entry1 = _make_entry("entry_111", dso_id="bkk")
    entry2 = _make_entry("entry_222", dso_id="bkk")

    coord.NettleieCoordinator(mock_hass, entry1)
    coord.NettleieCoordinator(mock_hass, entry2)

    assert mock_store.call_count == 2
    key1 = mock_store.call_args_list[0][0][2]
    key2 = mock_store.call_args_list[1][0][2]
    assert key1 != key2, f"Two entries got same storage key: {key1}"


def test_migration_from_dso_storage(mock_hass):
    """Loading data falls back to DSO-based storage key for migration."""
    import asyncio
    import importlib

    import stromkalkulator.coordinator as coord

    now = datetime.now()
    stored_data = {
        "daily_max_power": {now.strftime("%Y-%m-01"): 5.5},
        "monthly_consumption": {"dag": 100.0, "natt": 50.0},
        "current_month": now.month,
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
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_remove = AsyncMock()
        else:
            # New entry_id-based store is empty
            store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        return store

    importlib.reload(coord)
    coord.Store = MagicMock(side_effect=make_store)

    entry = _make_entry("entry_new", dso_id="bkk")
    coordinator = coord.NettleieCoordinator(mock_hass, entry)
    asyncio.run(coordinator._load_stored_data())

    # Should have loaded data from DSO-based fallback
    assert coordinator._daily_max_power == {now.strftime("%Y-%m-01"): 5.5}
    assert coordinator._monthly_consumption == {"dag": 100.0, "natt": 50.0}

    # Should have saved to new entry_id-based store
    entry_store = stores["stromkalkulator_entry_new"]
    entry_store.async_save.assert_called_once()

    # Should have removed old DSO-based store to prevent second instance from loading same data
    old_store = stores["stromkalkulator_bkk"]
    old_store.async_remove.assert_called_once()


def test_two_instances_same_dso_migration_no_data_sharing(mock_hass):
    """Second instance must NOT inherit first instance's migrated data.

    Regression test for https://github.com/fredrik-lindseth/Stromkalkulator/issues/1
    When two config entries share the same DSO, the first to migrate should
    clean up the old DSO-based storage so the second starts fresh.
    """
    import asyncio
    import importlib

    import stromkalkulator.coordinator as coord

    now = datetime.now()
    stored_data = {
        "daily_max_power": {
            now.strftime("%Y-%m-01"): 5.5,
            now.strftime("%Y-%m-02"): 7.2,
            now.strftime("%Y-%m-03"): 6.1,
        },
        "monthly_consumption": {"dag": 100.0, "natt": 50.0},
        "current_month": now.month,
        "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
        "previous_month_top_3": {},
        "previous_month_name": None,
    }

    # Track whether old store was removed
    old_store_removed = False

    def make_store(hass, version, key):
        nonlocal old_store_removed
        store = MagicMock()
        if key == "stromkalkulator_bkk":
            # Old DSO-based store: return data only if not yet removed
            if old_store_removed:
                store.async_load = AsyncMock(return_value=None)
            else:
                store.async_load = AsyncMock(return_value=stored_data)

            async def do_remove():
                nonlocal old_store_removed
                old_store_removed = True

            store.async_remove = AsyncMock(side_effect=do_remove)
        else:
            # Entry-based stores start empty
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
        return store

    importlib.reload(coord)
    coord.Store = MagicMock(side_effect=make_store)

    # First instance migrates and gets the data
    entry1 = _make_entry("entry_meter1", dso_id="bkk")
    coord1 = coord.NettleieCoordinator(mock_hass, entry1)
    asyncio.run(coord1._load_stored_data())
    assert coord1._daily_max_power == {
        now.strftime("%Y-%m-01"): 5.5,
        now.strftime("%Y-%m-02"): 7.2,
        now.strftime("%Y-%m-03"): 6.1,
    }

    # Second instance must NOT get the same data (old store was cleaned up)
    entry2 = _make_entry("entry_meter2", dso_id="bkk")
    coord2 = coord.NettleieCoordinator(mock_hass, entry2)
    asyncio.run(coord2._load_stored_data())
    assert coord2._daily_max_power == {}, (
        "Second instance should start fresh, not inherit first instance's migrated data"
    )
