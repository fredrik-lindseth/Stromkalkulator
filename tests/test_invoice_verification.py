"""Regresjoner funnet ved avstemming av BKK oktober 2026."""

from datetime import datetime
from itertools import pairwise

import pytest

from scripts.research import lag_replay_fixtures as fixtures
from scripts.research import verify_invoice_hourly as verification


@pytest.mark.parametrize(
    ("linje", "beregnet", "faktura", "ok"),
    [
        ("Total kWh", 1159.404, 1160.218, False),
        ("Total kWh", 1160.217, 1160.218, True),
        ("Forbruk natt kWh", 518.185, 518.956, False),
        ("Energiledd natt", 68.01, 68.11, False),
        ("Forbruksavgift", 103.34, 103.40, False),
        ("Enovaavgift", 14.50, 14.51, True),
        ("Kapasitet", 249.0, 250.0, False),
        ("Norgespris-komp", -1423.96, -1422.10, False),
        ("Total inkl. Norgespris", -757.51, -755.47, False),
    ],
)
def test_fakturaavvik_skal_ikke_skjules_av_en_prosent(linje, beregnet, faktura, ok):
    assert verification.innenfor_toleranse(linje, beregnet, faktura) is ok


def test_elhub_fixture_beholder_begge_vintertidstimer_i_tidsrekkefolge(monkeypatch):
    rader = {
        "2026-10-25T03:00:00+01:00": 3.0,
        "2026-10-25T02:00:00+01:00": 2.0,
        "2026-10-25T02:00:00+02:00": 1.0,
    }
    monkeypatch.setattr(fixtures.vne, "last_elhub", lambda navn: rader)
    monkeypatch.setattr(fixtures.vne, "elhub_csv", lambda navn: None)
    data = fixtures.bygg_elhub("oktober_2026")
    timer = data["hours"]
    assert [t["kwh"] for t in timer] == [1.0, 2.0, 3.0]
    tid = [datetime.fromisoformat(t["start_local"]).timestamp() for t in timer]
    assert [b - a for a, b in pairwise(tid)] == [3600, 3600]


def test_estimert_forbruk_blir_ikke_merket_som_malt(monkeypatch, tmp_path):
    sti = tmp_path / "elhub.csv"
    sti.write_text(
        "Fra;Volum;Kvalitet\n"
        "2026-10-25T22:00:00+01:00;1,420;Målt\n"
        "2026-10-25T23:00:00+01:00;1,370;Estimert\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(fixtures.vne, "elhub_csv", lambda navn: sti)
    data = fixtures.bygg_elhub("oktober_2026")
    assert data["metadata"]["kvalitetsavvik"] == {"2026-10-25T23:00:00+01:00": "Estimert"}
    assert "kvalitet «Målt»" not in data["metadata"]["kilde"]
    assert data["metadata"]["sum_kwh"] == 2.790


@pytest.mark.parametrize(("kompensasjon", "ok"), [(-1422.102465, True), (-1422.20, False)])
def test_komplett_elhub_kontrolleres_selv_om_han_har_hull(monkeypatch, capsys, kompensasjon, ok):
    monkeypatch.setattr(
        fixtures.vne,
        "analyser_maaned",
        lambda navn, skift: {
            "elhub_full": True,
            "komp_elhub": kompensasjon,
            "faktura": -1422.10,
            "manglende_timer": 1,
        },
    )
    assert verification.print_norgespris_eksakt("oktober_2026", 13) is ok
    tekst = capsys.readouterr().out
    assert "Elhub-kWh x publiserte Final-priser" in tekst
    assert "OK" in tekst if ok else "AVVIK" in tekst
