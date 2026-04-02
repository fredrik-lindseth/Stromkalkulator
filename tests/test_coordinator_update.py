"""End-to-end tests for NettleieCoordinator._async_update_data().

Tests the main calculation method with mocked HA state objects,
verifying correct values for day/night rates, strømstøtte,
Norgespris, electricity company price, energy accumulation,
and month transitions.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# Keep a reference to the real datetime class before any patching
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

    # Patch dt_util.now to return a real datetime
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
    electricity_company_price_sensor=None,
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
    if electricity_company_price_sensor:
        entry.data["electricity_provider_price_sensor"] = electricity_company_price_sensor
    return entry


def _make_hass(power_w=5000, spot_price=1.20, electricity_company_price=None):
    """Create a mock HA instance with sensor states."""
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        if entity_id == "sensor.elco_price" and electricity_company_price is not None:
            return _make_state(electricity_company_price)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _run_update(coord_module, coordinator, now=None):
    """Run _async_update_data with optional time override."""
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


class TestBasicUpdate:
    """Basic _async_update_data scenarios."""

    def test_returns_all_expected_keys(self, coord_module):
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)

        expected_keys = {
            "energiledd", "energiledd_dag", "energiledd_natt",
            "kapasitetsledd", "kapasitetstrinn_nummer", "kapasitetstrinn_intervall",
            "kapasitetsledd_per_kwh", "spot_price", "stromstotte",
            "spotpris_etter_stotte", "norgespris", "norgespris_stromstotte",
            "total_pris_norgespris", "kroner_spart_per_kwh",
            "total_price", "total_price_uten_stotte", "total_price_inkl_avgifter",
            "strompris_per_kwh", "strompris_per_kwh_etter_stotte",
            "forbruksavgift_inkl_mva", "enova_inkl_mva", "offentlige_avgifter",
            "electricity_company_price", "electricity_company_total",
            "current_power_kw", "avg_top_3_kw", "top_3_days",
            "is_day_rate", "dso", "har_norgespris", "avgiftssone",
            "monthly_consumption_dag_kwh", "monthly_consumption_natt_kwh",
            "monthly_consumption_total_kwh",
            "previous_month_consumption_dag_kwh", "previous_month_consumption_natt_kwh",
            "previous_month_consumption_total_kwh",
            "previous_month_top_3", "previous_month_avg_top_3_kw",
            "previous_month_name",
            "stromstotte_tak_naadd", "stromstotte_gjenstaaende_kwh",
            "margin_neste_trinn_kw", "neste_trinn_pris", "kapasitet_varsel",
            "monthly_norgespris_diff_kr", "previous_month_norgespris_diff_kr",
        }
        assert expected_keys.issubset(set(result.keys())), (
            f"Mangler nøkler: {expected_keys - set(result.keys())}"
        )

    def test_current_power_kw_converts_from_watts(self, coord_module):
        hass = _make_hass(power_w=7500)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 7.5

    def test_zero_power_when_sensor_unavailable(self, coord_module):
        hass = MagicMock()
        unavailable = MagicMock()
        unavailable.state = "unavailable"
        spot = _make_state(1.0)
        hass.states.get = MagicMock(side_effect=lambda eid: unavailable if "power" in eid else spot)

        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        result = _run_update(coord_module, coordinator)

        assert result["current_power_kw"] == 0

    def test_spot_price_passthrough(self, coord_module):
        hass = _make_hass(spot_price=1.50)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["spot_price"] == 1.50

    def test_dso_name_in_result(self, coord_module):
        hass = _make_hass()
        entry = _make_entry(dso_id="bkk")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["dso"] == "BKK"


class TestDayNightRate:
    """Day vs night rate selection."""

    def test_weekday_daytime_uses_day_rate(self, coord_module):
        """Weekday at 12:00 should use day rate (energiledd_dag)."""
        # 2026-04-09 is a Thursday, not a holiday
        day_noon = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=day_noon)

        assert result["is_day_rate"] is True
        assert result["energiledd"] == coordinator.energiledd_dag

    def test_weekend_uses_night_rate(self, coord_module):
        """Saturday should always use night rate."""
        saturday_noon = _real_datetime(2026, 4, 11, 12, 0)  # Saturday
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=saturday_noon)

        assert result["is_day_rate"] is False
        assert result["energiledd"] == coordinator.energiledd_natt

    def test_late_night_uses_night_rate(self, coord_module):
        """Weekday at 23:00 should use night rate."""
        late_night = _real_datetime(2026, 4, 9, 23, 0)  # Thursday 23:00
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=late_night)
        assert result["is_day_rate"] is False

    def test_early_morning_uses_night_rate(self, coord_module):
        """Weekday at 05:00 should use night rate."""
        early = _real_datetime(2026, 4, 9, 5, 0)  # Thursday 05:00
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=early)
        assert result["is_day_rate"] is False


class TestStromstotte:
    """Strømstøtte calculation in update loop."""

    def test_no_stromstotte_under_threshold(self, coord_module):
        """Spot price under threshold -> no strømstøtte."""
        hass = _make_hass(spot_price=0.50)  # Under threshold
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["stromstotte"] == 0.0

    def test_stromstotte_over_threshold(self, coord_module):
        """Spot price over threshold -> 90% of excess."""
        from stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE

        spot = 2.00
        hass = _make_hass(spot_price=spot)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        expected = round((spot - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result["stromstotte"] == expected

    def test_spotpris_etter_stotte(self, coord_module):
        """spotpris_etter_stotte = spot - strømstøtte."""
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["spotpris_etter_stotte"] == round(
            result["spot_price"] - result["stromstotte"], 4
        )

    def test_stromstotte_calculated_with_norgespris(self, coord_module):
        """Strømstøtte is always calculated from spot price, even with Norgespris.

        This enables comparison between Norgespris and spot+støtte.
        """
        from stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE

        hass = _make_hass(spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        expected = round((2.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result["stromstotte"] == expected

    def test_no_stromstotte_at_cap(self, coord_module):
        """When monthly consumption >= 5000 kWh, no strømstøtte."""
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        # Simulate having consumed >= 5000 kWh already
        coordinator._monthly_consumption = {"dag": 3000.0, "natt": 2500.0}

        result = _run_update(coord_module, coordinator)
        assert result["stromstotte"] == 0.0
        assert result["stromstotte_tak_naadd"] is True


class TestNorgespris:
    """Norgespris calculation in update loop."""

    def test_norgespris_active_total_price(self, coord_module):
        """With Norgespris, total_price uses norgespris instead of spot."""
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)

        assert result["har_norgespris"] is True
        # total_price should be norgespris + energiledd + fastledd
        assert result["total_price"] == result["total_price_uten_stotte"]
        # total_price should NOT include spot_price
        assert result["norgespris"] == 0.50  # Standard avgiftssone

    def test_norgespris_inactive_uses_spot(self, coord_module):
        """Without Norgespris, total_price uses spot price."""
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry(har_norgespris=False)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)

        assert result["har_norgespris"] is False
        # kroner_spart_per_kwh should be non-zero
        # (compares current price to norgespris)
        assert result["kroner_spart_per_kwh"] != 0.0

    def test_norgespris_kroner_spart_compares_to_spot(self, coord_module):
        """With Norgespris, kroner_spart compares to spot etter støtte."""
        from stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE

        hass = _make_hass(spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        # norgespris_total - spot_total_etter_stotte
        # With spot=2.00, strømstøtte is significant, so norgespris should be cheaper
        stromstotte = (2.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        spot_etter = 2.00 - stromstotte
        # kroner_spart = norgespris_total - spot_total_etter_stotte
        # = (norgespris + energiledd + fastledd) - (spot - støtte + energiledd + fastledd)
        # = norgespris - (spot - støtte)
        expected = round(result["norgespris"] - spot_etter, 4)
        assert result["kroner_spart_per_kwh"] == expected
        # With spot=2.00 and norgespris=0.50, norgespris is cheaper → negative value
        assert result["kroner_spart_per_kwh"] < 0

    def test_norgespris_nord_norge_avgiftssone(self, coord_module):
        """Nord-Norge gets lower norgespris (mva-fritak)."""
        hass = _make_hass(spot_price=1.00)
        entry = _make_entry(har_norgespris=True, avgiftssone="nord_norge")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["norgespris"] == 0.40  # 40 øre, no mva

    def test_norgespris_comparison_chain_regression(self, coord_module):
        """Regression: all comparison sensors must work with Norgespris.

        When har_norgespris=True, the user needs to compare their Norgespris
        total with what spot+støtte would cost. This requires:
        1. strømstøtte calculated from spot (not forced to 0)
        2. spotpris_etter_stotte = spot - strømstøtte (not raw spot)
        3. kroner_spart_per_kwh != 0 (actual comparison)
        4. total_price uses norgespris (not spot)
        """
        from stromkalkulator.const import STROMSTOTTE_LEVEL

        hass = _make_hass(spot_price=2.00)  # Well above strømstøtte threshold
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)

        # 1. Strømstøtte must be calculated (not 0)
        assert result["stromstotte"] > 0, "strømstøtte must be calculated for comparison"

        # 2. Spotpris etter støtte must be lower than raw spot
        assert result["spotpris_etter_stotte"] < result["spot_price"], (
            "spotpris_etter_stotte must deduct strømstøtte"
        )

        # 3. Comparison must be non-zero
        assert result["kroner_spart_per_kwh"] != 0.0, (
            "kroner_spart_per_kwh must compare norgespris vs spot+støtte"
        )

        # 4. Total price must use norgespris (not spot)
        assert result["spot_price"] > STROMSTOTTE_LEVEL  # sanity
        assert result["total_price"] < result["spot_price"], (
            "total_price should use norgespris (0.50), not spot (2.00)"
        )


class TestStromprisPerKwh:
    """strompris_per_kwh calculations."""

    def test_strompris_per_kwh_standard(self, coord_module):
        """Without Norgespris: strompris = spot + energiledd."""
        # 2026-04-09 is a Thursday, not a holiday
        day_noon = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(spot_price=1.50)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=day_noon)

        expected = round(1.50 + coordinator.energiledd_dag, 4)
        assert result["strompris_per_kwh"] == expected

    def test_strompris_per_kwh_etter_stotte(self, coord_module):
        """strompris_per_kwh_etter_stotte = spot - stromstotte + energiledd."""
        day_noon = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=day_noon)

        expected = round(2.00 - result["stromstotte"] + coordinator.energiledd_dag, 4)
        assert result["strompris_per_kwh_etter_stotte"] == expected

    def test_strompris_per_kwh_norgespris(self, coord_module):
        """With Norgespris: strompris = norgespris + energiledd."""
        day_noon = _real_datetime(2026, 4, 9, 12, 0)
        hass = _make_hass(spot_price=2.00)
        entry = _make_entry(har_norgespris=True)
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator, now=day_noon)

        expected = round(0.50 + coordinator.energiledd_dag, 4)
        assert result["strompris_per_kwh"] == expected


class TestElectricityCompanyPrice:
    """electricity_company_price sensor integration."""

    def test_no_sensor_configured(self, coord_module):
        hass = _make_hass()
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["electricity_company_price"] is None
        assert result["electricity_company_total"] is None

    def test_sensor_configured_with_value(self, coord_module):
        hass = _make_hass(electricity_company_price=0.85)
        entry = _make_entry(electricity_company_price_sensor="sensor.elco_price")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["electricity_company_price"] == 0.85
        assert result["electricity_company_total"] is not None
        # total = elco_price + energiledd + kapasitetsledd_per_kwh
        expected = round(0.85 + result["energiledd"] + result["kapasitetsledd_per_kwh"], 4)
        assert result["electricity_company_total"] == expected

    def test_cached_price_survives_api_outage(self, coord_module):
        """If sensor goes unavailable, last known price is used."""
        hass = _make_hass(electricity_company_price=0.85)
        entry = _make_entry(electricity_company_price_sensor="sensor.elco_price")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # First call: populate cache
        _run_update(coord_module, coordinator)

        # Now make sensor unavailable
        unavailable = MagicMock()
        unavailable.state = "unavailable"

        def get_state_unavailable(eid):
            if "power" in eid:
                return _make_state(5000)
            if "spot" in eid:
                return _make_state(1.20)
            if "elco" in eid:
                return unavailable
            return None

        hass.states.get = MagicMock(side_effect=get_state_unavailable)

        result = _run_update(coord_module, coordinator)
        # Should use cached price
        assert result["electricity_company_price"] == 0.85


class TestEnergyAccumulation:
    """Riemann sum energy consumption tracking."""

    def test_no_accumulation_on_first_call(self, coord_module):
        """First call should not accumulate energy (no previous timestamp)."""
        hass = _make_hass(power_w=10000)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["monthly_consumption_total_kwh"] == 0.0

    def test_accumulates_energy_on_second_call(self, coord_module):
        """Second call should accumulate energy based on elapsed time."""
        now = _real_datetime(2026, 4, 9, 12, 0)  # Thursday noon (not a holiday)
        later = now + timedelta(minutes=1)

        hass = _make_hass(power_w=6000)  # 6 kW
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=later)

        # 6 kW * (1 minute / 60 minutes) = 0.1 kWh
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert abs(total - 0.1) < 0.01

    def test_no_accumulation_at_zero_power(self, coord_module):
        """Zero power should not accumulate energy."""
        now = _real_datetime(2026, 4, 9, 12, 0)
        later = now + timedelta(minutes=10)

        hass = _make_hass(power_w=0)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        _run_update(coord_module, coordinator, now=now)
        result = _run_update(coord_module, coordinator, now=later)

        assert result["monthly_consumption_total_kwh"] == 0.0


class TestMonthTransition:
    """Month change behavior in update loop."""

    def test_month_change_resets_consumption(self, coord_module):
        """Changing month should reset current month data."""
        april_1 = _real_datetime(2026, 4, 1, 0, 1)

        hass = _make_hass(power_w=5000)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._current_month = "2026-03"  # March
        coordinator._monthly_consumption = {"dag": 500.0, "natt": 300.0}
        coordinator._daily_max_power = {"2026-03-01": 8.0, "2026-03-15": 10.0, "2026-03-20": 9.0}
        coordinator._monthly_norgespris_diff = 42.5

        result = _run_update(coord_module, coordinator, now=april_1)

        # Previous month data should be saved
        assert result["previous_month_consumption_dag_kwh"] == 500.0
        assert result["previous_month_consumption_natt_kwh"] == 300.0
        assert result["previous_month_name"] == "mars 2026"
        assert len(result["previous_month_top_3"]) == 3

        # Current month should be reset
        assert result["monthly_consumption_dag_kwh"] == 0.0
        assert result["monthly_consumption_natt_kwh"] == 0.0
        assert result["monthly_norgespris_diff_kr"] == 0.0

    def test_month_change_saves_top_3(self, coord_module):
        """Month change should preserve previous month top 3."""
        april_1 = _real_datetime(2026, 4, 1, 0, 1)

        hass = _make_hass(power_w=5000)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._current_month = "2026-03"
        coordinator._daily_max_power = {
            "2026-03-01": 8.0,
            "2026-03-10": 12.0,
            "2026-03-15": 10.0,
            "2026-03-20": 6.0,
        }

        result = _run_update(coord_module, coordinator, now=april_1)

        # Top 3 should be the 3 highest
        top_3 = result["previous_month_top_3"]
        assert len(top_3) == 3
        assert max(top_3.values()) == 12.0

    def test_no_reset_within_same_month(self, coord_module):
        """Update within the same month should not reset anything."""
        hass = _make_hass(power_w=5000)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)
        coordinator._monthly_consumption = {"dag": 100.0, "natt": 50.0}

        result = _run_update(coord_module, coordinator)
        # Consumption should not be reset, values >= what we set
        total = result["monthly_consumption_dag_kwh"] + result["monthly_consumption_natt_kwh"]
        assert total >= 150.0


class TestDailyMaxPower:
    """Daily max power tracking."""

    def test_updates_daily_max(self, coord_module):
        hass = _make_hass(power_w=10000)  # 10 kW
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["current_power_kw"] == 10.0
        assert len(result["top_3_days"]) == 1
        # The single day's max should be 10 kW
        assert next(iter(result["top_3_days"].values())) == 10.0

    def test_keeps_highest_value_per_day(self, coord_module):
        """Max power per day should only increase, never decrease."""
        hass = _make_hass(power_w=10000)
        entry = _make_entry()
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # First call: 10 kW
        _run_update(coord_module, coordinator)

        # Second call: lower power
        hass.states.get = MagicMock(
            side_effect=lambda eid: _make_state(3000) if "power" in eid else _make_state(1.0)
        )
        _run_update(coord_module, coordinator)

        # Max should still be 10 kW (use the fixture's fixed date)
        today = coord_module.dt_util.now.return_value.strftime("%Y-%m-%d")
        assert coordinator._daily_max_power.get(today) == 10.0


class TestOffentligeAvgifter:
    """Public fees calculation."""

    def test_standard_avgiftssone(self, coord_module):
        """Standard zone: forbruksavgift + enova, both with 25% mva."""
        hass = _make_hass()
        entry = _make_entry(avgiftssone="standard")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        # forbruksavgift: 0.0713 * 1.25 = 0.089125
        # enova: 0.01 * 1.25 = 0.0125
        # total: 0.101625 -> rounded to 0.1016
        assert result["forbruksavgift_inkl_mva"] == round(0.0713 * 1.25, 4)
        assert result["enova_inkl_mva"] == round(0.01 * 1.25, 4)

    def test_tiltakssone_no_avgifter(self, coord_module):
        """Tiltakssone: no forbruksavgift, no mva."""
        hass = _make_hass()
        entry = _make_entry(avgiftssone="tiltakssone")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        result = _run_update(coord_module, coordinator)
        assert result["forbruksavgift_inkl_mva"] == 0.0
        # Enova with no mva
        assert result["enova_inkl_mva"] == round(0.01, 4)
