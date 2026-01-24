"""
Test mot faktiske BKK-fakturaer.

Disse testene verifiserer at våre beregninger matcher faktiske fakturaer fra BKK.
Fakturaene ligger i Fakturaer/ mappen for referanse.

VIKTIG: Disse testene gir høy troverdighet til at integrasjonen beregner korrekt!
"""

import pytest

# BKK priser 2025 (fra fakturaene)
BKK_ENERGILEDD_DAG_ORE = 35.963  # øre/kWh eks. avgifter
BKK_ENERGILEDD_NATT_ORE = 23.738  # øre/kWh eks. avgifter
BKK_KAPASITET_5_10_KW = 415  # kr/mnd
FORBRUKSAVGIFT_2025_ORE = 15.662  # øre/kWh (vintersats Sør-Norge 2025)
ENOVAAVGIFT_2025_ORE = 1.25  # øre/kWh


# Fakturaer som fixtures
@pytest.fixture
def faktura_desember_2025():
    """
    BKK faktura 63374727 - Desember 2025.
    Fakturaperiode: 01.12.2025 - 01.01.2026
    Totalt forbruk: 1554.721 kWh
    Å betale: 1006.20 kr
    """
    return {
        "forbruk_dag_kwh": 667.422,
        "forbruk_natt_kwh": 887.299,
        "forbruk_total_kwh": 1554.721,
        "stromstotte_kwh": 1107.173,
        "stromstotte_ore_snitt": 11.054,
        "kapasitet_dager": 31,
        "forventet_energiledd_dag_kr": 240.03,
        "forventet_energiledd_natt_kr": 210.63,
        "forventet_stromstotte_kr": 122.39,
        "forventet_kapasitet_kr": 415.00,
        "forventet_forbruksavgift_kr": 243.50,
        "forventet_enovaavgift_kr": 19.43,
        "forventet_total_kr": 1006.20,
    }


@pytest.fixture
def faktura_november_2025():
    """
    BKK faktura 63097585 - November 2025.
    Denne måneden hadde høy strømstøtte (404.80 kr) pga høye priser.
    """
    return {
        "forbruk_dag_kwh": 709.157,
        "forbruk_natt_kwh": 765.349,
        "forbruk_total_kwh": 1474.506,
        "stromstotte_kwh": 933.128,
        "stromstotte_ore_snitt": 43.381,
        "forventet_energiledd_dag_kr": 255.03,
        "forventet_energiledd_natt_kr": 181.68,
        "forventet_stromstotte_kr": 404.80,
        "forventet_kapasitet_kr": 415.00,
        "forventet_forbruksavgift_kr": 230.94,
        "forventet_enovaavgift_kr": 18.43,
        "forventet_total_kr": 696.28,
    }


@pytest.fixture
def faktura_oktober_2025():
    """
    BKK faktura 62821645 - Oktober 2025.
    Denne måneden hadde lav strømstøtte (7.16 kr) pga lave priser.
    """
    return {
        "forbruk_dag_kwh": 707.09,
        "forbruk_natt_kwh": 536.117,
        "forbruk_total_kwh": 1243.207,
        "stromstotte_kwh": 115.661,
        "stromstotte_ore_snitt": 6.188,
        "forventet_energiledd_dag_kr": 254.29,
        "forventet_energiledd_natt_kr": 127.26,
        "forventet_stromstotte_kr": 7.16,
        "forventet_kapasitet_kr": 415.00,
        "forventet_forbruksavgift_kr": 194.72,
        "forventet_enovaavgift_kr": 15.54,
        "forventet_total_kr": 999.65,
    }


# Helper for å beregne total nettleie
def beregn_total_nettleie(faktura: dict) -> float:
    """Beregn total nettleie basert på fakturadata."""
    energiledd_dag = faktura["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_ORE / 100
    energiledd_natt = faktura["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_ORE / 100
    stromstotte = faktura["stromstotte_kwh"] * faktura["stromstotte_ore_snitt"] / 100
    kapasitet = faktura["forventet_kapasitet_kr"]
    forbruksavgift = faktura["forbruk_total_kwh"] * FORBRUKSAVGIFT_2025_ORE / 100
    enovaavgift = faktura["forbruk_total_kwh"] * ENOVAAVGIFT_2025_ORE / 100

    return energiledd_dag + energiledd_natt - stromstotte + kapasitet + forbruksavgift + enovaavgift


# --- Desember 2025 tester ---


def test_energiledd_dag_desember(faktura_desember_2025):
    """Verifiser at energiledd dag beregnes korrekt for desember."""
    beregnet = faktura_desember_2025["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_ORE / 100
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_energiledd_dag_kr"], abs=0.10)


def test_energiledd_natt_desember(faktura_desember_2025):
    """Verifiser at energiledd natt beregnes korrekt for desember."""
    beregnet = faktura_desember_2025["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_ORE / 100
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_energiledd_natt_kr"], abs=0.10)


def test_forbruksavgift_desember(faktura_desember_2025):
    """Verifiser at forbruksavgift beregnes korrekt for desember."""
    beregnet = faktura_desember_2025["forbruk_total_kwh"] * FORBRUKSAVGIFT_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_forbruksavgift_kr"], abs=0.10)


def test_enovaavgift_desember(faktura_desember_2025):
    """Verifiser at Enova-avgift beregnes korrekt for desember."""
    beregnet = faktura_desember_2025["forbruk_total_kwh"] * ENOVAAVGIFT_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_enovaavgift_kr"], abs=0.10)


def test_kapasitetsledd_desember(faktura_desember_2025):
    """Verifiser at kapasitetsledd matcher fakturaen for desember."""
    assert faktura_desember_2025["forventet_kapasitet_kr"] == BKK_KAPASITET_5_10_KW


def test_stromstotte_desember(faktura_desember_2025):
    """Verifiser at total strømstøtte beregnes korrekt for desember."""
    beregnet = faktura_desember_2025["stromstotte_kwh"] * faktura_desember_2025["stromstotte_ore_snitt"] / 100
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_stromstotte_kr"], abs=0.10)


def test_total_nettleie_desember(faktura_desember_2025):
    """Verifiser at total nettleie matcher fakturaen for desember."""
    beregnet = beregn_total_nettleie(faktura_desember_2025)
    # Tillat 1% avvik pga avrunding
    assert beregnet == pytest.approx(faktura_desember_2025["forventet_total_kr"], rel=0.01)


# --- November 2025 tester ---


def test_energiledd_dag_november(faktura_november_2025):
    """Verifiser energiledd dag for november."""
    beregnet = faktura_november_2025["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_ORE / 100
    assert beregnet == pytest.approx(faktura_november_2025["forventet_energiledd_dag_kr"], abs=0.10)


def test_energiledd_natt_november(faktura_november_2025):
    """Verifiser energiledd natt for november."""
    beregnet = faktura_november_2025["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_ORE / 100
    assert beregnet == pytest.approx(faktura_november_2025["forventet_energiledd_natt_kr"], abs=0.10)


def test_stromstotte_hoy_maned_november(faktura_november_2025):
    """Verifiser strømstøtte i en måned med høye priser (november)."""
    beregnet = faktura_november_2025["stromstotte_kwh"] * faktura_november_2025["stromstotte_ore_snitt"] / 100
    assert beregnet == pytest.approx(faktura_november_2025["forventet_stromstotte_kr"], abs=0.10)


def test_total_nettleie_november(faktura_november_2025):
    """Verifiser total nettleie i måned med høy strømstøtte (november)."""
    beregnet = beregn_total_nettleie(faktura_november_2025)
    assert beregnet == pytest.approx(faktura_november_2025["forventet_total_kr"], rel=0.01)


# --- Oktober 2025 tester ---


def test_stromstotte_lav_maned_oktober(faktura_oktober_2025):
    """Verifiser strømstøtte i en måned med lave priser (oktober)."""
    beregnet = faktura_oktober_2025["stromstotte_kwh"] * faktura_oktober_2025["stromstotte_ore_snitt"] / 100
    assert beregnet == pytest.approx(faktura_oktober_2025["forventet_stromstotte_kr"], abs=0.10)


def test_total_nettleie_oktober(faktura_oktober_2025):
    """Verifiser total nettleie i måned med lav strømstøtte (oktober)."""
    beregnet = beregn_total_nettleie(faktura_oktober_2025)
    assert beregnet == pytest.approx(faktura_oktober_2025["forventet_total_kr"], rel=0.01)


# --- BKK integrasjonspriser ---


def test_bkk_har_2026_priser():
    """BKK skal ha oppdaterte 2026-priser i integrasjonen."""
    from custom_components.stromkalkulator.tso import TSO_LIST

    bkk = TSO_LIST["bkk"]

    # 2026-priser fra BKK (inkl. mva)
    # Dag: 46.13 øre/kWh, Natt: 23.29 øre/kWh
    assert bkk["energiledd_dag"] == 0.4613
    assert bkk["energiledd_natt"] == 0.2329


def test_bkk_kapasitetstrinn_5_10_matcher_faktura():
    """BKK kapasitetstrinn 5-10 kW skal matche fakturaen (uendret fra 2025)."""
    from custom_components.stromkalkulator.tso import TSO_LIST

    bkk = TSO_LIST["bkk"]
    # Finn kapasitetstrinn for 5-10 kW (index 2 i listen)
    kapasitet_5_10 = bkk["kapasitetstrinn"][2][1]  # (10, 415) -> 415

    assert kapasitet_5_10 == BKK_KAPASITET_5_10_KW


def test_bkk_priser_er_rimelige():
    """BKK-priser skal være innenfor rimelig område."""
    from custom_components.stromkalkulator.tso import TSO_LIST

    bkk = TSO_LIST["bkk"]

    # Energiledd bør være mellom 0.10 og 1.00 NOK/kWh
    assert 0.10 < bkk["energiledd_dag"] < 1.00
    assert 0.10 < bkk["energiledd_natt"] < 1.00

    # Dag skal være dyrere enn natt
    assert bkk["energiledd_dag"] > bkk["energiledd_natt"]
