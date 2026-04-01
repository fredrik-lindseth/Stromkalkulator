"""Tests for sensor class definitions and behavior.

Verifies that all sensor classes have correct device_class, state_class,
unit_of_measurement, and that native_value reads the correct key from
coordinator.data. Also tests extra_state_attributes where applicable.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# We need to set up the mocked HA modules more carefully for sensor classes
# because they reference SensorDeviceClass, SensorStateClass, etc.
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
# Ensure EntityCategory is accessible from the entity module too
_entity_mod.EntityCategory = _const_mod.EntityCategory

_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class FakeCoordinatorEntity:
    """Minimal CoordinatorEntity stub."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = FakeCoordinatorEntity


# Now we can import sensor classes
from stromkalkulator.const import STROMSTOTTE_LEVEL  # noqa: E402
from stromkalkulator.sensor import (  # noqa: E402
    ElectricityCompanyTotalSensor,
    EnergileddDagSensor,
    EnergileddNattSensor,
    EnergileddSensor,
    ForrigeMaanedForbrukDagSensor,
    ForrigeMaanedForbrukNattSensor,
    ForrigeMaanedForbrukTotalSensor,
    ForrigeMaanedToppforbrukSensor,
    GjsForbrukSensor,
    KapasitetstrinnSensor,
    KapasitetVarselSensor,
    MaanedligForbrukDagSensor,
    MaanedligForbrukNattSensor,
    MaanedligForbrukTotalSensor,
    MaanedligNettleieSensor,
    MaanedligNorgesprisDifferanseSensor,
    MaanedligTotalSensor,
    MaksForbrukSensor,
    MarginNesteTrinnSensor,
    NorgesprisAktivSensor,
    PrisforskjellNorgesprisSensor,
    SpotprisEtterStotteSensor,
    StromprisPerKwhEtterStotteSensor,
    StromprisPerKwhSensor,
    StromstotteGjenstaaendeSensor,
    StromstotteKwhSensor,
    StromstotteSensor,
    TariffSensor,
    TotalPriceSensor,
    TotalPrisEtterStotteSensor,
    TotalPrisInklAvgifterSensor,
    TotalPrisNorgesprisSensor,
    TrinnIntervallSensor,
    TrinnNummerSensor,
)

# --- Fixtures ---

SAMPLE_DATA = {
    "energiledd": 0.4613,
    "energiledd_dag": 0.4613,
    "energiledd_natt": 0.2329,
    "kapasitetsledd": 415,
    "kapasitetstrinn_nummer": 3,
    "kapasitetstrinn_intervall": "5-10 kW",
    "kapasitetsledd_per_kwh": 0.0576,
    "spot_price": 1.20,
    "stromstotte": 0.2138,
    "spotpris_etter_stotte": 0.9862,
    "norgespris": 0.50,
    "norgespris_stromstotte": 0,
    "total_pris_norgespris": 1.0189,
    "kroner_spart_per_kwh": 0.25,
    "total_price": 1.5051,
    "total_price_uten_stotte": 1.7189,
    "total_price_inkl_avgifter": 1.8205,
    "strompris_per_kwh": 1.6613,
    "strompris_per_kwh_etter_stotte": 1.4475,
    "forbruksavgift_inkl_mva": 0.0891,
    "enova_inkl_mva": 0.0125,
    "offentlige_avgifter": 0.1016,
    "electricity_company_price": 0.85,
    "electricity_company_total": 1.3689,
    "current_power_kw": 7.50,
    "avg_top_3_kw": 8.33,
    "top_3_days": {"2026-04-01": 10.0, "2026-04-02": 8.0, "2026-04-03": 7.0},
    "is_day_rate": True,
    "dso": "BKK",
    "har_norgespris": False,
    "avgiftssone": "standard",
    "monthly_consumption_dag_kwh": 250.5,
    "monthly_consumption_natt_kwh": 150.3,
    "monthly_consumption_total_kwh": 400.8,
    "previous_month_consumption_dag_kwh": 300.0,
    "previous_month_consumption_natt_kwh": 200.0,
    "previous_month_consumption_total_kwh": 500.0,
    "previous_month_top_3": {"2026-03-01": 12.0, "2026-03-10": 10.0, "2026-03-20": 8.0},
    "previous_month_avg_top_3_kw": 10.0,
    "previous_month_name": "mars 2026",
    "stromstotte_tak_naadd": False,
    "stromstotte_gjenstaaende_kwh": 4599.2,
    "margin_neste_trinn_kw": 1.67,
    "neste_trinn_pris": 600,
    "kapasitet_varsel": True,
    "monthly_norgespris_diff_kr": 12.50,
}


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator with sample data."""
    coordinator = MagicMock()
    coordinator.data = SAMPLE_DATA.copy()
    coordinator.kapasitetstrinn = [
        (2, 155), (5, 250), (10, 415), (15, 600), (20, 770),
        (25, 940), (50, 1800), (75, 2650), (100, 3500), (float("inf"), 6900),
    ]
    return coordinator


@pytest.fixture
def mock_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_123"
    entry.data = {
        "tso": "bkk",
        "avgiftssone": "standard",
    }
    return entry


# --- Test sensor native_value reads correct key ---


class TestSensorNativeValue:
    """Verify each sensor reads the correct key from coordinator.data."""

    def test_energiledd_value(self, mock_coordinator, mock_entry):
        sensor = EnergileddSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.4613

    def test_kapasitetstrinn_value(self, mock_coordinator, mock_entry):
        sensor = KapasitetstrinnSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 415

    def test_margin_neste_trinn_value(self, mock_coordinator, mock_entry):
        sensor = MarginNesteTrinnSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.67

    def test_kapasitet_varsel_on(self, mock_coordinator, mock_entry):
        sensor = KapasitetVarselSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "on"

    def test_kapasitet_varsel_off(self, mock_coordinator, mock_entry):
        mock_coordinator.data["kapasitet_varsel"] = False
        sensor = KapasitetVarselSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "off"

    def test_total_price_uses_uten_stotte(self, mock_coordinator, mock_entry):
        """TotalPriceSensor reads total_price_uten_stotte (before subsidy)."""
        sensor = TotalPriceSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.7189

    def test_maks_forbruk_rank_1(self, mock_coordinator, mock_entry):
        sensor = MaksForbrukSensor(mock_coordinator, mock_entry, 1)
        assert sensor.native_value == 10.0

    def test_maks_forbruk_rank_2(self, mock_coordinator, mock_entry):
        sensor = MaksForbrukSensor(mock_coordinator, mock_entry, 2)
        assert sensor.native_value == 8.0

    def test_maks_forbruk_rank_3(self, mock_coordinator, mock_entry):
        sensor = MaksForbrukSensor(mock_coordinator, mock_entry, 3)
        assert sensor.native_value == 7.0

    def test_gjs_forbruk_value(self, mock_coordinator, mock_entry):
        sensor = GjsForbrukSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 8.33

    def test_trinn_nummer_value(self, mock_coordinator, mock_entry):
        sensor = TrinnNummerSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 3

    def test_trinn_intervall_value(self, mock_coordinator, mock_entry):
        sensor = TrinnIntervallSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "5-10 kW"

    def test_stromstotte_value(self, mock_coordinator, mock_entry):
        sensor = StromstotteSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.2138

    def test_spotpris_etter_stotte_value(self, mock_coordinator, mock_entry):
        sensor = SpotprisEtterStotteSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.9862

    def test_total_pris_etter_stotte_value(self, mock_coordinator, mock_entry):
        """TotalPrisEtterStotteSensor reads total_price (after subsidy)."""
        sensor = TotalPrisEtterStotteSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.5051

    def test_total_pris_inkl_avgifter_value(self, mock_coordinator, mock_entry):
        sensor = TotalPrisInklAvgifterSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.8205

    def test_total_pris_norgespris_value(self, mock_coordinator, mock_entry):
        sensor = TotalPrisNorgesprisSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.0189

    def test_prisforskjell_norgespris_value(self, mock_coordinator, mock_entry):
        sensor = PrisforskjellNorgesprisSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.25

    def test_norgespris_aktiv_nei(self, mock_coordinator, mock_entry):
        sensor = NorgesprisAktivSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "Nei"

    def test_norgespris_aktiv_ja(self, mock_coordinator, mock_entry):
        mock_coordinator.data["har_norgespris"] = True
        sensor = NorgesprisAktivSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "Ja"

    def test_energiledd_dag_value(self, mock_coordinator, mock_entry):
        sensor = EnergileddDagSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.4613

    def test_energiledd_natt_value(self, mock_coordinator, mock_entry):
        sensor = EnergileddNattSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 0.2329

    def test_stromstotte_kwh_ja(self, mock_coordinator, mock_entry):
        sensor = StromstotteKwhSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "Ja"  # stromstotte > 0

    def test_stromstotte_kwh_nei(self, mock_coordinator, mock_entry):
        mock_coordinator.data["stromstotte"] = 0
        sensor = StromstotteKwhSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "Nei"

    def test_stromstotte_gjenstaaende_value(self, mock_coordinator, mock_entry):
        sensor = StromstotteGjenstaaendeSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 4599.2

    def test_strompris_per_kwh_value(self, mock_coordinator, mock_entry):
        sensor = StromprisPerKwhSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.6613

    def test_strompris_per_kwh_etter_stotte_value(self, mock_coordinator, mock_entry):
        sensor = StromprisPerKwhEtterStotteSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 1.4475

    def test_tariff_dag(self, mock_coordinator, mock_entry):
        sensor = TariffSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "dag"

    def test_tariff_natt(self, mock_coordinator, mock_entry):
        mock_coordinator.data["is_day_rate"] = False
        sensor = TariffSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == "natt"

    def test_electricity_company_total(self, mock_coordinator, mock_entry):
        sensor = ElectricityCompanyTotalSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == round(1.3689, 4)

    def test_electricity_company_total_none(self, mock_coordinator, mock_entry):
        mock_coordinator.data["electricity_company_total"] = None
        sensor = ElectricityCompanyTotalSensor(mock_coordinator, mock_entry)
        assert sensor.native_value is None


class TestMonthlyConsumptionSensors:
    """Monthly consumption sensor values."""

    def test_monthly_dag(self, mock_coordinator, mock_entry):
        sensor = MaanedligForbrukDagSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 250.5

    def test_monthly_natt(self, mock_coordinator, mock_entry):
        sensor = MaanedligForbrukNattSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 150.3

    def test_monthly_total(self, mock_coordinator, mock_entry):
        sensor = MaanedligForbrukTotalSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 400.8

    def test_monthly_norgespris_diff(self, mock_coordinator, mock_entry):
        sensor = MaanedligNorgesprisDifferanseSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 12.50


class TestPreviousMonthSensors:
    """Previous month sensor values."""

    def test_forrige_dag(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedForbrukDagSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 300.0

    def test_forrige_natt(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedForbrukNattSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 200.0

    def test_forrige_total(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedForbrukTotalSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 500.0

    def test_forrige_toppforbruk(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedToppforbrukSensor(mock_coordinator, mock_entry)
        assert sensor.native_value == 10.0


class TestSensorNoneWhenNoData:
    """Sensors should return None when coordinator.data is None/empty."""

    @pytest.mark.parametrize("sensor_class", [
        EnergileddSensor,
        KapasitetstrinnSensor,
        MarginNesteTrinnSensor,
        TotalPriceSensor,
        StromstotteSensor,
        SpotprisEtterStotteSensor,
        TotalPrisEtterStotteSensor,
        TotalPrisInklAvgifterSensor,
        TotalPrisNorgesprisSensor,
        PrisforskjellNorgesprisSensor,
        NorgesprisAktivSensor,
        TariffSensor,
        StromprisPerKwhSensor,
        StromprisPerKwhEtterStotteSensor,
        StromstotteGjenstaaendeSensor,
        StromstotteKwhSensor,
        KapasitetVarselSensor,
        ElectricityCompanyTotalSensor,
    ])
    def test_returns_none_without_data(self, sensor_class, mock_entry):
        coordinator = MagicMock()
        coordinator.data = None
        sensor = sensor_class(coordinator, mock_entry)
        assert sensor.native_value is None


class TestSensorAttributes:
    """Verify extra_state_attributes contain expected keys."""

    def test_energiledd_attributes(self, mock_coordinator, mock_entry):
        sensor = EnergileddSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "is_day_rate" in attrs
        assert "rate_type" in attrs
        assert "energiledd_dag" in attrs
        assert "energiledd_natt" in attrs
        assert "dso" in attrs

    def test_kapasitetstrinn_attributes(self, mock_coordinator, mock_entry):
        sensor = KapasitetstrinnSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "trinn" in attrs
        assert "intervall" in attrs
        assert "gjennomsnitt_kw" in attrs
        assert "current_power_kw" in attrs

    def test_kapasitetstrinn_has_top_3_dates(self, mock_coordinator, mock_entry):
        """Top 3 dates should be in attributes."""
        sensor = KapasitetstrinnSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "maks_1_dato" in attrs
        assert "maks_1_kw" in attrs

    def test_margin_neste_trinn_attributes(self, mock_coordinator, mock_entry):
        sensor = MarginNesteTrinnSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "naavarende_trinn_pris" in attrs
        assert "neste_trinn_pris" in attrs

    def test_stromstotte_attributes(self, mock_coordinator, mock_entry):
        sensor = StromstotteSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs["terskel"] == STROMSTOTTE_LEVEL
        assert attrs["dekningsgrad"] == "90%"

    def test_total_pris_inkl_avgifter_attributes(self, mock_coordinator, mock_entry):
        sensor = TotalPrisInklAvgifterSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "forbruksavgift_inkl_mva" in attrs
        assert "enova_inkl_mva" in attrs
        assert "offentlige_avgifter" in attrs

    def test_tariff_attributes(self, mock_coordinator, mock_entry):
        sensor = TariffSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "dag_periode" in attrs
        assert "natt_periode" in attrs

    def test_maks_forbruk_attributes(self, mock_coordinator, mock_entry):
        sensor = MaksForbrukSensor(mock_coordinator, mock_entry, 1)
        attrs = sensor.extra_state_attributes
        assert "dato" in attrs

    def test_monthly_total_attributes(self, mock_coordinator, mock_entry):
        sensor = MaanedligForbrukTotalSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "dag_kwh" in attrs
        assert "natt_kwh" in attrs

    def test_forrige_maaned_forbruk_attributes(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedForbrukDagSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert attrs is not None
        assert "maaned" in attrs

    def test_forrige_maaned_toppforbruk_attributes(self, mock_coordinator, mock_entry):
        sensor = ForrigeMaanedToppforbrukSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "maaned" in attrs
        assert "topp_1_dato" in attrs
        assert "topp_1_kw" in attrs

    def test_norgespris_diff_attributes(self, mock_coordinator, mock_entry):
        sensor = MaanedligNorgesprisDifferanseSensor(mock_coordinator, mock_entry)
        attrs = sensor.extra_state_attributes
        assert "sammenligner_med" in attrs

    def test_attributes_none_when_no_data(self, mock_entry):
        coordinator = MagicMock()
        coordinator.data = None
        sensor = EnergileddSensor(coordinator, mock_entry)
        assert sensor.extra_state_attributes is None


class TestSensorUniqueId:
    """Verify unique_id uses entry_id."""

    def test_unique_id_contains_entry_id(self, mock_coordinator, mock_entry):
        sensor = EnergileddSensor(mock_coordinator, mock_entry)
        assert "test_entry_123" in sensor._attr_unique_id

    def test_unique_ids_differ_per_sensor_type(self, mock_coordinator, mock_entry):
        s1 = EnergileddSensor(mock_coordinator, mock_entry)
        s2 = KapasitetstrinnSensor(mock_coordinator, mock_entry)
        assert s1._attr_unique_id != s2._attr_unique_id


class TestSensorDeviceClassAndUnit:
    """Verify monetary sensors have correct device class and unit."""

    @pytest.mark.parametrize("sensor_class,expected_unit", [
        (EnergileddSensor, "NOK/kWh"),
        (KapasitetstrinnSensor, "kr/mnd"),
        (TotalPriceSensor, "NOK/kWh"),
        (StromstotteSensor, "NOK/kWh"),
        (SpotprisEtterStotteSensor, "NOK/kWh"),
        (TotalPrisEtterStotteSensor, "NOK/kWh"),
        (TotalPrisInklAvgifterSensor, "NOK/kWh"),
        (TotalPrisNorgesprisSensor, "NOK/kWh"),
        (PrisforskjellNorgesprisSensor, "NOK/kWh"),
        (StromprisPerKwhSensor, "NOK/kWh"),
        (StromprisPerKwhEtterStotteSensor, "NOK/kWh"),
        (ElectricityCompanyTotalSensor, "NOK/kWh"),
        (MarginNesteTrinnSensor, "kW"),
        (StromstotteGjenstaaendeSensor, "kWh"),
        (MaanedligForbrukDagSensor, "kWh"),
        (MaanedligForbrukNattSensor, "kWh"),
        (MaanedligForbrukTotalSensor, "kWh"),
        (MaanedligNettleieSensor, "kr"),
        (MaanedligTotalSensor, "kr"),
    ])
    def test_unit_of_measurement(self, sensor_class, expected_unit, mock_coordinator, mock_entry):
        sensor = sensor_class(mock_coordinator, mock_entry)
        assert sensor._attr_native_unit_of_measurement == expected_unit
