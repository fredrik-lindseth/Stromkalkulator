"""
Test mot BKK-faktura februar 2026.

Fakturaperiode: 01.02.2026 - 01.03.2026 (28 dager)
Norgespris-kunde (fast 50 øre/kWh inkl. mva)
Fakturanr: 063926706

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
BKK_KAPASITET_5_10_KW = 415  # kr/mnd


@pytest.fixture
def faktura_februar_2026():
    """BKK faktura 063926706 — Februar 2026.

    Norgespris-kunde. Tilgode 812.78 kr.
    Maks effekt: 5.909, 5.733, 5.477 kW → kapasitet 5-10 kW.
    """
    return {
        "periode_dager": 28,
        "forbruk_dag_kwh": 893.615,
        "forbruk_natt_kwh": 780.171,
        "forbruk_total_kwh": 1673.786,
        "maks_effekt": [5.909, 5.733, 5.477],
        "norgespris_snitt_kr_per_kwh": -1.0883,
        "forventet_energiledd_dag_kr": 321.36,
        "forventet_energiledd_natt_kr": 102.40,
        "forventet_norgespris_kr": -1821.64,
        "forventet_kapasitet_kr": 415.00,
        "forventet_forbruksavgift_kr": 149.17,
        "forventet_enovaavgift_kr": 20.93,
        "forventet_nettleie_kr": 1008.86,
        "forventet_total_kr": -812.78,
        "forventet_mva_kr": 201.77,
    }


# --- Energiledd ---


def test_energiledd_dag(faktura_februar_2026):
    """Energiledd dag: 893.615 kWh * 35.963 øre/kWh = 321.36 kr."""
    beregnet = faktura_februar_2026["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_februar_2026["forventet_energiledd_dag_kr"], abs=0.10)


def test_energiledd_natt(faktura_februar_2026):
    """Energiledd natt: 780.171 kWh * 13.125 øre/kWh = 102.40 kr."""
    beregnet = faktura_februar_2026["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_februar_2026["forventet_energiledd_natt_kr"], abs=0.10)


# --- Avgifter ---


def test_forbruksavgift(faktura_februar_2026):
    """Forbruksavgift: 1673.786 kWh * 8.913 øre/kWh = 149.17 kr."""
    beregnet = faktura_februar_2026["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_februar_2026["forventet_forbruksavgift_kr"], abs=0.10)


def test_forbruksavgift_matcher_const():
    """Vår FORBRUKSAVGIFT_ALMINNELIG * 1.25 = fakturans 8.913 øre/kWh."""
    beregnet_inkl_mva = FORBRUKSAVGIFT_ALMINNELIG * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_FORBRUKSAVGIFT_2026_ORE, abs=0.01)


def test_enovaavgift(faktura_februar_2026):
    """Enovaavgift: 1673.786 kWh * 1.25 øre/kWh = 20.93 kr."""
    beregnet = faktura_februar_2026["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura_februar_2026["forventet_enovaavgift_kr"], abs=0.10)


def test_enovaavgift_matcher_const():
    """Vår ENOVA_AVGIFT * 1.25 = fakturans 1.25 øre/kWh."""
    beregnet_inkl_mva = ENOVA_AVGIFT * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_ENOVAAVGIFT_2026_ORE, abs=0.01)


# --- Kapasitet ---


def test_kapasitetstrinn(faktura_februar_2026):
    """Kapasitet 5-10 kW = 415 kr/mnd."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    # Trinn 3: 5-10 kW
    assert bkk["kapasitetstrinn"][2] == (10, 415)
    assert faktura_februar_2026["forventet_kapasitet_kr"] == 415


def test_maks_effekt_gir_riktig_trinn(faktura_februar_2026):
    """Snitt av topp 3 (5.909, 5.733, 5.477) = 5.706 kW → trinn 3 (5-10 kW)."""
    topper = faktura_februar_2026["maks_effekt"]
    snitt = sum(topper) / len(topper)
    assert snitt == pytest.approx(5.706, abs=0.01)
    assert 5.0 < snitt <= 10.0  # trinn 3: 5-10 kW


# --- Norgespris ---


def test_norgespris_kompensasjon(faktura_februar_2026):
    """Norgespris: 1673.786 kWh * -1.0883 kr/kWh = -1821.64 kr."""
    beregnet = faktura_februar_2026["forbruk_total_kwh"] * faktura_februar_2026["norgespris_snitt_kr_per_kwh"]
    assert beregnet == pytest.approx(faktura_februar_2026["forventet_norgespris_kr"], abs=0.10)


def test_norgespris_fastpris_matcher_const():
    """Vår Norgespris-konstant: 50 øre/kWh inkl. mva for Sør-Norge."""
    assert NORGESPRIS_INKL_MVA_STANDARD == 0.50


# --- Nettleie total ---


def test_nettleie_total(faktura_februar_2026):
    """Nettleie = energiledd dag + natt + kapasitet + forbruksavgift + enova = 1008.86 kr."""
    f = faktura_februar_2026
    beregnet = (
        f["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
        + f["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
        + f["forventet_kapasitet_kr"]
        + f["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
        + f["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    )
    assert beregnet == pytest.approx(f["forventet_nettleie_kr"], rel=0.01)


def test_total_inkl_norgespris(faktura_februar_2026):
    """Total = nettleie + norgespris = 1008.86 + (-1821.64) = -812.78 kr."""
    total = faktura_februar_2026["forventet_nettleie_kr"] + faktura_februar_2026["forventet_norgespris_kr"]
    assert total == pytest.approx(faktura_februar_2026["forventet_total_kr"], abs=0.01)


def test_mva_beregning(faktura_februar_2026):
    """MVA = nettleie eks. mva * 25%. Nettleie inkl. mva = 1008.86, herav MVA 201.77."""
    nettleie_inkl = faktura_februar_2026["forventet_nettleie_kr"]
    mva = nettleie_inkl - nettleie_inkl / (1 + MVA_SATS)
    assert mva == pytest.approx(faktura_februar_2026["forventet_mva_kr"], abs=0.10)


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

    # Korrekt reverse: del på (1+mva) først, trekk fra avgifter
    eks_avgifter = energiledd_dag / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
    eks_avgifter_ore = eks_avgifter * 100

    # Faktura viser 35.963 øre inkl. mva → 28.770 øre eks. mva
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


def test_maanedlig_total_sensor_matcher_faktura(faktura_februar_2026):
    """MaanedligTotalSensor med fakturadata skal gi korrekt nettleie-total.

    Regresjonstest: energiledd_dag/natt fra dso.py inkluderer allerede
    forbruksavgift og enova. Hvis sensoren legger til avgifter separat,
    vil totalen bli ~170 kr for høy (dobbelttelling).
    """
    import sys
    from unittest.mock import MagicMock

    # Sett opp HA-mocks som test_monthly_sensors gjør
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
    f = faktura_februar_2026

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

    # Sensoren skal matche fakturaens nettleie-total (inkl. avgifter)
    assert sensor.native_value == pytest.approx(
        f["forventet_nettleie_kr"], rel=0.01
    ), (
        f"MaanedligTotalSensor={sensor.native_value}, "
        f"faktura={f['forventet_nettleie_kr']}. "
        f"Hvis sensoren er ~170 kr for høy, dobbelttelles avgifter."
    )
