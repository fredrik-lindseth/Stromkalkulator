"""
Test mot BKK-faktura mars 2026.

Fakturaperiode: 01.03.2026 - 01.04.2026 (31 dager)
Norgespris-kunde (fast 50 øre/kWh inkl. mva)
Fakturanr: 064202476

Verifiserer at våre beregninger matcher den faktiske fakturaen.
"""

import pytest

from custom_components.stromkalkulator.const import (
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
    NORGESPRIS_INKL_MVA_STANDARD,
)

# BKK 2026-priser fra fakturaen (inkl. mva, eks. offentlige avgifter)
BKK_ENERGILEDD_DAG_2026_ORE = 35.963  # øre/kWh inkl. mva
BKK_ENERGILEDD_NATT_2026_ORE = 13.125  # øre/kWh inkl. mva
BKK_FORBRUKSAVGIFT_2026_ORE = 8.913  # øre/kWh inkl. mva
BKK_ENOVAAVGIFT_2026_ORE = 1.25  # øre/kWh inkl. mva
BKK_KAPASITET_2_5_KW = 250  # kr/mnd


@pytest.fixture
def faktura_mars_2026():
    """BKK faktura 064202476 — Mars 2026.

    Norgespris-kunde. Tilgode 749.02 kr.
    Maks effekt: 4.798, 4.557, 4.534 kW → kapasitet 2-5 kW.
    """
    return {
        "periode_dager": 31,
        "forbruk_dag_kwh": 831.768,
        "forbruk_natt_kwh": 721.449,
        "forbruk_total_kwh": 1553.217,
        "maks_effekt": [4.798, 4.557, 4.534],
        "norgespris_snitt_kr_per_kwh": -0.99837,
        "forventet_energiledd_dag_kr": 299.13,
        "forventet_energiledd_natt_kr": 94.69,
        "forventet_norgespris_kr": -1550.68,
        "forventet_kapasitet_kr": 250.00,
        "forventet_forbruksavgift_kr": 138.43,
        "forventet_enovaavgift_kr": 19.41,
        "forventet_nettleie_kr": 801.66,
        "forventet_total_kr": -749.02,
        "forventet_mva_kr": 160.33,
    }


# --- Energiledd ---


def test_energiledd_dag(faktura_mars_2026):
    """Energiledd dag: 831.768 kWh * 35.963 øre/kWh = 299.13 kr."""
    beregnet = faktura_mars_2026["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_mars_2026["forventet_energiledd_dag_kr"], abs=0.10)


def test_energiledd_natt(faktura_mars_2026):
    """Energiledd natt: 721.449 kWh * 13.125 øre/kWh = 94.69 kr."""
    beregnet = faktura_mars_2026["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_mars_2026["forventet_energiledd_natt_kr"], abs=0.10)


# --- Avgifter ---


def test_forbruksavgift(faktura_mars_2026):
    """Forbruksavgift: 1553.217 kWh * 8.913 øre/kWh = 138.43 kr."""
    beregnet = faktura_mars_2026["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_mars_2026["forventet_forbruksavgift_kr"], abs=0.10)


def test_forbruksavgift_matcher_const():
    """Vår FORBRUKSAVGIFT_ALMINNELIG * 1.25 = fakturans 8.913 øre/kWh."""
    beregnet_inkl_mva = FORBRUKSAVGIFT_ALMINNELIG * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_FORBRUKSAVGIFT_2026_ORE, abs=0.01)


def test_enovaavgift(faktura_mars_2026):
    """Enovaavgift: 1553.217 kWh * 1.25 øre/kWh = 19.41 kr."""
    beregnet = faktura_mars_2026["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_mars_2026["forventet_enovaavgift_kr"], abs=0.10)


def test_enovaavgift_matcher_const():
    """Vår ENOVA_AVGIFT * 1.25 = fakturans 1.25 øre/kWh."""
    beregnet_inkl_mva = ENOVA_AVGIFT * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_ENOVAAVGIFT_2026_ORE, abs=0.01)


# --- Kapasitet ---


def test_kapasitetstrinn(faktura_mars_2026):
    """Kapasitet 2-5 kW = 250 kr/mnd."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    # Trinn 2: 2-5 kW
    assert bkk["kapasitetstrinn"][1] == (5, 250)
    assert faktura_mars_2026["forventet_kapasitet_kr"] == 250


def test_maks_effekt_gir_riktig_trinn(faktura_mars_2026):
    """Snitt av topp 3 (4.798, 4.557, 4.534) = 4.630 kW → trinn 2 (2-5 kW)."""
    topper = faktura_mars_2026["maks_effekt"]
    snitt = sum(topper) / len(topper)
    assert snitt == pytest.approx(4.630, abs=0.01)
    assert 2.0 < snitt <= 5.0  # trinn 2: 2-5 kW


# --- Norgespris ---


def test_norgespris_kompensasjon(faktura_mars_2026):
    """Norgespris: 1553.217 kWh * -0.99837 kr/kWh = -1550.68 kr."""
    beregnet = faktura_mars_2026["forbruk_total_kwh"] * faktura_mars_2026["norgespris_snitt_kr_per_kwh"]
    assert beregnet == pytest.approx(faktura_mars_2026["forventet_norgespris_kr"], abs=0.10)


def test_norgespris_fastpris_matcher_const():
    """Vår Norgespris-konstant: 50 øre/kWh inkl. mva for Sør-Norge."""
    assert NORGESPRIS_INKL_MVA_STANDARD == 0.50


# --- Nettleie total ---


def test_nettleie_total(faktura_mars_2026):
    """Nettleie = energiledd dag + natt + kapasitet + forbruksavgift + enova = 801.66 kr."""
    f = faktura_mars_2026
    beregnet = (
        f["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
        + f["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
        + f["forventet_kapasitet_kr"]
        + f["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
        + f["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    )
    assert beregnet == pytest.approx(f["forventet_nettleie_kr"], rel=0.01)


def test_total_inkl_norgespris(faktura_mars_2026):
    """Total = nettleie + norgespris = 801.66 + (-1550.68) = -749.02 kr."""
    total = faktura_mars_2026["forventet_nettleie_kr"] + faktura_mars_2026["forventet_norgespris_kr"]
    assert total == pytest.approx(faktura_mars_2026["forventet_total_kr"], abs=0.01)


def test_mva_beregning(faktura_mars_2026):
    """MVA = nettleie eks. mva * 25%. Nettleie inkl. mva = 801.66, herav MVA 160.33."""
    nettleie_inkl = faktura_mars_2026["forventet_nettleie_kr"]
    mva = nettleie_inkl - nettleie_inkl / (1 + MVA_SATS)
    assert mva == pytest.approx(faktura_mars_2026["forventet_mva_kr"], abs=0.10)


# --- Integrasjon: dso.py matcher fakturaen ---


def test_bkk_energiledd_dag_matcher_faktura():
    """dso.py energiledd_dag = energiledd + forbruksavgift + enova (alt inkl. mva)."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    forventet = (BKK_ENERGILEDD_DAG_2026_ORE + BKK_FORBRUKSAVGIFT_2026_ORE + BKK_ENOVAAVGIFT_2026_ORE) / 100
    assert bkk["energiledd_dag"] == pytest.approx(forventet, abs=0.001)


def test_bkk_energiledd_natt_matcher_faktura():
    """dso.py energiledd_natt = energiledd + forbruksavgift + enova (alt inkl. mva)."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    forventet = (BKK_ENERGILEDD_NATT_2026_ORE + BKK_FORBRUKSAVGIFT_2026_ORE + BKK_ENOVAAVGIFT_2026_ORE) / 100
    assert bkk["energiledd_natt"] == pytest.approx(forventet, abs=0.001)


def test_reverse_energiledd_dag_eks_avgifter():
    """Reverse-beregning: energiledd_dag → eks. avgifter eks. mva (for fakturasammenligning)."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    energiledd_dag = bkk["energiledd_dag"]

    eks_avgifter = energiledd_dag / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
    eks_avgifter_ore = eks_avgifter * 100

    faktura_eks_mva = BKK_ENERGILEDD_DAG_2026_ORE / (1 + MVA_SATS)
    assert eks_avgifter_ore == pytest.approx(faktura_eks_mva, abs=0.05)


def test_reverse_energiledd_natt_eks_avgifter():
    """Reverse-beregning: energiledd_natt → eks. avgifter eks. mva."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    energiledd_natt = bkk["energiledd_natt"]

    eks_avgifter = energiledd_natt / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
    eks_avgifter_ore = eks_avgifter * 100

    faktura_eks_mva = BKK_ENERGILEDD_NATT_2026_ORE / (1 + MVA_SATS)
    assert eks_avgifter_ore == pytest.approx(faktura_eks_mva, abs=0.05)


# --- End-to-end: MaanedligTotalSensor mot faktura ---


def test_maanedlig_total_sensor_matcher_faktura(faktura_mars_2026):
    """MaanedligTotalSensor med fakturadata skal gi korrekt nettleie-total.

    Regresjonstest: energiledd_dag/natt fra dso.py inkluderer allerede
    forbruksavgift og enova. Hvis sensoren legger til avgifter separat,
    vil totalen bli ~170 kr for høy (dobbelttelling).
    """
    import sys
    from unittest.mock import MagicMock

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

    from custom_components.stromkalkulator.dso import DSO_LIST
    from custom_components.stromkalkulator.sensor import MaanedligTotalSensor

    bkk = DSO_LIST["bkk"]
    f = faktura_mars_2026

    coord = MagicMock()
    coord.data = {
        "monthly_consumption_dag_kwh": f["forbruk_dag_kwh"],
        "monthly_consumption_natt_kwh": f["forbruk_natt_kwh"],
        "monthly_consumption_total_kwh": f["forbruk_total_kwh"],
        "energiledd_dag": bkk["energiledd_dag"],
        "energiledd_natt": bkk["energiledd_natt"],
        "kapasitetsledd": f["forventet_kapasitet_kr"],
        "stromstotte": 0.0,  # Norgespris-kunde, ingen strømstøtte
    }

    entry = MagicMock()
    entry.entry_id = "test"
    entry.data = {"tso": "bkk", "avgiftssone": "standard"}

    sensor = MaanedligTotalSensor(coord, entry)

    assert sensor.native_value == pytest.approx(
        f["forventet_nettleie_kr"], rel=0.01
    ), (
        f"MaanedligTotalSensor={sensor.native_value}, "
        f"faktura={f['forventet_nettleie_kr']}. "
        f"Hvis sensoren er ~160 kr for høy, dobbelttelles avgifter."
    )
