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
    NorgesprisAktivBinarySensor,
    StromstotteAktivBinarySensor,
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


class TestNorgesprisAktivBinarySensor:
    """Norgespris-aktiv, tidligere tekst-sensor med «Ja»/«Nei» i sensor.py."""

    def test_is_on_true_when_har_norgespris(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({"har_norgespris": True}), mock_entry)
        assert sensor.is_on is True

    def test_is_on_false_when_not_norgespris(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({"har_norgespris": False}), mock_entry)
        assert sensor.is_on is False

    def test_is_on_false_when_key_missing(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({"spot_price": 1.0}), mock_entry)
        assert sensor.is_on is False

    def test_is_on_none_without_data(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord(None), mock_entry)
        assert sensor.is_on is None

    def test_no_device_class(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({}), mock_entry)
        assert getattr(sensor, "_attr_device_class", None) is None

    def test_entity_category_is_diagnostic(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_entity_category == "diagnostic"

    def test_translation_key(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_translation_key == "norgespris_aktiv"

    def test_unique_id_uses_entry_id_and_stable_suffix(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_unique_id == "test_entry_123_norgespris_aktiv"

    def test_device_info_norgespris_device(self, mock_entry):
        sensor = NorgesprisAktivBinarySensor(_coord({}), mock_entry)
        info = sensor.device_info
        assert ("stromkalkulator", "test_entry_123_norgespris") in info["identifiers"]
        assert info["name"] == "Norgespris"


class TestStromstotteAktivBinarySensor:
    """Strømstøtte-aktiv, tidligere tekst-sensor med spot-gating i sensor.py."""

    def test_is_on_true_when_stotte_positive(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(
            _coord({"stromstotte": 0.21, "spot_price_valid": True}), mock_entry
        )
        assert sensor.is_on is True

    def test_is_on_false_when_stotte_zero(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(
            _coord({"stromstotte": 0, "spot_price_valid": True}), mock_entry
        )
        assert sensor.is_on is False

    def test_is_on_none_when_spot_invalid(self, mock_entry):
        """Spot-gating: uten gyldig spot kan støtten ikke avgjøres -> None."""
        sensor = StromstotteAktivBinarySensor(
            _coord({"stromstotte": 0.21, "spot_price_valid": False}), mock_entry
        )
        assert sensor.is_on is None

    def test_is_on_true_when_flag_missing_defaults_valid(self, mock_entry):
        """Manglende spot_price_valid behandles som gyldig (bakoverkompat)."""
        sensor = StromstotteAktivBinarySensor(_coord({"stromstotte": 0.21}), mock_entry)
        assert sensor.is_on is True

    def test_is_on_none_without_data(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord(None), mock_entry)
        assert sensor.is_on is None

    def test_no_device_class(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord({}), mock_entry)
        assert getattr(sensor, "_attr_device_class", None) is None

    def test_entity_category_is_diagnostic(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_entity_category == "diagnostic"

    def test_translation_key(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_translation_key == "stromstotte_aktiv"

    def test_unique_id_uses_entry_id_and_stable_suffix(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord({}), mock_entry)
        assert sensor._attr_unique_id == "test_entry_123_stromstotte_aktiv"

    def test_device_info_stromstotte_device(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord({}), mock_entry)
        info = sensor.device_info
        assert ("stromkalkulator", "test_entry_123_stromstotte") in info["identifiers"]
        assert info["name"] == "Strømstøtte"

    def test_attributes_expose_terskel_and_note(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(
            _coord(
                {
                    "spot_price": 0.87,
                    "stromstotte": 0.09,
                    "stromstotte_terskel": 0.77,
                    "boligtype": "bolig",
                    "spot_price_valid": True,
                }
            ),
            mock_entry,
        )
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["terskel"] == 0.77
        assert attrs["over_terskel"] is True
        assert "77.00" in attrs["note"]

    def test_attributes_standard_terskel(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(
            _coord(
                {
                    "spot_price": 1.20,
                    "stromstotte": 0.21,
                    "stromstotte_terskel": 0.9625,
                    "boligtype": "bolig",
                    "spot_price_valid": True,
                }
            ),
            mock_entry,
        )
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert attrs["terskel"] == 0.9625
        assert "96.25" in attrs["note"]

    def test_attributes_none_without_data(self, mock_entry):
        sensor = StromstotteAktivBinarySensor(_coord(None), mock_entry)
        assert sensor.extra_state_attributes is None
