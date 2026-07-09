"""Tests for sensor class definitions and behavior.

Verifies that all sensor classes have correct device_class, state_class,
unit_of_measurement, and that native_value reads the correct key from
coordinator.data. Also tests extra_state_attributes where applicable.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# We need to set up the mocked HA modules more carefully for sensor classes
# because they reference SensorDeviceClass, SensorStateClass, etc.
_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
    "MONETARY": "monetary",
    "POWER": "power",
    "ENERGY": "energy",
    "ENUM": "enum",
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
    EnovaavgiftSensor,
    ForbruksavgiftSensor,
    ForrigeMaanedForbrukDagSensor,
    ForrigeMaanedToppforbrukSensor,
    KapasitetstrinnSensor,
    MaanedligForbrukDagSensor,
    MaanedligForbrukNattSensor,
    MaanedligForbrukTotalSensor,
    MaanedligNettleieSensor,
    MaanedligNorgesprisDifferanseSensor,
    MaanedligTotalSensor,
    MaksForbrukSensor,
    MarginNesteTrinnSensor,
    OffentligeAvgifterSensor,
    PrisforskjellNorgesprisSensor,
    SpotprisEtterStotteSensor,
    StromprisNorgesprisSensor,
    StromprisPerKwhEtterStotteSensor,
    StromprisPerKwhSensor,
    StromstotteGjenstaaendeSensor,
    StromstotteSensor,
    TariffSensor,
    TotalPriceSensor,
    TotalPrisEtterStotteSensor,
    TotalPrisInklAvgifterSensor,
    TotalPrisNorgesprisSensor,
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
    "strompris_norgespris": 0.50,
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
    "top_3_days": {
        "2026-04-01": SimpleNamespace(kw=10.0, hour=16),
        "2026-04-02": SimpleNamespace(kw=8.0, hour=8),
        "2026-04-03": SimpleNamespace(kw=7.0, hour=20),
    },
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
    "previous_month_top_3": {
        "2026-03-01": SimpleNamespace(kw=12.0, hour=16),
        "2026-03-10": SimpleNamespace(kw=10.0, hour=8),
        "2026-03-20": SimpleNamespace(kw=8.0, hour=20),
    },
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
        StromprisNorgesprisSensor,
        PrisforskjellNorgesprisSensor,
        TariffSensor,
        StromprisPerKwhSensor,
        StromprisPerKwhEtterStotteSensor,
        StromstotteGjenstaaendeSensor,
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
    """Verify sensors have correct device class, state class and unit."""

    @pytest.mark.parametrize("sensor_class,expected_unit", [
        (EnergileddSensor, "NOK/kWh"),
        (KapasitetstrinnSensor, "kr/mnd"),
        (TotalPriceSensor, "NOK/kWh"),
        (StromstotteSensor, "NOK/kWh"),
        (SpotprisEtterStotteSensor, "NOK/kWh"),
        (TotalPrisEtterStotteSensor, "NOK/kWh"),
        (TotalPrisInklAvgifterSensor, "NOK/kWh"),
        (TotalPrisNorgesprisSensor, "NOK/kWh"),
        (StromprisNorgesprisSensor, "NOK/kWh"),
        (PrisforskjellNorgesprisSensor, "NOK/kWh"),
        (StromprisPerKwhSensor, "NOK/kWh"),
        (StromprisPerKwhEtterStotteSensor, "NOK/kWh"),
        (ElectricityCompanyTotalSensor, "NOK/kWh"),
        (MarginNesteTrinnSensor, "kW"),
        (StromstotteGjenstaaendeSensor, "kWh"),
        (MaanedligForbrukDagSensor, "kWh"),
        (MaanedligForbrukNattSensor, "kWh"),
        (MaanedligForbrukTotalSensor, "kWh"),
        (MaanedligNettleieSensor, "NOK"),
        (MaanedligTotalSensor, "NOK"),
    ])
    def test_unit_of_measurement(self, sensor_class, expected_unit, mock_coordinator, mock_entry):
        sensor = sensor_class(mock_coordinator, mock_entry)
        assert sensor._attr_native_unit_of_measurement == expected_unit

    # NOK/kWh og kr/mnd er per-enhet-satser, ikke pengebeløp. HA reserverer
    # MONETARY for ISO 4217-beløp og holder MONETARY-sensorer utenfor
    # measurement-statistikken. Satsene skal derfor ikke ha device_class, men
    # state_class MEASUREMENT så de fortsatt får statistikk (min/snitt/maks).
    @pytest.mark.parametrize("sensor_class", [
        EnergileddSensor,
        EnergileddDagSensor,
        EnergileddNattSensor,
        KapasitetstrinnSensor,
        OffentligeAvgifterSensor,
        ForbruksavgiftSensor,
        EnovaavgiftSensor,
        TotalPriceSensor,
        ElectricityCompanyTotalSensor,
        StromprisPerKwhSensor,
        StromprisPerKwhEtterStotteSensor,
        StromstotteSensor,
        SpotprisEtterStotteSensor,
        TotalPrisEtterStotteSensor,
        TotalPrisInklAvgifterSensor,
        TotalPrisNorgesprisSensor,
        StromprisNorgesprisSensor,
        PrisforskjellNorgesprisSensor,
    ])
    def test_rate_sensors_are_measurement_not_monetary(self, sensor_class, mock_coordinator, mock_entry):
        sensor = sensor_class(mock_coordinator, mock_entry)
        assert getattr(sensor, "_attr_device_class", None) is None
        assert sensor._attr_state_class == "measurement"

    # Faktiske kronebeløp (månedskostnader, differanser, inntekter) er ekte
    # pengeverdier med MONETARY device_class og enhet "NOK" (ISO 4217). Satser
    # hører ikke hjemme her, se docs/domain-rules.md.
    @pytest.mark.parametrize("sensor_class", [
        MaanedligNettleieSensor,
        MaanedligTotalSensor,
        MaanedligNorgesprisDifferanseSensor,
    ])
    def test_amount_sensors_stay_monetary(self, sensor_class, mock_coordinator, mock_entry):
        sensor = sensor_class(mock_coordinator, mock_entry)
        assert sensor._attr_device_class == "monetary"
        assert sensor._attr_native_unit_of_measurement == "NOK"


class TestEnumStateSensors:
    """Tariff-sensoren bruker ENUM device_class med definerte options.

    Strømstøtte-aktiv og Norgespris-aktiv var tidligere tekst-sensorer med
    "Ja"/"Nei" (kunne ikke være ENUM fordi hassfest krever [a-z0-9-_]+ og
    "Ja"/"Nei" er ugyldige). De er nå binary_sensor-entiteter, se
    tests/test_binary_sensor.py.
    """

    def test_tariff_enum_device_class_and_options(self, mock_coordinator, mock_entry):
        sensor = TariffSensor(mock_coordinator, mock_entry)
        assert sensor._attr_device_class == "enum"
        assert sensor._attr_options == ["dag", "natt"]
        assert getattr(sensor, "_attr_native_unit_of_measurement", None) is None
        assert getattr(sensor, "_attr_state_class", None) is None

    def test_tariff_native_value_is_a_declared_option(self, mock_coordinator, mock_entry):
        sensor = TariffSensor(mock_coordinator, mock_entry)
        assert sensor.native_value in sensor._attr_options


class TestHandleCoordinatorUpdateDedup:
    """_handle_coordinator_update skriver kun state når noe faktisk endret seg."""

    @staticmethod
    def _parent_of_base(sensor):
        """Klassen super()._handle_coordinator_update peker på (mocked CoordinatorEntity).

        Utledes fra selve instansen for å være robust mot modul-reload i suiten:
        NettleieBaseSensor er mro[1], og super-kallet treffer mro[2].
        """
        return type(sensor).__mro__[2]

    def test_dedups_unchanged_and_writes_on_change(self, mock_entry, monkeypatch):
        coordinator = MagicMock()
        coordinator.data = {"energiledd": 0.5}
        sensor = EnergileddSensor(coordinator, mock_entry)

        writes: list[int] = []
        monkeypatch.setattr(
            self._parent_of_base(sensor),
            "_handle_coordinator_update",
            lambda self: writes.append(1),
            raising=False,
        )
        # available finnes ikke i test-stubben; sett den som instans-attributt.
        sensor.available = True

        sensor._handle_coordinator_update()
        assert len(writes) == 1  # første refresh skriver

        sensor._handle_coordinator_update()
        assert len(writes) == 1  # uendret verdi -> ingen ny skriv

        coordinator.data = {"energiledd": 0.9}
        sensor._handle_coordinator_update()
        assert len(writes) == 2  # endret verdi -> ny skriv

    def test_write_when_availability_changes(self, mock_entry, monkeypatch):
        coordinator = MagicMock()
        coordinator.data = {"energiledd": 0.5}
        sensor = EnergileddSensor(coordinator, mock_entry)

        writes: list[int] = []
        monkeypatch.setattr(
            self._parent_of_base(sensor),
            "_handle_coordinator_update",
            lambda self: writes.append(1),
            raising=False,
        )

        sensor.available = True
        sensor._handle_coordinator_update()
        assert len(writes) == 1

        # Kun tilgjengeligheten endres; verdi/attributter er like -> skal skrive.
        sensor.available = False
        sensor._handle_coordinator_update()
        assert len(writes) == 2
