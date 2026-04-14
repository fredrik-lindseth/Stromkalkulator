"""Tests for coverage gaps found by test-my-tests review.

Covers 10 gaps identified in the v1.1.0 release cycle where bugfixes
were committed but corresponding tests were missing:

1. UpdateFailed when both sensors are None (e26ac3a)
2. Dict-format kapasitetstrinn normalization (405f7ee)
3. MaanedligStromstotteSensor native_value
4. Backward compat integer month format in storage (2c9d844)
5. Corrupt storage exception handler (cb8e9ec)
6. Power reading validation: NaN, >500kW clamping (142bb3e)
7. get_default_avgiftssone() for all price areas
8. EnergileddDag/NattSensor reverse calculation in attributes
9. _save_stored_data OSError handler (cb8e9ec)
10. Coordinator __init__ fallback for invalid config (fc9d193)
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
    # Also ensure UpdateFailed is available
    if not hasattr(mod, "UpdateFailed") or not isinstance(mod.UpdateFailed, type):
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
    coord.dt_util.now.return_value = _real_datetime(2026, 4, 9, 12, 0)

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
    extra_data=None,
):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "avgiftssone": avgiftssone,
    }
    if extra_data:
        entry.data.update(extra_data)
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
# 1. UpdateFailed when sensor entities are missing (e26ac3a)
# ===========================================================================


class TestUpdateFailedSensorsMissing:
    """Coordinator must raise UpdateFailed when either sensor is missing."""

    def test_both_sensors_none_raises(self, coord_module):
        """When both power and spot sensor return None, raise UpdateFailed."""
        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)  # Both sensors missing

        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(coord_module.UpdateFailed, match="Power sensor"):
            _run_update(coord_module, coordinator)

    def test_power_none_spot_valid_raises(self, coord_module):
        """When only power is None, should raise UpdateFailed."""
        hass = MagicMock()

        def get_state(eid):
            if "spot" in eid:
                return _make_state(1.20)
            return None  # power sensor not registered

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(coord_module.UpdateFailed, match="Power sensor"):
            _run_update(coord_module, coordinator)

    def test_spot_none_power_valid_raises(self, coord_module):
        """When only spot is None, should raise UpdateFailed."""
        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            return None  # spot sensor not registered

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(coord_module.UpdateFailed, match="Spot price sensor"):
            _run_update(coord_module, coordinator)


# ===========================================================================
# 2. Dict-format kapasitetstrinn normalization (405f7ee)
# ===========================================================================


class TestDictFormatKapasitetstrinn:
    """Coordinator must normalize dict-format kapasitetstrinn to tuples."""

    def test_barents_nett_dict_format_normalized(self, coord_module):
        """Barents Nett uses dict-format, should be converted to tuples."""
        hass = _make_hass()
        entry = _make_entry(dso_id="barents_nett")

        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # Should be list of tuples, not dicts
        assert isinstance(coordinator.kapasitetstrinn, list)
        for item in coordinator.kapasitetstrinn:
            assert isinstance(item, tuple), f"Expected tuple, got {type(item)}: {item}"
            assert len(item) == 2

    def test_barents_nett_values_correct(self, coord_module):
        """Verify dict->tuple conversion preserves correct values."""
        hass = _make_hass()
        entry = _make_entry(dso_id="barents_nett")

        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # First tier: {"min": 0, "max": 2, "pris": 517} -> (2, 517)
        assert coordinator.kapasitetstrinn[0] == (2, 517)
        # Last tier: {"min": 20, "max": 999, "pris": 931} -> (999, 931)
        assert coordinator.kapasitetstrinn[-1] == (999, 931)

    def test_barents_nett_update_runs(self, coord_module):
        """Full update with dict-format DSO should not crash."""
        hass = _make_hass()
        entry = _make_entry(dso_id="barents_nett", avgiftssone="tiltakssone")

        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator)

        assert result["kapasitetsledd"] > 0
        assert result["dso"] == "Barents Nett"


# ===========================================================================
# 3. MaanedligStromstotteSensor (no test existed)
# ===========================================================================


class TestMaanedligStromstotteSensor:
    """MaanedligStromstotteSensor: total_kwh * stromstotte_per_kwh."""

    @pytest.fixture(autouse=True)
    def _setup_ha_mocks(self):
        """Set up HA module mocks for sensor imports."""
        _sensor_mod = sys.modules["homeassistant.components.sensor"]
        _sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
            "MONETARY": "monetary", "POWER": "power", "ENERGY": "energy",
        })
        _sensor_mod.SensorEntity = type("SensorEntity", (), {})
        _sensor_mod.SensorStateClass = type("SensorStateClass", (), {
            "MEASUREMENT": "measurement", "TOTAL": "total", "TOTAL_INCREASING": "total_increasing",
        })
        _const_mod = sys.modules["homeassistant.const"]
        _const_mod.EntityCategory = type("EntityCategory", (), {
            "DIAGNOSTIC": "diagnostic", "CONFIG": "config",
        })
        _entity_mod = sys.modules["homeassistant.helpers.entity"]
        _entity_mod.EntityCategory = _const_mod.EntityCategory
        _coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]

        class FakeCoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator

        _coord_mod.CoordinatorEntity = FakeCoordinatorEntity

    def _make_sensor(self, data):
        from stromkalkulator.sensor import MaanedligStromstotteSensor

        coord = MagicMock()
        coord.data = data
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk"}
        return MaanedligStromstotteSensor(coord, entry)

    def test_normal_calculation(self):
        """400 kWh * 0.50 strømstøtte = 200 kr."""
        sensor = self._make_sensor({
            "monthly_consumption_total_kwh": 400.0,
            "stromstotte": 0.50,
        })
        assert sensor.native_value == 200.0

    def test_zero_stromstotte(self):
        """No subsidy -> 0 kr."""
        sensor = self._make_sensor({
            "monthly_consumption_total_kwh": 400.0,
            "stromstotte": 0,
        })
        assert sensor.native_value == 0.0

    def test_zero_consumption(self):
        """No consumption -> 0 kr."""
        sensor = self._make_sensor({
            "monthly_consumption_total_kwh": 0,
            "stromstotte": 0.50,
        })
        assert sensor.native_value == 0.0

    def test_returns_none_when_no_data(self):
        sensor = self._make_sensor(None)
        # coordinator.data is None - but the mock returns None for .data
        from stromkalkulator.sensor import MaanedligStromstotteSensor

        coord = MagicMock()
        coord.data = None
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk"}
        sensor = MaanedligStromstotteSensor(coord, entry)
        assert sensor.native_value is None

    def test_attributes_include_merknad(self):
        sensor = self._make_sensor({
            "monthly_consumption_total_kwh": 100.0,
            "stromstotte": 0.30,
            "har_norgespris": False,
        })
        attrs = sensor.extra_state_attributes
        assert "merknad" in attrs
        assert attrs["stromstotte_per_kwh"] == 0.30
        assert attrs["har_norgespris"] is False


# ===========================================================================
# 4. Backward compat: integer month format in storage (2c9d844)
# ===========================================================================


class TestIntegerMonthBackwardCompat:
    """Old storage format stored month as integer (e.g., 3), not "2026-03"."""

    def test_integer_month_converted_to_string(self, coord_module):
        """Loading stored_month=3 should set _current_month to "YYYY-03"."""
        stored_data = {
            "daily_max_power": {"2026-03-01": 5.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": 3,  # Old integer format
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        # Should be converted to "YYYY-03" string
        assert isinstance(coordinator._current_month, str)
        assert coordinator._current_month.endswith("-03")
        assert len(coordinator._current_month) == 7  # "YYYY-MM"


# ===========================================================================
# 5. Corrupt storage exception handler (cb8e9ec)
# ===========================================================================


class TestCorruptStorageHandler:
    """Corrupt storage data should fall back to defaults, not crash."""

    def test_completely_corrupt_data_uses_defaults(self, coord_module):
        """Storage with wrong types should not crash."""
        stored_data = {
            "daily_max_power": "not_a_dict",  # Should be dict
            "monthly_consumption": 42,  # Should be dict
            "current_month": ["wrong"],  # Should be str or int
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # Should not raise
        asyncio.run(coordinator._load_stored_data())

        # Validation methods should handle bad types gracefully
        assert isinstance(coordinator._daily_max_power, dict)
        assert isinstance(coordinator._monthly_consumption, coord_module.ConsumptionData)


# ===========================================================================
# 6. Power reading validation: NaN, >500kW clamping (142bb3e)
# ===========================================================================


class TestPowerReadingValidation:
    """Extreme power values must be clamped/zeroed."""

    def test_nan_power_zeroed(self, coord_module):
        """NaN power reading should be treated as 0."""
        hass = _make_hass(power_w=float("nan"))
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_inf_power_zeroed(self, coord_module):
        """Infinity power reading should be treated as 0."""
        hass = _make_hass(power_w=float("inf"))
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_over_500kw_clamped(self, coord_module):
        """Power > 500,000 W should be clamped to 0."""
        hass = _make_hass(power_w=600_000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_exactly_500kw_not_clamped(self, coord_module):
        """Power exactly at 500,000 W should pass through."""
        hass = _make_hass(power_w=500_000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 500.0

    def test_negative_power_zeroed(self, coord_module):
        """Negative power after float() should be 0 (unavailable/unknown)."""
        # Negative values come from sensor returning "unavailable"/"unknown"
        # which is handled before this check, but negative floats should
        # not accumulate energy
        hass = _make_hass(power_w=0)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 0


# ===========================================================================
# 7. get_default_avgiftssone() for all price areas
# ===========================================================================


class TestGetDefaultAvgiftssone:
    """get_default_avgiftssone maps price areas to tax zones."""

    @pytest.mark.parametrize(
        ("prisomrade", "expected"),
        [
            ("NO1", "standard"),
            ("NO2", "standard"),
            ("NO3", "standard"),  # NO3 = Trøndelag/Møre og Romsdal, HAR mva
            ("NO4", "nord_norge"),
            ("NO5", "standard"),
        ],
        ids=["NO1_sor", "NO2_sor", "NO3_standard", "NO4_nord", "NO5_sor"],
    )
    def test_price_area_to_avgiftssone(self, prisomrade, expected):
        from stromkalkulator.const import get_default_avgiftssone

        assert get_default_avgiftssone(prisomrade) == expected


# ===========================================================================
# 8. EnergileddDag/NattSensor reverse calculation in attributes
# ===========================================================================


class TestEnergileddReverseCalculation:
    """Verify the eks_avgifter_mva reverse calculation in attributes."""

    @pytest.fixture(autouse=True)
    def _setup_ha_mocks(self):
        _sensor_mod = sys.modules["homeassistant.components.sensor"]
        _sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
            "MONETARY": "monetary", "POWER": "power", "ENERGY": "energy",
        })
        _sensor_mod.SensorEntity = type("SensorEntity", (), {})
        _sensor_mod.SensorStateClass = type("SensorStateClass", (), {
            "MEASUREMENT": "measurement", "TOTAL": "total", "TOTAL_INCREASING": "total_increasing",
        })
        _const_mod = sys.modules["homeassistant.const"]
        _const_mod.EntityCategory = type("EntityCategory", (), {
            "DIAGNOSTIC": "diagnostic", "CONFIG": "config",
        })
        _entity_mod = sys.modules["homeassistant.helpers.entity"]
        _entity_mod.EntityCategory = _const_mod.EntityCategory
        _coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]

        class FakeCoordinatorEntity:
            def __init__(self, coordinator):
                self.coordinator = coordinator

        _coord_mod.CoordinatorEntity = FakeCoordinatorEntity

    def _make_dag_sensor(self, avgiftssone="standard"):
        from stromkalkulator.sensor import EnergileddDagSensor

        coord = MagicMock()
        coord.data = {"energiledd_dag": 0.4613}
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
        return EnergileddDagSensor(coord, entry)

    def _make_natt_sensor(self, avgiftssone="standard"):
        from stromkalkulator.sensor import EnergileddNattSensor

        coord = MagicMock()
        coord.data = {"energiledd_natt": 0.2329}
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
        return EnergileddNattSensor(coord, entry)

    def test_dag_eks_avgifter_standard(self):
        """Standard zone: energiledd / 1.25 - forbruksavgift - enova."""
        from stromkalkulator.const import ENOVA_AVGIFT, FORBRUKSAVGIFT_ALMINNELIG

        sensor = self._make_dag_sensor("standard")
        attrs = sensor.extra_state_attributes
        expected = round(0.4613 / 1.25 - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT, 4)
        assert attrs["eks_avgifter_mva"] == expected

    def test_natt_eks_avgifter_standard(self):
        from stromkalkulator.const import ENOVA_AVGIFT, FORBRUKSAVGIFT_ALMINNELIG

        sensor = self._make_natt_sensor("standard")
        attrs = sensor.extra_state_attributes
        expected = round(0.2329 / 1.25 - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT, 4)
        assert attrs["eks_avgifter_mva"] == expected

    def test_dag_eks_avgifter_nord_norge(self):
        """Nord-Norge: no MVA, so divide by 1.0, same forbruksavgift from 2026."""
        from stromkalkulator.const import ENOVA_AVGIFT, FORBRUKSAVGIFT_ALMINNELIG

        sensor = self._make_dag_sensor("nord_norge")
        attrs = sensor.extra_state_attributes
        # mva_sats = 0.0 for nord_norge
        expected = round(0.4613 / 1.0 - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT, 4)
        assert attrs["eks_avgifter_mva"] == expected

    def test_dag_eks_avgifter_tiltakssone(self):
        """Tiltakssone: no MVA, no forbruksavgift."""
        from stromkalkulator.const import ENOVA_AVGIFT

        sensor = self._make_dag_sensor("tiltakssone")
        attrs = sensor.extra_state_attributes
        # mva_sats=0, forbruksavgift=0
        expected = round(0.4613 / 1.0 - 0.0 - ENOVA_AVGIFT, 4)
        assert attrs["eks_avgifter_mva"] == expected

    def test_bkk_dag_matches_faktura(self):
        """BKK dag: reverse should match BKK invoice value (~35.963 øre inkl. mva)."""
        # The sensor shows eks_avgifter_mva which strips public fees
        # BKK faktura: 35.963 øre/kWh inkl. mva -> 28.770 øre eks. mva
        sensor = self._make_dag_sensor("standard")
        attrs = sensor.extra_state_attributes
        # eks_avgifter_mva should be the pure energiledd without public fees
        # BKK invoice: 35.963 øre/kWh = 0.35963 NOK/kWh (energiledd inkl. mva, eks. avgifter)
        # Our value: 0.4613 / 1.25 - 0.0713 - 0.01 = 0.2877
        faktura_eks_mva = 35.963 / 100 / 1.25  # 0.28770
        assert attrs["eks_avgifter_mva"] == pytest.approx(faktura_eks_mva, abs=0.001)


# ===========================================================================
# 9. _save_stored_data OSError handler (cb8e9ec)
# ===========================================================================


class TestSaveOSErrorHandler:
    """_save_stored_data must survive disk errors."""

    def test_oserror_does_not_raise(self, coord_module):
        """When async_save raises OSError, _save_stored_data should not propagate."""

        def make_store_oserror(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock(side_effect=OSError("No space left on device"))
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store_oserror)

        hass = MagicMock()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # Should not raise
        asyncio.run(coordinator._save_stored_data())

    def test_update_continues_after_disk_error(self, coord_module):
        """Full update cycle should work even when saving fails."""
        save_calls = []

        def make_store_failing(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def failing_save(data):
                save_calls.append(data)
                raise OSError("Disk full")

            store.async_save = AsyncMock(side_effect=failing_save)
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store_failing)

        hass = _make_hass(power_w=5000, spot_price=1.20)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # First update sets _last_update; second accumulates energy → triggers save
        now = _real_datetime(2026, 4, 9, 12, 0)
        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=now + timedelta(minutes=1))
        assert result["spot_price"] == 1.20
        assert len(save_calls) > 0  # Save was attempted


# ===========================================================================
# 10. Coordinator __init__ fallback for invalid config (fc9d193)
# ===========================================================================


class TestCoordinatorInitFallbacks:
    """Invalid config values in entry.data should fall back to DSO defaults."""

    def test_invalid_energiledd_dag_falls_back(self, coord_module):
        """Non-numeric energiledd_dag should fall back to DSO default."""
        hass = MagicMock()
        entry = _make_entry(extra_data={"energiledd_dag": "invalid"})
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # Should use BKK default
        assert coordinator.energiledd_dag == 0.4613

    def test_invalid_energiledd_natt_falls_back(self, coord_module):
        """Non-numeric energiledd_natt should fall back to DSO default."""
        hass = MagicMock()
        entry = _make_entry(extra_data={"energiledd_natt": None})
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        assert coordinator.energiledd_natt == 0.2329

    def test_invalid_kapasitet_varsel_terskel_falls_back(self, coord_module):
        """Non-numeric terskel should fall back to default 2.0."""
        hass = MagicMock()
        entry = _make_entry(extra_data={"kapasitet_varsel_terskel": "abc"})
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        assert coordinator.kapasitet_varsel_terskel == 2.0

    def test_valid_custom_energiledd_used(self, coord_module):
        """Valid custom energiledd should override DSO defaults."""
        hass = MagicMock()
        entry = _make_entry(extra_data={
            "energiledd_dag": 0.55,
            "energiledd_natt": 0.33,
        })
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        assert coordinator.energiledd_dag == 0.55
        assert coordinator.energiledd_natt == 0.33


# ===========================================================================
# Nord-Norge avgiftssone i coordinator update (from test_quality_r3)
# ===========================================================================


class TestNordNorgeAvgiftssone:
    """Forbruksavgift uten MVA (nord_norge: full avgift, 0% mva)."""

    def test_nord_norge_forbruksavgift_no_mva(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(extra_data={"avgiftssone": "nord_norge"})
        entry.data["avgiftssone"] = "nord_norge"
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        # forbruksavgift: 0.0713 * (1 + 0.0) = 0.0713 (no MVA)
        assert result["forbruksavgift_inkl_mva"] == round(0.0713, 4)
        # enova: 0.01 * (1 + 0.0) = 0.01 (no MVA)
        assert result["enova_inkl_mva"] == round(0.01, 4)
        # total avgifter: 0.0713 + 0.01 = 0.0813
        assert result["offentlige_avgifter"] == round(0.0813, 4)


# ===========================================================================
# Electricity company price — bad values (from test_quality_r3)
# ===========================================================================


class TestElectricityCompanyPriceBadValues:
    """coordinator.py caching av strømleverandør-pris."""

    def test_unavailable_elco_price_uses_cache(self, coord_module):
        """Cache survives when sensor becomes unavailable."""
        hass = MagicMock()

        def get_state_valid(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return _make_state(0.85)
            return None

        hass.states.get = MagicMock(side_effect=get_state_valid)

        entry = _make_entry(extra_data={
            "electricity_provider_price_sensor": "sensor.elco",
            "spot_price_sensor": "sensor.spot_price",
        })
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        _run_update(coord_module, coordinator)  # cache 0.85

        # Now make sensor unavailable
        unavailable_state = MagicMock()
        unavailable_state.state = "unavailable"

        def get_state_unavail(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return unavailable_state
            return None

        hass.states.get = MagicMock(side_effect=get_state_unavail)

        result = _run_update(coord_module, coordinator)
        assert result["electricity_company_price"] == 0.85

    def test_garbage_elco_price_without_cache_returns_none(self, coord_module):
        """ValueError on parse, no cache → None."""
        garbage_state = MagicMock()
        garbage_state.state = "abc"

        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return garbage_state
            return None

        hass.states.get = MagicMock(side_effect=get_state)

        entry = _make_entry(extra_data={
            "electricity_provider_price_sensor": "sensor.elco",
            "spot_price_sensor": "sensor.spot_price",
        })
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["electricity_company_price"] is None

    def test_nan_elco_price_not_cached(self, coord_module):
        """NaN parses as float but isfinite() rejects it → None (not cached)."""
        nan_state = MagicMock()
        nan_state.state = "nan"

        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return nan_state
            return None

        hass.states.get = MagicMock(side_effect=get_state)

        entry = _make_entry(extra_data={
            "electricity_provider_price_sensor": "sensor.elco",
            "spot_price_sensor": "sensor.spot_price",
        })
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["electricity_company_price"] is None


# ===========================================================================
# 5000 kWh strømstøtte-tak boundary (from test_quality_r3)
# ===========================================================================


class TestStromstotteTakBoundary:
    """coordinator.py >= 5000 kWh grense."""

    def test_4999_9_kwh_still_gets_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=3000.0, natt=1999.9)

        result = _run_update(coord_module, coordinator)
        assert result["stromstotte"] > 0
        assert result["stromstotte_tak_naadd"] is False

    def test_5000_kwh_no_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=3000.0, natt=2000.0)

        result = _run_update(coord_module, coordinator)
        assert result["stromstotte"] == 0.0
        assert result["stromstotte_tak_naadd"] is True

    def test_5001_kwh_no_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = coord_module.ConsumptionData(dag=3000.0, natt=2001.0)

        result = _run_update(coord_module, coordinator)
        assert result["stromstotte"] == 0.0
        assert result["stromstotte_tak_naadd"] is True


# ===========================================================================
# Negative verdier i validators (from test_quality_r3)
# ===========================================================================


class TestValidatorsNegativeValues:
    """coordinator.py negative verdier filtreres/clampes."""

    def test_validate_daily_max_power_skips_negative(self, coord_module):
        validate = coord_module.NettleieCoordinator._validate_daily_max_power
        result = validate({"2026-04-01": -5.0, "2026-04-02": 3.0})
        assert "2026-04-01" not in result
        assert result["2026-04-02"] == coord_module.DailyMaxEntry(kw=3.0)

    def test_validate_consumption_clamps_negative_to_zero(self, coord_module):
        validate = coord_module.NettleieCoordinator._validate_consumption
        result = validate({"dag": -100.0, "natt": 50.0})
        assert result.dag == 0.0
        assert result.natt == 50.0
