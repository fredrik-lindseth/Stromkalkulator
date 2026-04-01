"""R3 test quality: dekker bugfikser fra fuzzing som manglet tester.

Funn fra /test-my-tests (10 parallelle reviewers, 131 råfunn → 14 fikser).
Hver test refererer til commit som la til koden og item-nummer fra review.

Commits uten test:
- e26ac3a: raise UpdateFailed når begge sensorer mangler
- 142bb3e: avvis negative verdier, >500kW clamp
- cb8e9ec: OSError-håndtering, storage-validering
- 405f7ee: Barents Nett dict-format
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

_real_datetime = datetime


# ---------------------------------------------------------------------------
# Coordinator test infrastructure
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


def _make_state(value):
    state = MagicMock()
    state.state = str(value)
    return state


def _make_entry(entry_id="test_entry", dso_id="bkk", avgiftssone="standard",
                har_norgespris=False, elco_sensor=None):
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "avgiftssone": avgiftssone,
        "har_norgespris": har_norgespris,
    }
    if elco_sensor:
        entry.data["electricity_provider_price_sensor"] = elco_sensor
        entry.data["spot_price_sensor"] = "sensor.spot_price"
    return entry


def _make_hass(power_w=5000, spot_price=1.20, elco_price=None):
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        if entity_id == "sensor.elco" and elco_price is not None:
            return _make_state(elco_price)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _run(coord_module, coordinator, now=None):
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


# ===========================================================================
# Item 3: UpdateFailed når sensor-entiteter mangler (commit e26ac3a)
# ===========================================================================


class TestUpdateFailedSensorsMissing:
    """coordinator.py:262-265 — raise UpdateFailed for each missing sensor."""

    def test_both_sensors_none_raises(self, coord_module):
        """Når begge sensorer returnerer None, skal UpdateFailed raises (power first)."""
        # UpdateFailed er mocka — gjør den til et ekte exception
        class FakeUpdateFailed(Exception):
            pass

        coord_module.UpdateFailed = FakeUpdateFailed

        hass = MagicMock()
        hass.states.get = MagicMock(return_value=None)

        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(FakeUpdateFailed, match="Power sensor"):
            _run(coord_module, coordinator)

    def test_only_power_missing_raises(self, coord_module):
        """Bare power mangler → UpdateFailed."""
        class FakeUpdateFailed(Exception):
            pass

        coord_module.UpdateFailed = FakeUpdateFailed

        hass = MagicMock()

        def get_state(eid):
            if "spot" in eid:
                return _make_state(1.20)
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(FakeUpdateFailed, match="Power sensor"):
            _run(coord_module, coordinator)

    def test_only_spot_missing_raises(self, coord_module):
        """Bare spot mangler → UpdateFailed."""
        class FakeUpdateFailed(Exception):
            pass

        coord_module.UpdateFailed = FakeUpdateFailed

        hass = MagicMock()

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        with pytest.raises(FakeUpdateFailed, match="Spot price sensor"):
            _run(coord_module, coordinator)


# ===========================================================================
# Item 4: Power >500kW clamp + NaN/inf (commit 142bb3e)
# ===========================================================================


class TestPowerClamping:
    """coordinator.py:187-192 — clamp >500kW, filter NaN/inf."""

    def test_600kw_clamped_to_zero(self, coord_module):
        hass = _make_hass(power_w=600_000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_500kw_exactly_not_clamped(self, coord_module):
        hass = _make_hass(power_w=500_000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run(coord_module, coordinator)
        assert result["current_power_kw"] == 500.0

    def test_nan_power_becomes_zero(self, coord_module):
        hass = _make_hass(power_w="nan")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_inf_power_becomes_zero(self, coord_module):
        hass = _make_hass(power_w="inf")
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        result = _run(coord_module, coordinator)
        assert result["current_power_kw"] == 0

    def test_negative_power_no_accumulation(self, coord_module):
        """Negative power → no energy accumulation (power_kw < 0, guard: power_kw > 0)."""
        now = _real_datetime(2026, 6, 15, 12, 0)
        later = now.replace(minute=1)

        hass = _make_hass(power_w=-1000)
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        _run(coord_module, coordinator, now=now)
        result = _run(coord_module, coordinator, now=later)
        assert result["monthly_consumption_total_kwh"] == 0.0


# ===========================================================================
# Item 5: _save_stored_data OSError (commit cb8e9ec)
# ===========================================================================


class TestSaveOSError:
    """coordinator.py:579-581 — OSError fanger disk-feil."""

    def test_oserror_on_save_does_not_crash(self, coord_module):
        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock(side_effect=OSError("disk full"))
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())

        # Should not raise
        result = _run(coord_module, coordinator)
        assert result["spot_price"] == 1.20


# ===========================================================================
# Item 6: _load_stored_data corrupt data (commit cb8e9ec)
# ===========================================================================


class TestLoadCorruptData:
    """coordinator.py:523-524 — TypeError/KeyError/AttributeError fallback."""

    def test_corrupt_daily_max_power_type_error(self, coord_module):
        corrupt_data = {
            "daily_max_power": 42,  # Should be dict
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": "2026-06",
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=corrupt_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        # daily_max_power is validated by _validate_daily_max_power which returns {}
        # for non-dict input, so this should be empty
        assert coordinator._daily_max_power == {}

    def test_fully_garbled_storage_uses_defaults(self, coord_module):
        garbled = "not a dict at all"

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=garbled)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass()
        coordinator = coord_module.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        # Should use defaults without crashing
        assert coordinator._monthly_consumption == {"dag": 0.0, "natt": 0.0}


# ===========================================================================
# Item 7: MaanedligStromstotteSensor (null dekning)
# ===========================================================================


class TestMaanedligStromstotteSensor:
    """sensor.py:1364-1392 — total_kwh * stromstotte_per_kwh."""

    @pytest.fixture(autouse=True)
    def _setup_sensor_mocks(self):
        _sensor_mod = sys.modules["homeassistant.components.sensor"]
        _sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
            "MONETARY": "monetary", "POWER": "power", "ENERGY": "energy",
        })
        _sensor_mod.SensorEntity = type("SensorEntity", (), {})
        _sensor_mod.SensorStateClass = type("SensorStateClass", (), {
            "MEASUREMENT": "measurement", "TOTAL": "total",
            "TOTAL_INCREASING": "total_increasing",
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

    def _make_sensor(self, total_kwh, stromstotte):
        from stromkalkulator.sensor import MaanedligStromstotteSensor

        coordinator = MagicMock()
        coordinator.data = {
            "monthly_consumption_total_kwh": total_kwh,
            "stromstotte": stromstotte,
        }
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk"}
        return MaanedligStromstotteSensor(coordinator, entry)

    def test_normal_calculation(self):
        sensor = self._make_sensor(total_kwh=400.0, stromstotte=0.2138)
        assert sensor.native_value == pytest.approx(85.52)

    def test_zero_stromstotte(self):
        sensor = self._make_sensor(total_kwh=400.0, stromstotte=0)
        assert sensor.native_value == 0.0

    def test_zero_consumption(self):
        sensor = self._make_sensor(total_kwh=0.0, stromstotte=0.5)
        assert sensor.native_value == 0.0

    def test_none_data(self):
        from stromkalkulator.sensor import MaanedligStromstotteSensor

        coordinator = MagicMock()
        coordinator.data = None
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk"}
        sensor = MaanedligStromstotteSensor(coordinator, entry)
        assert sensor.native_value is None


# ===========================================================================
# Item 8: Barents Nett dict-format kapasitetstrinn i coordinator (commit 405f7ee)
# ===========================================================================


class TestBarentsNettDictFormat:
    """coordinator.py:106-110 — normalisering av dict-format til tupler."""

    def test_dict_format_normalized_to_tuples(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(dso_id="barents_nett", avgiftssone="tiltakssone")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # Should be normalized to tuples
        assert isinstance(coordinator.kapasitetstrinn, list)
        assert len(coordinator.kapasitetstrinn) > 0
        for item in coordinator.kapasitetstrinn:
            assert isinstance(item, tuple), f"Expected tuple, got {type(item)}: {item}"
            assert len(item) == 2

    def test_dict_format_runs_full_update(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(dso_id="barents_nett", avgiftssone="tiltakssone")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run(coord_module, coordinator)
        assert result["kapasitetsledd"] > 0


# ===========================================================================
# Item 9: get_default_avgiftssone (null dekning)
# ===========================================================================


class TestGetDefaultAvgiftssone:
    """const.py:179-190 — mapper prisområde til avgiftssone."""

    def test_no1_returns_standard(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO1") == "standard"

    def test_no2_returns_standard(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO2") == "standard"

    def test_no3_returns_nord_norge(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO3") == "nord_norge"

    def test_no4_returns_nord_norge(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO4") == "nord_norge"

    def test_no5_returns_standard(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO5") == "standard"

    def test_unknown_defaults_to_standard(self):
        from stromkalkulator.const import get_default_avgiftssone
        assert get_default_avgiftssone("NO99") == "standard"


# ===========================================================================
# Item 11: Nord-Norge avgiftssone i coordinator update
# ===========================================================================


class TestNordNorgeAvgiftssone:
    """Forbruksavgift uten MVA (nord_norge: full avgift, 0% mva)."""

    def test_nord_norge_forbruksavgift_no_mva(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(avgiftssone="nord_norge")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run(coord_module, coordinator)
        # forbruksavgift: 0.0713 * (1 + 0.0) = 0.0713 (no MVA)
        assert result["forbruksavgift_inkl_mva"] == round(0.0713, 4)
        # enova: 0.01 * (1 + 0.0) = 0.01 (no MVA)
        assert result["enova_inkl_mva"] == round(0.01, 4)
        # total avgifter: 0.0713 + 0.01 = 0.0813
        assert result["offentlige_avgifter"] == round(0.0813, 4)


# ===========================================================================
# Item 12: Electricity company price — bad values
# ===========================================================================


class TestElectricityCompanyPriceBadValues:
    """coordinator.py:349-367 — caching av strømleverandør-pris."""

    def test_unavailable_elco_price_uses_cache(self, coord_module):
        """Cache survives when sensor becomes unavailable."""
        hass = _make_hass(elco_price=0.85)
        entry = _make_entry(elco_sensor="sensor.elco")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        _run(coord_module, coordinator)  # cache 0.85

        # Now make sensor unavailable
        unavailable_state = MagicMock()
        unavailable_state.state = "unavailable"

        def get_state(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return unavailable_state
            return None

        hass.states.get = MagicMock(side_effect=get_state)

        result = _run(coord_module, coordinator)
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

        entry = _make_entry(elco_sensor="sensor.elco")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run(coord_module, coordinator)
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

        entry = _make_entry(elco_sensor="sensor.elco")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run(coord_module, coordinator)
        assert result["electricity_company_price"] is None


# ===========================================================================
# Item 13: 5000 kWh strømstøtte-tak boundary
# ===========================================================================


class TestStromstotteTakBoundary:
    """coordinator.py:270-275 — >= 5000 kWh grense."""

    def test_4999_9_kwh_still_gets_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = {"dag": 3000.0, "natt": 1999.9}

        result = _run(coord_module, coordinator)
        assert result["stromstotte"] > 0
        assert result["stromstotte_tak_naadd"] is False

    def test_5000_kwh_no_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = {"dag": 3000.0, "natt": 2000.0}

        result = _run(coord_module, coordinator)
        assert result["stromstotte"] == 0.0
        assert result["stromstotte_tak_naadd"] is True

    def test_5001_kwh_no_stromstotte(self, coord_module):
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = {"dag": 3000.0, "natt": 2001.0}

        result = _run(coord_module, coordinator)
        assert result["stromstotte"] == 0.0
        assert result["stromstotte_tak_naadd"] is True


# ===========================================================================
# Item 14: Negative verdier i validators
# ===========================================================================


class TestValidatorsNegativeValues:
    """coordinator.py:558-575 — negative verdier filtreres/clampes."""

    def test_validate_daily_max_power_skips_negative(self, coord_module):
        validate = coord_module.NettleieCoordinator._validate_daily_max_power
        result = validate({"2026-04-01": -5.0, "2026-04-02": 3.0})
        assert "2026-04-01" not in result
        assert result["2026-04-02"] == 3.0

    def test_validate_consumption_clamps_negative_to_zero(self, coord_module):
        validate = coord_module.NettleieCoordinator._validate_consumption
        result = validate({"dag": -100.0, "natt": 50.0})
        assert result["dag"] == 0.0
        assert result["natt"] == 50.0
