"""Tests for monthly sensor calculation logic.

P1 hull 1-4: Tests the native_value computation in
MaanedligNettleieSensor, MaanedligAvgifterSensor, MaanedligTotalSensor,
and ForrigeMaanedNettleieSensor, which all contain their own arithmetic
rather than just forwarding a coordinator key.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---- HA module mocks (must match conftest / test_sensor_classes) ----
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
    """Minimal CoordinatorEntity stub."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = FakeCoordinatorEntity

from stromkalkulator.const import (  # noqa: E402
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
)
from stromkalkulator.sensor import (  # noqa: E402
    DagskostnadSensor,
    ForrigeMaanedNettleieSensor,
    MaanedligAvgifterSensor,
    MaanedligForbrukTotalSensor,
    MaanedligNettleieSensor,
    MaanedligTotalSensor,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BKK_KAPASITETSTRINN = [
    (2, 155), (5, 250), (10, 415), (15, 600), (20, 770),
    (25, 940), (50, 1800), (75, 2650), (100, 3500), (float("inf"), 6900),
]


def _make_coordinator(data: dict) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.kapasitetstrinn = BKK_KAPASITETSTRINN
    return coord


def _make_entry(avgiftssone: str = "standard") -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
    return entry


# ---------------------------------------------------------------------------
# P1.1 — MaanedligNettleieSensor
# ---------------------------------------------------------------------------


class TestMaanedligNettleieSensor:
    """Beregner: dag_kwh * dag_pris + natt_kwh * natt_pris + kapasitet."""

    def test_normal_values(self):
        """200 kWh dag, 100 kWh natt, BKK-priser, trinn 3 (415 kr)."""
        data = {
            "monthly_consumption_dag_kwh": 200.0,
            "monthly_consumption_natt_kwh": 100.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
        }
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(200.0 * 0.4613 + 100.0 * 0.2329 + 415, 2)
        assert sensor.native_value == expected

    def test_zero_consumption(self):
        """0 kWh forbruk — should only return kapasitetsledd."""
        data = {
            "monthly_consumption_dag_kwh": 0,
            "monthly_consumption_natt_kwh": 0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
        }
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == 415.0

    def test_manual_calculation_matches(self):
        """Verify arithmetic with known input/output."""
        dag_kwh, natt_kwh = 350.0, 180.0
        dag_pris, natt_pris = 0.4613, 0.2329
        kapasitet = 600
        data = {
            "monthly_consumption_dag_kwh": dag_kwh,
            "monthly_consumption_natt_kwh": natt_kwh,
            "energiledd_dag": dag_pris,
            "energiledd_natt": natt_pris,
            "kapasitetsledd": kapasitet,
        }
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        manual = round(dag_kwh * dag_pris + natt_kwh * natt_pris + kapasitet, 2)
        assert sensor.native_value == manual

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligNettleieSensor(coord, _make_entry())
        assert sensor.native_value is None

    def test_extra_state_attributes_breakdown(self):
        """Attributes should expose dag/natt/kapasitet breakdown."""
        data = {
            "monthly_consumption_dag_kwh": 200.0,
            "monthly_consumption_natt_kwh": 100.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
        }
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["energiledd_dag_kr"] == round(200.0 * 0.4613, 2)
        assert attrs["energiledd_natt_kr"] == round(100.0 * 0.2329, 2)
        assert attrs["kapasitetsledd_kr"] == 415


# ---------------------------------------------------------------------------
# P1.2 — MaanedligAvgifterSensor
# ---------------------------------------------------------------------------


class TestMaanedligAvgifterSensor:
    """Beregner: total_kwh * (forbruksavgift_inkl + enova_inkl)."""

    def test_standard_avgiftssone(self):
        """Standard: full forbruksavgift + 25% mva."""
        total_kwh = 400.0
        data = {"monthly_consumption_total_kwh": total_kwh}
        sensor = MaanedligAvgifterSensor(
            _make_coordinator(data), _make_entry("standard")
        )
        forbruksavgift_inkl = FORBRUKSAVGIFT_ALMINNELIG * 1.25
        enova_inkl = ENOVA_AVGIFT * 1.25
        expected = round(total_kwh * (forbruksavgift_inkl + enova_inkl), 2)
        assert sensor.native_value == expected

    def test_nord_norge_avgiftssone(self):
        """Nord-Norge: same forbruksavgift as standard from 2026, but 0% mva."""
        total_kwh = 400.0
        data = {"monthly_consumption_total_kwh": total_kwh}
        sensor = MaanedligAvgifterSensor(
            _make_coordinator(data), _make_entry("nord_norge")
        )
        # No mva
        forbruksavgift_inkl = FORBRUKSAVGIFT_ALMINNELIG  # * 1.0
        enova_inkl = ENOVA_AVGIFT  # * 1.0
        expected = round(total_kwh * (forbruksavgift_inkl + enova_inkl), 2)
        assert sensor.native_value == expected

    def test_tiltakssone_avgiftssone(self):
        """Tiltakssone: 0 forbruksavgift, 0% mva, only Enova."""
        total_kwh = 400.0
        data = {"monthly_consumption_total_kwh": total_kwh}
        sensor = MaanedligAvgifterSensor(
            _make_coordinator(data), _make_entry("tiltakssone")
        )
        # forbruksavgift = 0, mva = 0%, only enova
        expected = round(total_kwh * ENOVA_AVGIFT, 2)
        assert sensor.native_value == expected

    def test_zero_consumption(self):
        """0 kWh -> 0 kr avgifter."""
        data = {"monthly_consumption_total_kwh": 0}
        sensor = MaanedligAvgifterSensor(
            _make_coordinator(data), _make_entry("standard")
        )
        assert sensor.native_value == 0.0

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligAvgifterSensor(coord, _make_entry())
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# P1.3 — MaanedligTotalSensor
# ---------------------------------------------------------------------------


class TestMaanedligTotalSensor:
    """Beregner: nettleie + avgifter - strømstøtte."""

    @pytest.fixture
    def base_data(self):
        return {
            "monthly_consumption_dag_kwh": 200.0,
            "monthly_consumption_natt_kwh": 100.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
            "stromstotte": 0.0,
        }

    def _expected_total(self, data, avgiftssone="standard"):
        """Calculate expected total from raw data using the same formula."""
        dag_kwh = data["monthly_consumption_dag_kwh"]
        natt_kwh = data["monthly_consumption_natt_kwh"]
        total_kwh = dag_kwh + natt_kwh
        nettleie = (
            dag_kwh * data["energiledd_dag"]
            + natt_kwh * data["energiledd_natt"]
            + data["kapasitetsledd"]
        )
        from datetime import datetime

        from stromkalkulator.const import get_forbruksavgift, get_mva_sats

        forbruksavgift = get_forbruksavgift(avgiftssone, datetime.now().month)
        mva = get_mva_sats(avgiftssone)
        avgifter = total_kwh * ((forbruksavgift + ENOVA_AVGIFT) * (1 + mva))
        stotte = total_kwh * data["stromstotte"]
        return round(nettleie + avgifter - stotte, 2)

    def test_standard_no_stromstotte(self, base_data):
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("standard")
        )
        expected = self._expected_total(base_data, "standard")
        assert sensor.native_value == expected

    def test_nord_norge_no_stromstotte(self, base_data):
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("nord_norge")
        )
        expected = self._expected_total(base_data, "nord_norge")
        assert sensor.native_value == expected

    def test_tiltakssone_no_stromstotte(self, base_data):
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("tiltakssone")
        )
        expected = self._expected_total(base_data, "tiltakssone")
        assert sensor.native_value == expected

    def test_with_stromstotte(self, base_data):
        """When strømstøtte > 0, total should decrease."""
        base_data["stromstotte"] = 0.50
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("standard")
        )
        expected = self._expected_total(base_data, "standard")
        assert sensor.native_value == expected
        # Sanity: with stromstotte the total should be lower
        base_data_no_stotte = {**base_data, "stromstotte": 0.0}
        total_without = self._expected_total(base_data_no_stotte, "standard")
        assert sensor.native_value < total_without

    def test_total_equals_nettleie_plus_avgifter_minus_stotte(self, base_data):
        """Verify the decomposition: total = nettleie + avgifter - strømstøtte."""
        base_data["stromstotte"] = 0.30
        # MaanedligTotalSensor uses dag+natt as total_kwh,
        # MaanedligAvgifterSensor uses monthly_consumption_total_kwh.
        # Set them consistently.
        dag_kwh = base_data["monthly_consumption_dag_kwh"]
        natt_kwh = base_data["monthly_consumption_natt_kwh"]
        base_data["monthly_consumption_total_kwh"] = dag_kwh + natt_kwh

        avgiftssone = "standard"
        coord = _make_coordinator(base_data)
        entry = _make_entry(avgiftssone)

        total_sensor = MaanedligTotalSensor(coord, entry)
        nettleie_sensor = MaanedligNettleieSensor(coord, entry)
        avgifter_sensor = MaanedligAvgifterSensor(coord, entry)

        total_kwh = dag_kwh + natt_kwh
        stotte_kr = round(total_kwh * base_data["stromstotte"], 2)

        # total ≈ nettleie + avgifter - strømstøtte
        manual = round(nettleie_sensor.native_value + avgifter_sensor.native_value - stotte_kr, 2)
        assert abs(total_sensor.native_value - manual) < 0.02

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligTotalSensor(coord, _make_entry())
        assert sensor.native_value is None

    def test_extra_state_attributes(self, base_data):
        """Attributes should contain nettleie, avgifter, strømstøtte breakdown."""
        base_data["stromstotte"] = 0.20
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("standard")
        )
        attrs = sensor.extra_state_attributes
        assert "nettleie_kr" in attrs
        assert "avgifter_kr" in attrs
        assert "stromstotte_kr" in attrs
        assert "forbruk_total_kwh" in attrs

    def test_vektet_snittpris_with_consumption(self, base_data):
        """vektet_snittpris_kr_per_kwh == native_value / total_kwh for known consumption."""
        base_data["monthly_consumption_dag_kwh"] = 500.0
        base_data["monthly_consumption_natt_kwh"] = 200.0
        base_data["stromstotte"] = 0.10
        sensor = MaanedligTotalSensor(
            _make_coordinator(base_data), _make_entry("standard")
        )
        total_kwh = 500.0 + 200.0
        expected = round(sensor.native_value / total_kwh, 4)
        attrs = sensor.extra_state_attributes
        assert attrs["vektet_snittpris_kr_per_kwh"] == expected

    def test_vektet_snittpris_zero_consumption(self):
        """vektet_snittpris_kr_per_kwh is None when total_kwh == 0."""
        data = {
            "monthly_consumption_dag_kwh": 0.0,
            "monthly_consumption_natt_kwh": 0.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
            "stromstotte": 0.0,
        }
        sensor = MaanedligTotalSensor(
            _make_coordinator(data), _make_entry("standard")
        )
        attrs = sensor.extra_state_attributes
        assert attrs["vektet_snittpris_kr_per_kwh"] is None


# ---------------------------------------------------------------------------
# P1.4 — ForrigeMaanedNettleieSensor (med _get_kapasitetsledd_for_avg)
# ---------------------------------------------------------------------------


class TestForrigeMaanedNettleieSensor:
    """Beregner nettleie for forrige måned med eget kapasitetstrinn-oppslag."""

    def test_with_normal_top_3(self):
        """Normal topp-3 => avg 10 kW => BKK trinn 3 (415 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 300.0,
            "previous_month_consumption_natt_kwh": 200.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "previous_month_top_3": {
                "2026-03-01": 12.0,
                "2026-03-10": 10.0,
                "2026-03-20": 8.0,
            },
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        # avg = (12+10+8)/3 = 10.0 => trinn (10, 415)
        expected = round(300.0 * 0.4613 + 200.0 * 0.2329 + 415, 2)
        assert sensor.native_value == expected

    def test_empty_top_3(self):
        """Tom topp-3 => kapasitet = 0."""
        data = {
            "previous_month_consumption_dag_kwh": 300.0,
            "previous_month_consumption_natt_kwh": 200.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "previous_month_top_3": {},
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(300.0 * 0.4613 + 200.0 * 0.2329, 2)
        assert sensor.native_value == expected

    def test_high_power_top_tier(self):
        """Very high average -> highest tier (6900 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 500.0,
            "previous_month_consumption_natt_kwh": 300.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "previous_month_top_3": {
                "2026-03-01": 120.0,
                "2026-03-10": 130.0,
                "2026-03-20": 150.0,
            },
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        # avg = (120+130+150)/3 ≈ 133.3 => exceeds 100 threshold => 6900
        expected = round(500.0 * 0.4613 + 300.0 * 0.2329 + 6900, 2)
        assert sensor.native_value == expected

    def test_low_power_first_tier(self):
        """Very low average -> first tier (155 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 50.0,
            "previous_month_consumption_natt_kwh": 30.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "previous_month_top_3": {
                "2026-03-01": 1.5,
                "2026-03-10": 1.8,
                "2026-03-20": 1.2,
            },
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        # avg = (1.5+1.8+1.2)/3 = 1.5 => <= 2 threshold => 155
        expected = round(50.0 * 0.4613 + 30.0 * 0.2329 + 155, 2)
        assert sensor.native_value == expected

    @pytest.mark.parametrize(
        "avg_power,expected_kapasitet",
        [
            (1.5, 155),    # trinn 1: <= 2 kW
            (2.0, 155),    # exactly at boundary
            (4.0, 250),    # trinn 2: <= 5 kW
            (10.0, 415),   # trinn 3: <= 10 kW
            (15.0, 600),   # trinn 4: <= 15 kW
            (20.0, 770),   # trinn 5: <= 20 kW
            (25.0, 940),   # trinn 6: <= 25 kW
            (50.0, 1800),  # trinn 7: <= 50 kW
            (75.0, 2650),  # trinn 8: <= 75 kW
            (100.0, 3500), # trinn 9: <= 100 kW
            (150.0, 6900), # trinn 10: > 100 kW (inf)
        ],
    )
    def test_kapasitetsledd_for_avg_tiers(self, avg_power, expected_kapasitet):
        """Verify _get_kapasitetsledd_for_avg selects correct tier."""
        # Use a single entry in top_3 so avg = that value
        data = {
            "previous_month_consumption_dag_kwh": 0.0,
            "previous_month_consumption_natt_kwh": 0.0,
            "energiledd_dag": 0.0,
            "energiledd_natt": 0.0,
            "previous_month_top_3": {"2026-03-01": avg_power},
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == float(expected_kapasitet)

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        coord.kapasitetstrinn = BKK_KAPASITETSTRINN
        sensor = ForrigeMaanedNettleieSensor(coord, _make_entry())
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# MaanedligForbrukTotalSensor — dag/natt-fordeling (%)
# ---------------------------------------------------------------------------


class TestDagNattFordeling:
    """Tester for dag_pct og natt_pct attributter på MaanedligForbrukTotalSensor."""

    def test_dag_natt_fordeling_normal(self):
        """750 dag / 250 natt = 75.0% / 25.0%."""
        data = {
            "monthly_consumption_dag_kwh": 750.0,
            "monthly_consumption_natt_kwh": 250.0,
            "monthly_consumption_total_kwh": 1000.0,
        }
        sensor = MaanedligForbrukTotalSensor(_make_coordinator(data), _make_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["dag_pct"] == 75.0
        assert attrs["natt_pct"] == 25.0

    def test_dag_natt_fordeling_zero_consumption(self):
        """0/0 forbruk => 0.0% / 0.0%, ingen division by zero."""
        data = {
            "monthly_consumption_dag_kwh": 0.0,
            "monthly_consumption_natt_kwh": 0.0,
            "monthly_consumption_total_kwh": 0.0,
        }
        sensor = MaanedligForbrukTotalSensor(_make_coordinator(data), _make_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["dag_pct"] == 0.0
        assert attrs["natt_pct"] == 0.0


# ---------------------------------------------------------------------------
# DagskostnadSensor
# ---------------------------------------------------------------------------


class TestDagskostnadSensor:
    """Tester for DagskostnadSensor som leser daily_cost_kr fra coordinator."""

    def test_dagskostnad_sensor(self):
        """Normal verdi fra coordinator.data."""
        data = {"daily_cost_kr": 42.50}
        sensor = DagskostnadSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == 42.50
        assert sensor._attr_native_unit_of_measurement == "kr"

    def test_dagskostnad_sensor_none_when_no_data(self):
        """Returnerer None når coordinator.data er None."""
        coord = MagicMock()
        coord.data = None
        sensor = DagskostnadSensor(coord, _make_entry())
        assert sensor.native_value is None

    def test_dagskostnad_sensor_none_when_key_missing(self):
        """Returnerer None når daily_cost_kr ikke finnes i data."""
        data = {}
        sensor = DagskostnadSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value is None
