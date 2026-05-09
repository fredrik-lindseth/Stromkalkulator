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

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import _make_entry, _make_hass, _make_state, _run_update

_real_datetime = datetime


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

    def test_export_revenue_uses_spot_price_eks_mva(self, coord_module):
        """Plusskunder får betalt spotpris eks. mva, ikke inkl. mva.

        Privatperson som selger kraft tilbake til strømleverandøren får
        kraft-prisen uten mva (privat har ikke utgående mva). Se incident 004
        og accountant-funn #1: før denne fixen ble eksportinntekt overrapportert
        med 25 % i Sør-Norge.
        """
        spot_price_inkl_mva = 1.50
        export_w = 6000
        hass = _make_hass(
            power_w=5000, spot_price=spot_price_inkl_mva, export_power_w=export_w
        )
        # Test-fixture har spotpris_inkl_mva=True (1.50 brukes direkte som inkl-mva-pris)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        # 6 kW * (1/60) h = 0.1 kWh
        # Eks. mva: 1.50 / 1.25 = 1.20 NOK/kWh
        # Revenue: 1.20 * 0.1 = 0.12 kr
        expected_kwh = 6.0 * (1 / 60)
        expected_revenue = (spot_price_inkl_mva / 1.25) * expected_kwh
        assert abs(result["monthly_export_kwh"] - expected_kwh) < 0.001
        assert abs(result["monthly_export_revenue_kr"] - expected_revenue) < 0.01

    def test_export_revenue_eks_mva_for_eks_mva_sensor(self, coord_module):
        """For eks-mva-sensor brukes verdien direkte uten konvertering."""
        spot_price_eks_mva = 1.20
        export_w = 6000
        hass = _make_hass(
            power_w=5000, spot_price=spot_price_eks_mva, export_power_w=export_w
        )
        # Spotpris-sensor leverer eks. mva (HA-core nordpool)
        entry = _make_entry(
            export_power_sensor="sensor.export_power", spotpris_inkl_mva=False
        )
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        expected_revenue = spot_price_eks_mva * 6.0 * (1 / 60)
        assert abs(result["monthly_export_revenue_kr"] - expected_revenue) < 0.01

    def test_export_revenue_no_mva_in_nord_norge(self, coord_module):
        """Nord-Norge har 0 % mva, eks=inkl, ingen konvertering."""
        spot_price = 1.20
        export_w = 6000
        hass = _make_hass(
            power_w=5000, spot_price=spot_price, export_power_w=export_w
        )
        entry = _make_entry(
            export_power_sensor="sensor.export_power", avgiftssone="nord_norge"
        )
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        t1 = t0 + timedelta(minutes=1)

        _run_update(coord_module, coordinator, now=t0)
        result = _run_update(coord_module, coordinator, now=t1)

        # Mva = 0, eks = inkl, ingen konvertering
        expected_revenue = spot_price * 6.0 * (1 / 60)
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

        # Transition to July: siste syklus (t1->t2) akkumuleres i juni FØR rollover
        t2 = _real_datetime(2026, 7, 1, 0, 1)
        july_result = _run_update(coord_module, coordinator, now=t2)

        # previous_month inneholder juni inkl. siste syklus
        assert july_result["previous_month_export_kwh"] > june_export_kwh
        assert july_result["previous_month_export_revenue_kr"] > june_export_revenue
        assert july_result["previous_month_cost_kr"] > june_cost

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

        # Siste syklus (t4->t5) akkumuleres i juni FØR rollover.
        # previous_month inneholder juni inkl. siste syklus.
        assert july_result["previous_month_export_kwh"] > june_export
        # Etter rollover er juli nullstilt
        assert july_result["monthly_export_kwh"] == 0.0


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


# =============================================================================
# Eksport-sensor feilhåndtering
# =============================================================================


class TestExportSensorErrorHandling:
    """Test that bad export sensor values are handled gracefully."""

    def test_export_sensor_non_numeric_value(self, coord_module):
        """ValueError from non-numeric export sensor state should not crash."""
        hass = MagicMock()

        def get_state(entity_id):
            if entity_id == "sensor.power":
                return _make_state(5000)
            if entity_id == "sensor.spot_price":
                return _make_state(1.20)
            if entity_id == "sensor.export_power":
                return _make_state("not_a_number")
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        # First update sets _last_update
        _run_update(coord_module, coordinator)
        # Second update has elapsed_hours > 0, hitting the export code path
        now = _real_datetime(2026, 6, 15, 12, 5)
        result = _run_update(coord_module, coordinator, now=now)
        assert result["monthly_export_kwh"] == 0.0

    def test_export_sensor_infinity_value(self, coord_module):
        """Infinity export reading should be treated as 0."""
        hass = MagicMock()

        def get_state(entity_id):
            if entity_id == "sensor.power":
                return _make_state(5000)
            if entity_id == "sensor.spot_price":
                return _make_state(1.20)
            if entity_id == "sensor.export_power":
                return _make_state("inf")
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        _run_update(coord_module, coordinator)
        now = _real_datetime(2026, 6, 15, 12, 5)
        result = _run_update(coord_module, coordinator, now=now)
        assert result["monthly_export_kwh"] == 0.0

    def test_export_sensor_over_500kw_clamped(self, coord_module):
        """Export reading > 500 kW (500,000 W) should be clamped to 0."""
        hass = MagicMock()

        def get_state(entity_id):
            if entity_id == "sensor.power":
                return _make_state(5000)
            if entity_id == "sensor.spot_price":
                return _make_state(1.20)
            if entity_id == "sensor.export_power":
                return _make_state(600_000)
            return None

        hass.states.get = MagicMock(side_effect=get_state)
        entry = _make_entry(export_power_sensor="sensor.export_power")
        coordinator = coord_module.NettleieCoordinator(hass, entry)

        _run_update(coord_module, coordinator)
        now = _real_datetime(2026, 6, 15, 12, 5)
        result = _run_update(coord_module, coordinator, now=now)
        assert result["monthly_export_kwh"] == 0.0
