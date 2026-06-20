"""
Test mot BKK-fakturaer.

Dekker både 2026 (Norgespris-kunde) og 2025 (pre-Norgespris, strømstøtte-kunde).
Parametrisert per måned. Tester som kun verifiserer satser (ikke avhengig
av forbruk/periode) kjøres som ikke-parametriserte enkelttester.

Strømstøtte-terskel:
- 2025: 75 øre/kWh eks. mva = 93,75 øre inkl. mva, 90 % refusjon over
- 2026: 77 øre/kWh eks. mva = 96,25 øre inkl. mva, 90 % refusjon over
Koden i const.py har bare 2026-verdien. Strømstøtte-replay for 2025 er
derfor ikke dekket av disse testene (fixturen har heller ikke spotpris-data).
"""

import pytest

from custom_components.stromkalkulator.const import (
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
    NORGESPRIS_INKL_MVA_STANDARD,
    compute_energiledd_inkl_mva,
)

# BKK 2026-priser fra fakturaene (inkl. mva, eks. offentlige avgifter).
# Disse er måneds-uavhengige for hele 2026.
BKK_ENERGILEDD_DAG_2026_ORE = 35.963  # øre/kWh inkl. mva
BKK_ENERGILEDD_NATT_2026_ORE = 13.125  # øre/kWh inkl. mva
BKK_FORBRUKSAVGIFT_2026_ORE = 8.913  # øre/kWh inkl. mva
BKK_ENOVAAVGIFT_2026_ORE = 1.25  # øre/kWh inkl. mva

# BKK 2025-priser fra fakturaene (inkl. mva). Dag-tariff er uendret fra 2026,
# men natt-tariff og forbruksavgift er begge høyere. Disse er hentet rett fra
# faktura-PDF-ene for okt/nov/des 2025; vi har ikke disse i dso.py eller const.py
# fordi koden kun støtter inneværende sats-år.
BKK_ENERGILEDD_DAG_2025_ORE = 35.963  # øre/kWh inkl. mva (samme som 2026)
BKK_ENERGILEDD_NATT_2025_ORE = 23.738  # øre/kWh inkl. mva (ned til 13,125 i 2026)
BKK_FORBRUKSAVGIFT_2025_ORE = 15.662  # øre/kWh inkl. mva (ned til 8,913 i 2026)
BKK_ENOVAAVGIFT_2025_ORE = 1.25  # øre/kWh inkl. mva (uendret)


# --- Faktura-fixtures ---


FAKTURA_FEBRUAR_2026 = {
    "navn": "februar_2026",
    "fakturanr": "012345681",
    "periode_dager": 28,
    "forbruk_dag_kwh": 893.615,
    "forbruk_natt_kwh": 780.171,
    "forbruk_total_kwh": 1673.786,
    "maks_effekt": [5.909, 5.733, 5.477],
    "maks_effekt_snitt": 5.706,
    "kapasitetstrinn_indeks": 2,  # Trinn 3: 5-10 kW
    "kapasitetstrinn_grense": (10, 415),
    "kapasitetstrinn_min_kw": 5.0,
    "kapasitetstrinn_maks_kw": 10.0,
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
    "dobbelttelling_avvik_kr": 170,
}


FAKTURA_MARS_2026 = {
    "navn": "mars_2026",
    "fakturanr": "012345682",
    "periode_dager": 31,
    "forbruk_dag_kwh": 831.768,
    "forbruk_natt_kwh": 721.449,
    "forbruk_total_kwh": 1553.217,
    "maks_effekt": [4.798, 4.557, 4.534],
    "maks_effekt_snitt": 4.630,
    "kapasitetstrinn_indeks": 1,  # Trinn 2: 2-5 kW
    "kapasitetstrinn_grense": (5, 250),
    "kapasitetstrinn_min_kw": 2.0,
    "kapasitetstrinn_maks_kw": 5.0,
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
    "dobbelttelling_avvik_kr": 160,
}


FAKTURA_APRIL_2026 = {
    "navn": "april_2026",
    "fakturanr": "012345683",
    "periode_dager": 30,
    "forbruk_dag_kwh": 620.829,
    "forbruk_natt_kwh": 760.998,
    "forbruk_total_kwh": 1381.827,
    "maks_effekt": [5.939, 4.779, 4.262],
    "maks_effekt_snitt": 4.993,
    "kapasitetstrinn_indeks": 1,  # Trinn 2: 2-5 kW (akkurat under 5,0 kW-grensen)
    "kapasitetstrinn_grense": (5, 250),
    "kapasitetstrinn_min_kw": 2.0,
    "kapasitetstrinn_maks_kw": 5.0,
    "norgespris_snitt_kr_per_kwh": -1.0333,
    "forventet_energiledd_dag_kr": 223.26,
    "forventet_energiledd_natt_kr": 99.88,
    "forventet_norgespris_kr": -1427.89,
    "forventet_kapasitet_kr": 250.00,
    "forventet_forbruksavgift_kr": 123.16,
    "forventet_enovaavgift_kr": 17.28,
    "forventet_nettleie_kr": 713.58,
    "forventet_total_kr": -714.31,
    "forventet_mva_kr": 142.72,
    "dobbelttelling_avvik_kr": 140,
}


FAKTURA_MAI_2026 = {
    "navn": "mai_2026",
    "fakturanr": "012345684",
    "periode_dager": 31,
    "forbruk_dag_kwh": 518.142,
    "forbruk_natt_kwh": 661.161,
    "forbruk_total_kwh": 1179.303,
    "maks_effekt": [5.167, 4.553, 4.357],
    "maks_effekt_snitt": 4.692,
    "kapasitetstrinn_indeks": 1,  # Trinn 2: 2-5 kW
    "kapasitetstrinn_grense": (5, 250),
    "kapasitetstrinn_min_kw": 2.0,
    "kapasitetstrinn_maks_kw": 5.0,
    "norgespris_snitt_kr_per_kwh": -0.87557,
    "forventet_energiledd_dag_kr": 186.34,
    "forventet_energiledd_natt_kr": 86.77,
    "forventet_norgespris_kr": -1032.56,
    "forventet_kapasitet_kr": 250.00,
    "forventet_forbruksavgift_kr": 105.10,
    "forventet_enovaavgift_kr": 14.74,
    "forventet_nettleie_kr": 642.95,
    "forventet_total_kr": -389.61,
    "forventet_mva_kr": 128.59,
    "dobbelttelling_avvik_kr": 120,
}


@pytest.fixture(
    params=[FAKTURA_FEBRUAR_2026, FAKTURA_MARS_2026, FAKTURA_APRIL_2026, FAKTURA_MAI_2026],
    ids=["februar_2026", "mars_2026", "april_2026", "mai_2026"],
)
def faktura(request):
    """BKK-faktura for én måned. Norgespris-kunde."""
    return request.param


# --- Pre-Norgespris-fakturaer (2025) ---
#
# Oktober, november og desember 2025 er pre-Norgespris (ordningen startet
# 1. oktober 2025, men disse fakturaene viser kun strømstøtte). Felles
# struktur, men 2025-priser. `forventet_stromstotte_kr` er fra fakturaen
# og kan ikke replayes mot coordinator fordi fixturene mangler spotpris-data
# og const.STROMSTOTTE_LEVEL er hardkodet til 2026-verdi.


FAKTURA_OKTOBER_2025 = {
    "navn": "oktober_2025",
    "fakturanr": "",  # ikke oppgitt i fakturaen
    "periode_dager": 31,
    "forbruk_dag_kwh": 707.090,
    "forbruk_natt_kwh": 536.117,
    "forbruk_total_kwh": 1243.207,
    "maks_effekt": [5.714, 5.475, 5.238],
    "maks_effekt_snitt": 5.476,
    "kapasitetstrinn_indeks": 2,  # Trinn 3: 5-10 kW
    "kapasitetstrinn_grense": (10, 415),
    "kapasitetstrinn_min_kw": 5.0,
    "kapasitetstrinn_maks_kw": 10.0,
    "stromstotte_snitt_ore_per_kwh": -6.188,  # gjelder kun de timer som er over terskel
    "forventet_energiledd_dag_kr": 254.29,
    "forventet_energiledd_natt_kr": 127.26,
    "forventet_stromstotte_kr": -7.16,
    "forventet_kapasitet_kr": 415.00,
    "forventet_forbruksavgift_kr": 194.72,
    "forventet_enovaavgift_kr": 15.54,
    "forventet_nettleie_kr": 1006.81,
    "forventet_total_kr": 999.65,
}


FAKTURA_NOVEMBER_2025 = {
    "navn": "november_2025",
    "fakturanr": "",
    "periode_dager": 30,
    "forbruk_dag_kwh": 709.157,
    "forbruk_natt_kwh": 765.349,
    "forbruk_total_kwh": 1474.506,
    "maks_effekt": [6.776, 5.451, 5.434],
    "maks_effekt_snitt": 5.887,
    "kapasitetstrinn_indeks": 2,  # Trinn 3: 5-10 kW
    "kapasitetstrinn_grense": (10, 415),
    "kapasitetstrinn_min_kw": 5.0,
    "kapasitetstrinn_maks_kw": 10.0,
    "stromstotte_snitt_ore_per_kwh": -43.381,
    "forventet_energiledd_dag_kr": 255.03,
    "forventet_energiledd_natt_kr": 181.68,
    "forventet_stromstotte_kr": -404.80,
    "forventet_kapasitet_kr": 415.00,
    "forventet_forbruksavgift_kr": 230.94,
    "forventet_enovaavgift_kr": 18.43,
    "forventet_nettleie_kr": 1101.08,
    "forventet_total_kr": 696.28,
}


FAKTURA_DESEMBER_2025 = {
    "navn": "desember_2025",
    "fakturanr": "",
    "periode_dager": 31,
    "forbruk_dag_kwh": 667.422,
    "forbruk_natt_kwh": 887.299,
    "forbruk_total_kwh": 1554.721,
    "maks_effekt": [6.233, 5.656, 5.572],
    "maks_effekt_snitt": 5.820,
    "kapasitetstrinn_indeks": 2,  # Trinn 3: 5-10 kW
    "kapasitetstrinn_grense": (10, 415),
    "kapasitetstrinn_min_kw": 5.0,
    "kapasitetstrinn_maks_kw": 10.0,
    "stromstotte_snitt_ore_per_kwh": -11.054,
    "forventet_energiledd_dag_kr": 240.03,
    "forventet_energiledd_natt_kr": 210.63,
    "forventet_stromstotte_kr": -122.39,
    "forventet_kapasitet_kr": 415.00,
    "forventet_forbruksavgift_kr": 243.50,
    "forventet_enovaavgift_kr": 19.43,
    "forventet_nettleie_kr": 1128.59,
    "forventet_total_kr": 1006.20,
}


@pytest.fixture(
    params=[FAKTURA_OKTOBER_2025, FAKTURA_NOVEMBER_2025, FAKTURA_DESEMBER_2025],
    ids=["oktober_2025", "november_2025", "desember_2025"],
)
def faktura_2025(request):
    """BKK-faktura for én måned i 2025 (pre-Norgespris, strømstøtte-kunde)."""
    return request.param


# --- Energiledd ---


def test_energiledd_dag(faktura):
    """Energiledd dag = forbruk_dag * 35.963 øre/kWh."""
    beregnet = faktura["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
    assert beregnet == pytest.approx(faktura["forventet_energiledd_dag_kr"], abs=0.10)


def test_energiledd_natt(faktura):
    """Energiledd natt = forbruk_natt * 13.125 øre/kWh."""
    beregnet = faktura["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura["forventet_energiledd_natt_kr"], abs=0.10)


# --- Avgifter ---


def test_forbruksavgift(faktura):
    """Forbruksavgift = forbruk_total * 8.913 øre/kWh."""
    beregnet = faktura["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura["forventet_forbruksavgift_kr"], abs=0.10)


def test_forbruksavgift_matcher_const():
    """Vår FORBRUKSAVGIFT_ALMINNELIG * 1.25 = fakturans 8.913 øre/kWh."""
    beregnet_inkl_mva = FORBRUKSAVGIFT_ALMINNELIG * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_FORBRUKSAVGIFT_2026_ORE, abs=0.01)


def test_enovaavgift(faktura):
    """Enovaavgift = forbruk_total * 1.25 øre/kWh."""
    beregnet = faktura["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    assert beregnet == pytest.approx(faktura["forventet_enovaavgift_kr"], abs=0.10)


def test_enovaavgift_matcher_const():
    """Vår ENOVA_AVGIFT * 1.25 = fakturans 1.25 øre/kWh."""
    beregnet_inkl_mva = ENOVA_AVGIFT * (1 + MVA_SATS) * 100  # øre
    assert beregnet_inkl_mva == pytest.approx(BKK_ENOVAAVGIFT_2026_ORE, abs=0.01)


# --- Kapasitet ---


def test_kapasitetstrinn(faktura):
    """Kapasitetstrinn fra dso.py matcher fakturaens beløp."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    assert bkk["kapasitetstrinn"][faktura["kapasitetstrinn_indeks"]] == faktura["kapasitetstrinn_grense"]
    assert faktura["forventet_kapasitet_kr"] == faktura["kapasitetstrinn_grense"][1]


def test_maks_effekt_gir_riktig_trinn(faktura):
    """Snitt av topp 3 maks-effekt skal lande i forventet kapasitetstrinn."""
    topper = faktura["maks_effekt"]
    snitt = sum(topper) / len(topper)
    assert snitt == pytest.approx(faktura["maks_effekt_snitt"], abs=0.01)
    assert faktura["kapasitetstrinn_min_kw"] < snitt <= faktura["kapasitetstrinn_maks_kw"]


# --- Norgespris ---


def test_norgespris_kompensasjon(faktura):
    """Norgespris = forbruk_total * snittpris_kr_per_kwh (negativt = tilgode)."""
    beregnet = faktura["forbruk_total_kwh"] * faktura["norgespris_snitt_kr_per_kwh"]
    assert beregnet == pytest.approx(faktura["forventet_norgespris_kr"], abs=0.10)


def test_norgespris_fastpris_matcher_const():
    """Vår Norgespris-konstant: 50 øre/kWh inkl. mva for Sør-Norge."""
    assert NORGESPRIS_INKL_MVA_STANDARD == 0.50


# --- Nettleie total ---


def test_nettleie_total(faktura):
    """Nettleie = energiledd dag + natt + kapasitet + forbruksavgift + enova."""
    f = faktura
    beregnet = (
        f["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2026_ORE / 100
        + f["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2026_ORE / 100
        + f["forventet_kapasitet_kr"]
        + f["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2026_ORE / 100
        + f["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2026_ORE / 100
    )
    assert beregnet == pytest.approx(f["forventet_nettleie_kr"], rel=0.01)


def test_total_inkl_norgespris(faktura):
    """Total = nettleie + norgespris."""
    total = faktura["forventet_nettleie_kr"] + faktura["forventet_norgespris_kr"]
    assert total == pytest.approx(faktura["forventet_total_kr"], abs=0.01)


def test_mva_beregning(faktura):
    """MVA = nettleie inkl. mva, herav 25%."""
    nettleie_inkl = faktura["forventet_nettleie_kr"]
    mva = nettleie_inkl - nettleie_inkl / (1 + MVA_SATS)
    assert mva == pytest.approx(faktura["forventet_mva_kr"], abs=0.10)


# --- Integrasjon: dso.py matcher fakturaen ---


def test_bkk_energiledd_dag_eks_mva_matcher_faktura():
    """dso.py energiledd_dag_eks_mva er ren nettleie eks. forbruksavgift/Enova/mva.

    Faktura viser 35,963 øre/kWh inkl. mva (eks. avgifter). Eks-mva-baseverdien
    skal matche 35,963 / 1,25 = 28,7704 øre/kWh.
    """
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    faktura_eks_mva_ore = BKK_ENERGILEDD_DAG_2026_ORE / (1 + MVA_SATS)
    assert bkk["energiledd_dag_eks_mva"] * 100 == pytest.approx(faktura_eks_mva_ore, abs=0.01)


def test_bkk_energiledd_natt_eks_mva_matcher_faktura():
    """dso.py energiledd_natt_eks_mva er ren nettleie eks. forbruksavgift/Enova/mva."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    faktura_eks_mva_ore = BKK_ENERGILEDD_NATT_2026_ORE / (1 + MVA_SATS)
    assert bkk["energiledd_natt_eks_mva"] * 100 == pytest.approx(faktura_eks_mva_ore, abs=0.01)


def test_compute_energiledd_dag_inkl_matcher_faktura():
    """compute_energiledd_inkl_mva(eks_mva, sone) skal gi fakturans inkl-pris."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    inkl = compute_energiledd_inkl_mva(bkk["energiledd_dag_eks_mva"], "standard")
    forventet_kr = (BKK_ENERGILEDD_DAG_2026_ORE + BKK_FORBRUKSAVGIFT_2026_ORE + BKK_ENOVAAVGIFT_2026_ORE) / 100
    # < 0,01 kr/kWh avvik (~0,1 øre), vesentlig bedre enn 0.5% gammel struktur
    assert inkl == pytest.approx(forventet_kr, abs=0.0001)


def test_compute_energiledd_natt_inkl_matcher_faktura():
    """compute_energiledd_inkl_mva for natt-tariff."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    inkl = compute_energiledd_inkl_mva(bkk["energiledd_natt_eks_mva"], "standard")
    forventet_kr = (BKK_ENERGILEDD_NATT_2026_ORE + BKK_FORBRUKSAVGIFT_2026_ORE + BKK_ENOVAAVGIFT_2026_ORE) / 100
    assert inkl == pytest.approx(forventet_kr, abs=0.0001)


def test_reverse_energiledd_dag_eks_avgifter():
    """Reverse-sjekk: compute_energiledd_inkl_mva er invers av eks-mva-base."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    inkl = compute_energiledd_inkl_mva(bkk["energiledd_dag_eks_mva"], "standard")

    eks_avgifter = inkl / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
    assert eks_avgifter * 100 == pytest.approx(bkk["energiledd_dag_eks_mva"] * 100, abs=0.001)


def test_reverse_energiledd_natt_eks_avgifter():
    """Reverse-sjekk for natt-tariff."""
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    inkl = compute_energiledd_inkl_mva(bkk["energiledd_natt_eks_mva"], "standard")

    eks_avgifter = inkl / (1 + MVA_SATS) - FORBRUKSAVGIFT_ALMINNELIG - ENOVA_AVGIFT
    assert eks_avgifter * 100 == pytest.approx(bkk["energiledd_natt_eks_mva"] * 100, abs=0.001)


# --- End-to-end: MaanedligTotalSensor mot faktura ---


def test_maanedlig_total_sensor_matcher_faktura(faktura):
    """MaanedligTotalSensor med fakturadata skal gi korrekt nettleie-total.

    Regresjonstest: energiledd_dag/natt fra dso.py inkluderer allerede
    forbruksavgift og enova. Hvis sensoren legger til avgifter separat,
    vil totalen bli ~160-170 kr for høy (dobbelttelling).
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
    f = faktura

    # Coordinator beregner inkl-mva-verdier fra eks-mva-base ved oppstart.
    energiledd_dag = compute_energiledd_inkl_mva(bkk["energiledd_dag_eks_mva"], "standard")
    energiledd_natt = compute_energiledd_inkl_mva(bkk["energiledd_natt_eks_mva"], "standard")

    coord = MagicMock()
    coord.data = {
        "monthly_consumption_dag_kwh": f["forbruk_dag_kwh"],
        "monthly_consumption_natt_kwh": f["forbruk_natt_kwh"],
        "monthly_consumption_total_kwh": f["forbruk_total_kwh"],
        "energiledd_dag": energiledd_dag,
        "energiledd_natt": energiledd_natt,
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
        f"Hvis sensoren er ~{f['dobbelttelling_avvik_kr']} kr for høy, dobbelttelles avgifter."
    )


# ============================================================================
# 2025-fakturaer (pre-Norgespris)
# ============================================================================
# Verifiserer at fakturaens beløp er internt konsistente med 2025-satser.
# 2025-tariffene finnes ikke i koden (dso.py og const.py har bare 2026), så
# disse testene er ren faktura-verifikasjon, ingen integrasjon mot const.


def test_2025_energiledd_dag(faktura_2025):
    """Energiledd dag = forbruk_dag * 35.963 øre/kWh (samme sats som 2026)."""
    beregnet = faktura_2025["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_2025["forventet_energiledd_dag_kr"], abs=0.10)


def test_2025_energiledd_natt(faktura_2025):
    """Energiledd natt = forbruk_natt * 23.738 øre/kWh (2025-sats, høyere enn 2026)."""
    beregnet = faktura_2025["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_2025["forventet_energiledd_natt_kr"], abs=0.10)


def test_2025_forbruksavgift(faktura_2025):
    """Forbruksavgift 2025 = forbruk_total * 15.662 øre/kWh."""
    beregnet = faktura_2025["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_2025["forventet_forbruksavgift_kr"], abs=0.10)


def test_2025_enovaavgift(faktura_2025):
    """Enovaavgift = forbruk_total * 1.25 øre/kWh."""
    beregnet = faktura_2025["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2025_ORE / 100
    assert beregnet == pytest.approx(faktura_2025["forventet_enovaavgift_kr"], abs=0.10)


def test_2025_kapasitetstrinn(faktura_2025):
    """Kapasitetstrinn fra dso.py matcher fakturaens beløp.

    Trinn-grensene har vært uendret 2025→2026, så DSO_LIST["bkk"] kan brukes.
    """
    from custom_components.stromkalkulator.dso import DSO_LIST

    bkk = DSO_LIST["bkk"]
    assert bkk["kapasitetstrinn"][faktura_2025["kapasitetstrinn_indeks"]] == (
        faktura_2025["kapasitetstrinn_grense"]
    )
    assert faktura_2025["forventet_kapasitet_kr"] == faktura_2025["kapasitetstrinn_grense"][1]


def test_2025_maks_effekt_gir_riktig_trinn(faktura_2025):
    """Snitt av topp 3 timesnitt-kW skal lande i forventet kapasitetstrinn."""
    topper = faktura_2025["maks_effekt"]
    snitt = sum(topper) / len(topper)
    assert snitt == pytest.approx(faktura_2025["maks_effekt_snitt"], abs=0.01)
    assert (
        faktura_2025["kapasitetstrinn_min_kw"]
        < snitt
        <= faktura_2025["kapasitetstrinn_maks_kw"]
    )


def test_2025_nettleie_total(faktura_2025):
    """Nettleie = energiledd dag + natt + kapasitet + forbruksavgift + enova."""
    f = faktura_2025
    beregnet = (
        f["forbruk_dag_kwh"] * BKK_ENERGILEDD_DAG_2025_ORE / 100
        + f["forbruk_natt_kwh"] * BKK_ENERGILEDD_NATT_2025_ORE / 100
        + f["forventet_kapasitet_kr"]
        + f["forbruk_total_kwh"] * BKK_FORBRUKSAVGIFT_2025_ORE / 100
        + f["forbruk_total_kwh"] * BKK_ENOVAAVGIFT_2025_ORE / 100
    )
    assert beregnet == pytest.approx(f["forventet_nettleie_kr"], rel=0.01)


def test_2025_total_inkl_stromstotte(faktura_2025):
    """Total å betale = nettleie + strømstøtte (negativt = refusjon)."""
    f = faktura_2025
    total = f["forventet_nettleie_kr"] + f["forventet_stromstotte_kr"]
    assert total == pytest.approx(f["forventet_total_kr"], abs=0.05)


def test_2025_stromstotte_intern_konsistens(faktura_2025):
    """Strømstøtte-snittsats * antall kompenserte kWh skal matche kr-beløp.

    Fakturaen oppgir et snitt øre/kWh som gjelder kun kompenserte timer
    (kWh over terskel). Vi sjekker bare at oppgitt snitt * fakturertes
    grunnlag er konsistent, ikke at coordinator beregner samme tall,
    siden STROMSTOTTE_LEVEL i const.py er 2026-verdi.
    """
    f = faktura_2025
    # Hvor mye refusjon hadde vi fått om alt forbruk var over terskel?
    maks_mulig = f["forbruk_total_kwh"] * f["stromstotte_snitt_ore_per_kwh"] / 100
    # Faktisk refusjon er |forventet_stromstotte_kr| ≤ |maks_mulig|
    assert abs(f["forventet_stromstotte_kr"]) <= abs(maks_mulig) + 0.10


# --- 2025-natt-tariff vs. 2026, sanity check ---


def test_2025_natt_hoyere_enn_2026():
    """2025-natt-tariff (23,738 øre/kWh) er ~10 øre høyere enn 2026 (13,125)."""
    assert BKK_ENERGILEDD_NATT_2025_ORE > BKK_ENERGILEDD_NATT_2026_ORE
    differanse = BKK_ENERGILEDD_NATT_2025_ORE - BKK_ENERGILEDD_NATT_2026_ORE
    assert differanse == pytest.approx(10.613, abs=0.001)


def test_2025_forbruksavgift_hoyere_enn_2026():
    """2025-forbruksavgift (15,662 øre/kWh) er ~6,7 øre høyere enn 2026 (8,913)."""
    assert BKK_FORBRUKSAVGIFT_2025_ORE > BKK_FORBRUKSAVGIFT_2026_ORE
    differanse = BKK_FORBRUKSAVGIFT_2025_ORE - BKK_FORBRUKSAVGIFT_2026_ORE
    assert differanse == pytest.approx(6.749, abs=0.001)
