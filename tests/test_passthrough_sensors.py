"""Tests for ForbruksavgiftSensor and EnovaavgiftSensor.

P3 hull 9: These sensors have their own calculation logic (not just
coordinator passthrough) — they compute avgifter from const.py values
using _get_forbruksavgift() / _get_mva_sats() methods.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# ---- HA module mocks ----
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

from stromkalkulator.const import (  # noqa: E402
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
)
from stromkalkulator.sensor import (  # noqa: E402
    EnovaavgiftSensor,
    ForbruksavgiftSensor,
)


def _make_entry(avgiftssone: str = "standard") -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
    return entry


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = {}
    return coord


# ===========================================================================
# ForbruksavgiftSensor
# ===========================================================================


class TestForbruksavgiftSensor:
    """ForbruksavgiftSensor computes forbruksavgift inkl. mva."""

    @pytest.mark.parametrize(
        "avgiftssone,expected",
        [
            ("standard", round(FORBRUKSAVGIFT_ALMINNELIG * (1 + MVA_SATS), 4)),
            ("nord_norge", round(FORBRUKSAVGIFT_ALMINNELIG * 1.0, 4)),
            ("tiltakssone", 0.0),
        ],
    )
    def test_native_value(self, avgiftssone, expected):
        sensor = ForbruksavgiftSensor(_make_coordinator(), _make_entry(avgiftssone))
        assert sensor.native_value == expected

    def test_standard_value_matches_manual(self):
        """Standard: 0.0713 * 1.25 = 0.089125."""
        sensor = ForbruksavgiftSensor(_make_coordinator(), _make_entry("standard"))
        assert sensor.native_value == round(0.0713 * 1.25, 4)

    def test_tiltakssone_is_zero(self):
        """Tiltakssone: 0 forbruksavgift -> 0.0."""
        sensor = ForbruksavgiftSensor(_make_coordinator(), _make_entry("tiltakssone"))
        assert sensor.native_value == 0.0

    def test_extra_state_attributes_standard(self):
        sensor = ForbruksavgiftSensor(_make_coordinator(), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert attrs["eks_mva"] == FORBRUKSAVGIFT_ALMINNELIG
        assert attrs["inkl_mva"] == round(FORBRUKSAVGIFT_ALMINNELIG * 1.25, 4)
        assert attrs["mva_sats"] == "25%"
        assert attrs["avgiftssone"] == "standard"

    def test_extra_state_attributes_nord_norge(self):
        sensor = ForbruksavgiftSensor(_make_coordinator(), _make_entry("nord_norge"))
        attrs = sensor.extra_state_attributes
        assert attrs["mva_sats"] == "0%"
        assert attrs["inkl_mva"] == round(FORBRUKSAVGIFT_ALMINNELIG, 4)


# ===========================================================================
# EnovaavgiftSensor
# ===========================================================================


class TestEnovaavgiftSensor:
    """EnovaavgiftSensor computes Enova-avgift inkl. mva."""

    @pytest.mark.parametrize(
        "avgiftssone,expected",
        [
            ("standard", round(ENOVA_AVGIFT * (1 + MVA_SATS), 4)),
            ("nord_norge", round(ENOVA_AVGIFT * 1.0, 4)),
            ("tiltakssone", round(ENOVA_AVGIFT * 1.0, 4)),
        ],
    )
    def test_native_value(self, avgiftssone, expected):
        sensor = EnovaavgiftSensor(_make_coordinator(), _make_entry(avgiftssone))
        assert sensor.native_value == expected

    def test_standard_value_matches_manual(self):
        """Standard: 0.01 * 1.25 = 0.0125."""
        sensor = EnovaavgiftSensor(_make_coordinator(), _make_entry("standard"))
        assert sensor.native_value == 0.0125

    def test_enova_always_present(self):
        """Even tiltakssone pays Enova (just without mva)."""
        sensor = EnovaavgiftSensor(_make_coordinator(), _make_entry("tiltakssone"))
        assert sensor.native_value == ENOVA_AVGIFT  # 0.01

    def test_extra_state_attributes_standard(self):
        sensor = EnovaavgiftSensor(_make_coordinator(), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert attrs["eks_mva"] == ENOVA_AVGIFT
        assert attrs["inkl_mva"] == round(ENOVA_AVGIFT * 1.25, 4)
        assert attrs["mva_sats"] == "25%"
        assert attrs["ore_per_kwh_eks_mva"] == round(ENOVA_AVGIFT * 100, 2)

    def test_extra_state_attributes_tiltakssone(self):
        sensor = EnovaavgiftSensor(_make_coordinator(), _make_entry("tiltakssone"))
        attrs = sensor.extra_state_attributes
        assert attrs["mva_sats"] == "0%"
        assert attrs["inkl_mva"] == ENOVA_AVGIFT
