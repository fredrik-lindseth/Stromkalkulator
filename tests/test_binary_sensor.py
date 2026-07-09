"""Tester for binary_sensor-plattformen (kapasitetsvarsel).

conftest mocker ikke homeassistant.components.binary_sensor, så modulen settes
opp her (samme mønster som test_sensor_classes.py gjør for sensor-modulen).
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# --- Mock HA-moduler binary_sensor.py trenger ved import ---
_bs_mod = MagicMock()
_bs_mod.BinarySensorDeviceClass = type("BinarySensorDeviceClass", (), {"PROBLEM": "problem"})
_bs_mod.BinarySensorEntity = type("BinarySensorEntity", (), {})
sys.modules["homeassistant.components.binary_sensor"] = _bs_mod

# DeviceInfo som ekte dict, så device_info kan inspiseres (conftest mocker den).
sys.modules["homeassistant.helpers.entity"].DeviceInfo = dict

_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class FakeCoordinatorEntity:
    """Minimal CoordinatorEntity-stub."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = FakeCoordinatorEntity

from stromkalkulator.binary_sensor import (  # noqa: E402
    KapasitetVarselBinarySensor,
)


@pytest.fixture
def mock_entry():
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {"tso": "bkk", "avgiftssone": "standard"}
    return entry


def _coord(data):
    coordinator = MagicMock()
    coordinator.data = data
    return coordinator


class TestKapasitetVarselBinarySensor:
    def test_is_on_true_when_varsel_set(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({"kapasitet_varsel": True}), mock_entry)
        assert sensor.is_on is True

    def test_is_on_false_when_varsel_unset(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({"kapasitet_varsel": False}), mock_entry)
        assert sensor.is_on is False

    def test_is_on_false_when_key_missing(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({"margin_neste_trinn_kw": 3.0}), mock_entry)
        assert sensor.is_on is False

    def test_is_on_none_without_data(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord(None), mock_entry)
        assert sensor.is_on is None

    def test_device_class_is_problem(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_device_class == "problem"

    def test_translation_key_preserved(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_translation_key == "kapasitet_varsel"

    def test_unique_id_uses_entry_id_and_stable_suffix(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_unique_id == "test_entry_123_kapasitet_varsel"

    def test_margin_attribute_preserved(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(
            _coord({"kapasitet_varsel": True, "margin_neste_trinn_kw": 1.67}), mock_entry
        )
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["margin_kw"] == 1.67

    def test_attributes_none_without_data(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord(None), mock_entry)
        assert sensor.extra_state_attributes is None

    def test_device_info_shares_nettleie_device(self, mock_entry):
        sensor = KapasitetVarselBinarySensor(_coord({}), mock_entry)
        info = sensor.device_info
        assert (
            "stromkalkulator",
            "test_entry_123_stromkalkulator",
        ) in info["identifiers"]
