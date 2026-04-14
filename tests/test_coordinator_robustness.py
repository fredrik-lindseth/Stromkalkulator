"""Tests for coordinator robustness: caching, clamping, validation.

P2 hull 6-8: Tests spotpris-caching branches, elapsed_hours clamping,
and the three static validation methods.
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
# Coordinator test infrastructure (same pattern as test_coordinator_update.py)
# ---------------------------------------------------------------------------


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
    # Ensure UpdateFailed is a real exception class (not a MagicMock)
    original_uf = getattr(mod, "UpdateFailed", None)
    if not isinstance(original_uf, type) or not issubclass(original_uf, BaseException):
        class UpdateFailed(Exception):
            pass
        mod.UpdateFailed = UpdateFailed
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
    state = MagicMock()
    state.state = str(value)
    return state


def _make_entry(
    entry_id="test_entry",
    dso_id="bkk",
    avgiftssone="standard",
):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "avgiftssone": avgiftssone,
    }
    return entry


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


def _run_update(coord_module, coordinator, now=None):
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


# ===========================================================================
# P2.6 — Spotpris-caching
# ===========================================================================


class TestSpotprisCaching:
    """Four branches in spot price reading (lines 229-243)."""

    def test_valid_spot_price_is_stored_and_used(self, coord_module):
        """Branch 1: Valid spot price -> stored and used."""
        hass = _make_hass(spot_price=1.50)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 1.50
        assert coordinator._last_spot_price == 1.50

    def test_invalid_spot_with_cache_uses_cache(self, coord_module):
        """Branch 2: ValueError on spot parse with existing cache -> cache used."""
        hass = _make_hass(spot_price=1.50)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # First update: populate cache
        _run_update(coord_module, coordinator)
        assert coordinator._last_spot_price == 1.50

        # Now make spot sensor return garbage
        garbage_state = MagicMock()
        garbage_state.state = "not_a_number"

        def get_state_garbage(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return garbage_state
            return None

        hass.states.get = MagicMock(side_effect=get_state_garbage)

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 1.50  # cached value

    def test_unavailable_sensor_with_cache_uses_cache(self, coord_module):
        """Branch 3: Sensor unavailable with cache -> cache used."""
        hass = _make_hass(spot_price=2.00)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # First update: populate cache
        _run_update(coord_module, coordinator)
        assert coordinator._last_spot_price == 2.00

        # Now make sensor unavailable
        unavailable_state = MagicMock()
        unavailable_state.state = "unavailable"

        def get_state_unavailable(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return unavailable_state
            return None

        hass.states.get = MagicMock(side_effect=get_state_unavailable)

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 2.00  # cached value

    def test_unavailable_sensor_without_cache_uses_zero(self, coord_module):
        """Branch 4: Sensor unavailable, no cache -> spot_price = 0."""
        unavailable_state = MagicMock()
        unavailable_state.state = "unavailable"
        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return unavailable_state
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 0

    def test_none_sensor_without_cache_raises(self, coord_module):
        """Sensor not found at all (returns None) -> UpdateFailed."""
        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            return None  # spot sensor not found

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(coord_module.UpdateFailed, match="Spot price sensor"):
            _run_update(coord_module, coordinator)

    def test_nan_spot_with_cache_uses_cache(self, coord_module):
        """NaN spot value should fall back to cache."""
        hass = _make_hass(spot_price=1.80)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        _run_update(coord_module, coordinator)

        # Now return NaN
        nan_state = MagicMock()
        nan_state.state = "nan"

        def get_state_nan(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return nan_state
            return None

        hass.states.get = MagicMock(side_effect=get_state_nan)

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 1.80


# ===========================================================================
# P2.7 — Elapsed time clamping
# ===========================================================================


class TestSpotprisCacheTTL:
    """Spot price cache expires after 2 hours."""

    def test_cache_expires_after_2_hours(self, coord_module):
        """Cached spot price should not be used after 2 hours."""
        hass = _make_hass(spot_price=1.50)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # First update: populate cache
        t0 = _real_datetime(2026, 4, 9, 10, 0)
        _run_update(coord_module, coordinator, now=t0)
        assert coordinator._last_spot_price == 1.50

        # Make spot sensor unavailable
        unavail = MagicMock()
        unavail.state = "unavailable"

        def get_state_unavail(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return unavail
            return None

        hass.states.get = MagicMock(side_effect=get_state_unavail)

        # 1 hour later: cache should still work
        t1 = _real_datetime(2026, 4, 9, 11, 0)
        result1 = _run_update(coord_module, coordinator, now=t1)
        assert result1["spot_price"] == 1.50

        # 3 hours later: cache should have expired, fallback to 0.0
        t2 = _real_datetime(2026, 4, 9, 13, 1)
        result2 = _run_update(coord_module, coordinator, now=t2)
        assert result2["spot_price"] == 0.0


class TestElapsedTimeClamping:
    """elapsed_hours = max(0.0, min(elapsed_hours, 0.1))"""

    def test_normal_1_minute_interval(self, coord_module):
        """Normal 1-minute update interval -> ~0.0167 hours."""
        now = _real_datetime(2026, 4, 9, 12, 0)
        later = now + timedelta(minutes=1)

        hass = _make_hass(power_w=6000)  # 6 kW
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=later)

        # 6 kW * (1/60 h) ≈ 0.1 kWh
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert abs(total - 0.1) < 0.01

    def test_large_clock_jump_clamped(self, coord_module):
        """1 hour clock jump forward -> clamped to 0.1 h (6 min)."""
        now = _real_datetime(2026, 4, 9, 12, 0)
        much_later = now + timedelta(hours=1)

        hass = _make_hass(power_w=6000)  # 6 kW
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=much_later)

        # Clamped to 0.1h: 6 kW * 0.1 = 0.6 kWh
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert abs(total - 0.6) < 0.01

    def test_clock_jump_backward_clamped_to_zero(self, coord_module):
        """Negative elapsed time (clock jump back) -> clamped to 0.0."""
        now = _real_datetime(2026, 4, 9, 12, 0)
        earlier = now - timedelta(minutes=5)

        hass = _make_hass(power_w=6000)  # 6 kW
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=earlier)

        # Should accumulate 0 kWh due to clamp
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert total == 0.0

    def test_exactly_6_minutes_not_clamped(self, coord_module):
        """6 minutes = 0.1 hours exactly, should not be clamped."""
        now = _real_datetime(2026, 4, 9, 12, 0)
        later = now + timedelta(minutes=6)

        hass = _make_hass(power_w=6000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=later)

        # 6 kW * 0.1 h = 0.6 kWh
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert abs(total - 0.6) < 0.01


# ===========================================================================
# P2.8 — Storage validation static methods
# ===========================================================================


class TestValidateFloat:
    """NettleieCoordinator._validate_float()"""

    @pytest.fixture
    def validate(self, coord_module):
        return coord_module.NettleieCoordinator._validate_float

    def test_valid_float(self, validate):
        assert validate(3.14) == 3.14

    def test_valid_int(self, validate):
        assert validate(42) == 42.0

    def test_string_abc(self, validate):
        assert validate("abc") == 0.0

    def test_none(self, validate):
        assert validate(None) == 0.0

    def test_nan(self, validate):
        assert validate(float("nan")) == 0.0

    def test_inf(self, validate):
        assert validate(float("inf")) == 0.0

    def test_negative_inf(self, validate):
        assert validate(float("-inf")) == 0.0

    def test_negative_float(self, validate):
        assert validate(-5.5) == -5.5

    def test_zero(self, validate):
        assert validate(0.0) == 0.0

    def test_string_number(self, validate):
        """Numeric string should be converted."""
        assert validate("3.14") == 3.14


class TestValidateDailyMaxPower:
    """NettleieCoordinator._validate_daily_max_power()"""

    @pytest.fixture
    def validate(self, coord_module):
        return coord_module.NettleieCoordinator._validate_daily_max_power

    def test_valid_dict(self, validate, coord_module):
        data = {"2026-04-01": {"kw": 10.0, "hour": 8}, "2026-04-02": {"kw": 8.5, "hour": 16}}
        result = validate(data)
        assert result == {
            "2026-04-01": coord_module.DailyMaxEntry(kw=10.0, hour=8),
            "2026-04-02": coord_module.DailyMaxEntry(kw=8.5, hour=16),
        }

    def test_dict_with_nan_values_skipped(self, validate):
        data = {"2026-04-01": {"kw": 10.0, "hour": 8}, "2026-04-02": float("nan")}
        result = validate(data)
        assert "2026-04-01" in result
        assert "2026-04-02" not in result

    def test_dict_with_inf_values_skipped(self, validate):
        data = {"2026-04-01": float("inf"), "2026-04-02": {"kw": 5.0, "hour": 10}}
        result = validate(data)
        assert "2026-04-01" not in result
        assert result["2026-04-02"].kw == 5.0

    def test_list_returns_empty(self, validate):
        """Wrong type (list) -> empty dict."""
        assert validate([1, 2, 3]) == {}

    def test_none_returns_empty(self, validate):
        assert validate(None) == {}

    def test_string_values_converted(self, validate, coord_module):
        """String values that can be floats should be migrated to dict format."""
        result = validate({"2026-04-01": "10.5"})
        assert result["2026-04-01"] == coord_module.DailyMaxEntry(kw=10.5)

    def test_invalid_string_values_skipped(self, validate):
        result = validate({"2026-04-01": "not_a_number"})
        assert result == {}

    def test_empty_dict(self, validate):
        assert validate({}) == {}


class TestValidateConsumption:
    """NettleieCoordinator._validate_consumption()"""

    @pytest.fixture
    def validate(self, coord_module):
        return coord_module.NettleieCoordinator._validate_consumption

    def test_valid_dict(self, validate, coord_module):
        data = {"dag": 100.0, "natt": 50.0}
        result = validate(data)
        assert result == coord_module.ConsumptionData(dag=100.0, natt=50.0)

    def test_missing_keys_default_to_zero(self, validate, coord_module):
        """Dict without dag/natt should default both to 0."""
        result = validate({"other": 42})
        assert result == coord_module.ConsumptionData()

    def test_not_dict_returns_defaults(self, validate, coord_module):
        result = validate("not_a_dict")
        assert result == coord_module.ConsumptionData()

    def test_none_returns_defaults(self, validate, coord_module):
        result = validate(None)
        assert result == coord_module.ConsumptionData()

    def test_nan_values_replaced_with_zero(self, validate):
        result = validate({"dag": float("nan"), "natt": 50.0})
        assert result.dag == 0.0
        assert result.natt == 50.0

    def test_inf_values_replaced_with_zero(self, validate):
        result = validate({"dag": float("inf"), "natt": float("-inf")})
        assert result.dag == 0.0
        assert result.natt == 0.0

    def test_string_number_converted(self, validate):
        result = validate({"dag": "100.5", "natt": "50.0"})
        assert result.dag == 100.5
        assert result.natt == 50.0

    def test_invalid_string_replaced(self, validate):
        result = validate({"dag": "abc", "natt": 50.0})
        assert result.dag == 0.0
        assert result.natt == 50.0

    def test_partial_keys(self, validate):
        """Only dag present -> natt defaults to 0."""
        result = validate({"dag": 100.0})
        assert result.dag == 100.0
        assert result.natt == 0.0
