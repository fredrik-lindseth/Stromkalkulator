"""Tester for sonebevisst strømstøtte-terskel (incident 005).

Strømstøtte gis for spotpris over 77 øre/kWt EKS. mva. mva-kompensasjonen
(x1,25) legges kun på der mva faktisk betales. I mva-frie soner (nord_norge,
tiltakssonen) er terskelen derfor 77 øre, ikke 96,25 øre.

Før fiksen var terskelen flat 0,9625 for alle soner (const.STROMSTOTTE_LEVEL),
så nord-kunder mellom 77 og 96,25 øre fikk feilaktig null støtte. Se
docs/incidents/005-stromstotte-terskel-mva-sone.md.
"""

from __future__ import annotations

import asyncio
import sys
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry as _base_make_entry
from tests.conftest import _make_hass as _base_make_hass

# ---- HA module mocks for sensor-instansiering (samme mønster som test_sensor_classes) ----
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
_const_mod.EntityCategory = type("EntityCategory", (), {"DIAGNOSTIC": "diagnostic", "CONFIG": "config"})
_entity_mod = sys.modules["homeassistant.helpers.entity"]
_entity_mod.EntityCategory = _const_mod.EntityCategory
_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class _FakeCoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = _FakeCoordinatorEntity

from stromkalkulator.const import (  # noqa: E402
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    get_stromstotte_terskel,
)
from stromkalkulator.sensor import StromstotteSensor  # noqa: E402

# Terskler per sone (NOK/kWh, samme enhet som normalisert spotpris)
TERSKEL = {
    "standard": 0.9625,   # 77 øre * 1.25
    "nord_norge": 0.77,   # mva-fritak
    "tiltakssone": 0.77,  # mva-fritak
}


def _run(coord):
    return asyncio.run(coord._async_update_data())


def _coord_for(coord_module, avgiftssone: str, spot: float):
    """Coordinator med spotpris_inkl_mva=True (rå spot == spot inkl. mva) og power=0."""
    entry = _base_make_entry(
        entry_id="test_entry",
        dso_id="bkk",
        spotpris_inkl_mva=True,
        avgiftssone=avgiftssone,
        har_norgespris=False,
    )
    hass = _base_make_hass(power_w=0, spot_price=spot)
    coord = coord_module.NettleieCoordinator(hass, entry)
    coord._store_loaded = True
    return coord


class TestTerskelHelper:
    """get_stromstotte_terskel er sonebevisst og matcher STROMSTOTTE_LEVEL i standard."""

    def test_standard_er_96_25(self):
        assert get_stromstotte_terskel("standard") == pytest.approx(0.9625)

    def test_standard_matcher_stromstotte_level(self):
        assert get_stromstotte_terskel("standard") == pytest.approx(STROMSTOTTE_LEVEL)

    def test_nord_norge_er_77(self):
        assert get_stromstotte_terskel("nord_norge") == pytest.approx(0.77)

    def test_tiltakssone_er_77(self):
        assert get_stromstotte_terskel("tiltakssone") == pytest.approx(0.77)


class TestSonebevisstStotte:
    """Strømstøtte i coordinator bruker sonebevisst terskel rundt begge grensene."""

    @pytest.mark.parametrize(
        "avgiftssone,spot",
        [
            # standard rundt 96,25: støtte kun over 96,25
            ("standard", 0.96),
            ("standard", 1.0625),
            # standard i 77-96,25-båndet: INGEN støtte (kontrast mot nord)
            ("standard", 0.87),
            ("standard", 0.76),
            # nord_norge rundt 77
            ("nord_norge", 0.76),
            ("nord_norge", 0.87),   # regresjon: flat terskel ga 0 her
            # nord_norge videre opp mot/over 96,25 (lineær fra 77)
            ("nord_norge", 0.96),
            ("nord_norge", 1.07),
            # tiltakssone speiler nord
            ("tiltakssone", 0.76),
            ("tiltakssone", 0.87),  # regresjon
            ("tiltakssone", 0.96),
        ],
    )
    def test_stotte_rundt_grensene(self, coord_module, avgiftssone, spot):
        coord = _coord_for(coord_module, avgiftssone, spot)
        result = _run(coord)

        terskel = TERSKEL[avgiftssone]
        expected = round((spot - terskel) * STROMSTOTTE_RATE, 4) if spot > terskel else 0.0

        assert result["stromstotte_terskel"] == pytest.approx(terskel, abs=1e-9)
        assert result["stromstotte"] == pytest.approx(expected, abs=1e-9)

    @pytest.mark.parametrize("avgiftssone", ["nord_norge", "tiltakssone"])
    def test_mid_band_gir_positiv_stotte_i_nord(self, coord_module, avgiftssone):
        """Kjernen i buggen: spot 0,87 (mellom 77 og 96,25 øre) må gi støtte i nord."""
        coord = _coord_for(coord_module, avgiftssone, 0.87)
        result = _run(coord)
        assert result["stromstotte"] == pytest.approx(0.09, abs=1e-4)

    def test_standard_mid_band_gir_ingen_stotte(self, coord_module):
        """Samme spot i standard-sonen skal fortsatt gi null (under 96,25)."""
        coord = _coord_for(coord_module, "standard", 0.87)
        result = _run(coord)
        assert result["stromstotte"] == 0.0


class TestSensorTerskelAttributt:
    """Sensor-attributter viser sonebevisst terskel, ikke flat 0,9625."""

    def _coord_stub(self, terskel: float, spot: float):
        coord = MagicMock()
        coord.data = {
            "spot_price": spot,
            "stromstotte": max(0.0, (spot - terskel)) * STROMSTOTTE_RATE,
            "stromstotte_terskel": terskel,
            "stromstotte_tak_naadd": False,
            "boligtype": "bolig",
            "spot_price_valid": True,
        }
        return coord

    def _entry(self, avgiftssone: str):
        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
        return entry

    def test_stromstotte_sensor_bruker_sonebevisst_terskel(self):
        sensor = StromstotteSensor(self._coord_stub(0.77, 0.87), self._entry("nord_norge"))
        attrs = sensor.extra_state_attributes
        assert attrs["terskel"] == pytest.approx(0.77)

    # Strømstøtte-aktiv-attributtene (terskel/over_terskel/note) er flyttet til
    # binary_sensor; sonebevisst terskel dekkes av
    # tests/test_binary_sensor.py::TestStromstotteAktivBinarySensor.
