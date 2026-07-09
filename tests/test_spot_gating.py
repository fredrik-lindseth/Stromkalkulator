"""Tester for gating av spot-avhengige pris-sensorer (incident 004-etterspill / 65r3).

Ved kaldstart eller spot-bortfall utover cache-vinduet settes spot til 0,0 og
spot_price_valid=False. Spot-avhengige pris-sensorer skal da returnere None
(unavailable) i stedet for å publisere 0-baserte priser til recorderen.
Energiledd, kapasitet og Norgespris-under-tak er spot-uavhengige og skal
fortsatt være tilgjengelige.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_entry as _base_make_entry
from tests.conftest import _make_hass as _base_make_hass

# ---- HA module mocks for sensor-instansiering ----
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

from stromkalkulator.sensor import (  # noqa: E402
    ElectricityCompanyTotalSensor,
    EnergileddSensor,
    KapasitetstrinnSensor,
    PrisforskjellNorgesprisSensor,
    SpotprisEtterStotteSensor,
    StromprisNorgesprisSensor,
    StromprisPerKwhEtterStotteSensor,
    StromprisPerKwhSensor,
    StromstotteAktivSensor,
    StromstotteGjenstaaendeSensor,
    StromstotteSensor,
    TotalPriceSensor,
    TotalPrisEtterStotteSensor,
    TotalPrisInklAvgifterSensor,
    TotalPrisNorgesprisSensor,
)


def _data(spot_valid=True, har_norgespris=False, over_tak=False):
    return {
        "total_price": 1.5,
        "total_price_uten_stotte": 1.7,
        "total_price_inkl_avgifter": 1.8,
        "spot_price": 1.2,
        "stromstotte": 0.2,
        "spotpris_etter_stotte": 1.0,
        "strompris_per_kwh": 1.6,
        "strompris_per_kwh_etter_stotte": 1.4,
        "kroner_spart_per_kwh": 0.3,
        "norgespris": 0.5,
        "strompris_norgespris": 0.5,
        "total_pris_norgespris": 1.0,
        "energiledd": 0.46,
        "energiledd_dag": 0.46,
        "energiledd_natt": 0.23,
        "kapasitetsledd": 415,
        "kapasitetstrinn_nummer": 3,
        "kapasitetstrinn_intervall": "5-10 kW",
        "kapasitetsledd_per_kwh": 0.05,
        "avg_top_3_kw": 8.0,
        "current_power_kw": 7.0,
        "top_3_days": {},
        "stromstotte_gjenstaaende_kwh": 4600.0,
        "electricity_company_total": 1.36,
        "electricity_company_price": 0.85,
        "stromstotte_terskel": 0.9625,
        "stromstotte_tak_naadd": False,
        "boligtype": "bolig",
        "monthly_consumption_total_kwh": 100.0,
        "dso": "BKK",
        "is_day_rate": True,
        "har_norgespris": har_norgespris,
        "norgespris_over_tak": over_tak,
        "spot_price_valid": spot_valid,
    }


def _coord(data):
    coord = MagicMock()
    coord.data = data
    return coord


def _entry():
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "standard"}
    return entry


# Sensorer som alltid er spot-avhengige (uansett prismodus)
ALLTID_SPOT = [
    TotalPriceSensor,
    SpotprisEtterStotteSensor,
    StromstotteSensor,
    PrisforskjellNorgesprisSensor,
]


class TestSensorGating:
    """Spot-avhengige pris-sensorer returnerer None når spot_price_valid=False."""

    @pytest.mark.parametrize("sensor_cls", ALLTID_SPOT)
    def test_alltid_spot_none_ved_ugyldig(self, sensor_cls):
        sensor = sensor_cls(_coord(_data(spot_valid=False)), _entry())
        assert sensor.native_value is None

    @pytest.mark.parametrize("sensor_cls", ALLTID_SPOT)
    def test_alltid_spot_verdi_ved_gyldig(self, sensor_cls):
        sensor = sensor_cls(_coord(_data(spot_valid=True)), _entry())
        assert sensor.native_value is not None

    def test_stromstotte_aktiv_none_ved_ugyldig(self):
        sensor = StromstotteAktivSensor(_coord(_data(spot_valid=False)), _entry())
        assert sensor.native_value is None

    @pytest.mark.parametrize(
        "sensor_cls",
        [
            StromprisPerKwhSensor,
            TotalPrisEtterStotteSensor,
            TotalPrisInklAvgifterSensor,
            StromprisPerKwhEtterStotteSensor,
        ],
    )
    def test_betinget_spot_none_uten_norgespris(self, sensor_cls):
        """Uten Norgespris er disse spot-avhengige -> None ved ugyldig spot."""
        sensor = sensor_cls(_coord(_data(spot_valid=False, har_norgespris=False)), _entry())
        assert sensor.native_value is None

    @pytest.mark.parametrize(
        "sensor_cls",
        [
            StromprisPerKwhSensor,
            TotalPrisEtterStotteSensor,
            TotalPrisInklAvgifterSensor,
            StromprisPerKwhEtterStotteSensor,
        ],
    )
    def test_betinget_spot_tilgjengelig_norgespris_under_tak(self, sensor_cls):
        """Norgespris under taket bruker fast pris -> tilgjengelig selv uten spot."""
        sensor = sensor_cls(
            _coord(_data(spot_valid=False, har_norgespris=True, over_tak=False)), _entry()
        )
        assert sensor.native_value is not None

    @pytest.mark.parametrize(
        "sensor_cls",
        [
            StromprisPerKwhSensor,
            TotalPrisEtterStotteSensor,
            TotalPrisInklAvgifterSensor,
            StromprisPerKwhEtterStotteSensor,
        ],
    )
    def test_betinget_spot_none_norgespris_over_tak(self, sensor_cls):
        """Over taket faller Norgespris-kunder tilbake på spot -> None uten spot."""
        sensor = sensor_cls(
            _coord(_data(spot_valid=False, har_norgespris=True, over_tak=True)), _entry()
        )
        assert sensor.native_value is None

    @pytest.mark.parametrize("sensor_cls", [TotalPrisNorgesprisSensor, StromprisNorgesprisSensor])
    def test_norgespris_familie_under_tak_tilgjengelig(self, sensor_cls):
        sensor = sensor_cls(_coord(_data(spot_valid=False, over_tak=False)), _entry())
        assert sensor.native_value is not None

    @pytest.mark.parametrize("sensor_cls", [TotalPrisNorgesprisSensor, StromprisNorgesprisSensor])
    def test_norgespris_familie_over_tak_none(self, sensor_cls):
        sensor = sensor_cls(_coord(_data(spot_valid=False, over_tak=True)), _entry())
        assert sensor.native_value is None

    @pytest.mark.parametrize(
        "sensor_cls",
        [EnergileddSensor, KapasitetstrinnSensor, StromstotteGjenstaaendeSensor, ElectricityCompanyTotalSensor],
    )
    def test_spot_uavhengige_ikke_gatet(self, sensor_cls):
        """Energiledd, kapasitet, gjenstående kWh og leverandørpris er ikke spot-avhengige."""
        sensor = sensor_cls(_coord(_data(spot_valid=False)), _entry())
        assert sensor.native_value is not None

    def test_manglende_flagg_defaulter_til_gyldig(self):
        """Bakoverkompat: data uten spot_price_valid skal behandles som gyldig."""
        data = _data(spot_valid=True)
        del data["spot_price_valid"]
        sensor = TotalPriceSensor(_coord(data), _entry())
        assert sensor.native_value is not None


class TestCoordinatorSpotValidFlag:
    """Coordinator eksponerer spot_price_valid i data-dicten."""

    def _coord(self, coord_module, spot_price):
        entry = _base_make_entry(
            entry_id="test_entry",
            dso_id="bkk",
            spotpris_inkl_mva=True,
            avgiftssone="standard",
        )
        hass = _base_make_hass(power_w=0, spot_price=spot_price)
        coord = coord_module.NettleieCoordinator(hass, entry)
        coord._store_loaded = True
        return coord

    def test_gyldig_spot_gir_true(self, coord_module):
        coord = self._coord(coord_module, 1.20)
        result = asyncio.run(coord._async_update_data())
        assert result["spot_price_valid"] is True

    def test_kaldstart_gir_false_og_spot_0(self, coord_module):
        """Spot unavailable uten cache (kaldstart) -> ugyldig, spot 0."""
        coord = self._coord(coord_module, "unavailable")
        result = asyncio.run(coord._async_update_data())
        assert result["spot_price_valid"] is False
        assert result["spot_price"] == 0.0

    def test_bortfall_over_cache_vindu_gir_false(self, coord_module):
        """Cachet spot eldre enn 2 timer -> ugyldig."""
        coord = self._coord(coord_module, "unavailable")
        coord._last_spot_price = 1.0
        coord._last_spot_price_time = datetime(2026, 6, 15, 8, 0)  # 4t før nå (12:00)
        result = asyncio.run(coord._async_update_data())
        assert result["spot_price_valid"] is False

    def test_bortfall_innenfor_cache_vindu_gir_true(self, coord_module):
        """Cachet spot yngre enn 2 timer -> gyldig, bruker cachet verdi."""
        coord = self._coord(coord_module, "unavailable")
        coord._last_spot_price = 1.0
        coord._last_spot_price_time = datetime(2026, 6, 15, 11, 30)  # 30 min før nå
        result = asyncio.run(coord._async_update_data())
        assert result["spot_price_valid"] is True
        assert result["spot_price"] == pytest.approx(1.0)
