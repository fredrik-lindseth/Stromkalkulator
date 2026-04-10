"""Tests for shared helper functions in sensor.py and coordinator.py."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

import pytest

# Patch HA modules so sensor.py classes can be imported without a live HA instance.
# This must mirror what test_sensor_classes.py does to avoid metaclass conflicts.
_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
    "MONETARY": "monetary",
    "POWER": "power",
    "ENERGY": "energy",
})
_sensor_mod.SensorEntity = type("SensorEntity", (), {})
_sensor_mod.SensorStateClass = type("SensorStateClass", (), {
    "MEASUREMENT": "measurement",
    "TOTAL": "total",
    "TOTAL_INCREASING": "total_increasing",
})

_const_mod = sys.modules["homeassistant.const"]
_const_mod.EntityCategory = type("EntityCategory", (), {
    "DIAGNOSTIC": "diagnostic",
    "CONFIG": "config",
})

_entity_mod = sys.modules["homeassistant.helpers.entity"]
_entity_mod.EntityCategory = _const_mod.EntityCategory

_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class _FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = _FakeCoordinatorEntity

from stromkalkulator.sensor import _beregn_nettleie  # noqa: E402


class TestBeregnNettleie:
    """Tests for _beregn_nettleie helper."""

    def test_basic_calculation(self):
        result = _beregn_nettleie(100.0, 50.0, 0.4613, 0.2329, 600)
        expected = (100.0 * 0.4613) + (50.0 * 0.2329) + 600
        assert result == round(expected, 2)

    def test_zero_consumption(self):
        result = _beregn_nettleie(0.0, 0.0, 0.4613, 0.2329, 600)
        assert result == 600.0

    def test_without_kapasitetsledd(self):
        result = _beregn_nettleie(100.0, 50.0, 0.4613, 0.2329)
        expected = (100.0 * 0.4613) + (50.0 * 0.2329)
        assert result == round(expected, 2)

    def test_rounding(self):
        result = _beregn_nettleie(33.333, 66.666, 0.1111, 0.2222, 155)
        assert result == round((33.333 * 0.1111) + (66.666 * 0.2222) + 155, 2)


class _FakeDataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator used during coordinator import."""

    def __init_subclass__(cls, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass


@pytest.fixture(autouse=True)
def _patch_coordinator_base():
    """Ensure NettleieCoordinator inherits from a real class, not a MagicMock."""
    original = getattr(_coord_mod, "DataUpdateCoordinator", None)
    _coord_mod.DataUpdateCoordinator = _FakeDataUpdateCoordinator
    import stromkalkulator.coordinator as coord
    importlib.reload(coord)
    yield coord.NettleieCoordinator
    _coord_mod.DataUpdateCoordinator = original


class TestReadPowerW:
    """Tests for _read_power_w helper."""

    def _make_state(self, value):
        state = MagicMock()
        state.state = value
        return state

    def test_normal_value(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("5000"))
        assert result == 5000.0

    def test_unavailable(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("unavailable"))
        assert result == 0.0

    def test_unknown(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("unknown"))
        assert result == 0.0

    def test_none_state(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(None)
        assert result == 0.0

    def test_non_numeric(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("abc"))
        assert result == 0.0

    def test_nan(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("nan"))
        assert result == 0.0

    def test_inf(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("inf"))
        assert result == 0.0

    def test_over_500kw_clamped(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("600000"))
        assert result == 0.0

    def test_negative(self, _patch_coordinator_base):
        result = _patch_coordinator_base._read_power_w(self._make_state("-100"))
        assert result == -100.0
