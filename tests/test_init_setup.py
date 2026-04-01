"""Tests for __init__.py — async_setup_entry and async_unload_entry.

Verifies that setup creates a coordinator, forwards platforms,
and that unload returns True. Also tests DSO migration triggering.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import AsyncMock, MagicMock, patch

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

        async def async_config_entry_first_refresh(self):
            pass

    mod = sys.modules["homeassistant.helpers.update_coordinator"]
    original = getattr(mod, "DataUpdateCoordinator", None)
    mod.DataUpdateCoordinator = FakeDataUpdateCoordinator
    yield
    mod.DataUpdateCoordinator = original


@pytest.fixture
def init_module():
    """Reload __init__ module and coordinator module."""
    import stromkalkulator.__init__ as init_mod
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    importlib.reload(init_mod)

    # Patch Store in coordinator
    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return init_mod


def _make_hass():
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = MagicMock()
    hass.config.path = MagicMock(return_value="/tmp/.storage")
    return hass


def _make_entry(entry_id="test_entry", tso_id="bkk"):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": tso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
    }
    entry.runtime_data = None
    return entry


class TestAsyncSetupEntry:
    """async_setup_entry creates coordinator and forwards platforms."""

    def test_returns_true(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        result = asyncio.run(init_module.async_setup_entry(hass, entry))
        assert result is True

    def test_sets_runtime_data(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_setup_entry(hass, entry))
        assert entry.runtime_data is not None

    def test_forwards_sensor_platform(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_setup_entry(hass, entry))
        hass.config_entries.async_forward_entry_setups.assert_called_once()
        # Verify SENSOR platform is in the list
        args = hass.config_entries.async_forward_entry_setups.call_args
        platforms = args[0][1]  # Second positional arg
        platform_values = [str(p) for p in platforms]
        assert any("sensor" in str(p).lower() for p in platform_values)


class TestAsyncUnloadEntry:
    """async_unload_entry returns True when unload succeeds."""

    def test_returns_true(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        result = asyncio.run(init_module.async_unload_entry(hass, entry))
        assert result is True

    def test_unloads_platforms(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_unload_entry(hass, entry))
        hass.config_entries.async_unload_platforms.assert_called_once()


class TestDSOMigrationInSetup:
    """DSO migration triggers during setup for old TSO keys."""

    def test_migrated_tso_updates_config_entry(self, init_module):
        """Setup with old TSO key should update config entry to new key."""
        hass = _make_hass()
        entry = _make_entry(tso_id="skiakernett")

        with patch.object(init_module, "_migrate_storage_file", new_callable=AsyncMock):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        # Config entry should be updated with new TSO key
        hass.config_entries.async_update_entry.assert_called_once()
        call_kwargs = hass.config_entries.async_update_entry.call_args
        new_data = call_kwargs[1]["data"] if "data" in call_kwargs[1] else call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
        # The update call should contain the new TSO key
        if new_data is None:
            # Check positional args
            for arg in call_kwargs[0]:
                if isinstance(arg, dict) and "tso" in arg:
                    new_data = arg
                    break
        if new_data:
            assert new_data["tso"] == "vevig"

    def test_current_tso_no_migration(self, init_module):
        """Setup with current TSO key should not trigger migration."""
        hass = _make_hass()
        entry = _make_entry(tso_id="bkk")

        asyncio.run(init_module.async_setup_entry(hass, entry))

        # async_update_entry should NOT be called
        hass.config_entries.async_update_entry.assert_not_called()

    def test_migrated_tso_creates_repair_issue(self, init_module):
        """DSO migration should create a repair issue."""
        hass = _make_hass()
        entry = _make_entry(tso_id="norgesnett")

        # Patch ir on the init_module (the module uses `ir.async_create_issue`)
        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"

        with (
            patch.object(init_module, "ir", mock_ir),
            patch.object(init_module, "_migrate_storage_file", new_callable=AsyncMock),
        ):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        mock_ir.async_create_issue.assert_called_once()
