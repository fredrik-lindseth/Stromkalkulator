"""Tests for monthly sensor calculation logic.

P1 hull 1-4: Tests the native_value computation in
MaanedligNettleieSensor, MaanedligAvgifterSensor, MaanedligTotalSensor,
and ForrigeMaanedNettleieSensor, which all contain their own arithmetic
rather than just forwarding a coordinator key.
"""

from __future__ import annotations

import sys
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

# ---- HA module mocks (must match conftest / test_sensor_classes) ----
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
    AkkumulertKostnadSensor,
    DagskostnadSensor,
    EstimertMaanedskostnadSensor,
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
    (2, 155),
    (5, 250),
    (10, 415),
    (15, 600),
    (20, 770),
    (25, 940),
    (50, 1800),
    (75, 2650),
    (100, 3500),
    (float("inf"), 6900),
]


def _make_coordinator(data: dict) -> MagicMock:
    coord = MagicMock()
    coord.data = data
    coord.kapasitetstrinn = BKK_KAPASITETSTRINN
    return coord


def _bok(
    dag_kr: float = 0.0,
    natt_kr: float = 0.0,
    avgifter_kr: float = 0.0,
    fastledd_kr: float = 0.0,
    stotte_kr: float = 0.0,
    **ekstra,
) -> dict:
    """Data-dicten slik coordinatoren fyller den etter at kroner er bokført.

    Sensorene skal lese disse feltene. Tester som vil vise at de ikke regner
    selv, legger på forbruk og satser som `ekstra` og forventer at de ignoreres.
    """
    data = {
        "monthly_energiledd_dag_kr": dag_kr,
        "monthly_energiledd_natt_kr": natt_kr,
        "monthly_avgifter_kr": avgifter_kr,
        "monthly_accumulated_cost_energiledd_kr": dag_kr + natt_kr + avgifter_kr,
        "monthly_accumulated_cost_kapasitetsledd_kr": fastledd_kr,
        "monthly_stromstotte_kr": stotte_kr,
    }
    data.update(ekstra)
    return data


def _make_entry(avgiftssone: str = "standard") -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": avgiftssone}
    return entry


# ---------------------------------------------------------------------------
# P1.1: MaanedligNettleieSensor
# ---------------------------------------------------------------------------


class TestMaanedligNettleieSensor:
    """Leser bokført energiledd pluss bokført fastledd."""

    def test_normal_values(self):
        """Mai 2026 fra BKK-fakturaen: energiledd 392,96 og fastledd 250."""
        data = _bok(dag_kr=186.34, natt_kr=86.77, avgifter_kr=119.85, fastledd_kr=249.99)
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == 642.95

    def test_zero_consumption(self):
        """Ingen energi bokført: bare fastleddet står igjen."""
        data = _bok(fastledd_kr=415.0)
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == 415.0

    def test_ignorerer_forbruk_og_satser(self):
        """Satser ganget med kilowattimer skal ikke kunne påvirke verdien."""
        data = _bok(
            dag_kr=100.0,
            natt_kr=50.0,
            avgifter_kr=25.0,
            fastledd_kr=200.0,
            monthly_consumption_dag_kwh=350.0,
            monthly_consumption_natt_kwh=180.0,
            energiledd_dag=0.4613,
            energiledd_natt=0.2329,
            kapasitetsledd=600,
        )
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        assert sensor.native_value == 375.0

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligNettleieSensor(coord, _make_entry())
        assert sensor.native_value is None

    def test_extra_state_attributes_breakdown(self):
        """Splitten er fakturaens: dag, natt og avgifter hver for seg."""
        data = _bok(dag_kr=186.34, natt_kr=86.77, avgifter_kr=119.85, fastledd_kr=249.99)
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        attrs = sensor.extra_state_attributes
        assert attrs["energiledd_dag_kr"] == 186.34
        assert attrs["energiledd_natt_kr"] == 86.77
        assert attrs["avgifter_kr"] == 119.85
        assert attrs["kapasitetsledd_kr"] == 249.99

    def test_attributter_summerer_til_verdien(self):
        """De fire leddene er hele nettleien, ikke et utvalg av den."""
        data = _bok(dag_kr=212.41, natt_kr=58.14, avgifter_kr=105.04, fastledd_kr=249.99)
        sensor = MaanedligNettleieSensor(_make_coordinator(data), _make_entry())
        attrs = sensor.extra_state_attributes
        sum_attrs = (
            attrs["energiledd_dag_kr"]
            + attrs["energiledd_natt_kr"]
            + attrs["avgifter_kr"]
            + attrs["kapasitetsledd_kr"]
        )
        assert round(sum_attrs, 2) == sensor.native_value


# ---------------------------------------------------------------------------
# P1.2: MaanedligAvgifterSensor
# ---------------------------------------------------------------------------


class TestMaanedligAvgifterSensor:
    """Leser bokførte avgifter, og deler dem etter forholdet mellom satsene."""

    def test_leser_bokfort_belop(self):
        """Verdien er feltet, ikke kilowattimer ganget med en sats."""
        data = _bok(
            avgifter_kr=119.85,
            monthly_consumption_total_kwh=400.0,
            forbruksavgift_inkl_mva=FORBRUKSAVGIFT_ALMINNELIG * 1.25,
            enova_inkl_mva=ENOVA_AVGIFT * 1.25,
        )
        sensor = MaanedligAvgifterSensor(_make_coordinator(data), _make_entry("standard"))
        assert sensor.native_value == 119.85

    def test_splitt_etter_satsforhold(self):
        """Mai 2026: 105,10 forbruksavgift og 14,74 Enova på fakturaen."""
        data = _bok(
            avgifter_kr=119.85,
            forbruksavgift_inkl_mva=FORBRUKSAVGIFT_ALMINNELIG * 1.25,
            enova_inkl_mva=ENOVA_AVGIFT * 1.25,
        )
        sensor = MaanedligAvgifterSensor(_make_coordinator(data), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert attrs["forbruksavgift_kr"] == pytest.approx(105.10, abs=0.05)
        assert attrs["enovaavgift_kr"] == pytest.approx(14.75, abs=0.05)
        assert attrs["forbruksavgift_kr"] + attrs["enovaavgift_kr"] == pytest.approx(119.85, abs=0.01)
        assert attrs["avgiftssone"] == "standard"

    def test_tiltakssone_gir_alt_til_enova(self):
        """Uten forbruksavgift er hele beløpet Enova."""
        data = _bok(avgifter_kr=5.0, forbruksavgift_inkl_mva=0.0, enova_inkl_mva=ENOVA_AVGIFT)
        sensor = MaanedligAvgifterSensor(_make_coordinator(data), _make_entry("tiltakssone"))
        attrs = sensor.extra_state_attributes
        assert attrs["forbruksavgift_kr"] == 0.0
        assert attrs["enovaavgift_kr"] == 5.0

    def test_uten_satser_i_dicten_gir_null_splitt(self):
        """Mangler begge satsene, er null ærligere enn en divisjon med null."""
        data = _bok(avgifter_kr=50.0)
        sensor = MaanedligAvgifterSensor(_make_coordinator(data), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert attrs["forbruksavgift_kr"] == 0.0
        assert attrs["enovaavgift_kr"] == 50.0

    def test_zero_consumption(self):
        """Ingenting bokført -> 0 kr avgifter."""
        sensor = MaanedligAvgifterSensor(_make_coordinator(_bok()), _make_entry("standard"))
        assert sensor.native_value == 0.0

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligAvgifterSensor(coord, _make_entry())
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# P1.3: MaanedligTotalSensor
# ---------------------------------------------------------------------------


class TestMaanedligTotalSensor:
    """Beregner: nettleie - strømstøtte.

    energiledd_dag/natt fra dso.py inkluderer allerede forbruksavgift + enova,
    så avgifter legges IKKE til separat (det ville vært dobbelttelling).
    """

    @pytest.fixture
    def base_data(self):
        return _bok(
            dag_kr=92.26,
            natt_kr=23.29,
            avgifter_kr=53.55,
            fastledd_kr=415.0,
            monthly_consumption_dag_kwh=200.0,
            monthly_consumption_natt_kwh=100.0,
            monthly_consumption_total_kwh=300.0,
        )

    @pytest.mark.parametrize("avgiftssone", ["standard", "nord_norge", "tiltakssone"])
    def test_total_equals_nettleie_minus_stotte(self, base_data, avgiftssone):
        """total = nettleie - strømstøtte (avgifter allerede i energiledd)."""
        base_data["monthly_stromstotte_kr"] = 90.0

        coord = _make_coordinator(base_data)
        entry = _make_entry(avgiftssone)

        total_sensor = MaanedligTotalSensor(coord, entry)
        nettleie_sensor = MaanedligNettleieSensor(coord, entry)

        # total = nettleie - strømstøtte (IKKE + avgifter, de er allerede i energiledd)
        assert total_sensor.native_value == round(nettleie_sensor.native_value - 90.0, 2)

    def test_total_does_not_double_count_avgifter(self, base_data):
        """Regresjonstest: total skal IKKE inkludere avgifter separat.

        Avgiftene ligger allerede i det bokførte energileddet. Legges de til en
        gang til, blir totalen 53,55 kr for høy i denne måneden.
        """
        coord = _make_coordinator(base_data)
        entry = _make_entry("standard")

        total_sensor = MaanedligTotalSensor(coord, entry)
        nettleie_sensor = MaanedligNettleieSensor(coord, entry)
        avgifter_sensor = MaanedligAvgifterSensor(coord, entry)

        # Total skal være lik nettleie (ikke nettleie + avgifter)
        assert total_sensor.native_value == nettleie_sensor.native_value
        # Avgifter-sensoren er informasjonell: den viser hva som allerede er
        # inkludert i nettleien, men legges ikke til i totalen
        assert avgifter_sensor.native_value > 0

    def test_stromstotte_reduces_total(self, base_data):
        """When strømstøtte > 0, total should decrease."""
        coord_no_stotte = _make_coordinator({**base_data, "monthly_stromstotte_kr": 0.0})
        coord_with_stotte = _make_coordinator({**base_data, "monthly_stromstotte_kr": 150.0})

        total_without = MaanedligTotalSensor(coord_no_stotte, _make_entry("standard")).native_value
        total_with = MaanedligTotalSensor(coord_with_stotte, _make_entry("standard")).native_value

        assert total_with == round(total_without - 150.0, 2)

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        sensor = MaanedligTotalSensor(coord, _make_entry())
        assert sensor.native_value is None

    def test_extra_state_attributes(self, base_data):
        """Attributes should contain nettleie, strømstøtte breakdown."""
        base_data["monthly_stromstotte_kr"] = 60.0
        sensor = MaanedligTotalSensor(_make_coordinator(base_data), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert "nettleie_kr" in attrs
        assert "stromstotte_kr" in attrs
        assert "forbruk_total_kwh" in attrs
        # avgifter_kr skal IKKE være her: avgifter er allerede inkludert i nettleie
        assert "avgifter_kr" not in attrs

    def test_vektet_snittpris_with_consumption(self, base_data):
        """vektet_snittpris_kr_per_kwh == native_value / total_kwh for known consumption."""
        base_data["monthly_consumption_dag_kwh"] = 500.0
        base_data["monthly_consumption_natt_kwh"] = 200.0
        base_data["monthly_stromstotte_kr"] = 30.0
        sensor = MaanedligTotalSensor(_make_coordinator(base_data), _make_entry("standard"))
        total_kwh = 500.0 + 200.0
        expected = round(sensor.native_value / total_kwh, 4)
        attrs = sensor.extra_state_attributes
        assert attrs["vektet_snittpris_kr_per_kwh"] == expected

    def test_vektet_snittpris_zero_consumption(self):
        """vektet_snittpris_kr_per_kwh is None when total_kwh == 0."""
        data = _bok(
            fastledd_kr=415.0,
            monthly_consumption_dag_kwh=0.0,
            monthly_consumption_natt_kwh=0.0,
        )
        sensor = MaanedligTotalSensor(_make_coordinator(data), _make_entry("standard"))
        attrs = sensor.extra_state_attributes
        assert attrs["vektet_snittpris_kr_per_kwh"] is None


# ---------------------------------------------------------------------------
# P1.4: ForrigeMaanedNettleieSensor (med _get_kapasitetsledd_for_avg)
# ---------------------------------------------------------------------------


class TestForrigeMaanedNettleieSensor:
    """Beregner nettleie for forrige måned med eget kapasitetstrinn-oppslag."""

    def test_with_normal_top_3(self):
        """Normal topp-3 => avg 10 kW => BKK trinn 3 (415 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 300.0,
            "previous_month_consumption_natt_kwh": 200.0,
            "previous_month_energiledd_dag": 0.4613,
            "previous_month_energiledd_natt": 0.2329,
            "previous_month_kapasitetsledd": 415,
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(300.0 * 0.4613 + 200.0 * 0.2329 + 415, 2)
        assert sensor.native_value == expected

    def test_empty_top_3(self):
        """Tom topp-3 => kapasitet = 0."""
        data = {
            "previous_month_consumption_dag_kwh": 300.0,
            "previous_month_consumption_natt_kwh": 200.0,
            "previous_month_energiledd_dag": 0.4613,
            "previous_month_energiledd_natt": 0.2329,
            "previous_month_kapasitetsledd": 0,
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(300.0 * 0.4613 + 200.0 * 0.2329, 2)
        assert sensor.native_value == expected

    def test_high_power_top_tier(self):
        """Very high average -> highest tier (6900 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 500.0,
            "previous_month_consumption_natt_kwh": 300.0,
            "previous_month_energiledd_dag": 0.4613,
            "previous_month_energiledd_natt": 0.2329,
            "previous_month_kapasitetsledd": 6900,
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(500.0 * 0.4613 + 300.0 * 0.2329 + 6900, 2)
        assert sensor.native_value == expected

    def test_low_power_first_tier(self):
        """Very low average -> first tier (155 kr)."""
        data = {
            "previous_month_consumption_dag_kwh": 50.0,
            "previous_month_consumption_natt_kwh": 30.0,
            "previous_month_energiledd_dag": 0.4613,
            "previous_month_energiledd_natt": 0.2329,
            "previous_month_kapasitetsledd": 155,
        }
        sensor = ForrigeMaanedNettleieSensor(_make_coordinator(data), _make_entry())
        expected = round(50.0 * 0.4613 + 30.0 * 0.2329 + 155, 2)
        assert sensor.native_value == expected

    def test_returns_none_when_no_data(self):
        coord = MagicMock()
        coord.data = None
        coord.kapasitetstrinn = BKK_KAPASITETSTRINN
        sensor = ForrigeMaanedNettleieSensor(coord, _make_entry())
        assert sensor.native_value is None


# ---------------------------------------------------------------------------
# MaanedligForbrukTotalSensor: dag/natt-fordeling (%)
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
        assert sensor._attr_native_unit_of_measurement == "NOK"

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


# ---------------------------------------------------------------------------
# EstimertMaanedskostnadSensor
# ---------------------------------------------------------------------------


class TestEstimertMaanedskostnadSensor:
    """Projiserer variable kostnader til full måned + kapasitetsledd."""

    def _base_data(self):
        return _bok(
            dag_kr=69.20,
            natt_kr=11.65,
            avgifter_kr=35.70,
            fastledd_kr=207.5,
            kapasitetsledd=415,
        )

    @patch("stromkalkulator.sensor.dt_util")
    def test_basic_projection_mid_month(self, mock_dt):
        """Dag 15 av 30-dagers måned: estimat ~2x nåværende variable + kapasitet."""
        # April has 30 days, mock day 15
        mock_dt.now.return_value = datetime(2026, 4, 15, 12, 0, 0)
        data = self._base_data()
        sensor = EstimertMaanedskostnadSensor(_make_coordinator(data), _make_entry("standard"))

        # Den variable delen er bokført energiledd minus bokført støtte, skalert
        # fra 15 til 30 dager. Fastleddet legges på som helt månedsbeløp.
        bokfort = 69.20 + 11.65 + 35.70
        assert sensor.native_value == round((bokfort / 15) * 30 + 415, 0)

    @patch("stromkalkulator.sensor.dt_util")
    def test_stotte_trekkes_fra_for_projisering(self, mock_dt):
        """Støtten reduserer den variable delen, og skaleres derfor med den."""
        mock_dt.now.return_value = datetime(2026, 4, 15, 12, 0, 0)
        data = self._base_data()
        data["monthly_stromstotte_kr"] = 16.55
        sensor = EstimertMaanedskostnadSensor(_make_coordinator(data), _make_entry("standard"))
        bokfort = 69.20 + 11.65 + 35.70 - 16.55
        assert sensor.native_value == round((bokfort / 15) * 30 + 415, 0)

    @patch("stromkalkulator.sensor.dt_util")
    def test_first_day_returns_value(self, mock_dt):
        """Dag 1 skal returnere en verdi (ikke None eller krasje)."""
        mock_dt.now.return_value = datetime(2026, 4, 1, 8, 0, 0)
        data = self._base_data()
        sensor = EstimertMaanedskostnadSensor(_make_coordinator(data), _make_entry("standard"))
        value = sensor.native_value
        assert value is not None
        # On day 1, variable cost projected to full month + kapasitet
        assert value > 0

    @patch("stromkalkulator.sensor.dt_util")
    def test_returns_none_when_no_data(self, mock_dt):
        """Returnerer None når coordinator.data er None."""
        mock_dt.now.return_value = datetime(2026, 4, 15, 12, 0, 0)
        coord = MagicMock()
        coord.data = None
        sensor = EstimertMaanedskostnadSensor(coord, _make_entry())
        assert sensor.native_value is None

    @patch("stromkalkulator.sensor.dt_util")
    def test_december_days_in_month(self, mock_dt):
        """Desember har 31 dager (spesialcase i koden)."""
        mock_dt.now.return_value = datetime(2026, 12, 10, 12, 0, 0)
        data = self._base_data()
        sensor = EstimertMaanedskostnadSensor(_make_coordinator(data), _make_entry("standard"))
        value = sensor.native_value
        assert value is not None
        # Just verify it computes without error and is positive
        assert value > 0


# ---------------------------------------------------------------------------
# Ukjent fastledd (Egendefinert uten trinntabell, kontrakt §9)
# ---------------------------------------------------------------------------


class TestUkjentFastledd:
    """Et månedsbeløp uten kapasitetsledd er systematisk for lavt.

    Da skal sensoren være Ukjent, ikke vise en total som mangler en av de to
    store postene. Forbrukssensorene og avgiftene er uberørt: de har ingenting
    med fastleddet å gjøre.
    """

    def _data(self, *, ukjent: bool):
        return _bok(
            dag_kr=69.20,
            natt_kr=11.65,
            avgifter_kr=35.70,
            fastledd_kr=0 if ukjent else 207.5,
            monthly_consumption_dag_kwh=150.0,
            monthly_consumption_natt_kwh=50.0,
            monthly_consumption_total_kwh=200.0,
            kapasitetsledd=0 if ukjent else 415,
            monthly_accumulated_cost_kr=123.45,
            fastledd_ukjent=ukjent,
        )

    @pytest.mark.parametrize(
        "sensor_class",
        [MaanedligNettleieSensor, MaanedligTotalSensor, AkkumulertKostnadSensor],
    )
    def test_maanedsbeloep_er_ukjent(self, sensor_class):
        sensor = sensor_class(_make_coordinator(self._data(ukjent=True)), _make_entry())
        assert sensor.native_value is None
        assert sensor.extra_state_attributes["fastledd_ukjent"] is True

    @pytest.mark.parametrize(
        "sensor_class",
        [MaanedligNettleieSensor, MaanedligTotalSensor, AkkumulertKostnadSensor],
    )
    def test_kjent_fastledd_gir_tall_som_foer(self, sensor_class):
        sensor = sensor_class(_make_coordinator(self._data(ukjent=False)), _make_entry())
        assert sensor.native_value is not None
        assert "fastledd_ukjent" not in sensor.extra_state_attributes

    @patch("stromkalkulator.sensor.dt_util")
    def test_estimert_maanedskostnad_er_ukjent(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 4, 15, 12, 0, 0)
        sensor = EstimertMaanedskostnadSensor(
            _make_coordinator(self._data(ukjent=True)), _make_entry("standard")
        )
        assert sensor.native_value is None

    @patch("stromkalkulator.sensor.dt_util")
    def test_estimert_maanedskostnad_uberoert_med_trinn(self, mock_dt):
        mock_dt.now.return_value = datetime(2026, 4, 15, 12, 0, 0)
        sensor = EstimertMaanedskostnadSensor(
            _make_coordinator(self._data(ukjent=False)), _make_entry("standard")
        )
        assert sensor.native_value is not None

    def test_avgifter_og_forbruk_er_uberoert(self):
        data = self._data(ukjent=True)
        assert MaanedligAvgifterSensor(_make_coordinator(data), _make_entry()).native_value is not None
        assert MaanedligForbrukTotalSensor(_make_coordinator(data), _make_entry()).native_value is not None
