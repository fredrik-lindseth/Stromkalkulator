"""Tester for randtime-regelen i scripts/research/fyll_spothull_fra_nordpool.py.

Når Nord Pool-sensoren faller ut presis ved døgnskiftet, har HA-recorderen
likevel en verdi for time 00: statistikk-kompilatoren snitter bare over
numeriske states, så staten fra 23:45-kvarteret kvelden før bæres gjennom hele
timen. Den verdien er ikke en måling, og timen hører til hullet. Regelen som
kjenner den igjen må treffe randtimen og bare den, ellers overskriver scriptet
ekte målinger med arkivpriser.

Nærheten til 23:45-kvarteret holder ikke alene: på en flat natt ligger en ekte
måling i time 00 også innenfor toleransen. Derfor kreves det i tillegg at
verdien bommer på sin egen publiserte time.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "research" / "fyll_spothull_fra_nordpool.py"

spec = importlib.util.spec_from_file_location("fyll_spothull", SCRIPT)
assert spec is not None and spec.loader is not None
fyll = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fyll)

TZ = "+02:00"
START = datetime.fromisoformat(f"2026-08-16T00:00:00{TZ}")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _arkiv(
    sti: Path,
    timer: int = 72,
    nok_mwh: float = 1500.0,
    steg: float = 4.0,
    avvik: dict[str, float] | None = None,
) -> Path:
    """Kvarterarkiv med fire kvarter per time, stigende priser.

    `steg` er prisøkningen per kvarter; 0 gir en flat serie. `avvik` setter
    enkeltkvarter til en gitt pris, nøklet på lokal ISO.
    """
    avvik = avvik or {}
    kvarter = []
    for i in range(timer * 4):
        start = _iso(START + timedelta(minutes=15 * i))
        kvarter.append(
            {
                "start_local": start,
                "nok_mwh": avvik.get(start, nok_mwh + steg * i),
            }
        )
    sti.write_text(
        json.dumps({"daily": [{"kvarter": kvarter}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    return sti


def _timespris(arkiv: Path, ts: str) -> float:
    return fyll.les_arkiv(arkiv)[0][ts]


def _kvarterpris(arkiv: Path, ts: str) -> float:
    return fyll.les_arkiv(arkiv)[1][ts]


def _fixture(sti: Path, hours: list[dict[str, Any]]) -> Path:
    sti.write_text(
        json.dumps({"metadata": {}, "hours": hours}, ensure_ascii=False),
        encoding="utf-8",
    )
    return sti


def _kjor(fixture: Path, arkiv: Path, *ekstra: str) -> int:
    argv = sys.argv
    sys.argv = [
        "fyll_spothull_fra_nordpool.py",
        "--fixture",
        str(fixture),
        "--arkiv",
        str(arkiv),
        *ekstra,
    ]
    try:
        return fyll.main()
    finally:
        sys.argv = argv


def _les(sti: Path) -> dict[str, Any]:
    return json.loads(sti.read_text(encoding="utf-8"))


def _doegn(arkiv: Path, dag: int, hull_fra: int) -> list[dict[str, Any]]:
    """Ett døgn der timene fra og med `hull_fra` mangler recorder-pris."""
    hours = []
    for t in range(24):
        ts = _iso(datetime.fromisoformat(f"2026-08-{dag:02d}T00:00:00{TZ}") + timedelta(hours=t))
        pris = None if t >= hull_fra else round(_timespris(arkiv, ts), 6)
        hours.append({"start_local": ts, "kwh": 1.0, "spot_nok_kwh_eks_mva": pris})
    return hours


def test_randtime_fylles_og_begrunnes(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    # Time 00 den 17. bærer staten fra 16.08 kl. 23:45.
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    randtime = ut["hours"][24]
    ts = randtime["start_local"]
    assert randtime["spot_kilde"] == "nordpool_publisert"
    assert randtime["spot_nok_kwh_eks_mva"] == pytest.approx(_timespris(arkiv, ts), abs=1e-6)

    meta = ut["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["fylte_timer"] == 24  # 23 hulltimer pluss randtimen
    assert list(meta["randtimer"]) == [ts]
    assert meta["randtimer"][ts]["begrunnelse"] == "randtime_forrige_kvarter"
    # Timen før randtimen er en ekte måling og skal stå urørt.
    assert "spot_kilde" not in ut["hours"][23]


def test_time_00_uten_hull_etter_seg_star_urort(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 24)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert "spot_kilde" not in ut["hours"][24]
    assert ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"] == {}


def test_time_00_langt_fra_forrige_kvarter_star_urort(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    # Ett øre unna forrige kvarter: over toleransen, altså en ekte måling.
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}") + 0.01, 6)
    maalt = hours[24]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][24]


def test_ekte_maaling_i_time_00_pa_flat_natt_star_urort(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Hullet starter kl. 01 på en flat natt, og time 00 er en ekte måling.

    Prisen står stille gjennom natten, så målingen i time 00 havner tilfeldig
    innenfor 0,5 øre av 23:45-kvarteret. Den stemmer samtidig med sin egen
    publiserte time, og da er den ikke en båret verdi. Timen skal stå.
    """
    arkiv = _arkiv(
        tmp_path / "arkiv.json",
        steg=0.0,
        avvik={f"2026-08-16T23:45:00{TZ}": 1497.0},
    )
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    maalt = hours[24]["spot_nok_kwh_eks_mva"]
    ts = hours[24]["start_local"]
    # 0,3 øre fra 23:45-kvarteret, altså innenfor randtime-toleransen, men
    # midt på sin egen publiserte time.
    assert abs(maalt - _kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}")) < 0.005
    assert maalt == pytest.approx(_timespris(arkiv, ts), abs=1e-9)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][24]
    meta = ut["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["randtimer"] == {}
    assert meta["fylte_timer"] == 23  # bare hulltimene 01-23
    assert "Lot timen stå" in capsys.readouterr().out


def test_randtime_med_trang_margin_fylles(tmp_path: Path) -> None:
    """Som 31.08: verdien treffer 23:45-kvarteret, men bommer 0,52 øre på egen time."""
    time_00 = f"2026-08-17T00:00:00{TZ}"
    arkiv = _arkiv(
        tmp_path / "arkiv.json",
        steg=0.0,
        avvik={_iso(datetime.fromisoformat(time_00) + timedelta(minutes=15 * k)): 1505.2 for k in range(4)},
    )
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_kilde"] == "nordpool_publisert"
    assert list(ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"]) == [time_00]


def test_time_00_uten_publisert_pris_star_urort(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Mangler arkivet timen selv, kan kravet mot egen time ikke prøves."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    data = json.loads(arkiv.read_text(encoding="utf-8"))
    time_00 = f"2026-08-17T00:00:00{TZ}"
    data["daily"][0]["kvarter"] = [
        kv for kv in data["daily"][0]["kvarter"] if not kv["start_local"].startswith("2026-08-17T00:")
    ]
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    maalt = hours[24]["spot_nok_kwh_eks_mva"]
    arkiv.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][24]
    utskrift = capsys.readouterr().out
    assert time_00 in utskrift
    assert "Lot timen stå" in utskrift


def test_ny_kjoring_beholder_randtimen(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0
    forste = _les(fixture)
    assert _kjor(fixture, arkiv) == 0
    andre = _les(fixture)

    assert andre["hours"] == forste["hours"]
    meta = andre["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["fylte_timer"] == 24
    assert meta["randtimer"] == forste["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"]


def test_overstyr_krever_begrunnelse(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    fixture = _fixture(tmp_path / "fixture.json", _doegn(arkiv, 16, 24))

    assert _kjor(fixture, arkiv, "--overstyr", f"2026-08-16T05:00:00{TZ}") == 1
