"""Tests for shared helper functions in sensor.py and coordinator.py."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

# Patch HA modules so sensor.py classes can be imported without a live HA instance.
# This must mirror what test_sensor_classes.py does to avoid metaclass conflicts.
_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorDeviceClass = type(
    "SensorDeviceClass",
    (),
    {
        "MONETARY": "monetary",
        "POWER": "power",
        "ENERGY": "energy",
    },
)
_sensor_mod.SensorEntity = type("SensorEntity", (), {})
_sensor_mod.SensorStateClass = type(
    "SensorStateClass",
    (),
    {
        "MEASUREMENT": "measurement",
        "TOTAL": "total",
        "TOTAL_INCREASING": "total_increasing",
    },
)

_const_mod = sys.modules["homeassistant.const"]
_const_mod.EntityCategory = type(
    "EntityCategory",
    (),
    {
        "DIAGNOSTIC": "diagnostic",
        "CONFIG": "config",
    },
)

_entity_mod = sys.modules["homeassistant.helpers.entity"]
_entity_mod.EntityCategory = _const_mod.EntityCategory

_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class _FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = _FakeCoordinatorEntity

from stromkalkulator.sensor import _bokfort_nettleie, _tall  # noqa: E402


class TestTall:
    """`_tall` skal gi et tall, også når coordinatoren ikke har feltet."""

    def test_leser_tallet(self):
        assert _tall({"a": 12.5}, "a") == 12.5

    def test_manglende_felt_er_null(self):
        assert _tall({}, "a") == 0.0

    def test_none_er_null(self):
        assert _tall({"a": None}, "a") == 0.0

    def test_tekst_er_null(self):
        assert _tall({"a": "mye"}, "a") == 0.0

    def test_bool_teller_ikke_som_tall(self):
        """True er 1 i Python. Et krone- eller kWh-felt som er bool er en feil."""
        assert _tall({"a": True}, "a") == 0.0

    def test_heltall_blir_flyttall(self):
        verdi = _tall({"a": 415}, "a")
        assert verdi == 415.0
        assert isinstance(verdi, float)


class TestBokfortNettleie:
    """Nettleien er energileddet pluss fastleddet slik boken førte dem."""

    def test_summerer_de_to_bokforte_leddene(self):
        data = {
            "monthly_accumulated_cost_energiledd_kr": 392.9573,
            "monthly_accumulated_cost_kapasitetsledd_kr": 249.9944,
        }
        assert _bokfort_nettleie(data) == pytest.approx(642.9517)

    def test_ingen_bokforing_er_null(self):
        assert _bokfort_nettleie({}) == 0.0

    def test_ganger_ikke_kilowattimer_med_satser(self):
        """Forbruk og satser i dicten skal ikke påvirke svaret."""
        data = {
            "monthly_accumulated_cost_energiledd_kr": 100.0,
            "monthly_accumulated_cost_kapasitetsledd_kr": 50.0,
            "monthly_consumption_dag_kwh": 900.0,
            "monthly_consumption_natt_kwh": 800.0,
            "energiledd_dag": 0.4613,
            "energiledd_natt": 0.2329,
            "kapasitetsledd": 415,
        }
        assert _bokfort_nettleie(data) == 150.0


class _FakeDataUpdateCoordinator:
    """Minimal stand-in for DataUpdateCoordinator used during coordinator import."""

    def __init_subclass__(cls, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, *, name, update_interval):
        self.hass = hass


@pytest.fixture(autouse=True)
def _patch_coordinator_base():
    """Ensure NettleieCoordinator inherits from a real class, not a MagicMock."""
    original = getattr(_coord_mod, "DataUpdateCoordinator", None)
    _coord_mod.DataUpdateCoordinator = _FakeDataUpdateCoordinator
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    yield coord.NettleieCoordinator
    _coord_mod.DataUpdateCoordinator = original


class TestEffektWatt:
    """Effektavlesningen, etter at adapteren tok over enhetene.

    `_read_sensor_float` er borte. Den returnerte 0.0 for alt som ikke var et
    tall, og en 0 er en måling som sier at anlegget ikke bruker noe. Nå er
    utfall None, og det er en annen påstand.
    """

    def _make_coordinator(self, cls, sensor_value, unit=None):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "tso": "bkk",
            "power_sensor": "sensor.power",
            "spot_price_sensor": "sensor.spot",
            "spotpris_inkl_mva": True,
        }
        entry.entry_id = "test_entry"
        state = MagicMock()
        state.state = sensor_value
        state.attributes = {"unit_of_measurement": unit} if unit else {}
        state.last_updated = None
        hass.states.get = MagicMock(return_value=state)
        return cls(hass, entry)

    def _make_coordinator_none(self, cls):
        hass = MagicMock()
        entry = MagicMock()
        entry.data = {
            "tso": "bkk",
            "power_sensor": "sensor.power",
            "spot_price_sensor": "sensor.spot",
            "spotpris_inkl_mva": True,
        }
        entry.entry_id = "test_entry"
        hass.states.get = MagicMock(return_value=None)
        return cls(hass, entry)

    def _les(self, coord, rolle="effekt"):
        coord._les_inputer(datetime(2026, 6, 15, 12, 0))
        return coord._effekt_watt(rolle)

    def test_normal_value(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "5000")
        assert self._les(coord) == 5000.0

    def test_kilowatt_normaliseres_til_watt(self, _patch_coordinator_base):
        """Funnet som ga tusen ganger for lite: en kW-sensor ble lest som W."""
        coord = self._make_coordinator(_patch_coordinator_base, "5", unit="kW")
        assert self._les(coord) == 5000.0

    def test_unavailable(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "unavailable")
        assert self._les(coord) is None

    def test_unknown(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "unknown")
        assert self._les(coord) is None

    def test_none_state(self, _patch_coordinator_base):
        coord = self._make_coordinator_none(_patch_coordinator_base)
        assert self._les(coord) is None

    def test_non_numeric(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "abc")
        assert self._les(coord) is None

    def test_nan(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "nan")
        assert self._les(coord) is None

    def test_inf(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "inf")
        assert self._les(coord) is None

    def test_over_500kw_avvises(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "600000")
        assert self._les(coord) is None

    def test_negative(self, _patch_coordinator_base):
        # Negativ effekt klippes til 0: power_sensor er unidireksjonell import,
        # negative verdier er sensorstøy eller feilkonfig og skal ikke telle.
        coord = self._make_coordinator(_patch_coordinator_base, "-100")
        assert self._les(coord) == 0.0

    def test_rolle_uten_entitet(self, _patch_coordinator_base):
        coord = self._make_coordinator(_patch_coordinator_base, "5000")
        assert self._les(coord, rolle="eksport") is None
