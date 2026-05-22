"""
End-to-end snapshot-test fra ekte hourly måler-data til fakturasum.

Tar `tests/fixtures/bkk_april_2026_hourly.json` (720 timer med tpi-delta,
spotpris eks. mva og maks effekt) og kjører fakturaberegnings-logikken
over den. Verifiserer at hver linje matcher FAKTURA_APRIL_2026 i
test_faktura_bkk.py innenfor dokumentert sample-toleranse.

Fyller gapet mellom hourly måler-data og fakturasum som de aggregerte
testene i test_faktura_bkk.py ikke dekker.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import pytest

from custom_components.stromkalkulator.const import (
    DAY_RATE_END_HOUR,
    DAY_RATE_START_HOUR,
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
    NORGESPRIS_INKL_MVA_STANDARD,
    WEEKEND_WEEKDAY_START,
)
from custom_components.stromkalkulator.dso import DSO_LIST
from tests.test_faktura_bkk import (
    BKK_ENERGILEDD_DAG_2026_ORE,
    BKK_ENERGILEDD_NATT_2026_ORE,
    BKK_ENOVAAVGIFT_2026_ORE,
    BKK_FORBRUKSAVGIFT_2026_ORE,
    FAKTURA_APRIL_2026,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "bkk_april_2026_hourly.json"

# Bevegelige helligdager april 2026 (lokaltid, NO5).
# Skjærtorsdag, langfredag, 1. påskedag, 2. påskedag.
HELLIGDAGER_APRIL_2026 = {
    date(2026, 4, 2),
    date(2026, 4, 3),
    date(2026, 4, 5),
    date(2026, 4, 6),
}


@pytest.fixture(scope="module")
def hourly_data():
    """Last hourly snapshot for BKK april 2026."""
    with open(FIXTURE_PATH) as f:
        return json.load(f)


def _er_dag_time(iso_local: str) -> bool:
    """Sann hvis timen er dag-tariff: man-fre 06-22, ikke helligdag."""
    d = date.fromisoformat(iso_local[:10])
    time = int(iso_local[11:13])
    if d.weekday() >= WEEKEND_WEEKDAY_START:
        return False
    if d in HELLIGDAGER_APRIL_2026:
        return False
    return DAY_RATE_START_HOUR <= time < DAY_RATE_END_HOUR


def _split_dag_natt(hours):
    """Returner (dag_kwh, natt_kwh) basert på tariff-vinduer."""
    dag = sum(h["kwh"] for h in hours if _er_dag_time(h["start_local"]))
    natt = sum(h["kwh"] for h in hours if not _er_dag_time(h["start_local"]))
    return dag, natt


def _topp3_snitt_kw(hours):
    """Snitt av topp 3 høyeste timer per unike dato.

    `kwh` per time er numerisk identisk med snitt-effekt i kW når
    oppløsningen er én time. Det er denne størrelsen BKK bruker for
    kapasitetstrinn (ikke instantan toppeffekt).
    """
    per_dato: dict[str, float] = defaultdict(float)
    for h in hours:
        d = h["start_local"][:10]
        if h["kwh"] > per_dato[d]:
            per_dato[d] = h["kwh"]
    topp3 = sorted(per_dato.values(), reverse=True)[:3]
    return sum(topp3) / 3


def _norgespris_kompensasjon(hours) -> float:
    """Time-for-time Norgespris-komp, returnert som negativt beløp (tilgode).

    Spot er eks. mva. Skaler til inkl. mva før sammenligning med
    fastprisen 0,50 kr/kWh. Kun positiv differanse gir kompensasjon.
    """
    komp = 0.0
    for h in hours:
        spot_inkl_mva = h["spot_nok_kwh_eks_mva"] * (1 + MVA_SATS)
        diff = spot_inkl_mva - NORGESPRIS_INKL_MVA_STANDARD
        if diff > 0:
            komp += diff * h["kwh"]
    return -komp


# --- Enkeltlinjer ---


def test_total_kwh(hourly_data):
    """Sum av tpi-delta per time matcher fakturatotal innenfor 50 Wh."""
    total = sum(h["kwh"] for h in hourly_data["hours"])
    assert total == pytest.approx(FAKTURA_APRIL_2026["forbruk_total_kwh"], abs=0.05)


def test_dag_natt_split(hourly_data):
    """Dag/natt-klassifisering matcher fakturasplittt innenfor 100 Wh."""
    dag, natt = _split_dag_natt(hourly_data["hours"])
    assert dag == pytest.approx(FAKTURA_APRIL_2026["forbruk_dag_kwh"], abs=0.10)
    assert natt == pytest.approx(FAKTURA_APRIL_2026["forbruk_natt_kwh"], abs=0.10)


def test_topp_3_kapasitet(hourly_data):
    """Topp 3 høyeste timer per dato gir snitt i trinn 2 (2-5 kW)."""
    snitt = _topp3_snitt_kw(hourly_data["hours"])
    assert snitt == pytest.approx(FAKTURA_APRIL_2026["maks_effekt_snitt"], abs=0.1)
    assert (
        FAKTURA_APRIL_2026["kapasitetstrinn_min_kw"]
        < snitt
        <= FAKTURA_APRIL_2026["kapasitetstrinn_maks_kw"]
    )
    bkk = DSO_LIST["bkk"]
    trinn = bkk["kapasitetstrinn"][FAKTURA_APRIL_2026["kapasitetstrinn_indeks"]]
    assert trinn == FAKTURA_APRIL_2026["kapasitetstrinn_grense"]


def test_norgespris_kompensasjon(hourly_data):
    """Time-for-time Norgespris-komp matcher faktura innenfor 5 kr."""
    komp = _norgespris_kompensasjon(hourly_data["hours"])
    assert komp == pytest.approx(FAKTURA_APRIL_2026["forventet_norgespris_kr"], abs=5.0)


# --- End-to-end ---


def test_total_konsistens(hourly_data):
    """Alle fakturalinjer rekonstruert fra hourly data matcher FAKTURA_APRIL_2026."""
    hours = hourly_data["hours"]
    f = FAKTURA_APRIL_2026

    dag_kwh, natt_kwh = _split_dag_natt(hours)
    total_kwh = dag_kwh + natt_kwh

    energiledd_dag = dag_kwh * BKK_ENERGILEDD_DAG_2026_ORE / 100
    energiledd_natt = natt_kwh * BKK_ENERGILEDD_NATT_2026_ORE / 100
    forbruksavgift = total_kwh * BKK_FORBRUKSAVGIFT_2026_ORE / 100
    enovaavgift = total_kwh * BKK_ENOVAAVGIFT_2026_ORE / 100

    snitt_kw = _topp3_snitt_kw(hours)
    bkk = DSO_LIST["bkk"]
    kapasitet_kr = next(
        kr for grense, kr in bkk["kapasitetstrinn"] if snitt_kw <= grense
    )
    norgespris = _norgespris_kompensasjon(hours)

    assert energiledd_dag == pytest.approx(f["forventet_energiledd_dag_kr"], abs=0.10)
    assert energiledd_natt == pytest.approx(f["forventet_energiledd_natt_kr"], abs=0.10)
    assert forbruksavgift == pytest.approx(f["forventet_forbruksavgift_kr"], abs=0.10)
    assert enovaavgift == pytest.approx(f["forventet_enovaavgift_kr"], abs=0.10)
    assert kapasitet_kr == f["forventet_kapasitet_kr"]
    assert norgespris == pytest.approx(f["forventet_norgespris_kr"], abs=5.0)

    nettleie = energiledd_dag + energiledd_natt + kapasitet_kr + forbruksavgift + enovaavgift
    assert nettleie == pytest.approx(f["forventet_nettleie_kr"], rel=0.01)

    total = nettleie + norgespris
    assert total == pytest.approx(f["forventet_total_kr"], abs=5.0)


def test_const_brukt_i_klassifisering():
    """Sanity: konstantene fra const.py matcher BKK-tariff-vinduet."""
    assert DAY_RATE_START_HOUR == 6
    assert DAY_RATE_END_HOUR == 22
    assert WEEKEND_WEEKDAY_START == 5
    assert FORBRUKSAVGIFT_ALMINNELIG == 0.0713
    assert ENOVA_AVGIFT == 0.01
