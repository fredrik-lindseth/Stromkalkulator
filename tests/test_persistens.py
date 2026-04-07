"""Tests for persistent storage: load, save, migration, and month-change reset.

Verifies _load_stored_data, _save_stored_data, migration from DSO-based
storage to entry-based storage, and correct data reset on stored month mismatch.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(autouse=True)
def _patch_update_coordinator():
    """Replace mocked DataUpdateCoordinator with a real base class."""

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


def _make_entry(entry_id="entry_test", dso_id="bkk"):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
    }
    return entry


def _reload_coord():
    """Reload coordinator module fresh."""
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    return coord


class TestSaveLoadCycle:
    """Data should survive a save -> load cycle."""

    def test_round_trip(self):
        """Saved data is faithfully restored on load."""
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)

        # Set some state
        coordinator._daily_max_power = {"2026-04-01": 8.5, "2026-04-02": 12.0}
        coordinator._monthly_consumption = {"dag": 200.0, "natt": 100.0}
        coordinator._monthly_norgespris_diff = 15.5
        coordinator._previous_month_consumption = {"dag": 300.0, "natt": 150.0}
        coordinator._previous_month_top_3 = {"2026-03-01": 10.0, "2026-03-10": 9.0}
        coordinator._previous_month_name = "mars 2026"

        asyncio.run(coordinator._save_stored_data())

        # Verify save was called with correct data
        assert saved_data["daily_max_power"] == {"2026-04-01": 8.5, "2026-04-02": 12.0}
        assert saved_data["monthly_consumption"] == {"dag": 200.0, "natt": 100.0}
        assert saved_data["monthly_norgespris_diff"] == 15.5
        assert saved_data["previous_month_consumption"] == {"dag": 300.0, "natt": 150.0}
        assert saved_data["previous_month_top_3"] == {"2026-03-01": 10.0, "2026-03-10": 9.0}
        assert saved_data["previous_month_name"] == "mars 2026"

        # Now create a new coordinator and load the saved data
        def make_store_with_data(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=saved_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store_with_data)

        coordinator2 = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._daily_max_power == {"2026-04-01": 8.5, "2026-04-02": 12.0}
        assert coordinator2._monthly_consumption == {"dag": 200.0, "natt": 100.0}
        assert coordinator2._monthly_norgespris_diff == 15.5
        assert coordinator2._previous_month_consumption == {"dag": 300.0, "natt": 150.0}
        assert coordinator2._previous_month_top_3 == {"2026-03-01": 10.0, "2026-03-10": 9.0}
        assert coordinator2._previous_month_name == "mars 2026"

    def test_load_empty_store_uses_defaults(self):
        """Loading from empty store should keep default values."""
        coord = _reload_coord()

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._daily_max_power == {}
        assert coordinator._monthly_consumption == {"dag": 0.0, "natt": 0.0}
        assert coordinator._previous_month_top_3 == {}


class TestMigrationFromDSOStorage:
    """Migration from old DSO-based storage to entry-based storage."""

    def test_migrates_from_dso_key_to_entry_key(self):
        """When entry store is empty, data from DSO store is loaded and migrated."""
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 5.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        stores = {}

        def make_store(hass, version, key):
            store = MagicMock()
            stores[key] = store
            if key == "stromkalkulator_bkk":
                store.async_load = AsyncMock(return_value=stored_data)
                store.async_remove = AsyncMock()
            else:
                store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry("entry_new", dso_id="bkk")
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # Data should be loaded from old store
        assert coordinator._daily_max_power == {"2026-04-01": 5.0}

        # New store should be saved to
        entry_store = stores["stromkalkulator_entry_new"]
        entry_store.async_save.assert_called_once()

        # Old store should be removed
        old_store = stores["stromkalkulator_bkk"]
        old_store.async_remove.assert_called_once()

    def test_no_migration_when_entry_store_has_data(self):
        """When entry store has data, DSO store is never checked."""
        coord = _reload_coord()

        now = datetime.now()
        entry_data = {
            "daily_max_power": {"2026-04-01": 9.0},
            "monthly_consumption": {"dag": 200.0, "natt": 100.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        old_store_accessed = False

        def make_store(hass, version, key):
            nonlocal old_store_accessed
            store = MagicMock()
            if key == "stromkalkulator_entry_test":
                store.async_load = AsyncMock(return_value=entry_data)
            else:
                old_store_accessed = True
                store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry("entry_test", dso_id="bkk")
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # Should have loaded from entry store, not DSO store
        assert coordinator._daily_max_power == {"2026-04-01": 9.0}
        assert not old_store_accessed


class TestMonthMismatchReset:
    """Loading stored data from a different month should reset current-month data."""

    def test_stored_month_differs_sets_stored_month(self):
        """If stored month != current month, _current_month is set to stored value
        so that the normal month-transition in _async_update_data fires."""
        coord = _reload_coord()

        now = datetime.now()
        current_month_str = now.strftime("%Y-%m")
        # Use a different month string
        old_month_str = "2025-12"
        assert old_month_str != current_month_str

        stored_data = {
            "daily_max_power": {"old-date": 15.0},
            "monthly_consumption": {"dag": 500.0, "natt": 300.0},
            "current_month": old_month_str,
            "monthly_norgespris_diff": 99.9,
            "previous_month_consumption": {"dag": 250.0, "natt": 150.0},
            "previous_month_top_3": {"2025-11-01": 8.0},
            "previous_month_name": "november 2025",
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # _current_month should be set to stored value (triggers transition in _async_update_data)
        assert coordinator._current_month == old_month_str
        # Data is loaded as-is; transition happens in _async_update_data
        assert coordinator._daily_max_power == {"old-date": 15.0}

        # Previous month data should be preserved
        assert coordinator._previous_month_consumption == {"dag": 250.0, "natt": 150.0}
        assert coordinator._previous_month_top_3 == {"2025-11-01": 8.0}
        assert coordinator._previous_month_name == "november 2025"

    def test_stored_month_matches_preserves_data(self):
        """If stored month == current month, data is preserved."""
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 7.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._daily_max_power == {"2026-04-01": 7.0}
        assert coordinator._monthly_consumption == {"dag": 100.0, "natt": 50.0}


class TestSaveDataStructure:
    """Verify the structure of saved data."""

    def test_save_includes_all_fields(self):
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._save_stored_data())

        expected_keys = {
            "daily_max_power",
            "monthly_consumption",
            "current_month",
            "previous_month_consumption",
            "previous_month_top_3",
            "previous_month_name",
            "monthly_norgespris_diff",
            "previous_month_norgespris_diff",
            "daily_cost",
            "current_date",
            "current_hour_energy",
            "current_hour",
            "monthly_export_kwh",
            "monthly_export_revenue",
            "monthly_cost",
            "previous_month_export_kwh",
            "previous_month_export_revenue",
            "previous_month_cost",
        }
        assert expected_keys == set(saved_data.keys())

    def test_save_stores_current_month_as_string(self):
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._save_stored_data())

        # Coordinator init uses dt_util.now() which conftest sets to 2026-06-15
        assert saved_data["current_month"] == "2026-06"


class TestLoadMissingFields:
    """Loading data with missing optional fields should use defaults."""

    def test_missing_norgespris_diff_defaults_to_zero(self):
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 5.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.month,
            # missing: monthly_norgespris_diff
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._monthly_norgespris_diff == 0.0

    def test_missing_previous_month_defaults(self):
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.month,
            # missing: previous_month_*, monthly_norgespris_diff
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._previous_month_consumption == {"dag": 0.0, "natt": 0.0}
        assert coordinator._previous_month_top_3 == {}
        assert coordinator._previous_month_name is None
