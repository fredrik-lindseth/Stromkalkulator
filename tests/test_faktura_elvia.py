"""Regresjon mot en ekte Elvia-faktura og Elhub-måleserie (NO1, august 2026).

Fixturen er anonymisert: den inneholder bare lokal intervallstart og kWh.
Fakturaen er den uavhengige fasiten for forbruk, tariffdeling og nettleie.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from custom_components.stromkalkulator.avregning import Tariff, Tariffregel
from custom_components.stromkalkulator.const import compute_energiledd_inkl_mva
from custom_components.stromkalkulator.dso import DSO_LIST

FIXTURE = Path(__file__).parent / "fixtures" / "elvia_august_2026.json"

# Elvia-faktura for 01.08.2026--01.09.2026. Alle beløp er inkl. mva.
FAKTURA = {
    "forbruk_kwh": 668.585,
    "dag_kwh": 354.306,
    "natt_kwh": 314.279,
    "dag_kr": 164.39,
    "natt_kr": 98.69,
    "kapasitet_kr": 250.00,
    "stromstonad_kr": -405.43,
    "nettleie_kr": 107.65,
    "topper_kw": (3.442, 3.479, 3.662),
}


def _timer() -> list[dict[str, object]]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["hours"]


def test_elhub_forbruk_og_tariffdeling_treffer_faktura() -> None:
    """Katalogens faktiske tariffregel deler den målte Elhub-serien riktig."""
    regel = Tariffregel()
    timer = _timer()
    dag = sum(
        float(time["kwh"])
        for time in timer
        if regel.tariff(datetime.fromisoformat(str(time["start_local"]))) is Tariff.DAG
    )
    natt = sum(float(time["kwh"]) for time in timer) - dag

    assert len(timer) == 744
    assert dag + natt == pytest.approx(FAKTURA["forbruk_kwh"], abs=1e-9)
    assert dag == pytest.approx(FAKTURA["dag_kwh"], abs=1e-9)
    assert natt == pytest.approx(FAKTURA["natt_kwh"], abs=1e-9)


def test_elvia_energiledd_treffer_fakturalinjene() -> None:
    """Elvias katalogsatser gir fakturaens to energiledd etter øreavrunding."""
    elvia = DSO_LIST["elvia"]
    dag_sats = compute_energiledd_inkl_mva(elvia["energiledd_dag_eks_mva"], "standard")
    natt_sats = compute_energiledd_inkl_mva(elvia["energiledd_natt_eks_mva"], "standard")

    # Fakturaens underliggende dagssats er 46,398 øre/kWh. Katalogen lagrer
    # den publiserte satsen med to desimaler (46,400 øre), som er < 1 øre på
    # hele fakturalinjen ved fakturaens avrunding.
    assert dag_sats == pytest.approx(0.4640, abs=1e-9)
    assert natt_sats == pytest.approx(0.3140, abs=1e-9)
    assert FAKTURA["dag_kwh"] * dag_sats == pytest.approx(FAKTURA["dag_kr"], abs=0.01)
    assert FAKTURA["natt_kwh"] * natt_sats == pytest.approx(FAKTURA["natt_kr"], abs=0.01)


def test_elvia_kapasitetstrinn_og_nettleie_treffer_faktura() -> None:
    """Tre reelle månedsmaks gir Elvias 2--5 kW-trinn og fakturasummen."""
    elvia = DSO_LIST["elvia"]
    snitt_topp = sum(FAKTURA["topper_kw"]) / len(FAKTURA["topper_kw"])
    kapasitet = next(kr for grense, kr in elvia["kapasitetstrinn"] if snitt_topp <= grense)

    assert snitt_topp == pytest.approx(3.528, abs=0.0005)
    assert kapasitet == FAKTURA["kapasitet_kr"]
    brutto = FAKTURA["dag_kr"] + FAKTURA["natt_kr"] + kapasitet
    assert brutto + FAKTURA["stromstonad_kr"] == pytest.approx(FAKTURA["nettleie_kr"], abs=0.005)
