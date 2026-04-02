"""Tests for OffentligeAvgifterSensor calculation logic.

P1 hull 5: The sensor calculates avgifter independently using its own
_get_forbruksavgift() and _get_mva_sats() methods, then combines them
in native_value.  We verify that all three avgiftssoner produce the
correct result consistent with const.py values.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

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
from stromkalkulator.sensor import OffentligeAvgifterSensor  # noqa: E402


def _make_entry(avgiftssone: str = "standard") -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
    return entry


def _make_coordinator() -> MagicMock:
    coord = MagicMock()
    coord.data = {}
    return coord


class TestOffentligeAvgifterSensor:
    """OffentligeAvgifterSensor calculates avgifter independently."""

    def test_standard_avgiftssone(self):
        """Standard: forbruksavgift + enova, both with 25% mva."""
        sensor = OffentligeAvgifterSensor(_make_coordinator(), _make_entry("standard"))
        total_eks = FORBRUKSAVGIFT_ALMINNELIG + ENOVA_AVGIFT
        expected = round(total_eks * (1 + MVA_SATS), 2)
        assert sensor.native_value == expected

    def test_nord_norge_avgiftssone(self):
        """Nord-Norge: same forbruksavgift from 2026, but 0% mva."""
        sensor = OffentligeAvgifterSensor(_make_coordinator(), _make_entry("nord_norge"))
        total_eks = FORBRUKSAVGIFT_ALMINNELIG + ENOVA_AVGIFT
        expected = round(total_eks * 1.0, 2)  # 0% mva
        assert sensor.native_value == expected

    def test_tiltakssone_avgiftssone(self):
        """Tiltakssone: 0 forbruksavgift, 0% mva, only Enova."""
        sensor = OffentligeAvgifterSensor(_make_coordinator(), _make_entry("tiltakssone"))
        expected = round(ENOVA_AVGIFT * 1.0, 2)
        assert sensor.native_value == expected

    def test_extra_state_attributes_structure(self):
        """Attributes should contain all fee components."""
        sensor = OffentligeAvgifterSensor(_make_coordinator(), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert "avgiftssone" in attrs
        assert "forbruksavgift_eks_mva" in attrs
        assert "forbruksavgift_inkl_mva" in attrs
        assert "enova_avgift_eks_mva" in attrs
        assert "enova_avgift_inkl_mva" in attrs
        assert "mva_sats" in attrs

    def test_attributes_mva_string_format(self):
        """MVA should be formatted as percentage string."""
        sensor = OffentligeAvgifterSensor(_make_coordinator(), _make_entry("standard"))
        assert sensor.extra_state_attributes["mva_sats"] == "25%"

        sensor_nord = OffentligeAvgifterSensor(
            _make_coordinator(), _make_entry("nord_norge")
        )
        assert sensor_nord.extra_state_attributes["mva_sats"] == "0%"
