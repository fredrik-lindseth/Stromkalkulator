"""Tests for storage key isolation between config entries."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

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
            pass

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


def _make_entry(entry_id: str, tso_id: str = "bkk") -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": tso_id,
        "power_sensor": f"sensor.power_{entry_id}",
    }
    return entry


def test_storage_key_uses_entry_id(mock_store, mock_hass):
    """Storage key must include entry_id, not just tso_id."""
    # Re-import to pick up the patched DataUpdateCoordinator
    import importlib

    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    # Re-apply Store mock after reload
    mock_store.reset_mock()
    coord.Store = mock_store

    entry = _make_entry("entry_abc123", tso_id="bkk")
    coord.NettleieCoordinator(mock_hass, entry)

    mock_store.assert_called_once()
    store_key = mock_store.call_args[0][2]
    assert "entry_abc123" in store_key, f"Storage key should contain entry_id, got: {store_key}"


def test_two_entries_same_tso_get_different_storage(mock_store, mock_hass):
    """Two entries with same TSO must get different storage keys."""
    import importlib

    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    mock_store.reset_mock()
    coord.Store = mock_store

    entry1 = _make_entry("entry_111", tso_id="bkk")
    entry2 = _make_entry("entry_222", tso_id="bkk")

    coord.NettleieCoordinator(mock_hass, entry1)
    coord.NettleieCoordinator(mock_hass, entry2)

    assert mock_store.call_count == 2
    key1 = mock_store.call_args_list[0][0][2]
    key2 = mock_store.call_args_list[1][0][2]
    assert key1 != key2, f"Two entries got same storage key: {key1}"
