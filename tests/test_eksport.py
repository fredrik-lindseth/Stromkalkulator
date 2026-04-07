"""Tests for solar export / electricity selling functionality.

Verifies:
- Export energy accumulation from export power sensor
- Export revenue calculation (spot price x exported kWh)
- Monthly net cost (consumption cost - export revenue)
- Month transition archives export data
- No export data when sensor not configured
- Storage persistence of export fields
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

_real_datetime = datetime


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


@pytest.fixture
def coord_module():
    """Reload coordinator module and patch Store + dt_util."""
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


def _make_state(value):
    """Create a mock HA state object."""
    state = MagicMock()
    state.state = str(value)
    return state


def _make_entry(
    entry_id="test_entry",
    dso_id="bkk",
    har_norgespris=False,
    avgiftssone="standard",
    export_power_sensor=None,
):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "har_norgespris": har_norgespris,
        "avgiftssone": avgiftssone,
    }
    if export_power_sensor:
        entry.data["export_power_sensor"] = export_power_sensor
    return entry


def _make_hass(power_w=5000, spot_price=1.20, export_power_w=None):
    """Create a mock HA instance with sensor states."""
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        if entity_id == "sensor.export_power" and export_power_w is not None:
            return _make_state(export_power_w)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _run_update(coord_module, coordinator, now=None):
    """Run _async_update_data with optional time override."""
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


class TestExportNotConfigured:
    """When no export sensor is configured, export data should be zero."""

    def test_eksport_konfigurert_is_false(self, coord_module):
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["eksport_konfigurert"] is False

    def test_export_fields_are_zero(self, coord_module):
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["monthly_export_kwh"] == 0.0
        assert result["monthly_export_revenue_kr"] == 0.0

    def test_net_cost_equals_consumption_cost(self, coord_module):
        """Without export, net cost = consumption cost."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["monthly_net_cost_kr"] == result["monthly_cost_kr"]


class TestExportAccumulation:
    """Export energy and revenue accumulation."""

    def test_eksport_konfigurert_is_true(self, coord_module):
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["eksport_konfigurert"] is True

    def test_export_accumulates_energy(self, coord_module):
        """Export energy should accumulate over multiple updates."""
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)
        t2 = t1 + timedelta(minutes=1)

        # First update — sets _last_update, no accumulation yet
        _run_update(coord_module, coordinator, now=t0)
        # Second update — 1 minute elapsed, 3 kW export = 0.05 kWh
        result1 = _run_update(coord_module, coordinator, now=t1)
        export_kwh_1 = result1["monthly_export_kwh"]
        assert export_kwh_1 > 0

        # Third update — another minute
        result2 = _run_update(coord_module, coordinator, now=t2)
        export_kwh_2 = result2["monthly_export_kwh"]
        assert export_kwh_2 > export_kwh_1

    def test_export_revenue_uses_spot_price(self, coord_module):
        """Revenue = spot_price x exported_kwh, no fees."""
        spot_price = 1.50
        export_w = 6000  # 6 kW
        hass = _make_hass(power_w=5000, spot_price=spot_price, export_power_w=export_w)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        # 6 kW * (1/60) h = 0.1 kWh. Revenue = 1.50 * 0.1 = 0.15 kr
        expected_kwh = 6.0 * (1 / 60)
        expected_revenue = spot_price * expected_kwh
        assert abs(result["monthly_export_kwh"] - expected_kwh) < 0.001
        assert abs(result["monthly_export_revenue_kr"] - expected_revenue) < 0.01

    def test_no_export_when_zero_power(self, coord_module):
        """Zero export power should not accumulate."""
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=0)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        assert result["monthly_export_kwh"] == 0.0
        assert result["monthly_export_revenue_kr"] == 0.0

    def test_no_export_when_sensor_unavailable(self, coord_module):
        """Unavailable export sensor should not accumulate."""
        hass = MagicMock()
        unavailable_state = MagicMock()
        unavailable_state.state = "unavailable"

        def get_state(entity_id):
            if entity_id == "sensor.power":
                return _make_state(5000)
            if entity_id == "sensor.spot_price":
                return _make_state(1.20)
            if entity_id == "sensor.export_power":
                return unavailable_state
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        assert result["monthly_export_kwh"] == 0.0


class TestNetCost:
    """Net cost calculation (consumption - export)."""

    def test_net_cost_subtracts_export_revenue(self, coord_module):
        """Net cost = monthly_cost - monthly_export_revenue."""
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        net_cost = result["monthly_net_cost_kr"]
        cost = result["monthly_cost_kr"]
        revenue = result["monthly_export_revenue_kr"]
        assert abs(net_cost - (cost - revenue)) < 0.01

    def test_monthly_cost_accumulates(self, coord_module):
        """Monthly cost should accumulate over updates."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)
        t2 = t1 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result1 = _run_update(coord_module, coordinator, now=t1)
        result2 = _run_update(coord_module, coordinator, now=t2)

        assert result2["monthly_cost_kr"] > result1["monthly_cost_kr"]


class TestMonthTransitionExport:
    """Export data should be archived at month transition."""

    def test_archives_export_data(self, coord_module):
        """Previous month export fields populated after month transition."""
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # Build up some export data in June
        t0 = _real_datetime(2026, 6, 30, 23, 58)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        june_result = _run_update(coord_module, coordinator, now=t1)

        june_export_kwh = june_result["monthly_export_kwh"]
        june_export_revenue = june_result["monthly_export_revenue_kr"]
        june_cost = june_result["monthly_cost_kr"]

        # Transition to July
        t2 = _real_datetime(2026, 7, 1, 0, 1)
        july_result = _run_update(coord_module, coordinator, now=t2)

        assert july_result["previous_month_export_kwh"] == june_export_kwh
        assert july_result["previous_month_export_revenue_kr"] == june_export_revenue
        assert july_result["previous_month_cost_kr"] == june_cost

    def test_resets_current_month_export(self, coord_module):
        """Current month export should reset after month transition.

        The first July update itself accumulates a tiny amount from
        the elapsed time since the last June update. We use close
        timestamps around midnight to keep the accumulated amount small.
        """
        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # Build up data over multiple updates in June (close to midnight)
        t0 = _real_datetime(2026, 6, 30, 23, 55)
        t1 = t0 + timedelta(minutes=1)
        t2 = t1 + timedelta(minutes=1)
        t3 = t2 + timedelta(minutes=1)
        t4 = t3 + timedelta(minutes=1)
        _run_update(coord_module, coordinator, now=t0)
        _run_update(coord_module, coordinator, now=t1)
        _run_update(coord_module, coordinator, now=t2)
        _run_update(coord_module, coordinator, now=t3)
        june_result = _run_update(coord_module, coordinator, now=t4)

        june_export = june_result["monthly_export_kwh"]
        assert june_export > 0

        # Transition to July (1 min later)
        t5 = _real_datetime(2026, 7, 1, 0, 0)
        july_result = _run_update(coord_module, coordinator, now=t5)

        # The reset happened. Verify previous month got June data.
        assert july_result["previous_month_export_kwh"] == june_export
        # Current month has only a tiny bit from this single update
        # (1 min * 3 kW = 0.05 kWh), much less than June's 4 updates
        assert july_result["monthly_export_kwh"] < june_export


class TestExportStorage:
    """Export data persists to storage."""

    def test_saves_export_fields(self, coord_module):
        """Storage should include export fields."""
        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        _run_update(coord_module, coordinator, now=t1)

        assert "monthly_export_kwh" in saved_data
        assert "monthly_export_revenue" in saved_data
        assert "monthly_cost" in saved_data
        assert saved_data["monthly_export_kwh"] > 0

    def test_loads_export_fields(self, coord_module):
        """Export data should be restored from storage."""
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": "2026-06",
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
            "monthly_norgespris_diff": 0.0,
            "previous_month_norgespris_diff": 0.0,
            "daily_cost": 5.0,
            "current_date": "2026-06-15",
            "current_hour_energy": 0.0,
            "current_hour": 12,
            "monthly_export_kwh": 42.5,
            "monthly_export_revenue": 51.0,
            "monthly_cost": 200.0,
            "previous_month_export_kwh": 30.0,
            "previous_month_export_revenue": 36.0,
            "previous_month_cost": 180.0,
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass(power_w=5000, spot_price=1.20, export_power_w=3000)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)

        # Loaded values should be present (plus any small accumulation from the update)
        assert result["monthly_export_kwh"] >= 42.5
        assert result["monthly_export_revenue_kr"] >= 51.0
        assert result["monthly_cost_kr"] >= 200.0
        assert result["previous_month_export_kwh"] == 30.0
        assert result["previous_month_export_revenue_kr"] == 36.0
        assert result["previous_month_cost_kr"] == 180.0
