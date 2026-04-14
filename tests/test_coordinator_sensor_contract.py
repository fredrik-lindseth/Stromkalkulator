"""Contract test: coordinator output must be compatible with sensor input.

Runs a real coordinator update, then feeds the result into sensor classes
to verify they don't crash. This catches type mismatches between coordinator
and sensor (e.g. dict vs dataclass) that unit tests miss because they mock
coordinator.data independently.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

_real_datetime = datetime


# ---------------------------------------------------------------------------
# Coordinator infrastructure (same as test_coordinator_update.py)
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_update_coordinator():
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
def coord_module():
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    coord.dt_util = MagicMock()
    coord.dt_util.now.return_value = _real_datetime(2026, 6, 15, 12, 0)

    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return coord


# ---------------------------------------------------------------------------
# Sensor infrastructure (same as test_sensor_classes.py)
# ---------------------------------------------------------------------------

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


class FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = FakeCoordinatorEntity

from stromkalkulator.sensor import (  # noqa: E402
    ForrigeMaanedToppforbrukSensor,
    KapasitetstrinnSensor,
    MaksForbrukSensor,
    MarginNesteTrinnSensor,
    SpotprisEtterStotteSensor,
    StromstotteSensor,
    TariffSensor,
    TotalPriceSensor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(value):
    state = MagicMock()
    state.state = str(value)
    return state


def _make_hass(power_w=5000, spot_price=1.20):
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _make_entry(entry_id="test_entry", dso_id="bkk", har_norgespris=False):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "har_norgespris": har_norgespris,
        "avgiftssone": "standard",
    }
    return entry


def _build_coordinator_with_data(coord_module):
    """Run coordinator across an hour boundary to populate daily_max_power."""
    hass = _make_hass(power_w=8000, spot_price=1.50)
    entry = _make_entry()
    coordinator = coord_module.NettleieCoordinator(hass, entry)

    # First update at 09:50 - starts accumulating energy in hour 9
    now = _real_datetime(2026, 6, 15, 9, 50)
    coord_module.dt_util.now.return_value = now
    asyncio.run(coordinator._async_update_data())

    # Second update still in hour 9 - accumulates more energy
    t2 = now + timedelta(minutes=5)
    coord_module.dt_util.now.return_value = t2
    asyncio.run(coordinator._async_update_data())

    # Third update crosses into hour 10 - triggers daily_max_power write
    t3 = _real_datetime(2026, 6, 15, 10, 1)
    coord_module.dt_util.now.return_value = t3
    data = asyncio.run(coordinator._async_update_data())

    coordinator.data = data
    return coordinator, entry, data


# ---------------------------------------------------------------------------
# Contract tests
# ---------------------------------------------------------------------------


class TestCoordinatorSensorContract:
    """Sensors must be able to read coordinator.data without type errors."""

    def test_maks_forbruk_reads_top_3_days(self, coord_module):
        """MaksForbrukSensor can read top_3_days from real coordinator output."""
        coordinator, entry, data = _build_coordinator_with_data(coord_module)

        assert "top_3_days" in data
        assert len(data["top_3_days"]) >= 1

        sensor = MaksForbrukSensor(coordinator, entry, 1)
        value = sensor.native_value
        assert value is not None
        assert isinstance(value, float)
        assert value > 0

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "dato" in attrs
        assert "time" in attrs

    def test_kapasitetstrinn_reads_top_3(self, coord_module):
        """KapasitetstrinnSensor extra_state_attributes reads top_3_days."""
        coordinator, entry, _data = _build_coordinator_with_data(coord_module)

        sensor = KapasitetstrinnSensor(coordinator, entry)
        value = sensor.native_value
        assert value is not None

        attrs = sensor.extra_state_attributes
        assert attrs is not None
        # Should contain maks_1_kw from top_3_days
        assert "maks_1_kw" in attrs

    def test_forrige_maaned_toppforbruk_after_month_transition(self, coord_module):
        """ForrigeMaanedToppforbrukSensor reads previous_month_top_3."""
        coordinator, entry, data = _build_coordinator_with_data(coord_module)

        # Simulate month transition: move accumulated data to previous month
        coordinator._previous_month_top_3 = dict(coordinator._daily_max_power)
        coordinator._previous_month_name = "mai 2026"

        # Re-run update to populate previous month fields in data
        now = _real_datetime(2026, 7, 1, 10, 0)
        coord_module.dt_util.now.return_value = now
        data = asyncio.run(coordinator._async_update_data())
        coordinator.data = data

        sensor = ForrigeMaanedToppforbrukSensor(coordinator, entry)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "topp_1_kw" in attrs

    def test_basic_sensors_dont_crash(self, coord_module):
        """All common sensors can read from real coordinator output."""
        coordinator, entry, _data = _build_coordinator_with_data(coord_module)

        sensors = [
            TotalPriceSensor(coordinator, entry),
            StromstotteSensor(coordinator, entry),
            SpotprisEtterStotteSensor(coordinator, entry),
            TariffSensor(coordinator, entry),
            MarginNesteTrinnSensor(coordinator, entry),
        ]

        for sensor in sensors:
            # Should not raise
            value = sensor.native_value
            assert value is not None, f"{sensor.__class__.__name__} returned None"
