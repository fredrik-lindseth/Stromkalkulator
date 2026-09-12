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

Begge avstandene måles mot kurs-årgangsjusterte priser. På en dag der HA lagret
prisene med en foreløpig valutakurs ligger hele døgnet skjevt mot publisert
pris med en tilnærmet konstant faktor, og uten justeringen bommer en ekte
måling på sin egen time av en grunn som ikke har noe med hull å gjøre.
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


def _doegn(arkiv: Path, dag: int, hull_fra: int, hull_til: int = 24) -> list[dict[str, Any]]:
    """Ett døgn der timene fra og med `hull_fra` til `hull_til` mangler recorder-pris.

    Døgnene i testene under lar som regel timene fra 17 og ut stå, slik 17.08
    ser ut i virkeligheten. Randtime-regelen måler kurs-årgangen på døgnets egne
    ekte timer, så et helt hullet døgn er et annet tilfelle enn et delvis hullet,
    og det har sin egen test.
    """
    hours = []
    for t in range(24):
        ts = _iso(datetime.fromisoformat(f"2026-08-{dag:02d}T00:00:00{TZ}") + timedelta(hours=t))
        pris = None if hull_fra <= t < hull_til else round(_timespris(arkiv, ts), 6)
        hours.append({"start_local": ts, "kwh": 1.0, "spot_nok_kwh_eks_mva": pris})
    return hours


def test_randtime_fylles_og_begrunnes(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
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
    assert meta["fylte_timer"] == 17  # 16 hulltimer pluss randtimen
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
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
    # Ett øre unna forrige kvarter: over toleransen, altså en ekte måling.
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}") + 0.01, 6)
    maalt = hours[24]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][24]


def test_ekte_maaling_i_time_00_pa_flat_natt_star_urort(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
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
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
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
    assert meta["fylte_timer"] == 16  # bare hulltimene 01-16
    assert "Lot timen stå" in capsys.readouterr().out


def test_randtime_med_trang_margin_fylles(tmp_path: Path) -> None:
    """Som 31.08: verdien treffer 23:45-kvarteret, men bommer 0,52 øre på egen time."""
    time_00 = f"2026-08-17T00:00:00{TZ}"
    arkiv = _arkiv(
        tmp_path / "arkiv.json",
        steg=0.0,
        avvik={_iso(datetime.fromisoformat(time_00) + timedelta(minutes=15 * k)): 1505.2 for k in range(4)},
    )
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
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
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
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
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0
    forste = _les(fixture)
    assert _kjor(fixture, arkiv) == 0
    andre = _les(fixture)

    assert andre["hours"] == forste["hours"]
    meta = andre["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["fylte_timer"] == 17
    assert meta["randtimer"] == forste["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"]


def test_overstyr_krever_begrunnelse(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    fixture = _fixture(tmp_path / "fixture.json", _doegn(arkiv, 16, 24))

    assert _kjor(fixture, arkiv, "--overstyr", f"2026-08-16T05:00:00{TZ}") == 1


AARGANG = 0.994
"""Kurs-årgang på 0,6 % skjevhet, innenfor det som er målt i fixturene (opptil 0,63 %)."""


def _doegn_med_aargang(arkiv: Path, dag: int, hull: range, aargang: float) -> list[dict[str, Any]]:
    """Ett døgn der HA-recorderen lagret prisene med en annen valutakurs.

    Timene i `hull` mangler recorder-pris. De andre ligger `aargang` ganger den
    publiserte prisen, slik et døgn ser ut når FX-markedet var stengt på
    auksjonsdagen.
    """
    hours = []
    for t in range(24):
        ts = _iso(datetime.fromisoformat(f"2026-08-{dag:02d}T00:00:00{TZ}") + timedelta(hours=t))
        pris = None if t in hull else round(_timespris(arkiv, ts) * aargang, 6)
        hours.append({"start_local": ts, "kwh": 1.0, "spot_nok_kwh_eks_mva": pris})
    return hours


def test_ekte_maaling_pa_aargangsdag_star_urort(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Hullet starter kl. 01 på en dag der HA lagret prisene med foreløpig kurs.

    Hele døgnet ligger 0,6 % under publisert pris, så en helt ekte måling i
    time 00 bommer på sin egen publiserte time av en grunn som ikke har noe med
    hullet å gjøre. Faller den samtidig innenfor 0,5 øre av 23:45-kvarteret,
    var begge krav oppfylt før årgangsjusteringen kom inn. Justert mot døgnets
    egen kurs-årgang treffer målingen sin egen time blink, og timen skal stå.
    """
    time_00 = f"2026-08-17T00:00:00{TZ}"
    arkiv = _arkiv(
        tmp_path / "arkiv.json",
        steg=0.0,
        # Publisert time 00 ligger 1,2 øre over 23:45-kvarteret kvelden før.
        avvik={_iso(datetime.fromisoformat(time_00) + timedelta(minutes=15 * k)): 1512.0 for k in range(4)},
    )
    hours = _doegn(arkiv, 16, 24) + _doegn_med_aargang(arkiv, 17, range(1, 12), AARGANG)
    maalt = hours[24]["spot_nok_kwh_eks_mva"]

    # Krav 1 er oppfylt: målingen ligger 0,29 øre fra 23:45-kvarteret.
    assert abs(maalt - _kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}")) < fyll.RANDTIME_TOLERANSE_NOK
    # Mot rå publisert pris ville krav 2 også slått til, altså den gamle regelen.
    avstand_forrige = abs(maalt - _kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"))
    avstand_raa = abs(maalt - _timespris(arkiv, time_00))
    assert avstand_raa >= avstand_forrige + fyll.RANDTIME_EGEN_TIME_MARGIN_NOK

    fixture = _fixture(tmp_path / "fixture.json", hours)
    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][24]
    meta = ut["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["randtimer"] == {}
    assert meta["fylte_timer"] == 11  # bare hulltimene 01-11
    utskrift = capsys.readouterr().out
    assert "Lot timen stå" in utskrift
    assert "kurs-årgang 0.99400" in utskrift


def test_baaret_verdi_fra_aargangsdag_fylles(tmp_path: Path) -> None:
    """Kvelden før er en årgangsdag, så den bårne verdien ligger 0,9 øre fra rå kvarterpris.

    Uten justering faller randtimen ut på krav 1 og blir stående som en måling
    den ikke er. Målt mot kvarteret justert for årgangen den ble lagret med,
    treffer den blink.
    """
    time_00 = f"2026-08-17T00:00:00{TZ}"
    arkiv = _arkiv(
        tmp_path / "arkiv.json",
        steg=0.0,
        avvik={_iso(datetime.fromisoformat(time_00) + timedelta(minutes=15 * k)): 1550.0 for k in range(4)},
    )
    hours = _doegn_med_aargang(arkiv, 16, range(0), AARGANG) + _doegn(arkiv, 17, 1, 17)
    baaret = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}") * AARGANG, 6)
    hours[24]["spot_nok_kwh_eks_mva"] = baaret
    # Rå avstand til kvarteret er over toleransen; det er kurs-årgangen, ikke en måling.
    assert abs(baaret - _kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}")) > fyll.RANDTIME_TOLERANSE_NOK

    fixture = _fixture(tmp_path / "fixture.json", hours)
    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_kilde"] == "nordpool_publisert"
    assert list(ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"]) == [time_00]


def test_maal_aargang_krever_nok_timer_og_konstant_faktor(tmp_path: Path) -> None:
    """Årgangen regnes som umålt når døgnet er for tynt eller ikke en konstant faktor."""
    arkiv = _arkiv(tmp_path / "arkiv.json", steg=0.0)
    priser = fyll.les_arkiv(arkiv)[0]

    helt_doegn = _doegn_med_aargang(arkiv, 16, range(0), AARGANG)
    maalt = fyll.maal_aargang(helt_doegn, priser, "2026-08-16")
    assert maalt.ratio == pytest.approx(AARGANG, abs=1e-9)
    assert maalt.grunn == "kurs-årgang 0.99400"

    tynt = _doegn_med_aargang(arkiv, 16, range(5, 24), AARGANG)  # fem ekte timer
    umaalt = fyll.maal_aargang(tynt, priser, "2026-08-16")
    assert umaalt.ratio is None
    assert "5 ekte timer" in umaalt.grunn

    spriker = _doegn_med_aargang(arkiv, 16, range(0), AARGANG)
    spriker[3]["spot_nok_kwh_eks_mva"] = round(float(spriker[3]["spot_nok_kwh_eks_mva"]) * 1.01, 6)
    varierer = fyll.maal_aargang(spriker, priser, "2026-08-16")
    assert varierer.ratio is None
    assert "varierer" in varierer.grunn


DELMAALT_TIME = f"2026-08-18T05:00:00{TZ}"
DELMAALT_INDEKS = 48 + 5


def _fylt_doegn_med_randtime(arkiv: Path) -> list[dict[str, Any]]:
    """Tre døgn: 16.08 helt målt, 17.08 hullet fra kl. 01, 18.08 helt målt.

    Time 00 den 17. bærer staten fra 16.08 kl. 23:45, altså randtimen. 18.08
    kl. 05 er en delvis målt time: sensoren falt ut midt i timen, så recorderen
    har et snitt av bare den delen den rakk. Den er kandidaten for --overstyr,
    og den ligger på et døgn randtime-regelen ikke måler kurs-årgang på.
    """
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1, 17) + _doegn(arkiv, 18, 24)
    hours[24]["spot_nok_kwh_eks_mva"] = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    hours[DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"] = round(_timespris(arkiv, DELMAALT_TIME) * 0.8, 6)
    return hours


def test_helt_hullet_doegn_gir_ingen_automatisk_randtime(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """31.08-tilfellet: døgnet har ingen ekte timer, så kurs-årgangen kan ikke måles.

    Uten årgangen kan ikke avstanden til egen publiserte time prøves, og da er
    det ikke avgjort om verdien er båret eller målt. Timen skal stå, og
    scriptet skal si hva som ikke lot seg måle.
    """
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    time_00 = str(hours[24]["start_local"])
    baaret = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    hours[24]["spot_nok_kwh_eks_mva"] = baaret
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == baaret
    assert "spot_kilde" not in ut["hours"][24]
    meta = ut["metadata"]["spothull"]["fylt_fra_nordpool"]
    assert meta["randtimer"] == {}
    assert meta["fylte_timer"] == 23  # hulltimene 01-23, ikke time 00
    utskrift = capsys.readouterr().out
    assert "kurs-årgangen for 2026-08-17 er umålt" in utskrift
    assert "0 ekte timer" in utskrift
    assert f'--overstyr "{time_00}=' in utskrift


def test_umaalt_aargang_kan_avgjores_med_overstyr(tmp_path: Path) -> None:
    """Beslutningen scriptet ikke tar selv, tas for hånd og arkiveres."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _doegn(arkiv, 16, 24) + _doegn(arkiv, 17, 1)
    time_00 = str(hours[24]["start_local"])
    baaret = round(_kvarterpris(arkiv, f"2026-08-16T23:45:00{TZ}"), 6)
    hours[24]["spot_nok_kwh_eks_mva"] = baaret
    fixture = _fixture(tmp_path / "fixture.json", hours)

    grunn = "hele døgnet er hullet; HA-loggen viser unknown 00:00:00"
    assert _kjor(fixture, arkiv, "--overstyr", f"{time_00}={grunn}") == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_kilde"] == "nordpool_publisert"
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == pytest.approx(_timespris(arkiv, time_00), abs=1e-6)
    overstyrt = ut["metadata"]["spothull"]["fylt_fra_nordpool"]["overstyrte_timer"][time_00]
    assert overstyrt["recorder_nok_kwh"] == baaret
    assert overstyrt["begrunnelse"] == grunn


def test_varierende_kurs_i_doegnet_lar_timen_sta(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Er ikke døgnet lagret med én kurs, er årgangen umålt og timen står."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _fylt_doegn_med_randtime(arkiv)
    baaret = hours[24]["spot_nok_kwh_eks_mva"]
    # Sprik i de ekte timene den 17.: faktoren er ikke konstant over døgnet.
    hours[24 + 20]["spot_nok_kwh_eks_mva"] = round(float(hours[24 + 20]["spot_nok_kwh_eks_mva"]) * 1.01, 6)
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][24]["spot_nok_kwh_eks_mva"] == baaret
    assert "spot_kilde" not in ut["hours"][24]
    assert ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"] == {}
    assert "varierer over døgnet" in capsys.readouterr().out


def test_gjentatt_kjoring_endrer_ingenting(tmp_path: Path) -> None:
    """Andre kjøring på samme fixture skal ikke røre en bokstav.

    Både randtimen, den manuelle overstyringen og datoen for fyllingen står
    urørt. Datoen er med fordi en kjøring som bare bekrefter fixturen ikke skal
    kunne påstå at den ble fylt i dag.
    """
    arkiv = _arkiv(tmp_path / "arkiv.json")
    fixture = _fixture(tmp_path / "fixture.json", _fylt_doegn_med_randtime(arkiv))
    overstyrt_time = DELMAALT_TIME

    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}=sensoren falt ut midt i timen") == 0
    # Gammel dato i metadata står som bevis på at kjøring to ikke skriver ny.
    forste = _les(fixture)
    forste["metadata"]["spothull"]["fylt_fra_nordpool"]["dato"] = "2026-01-02"
    fixture.write_text(json.dumps(forste, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    fasit = fixture.read_text(encoding="utf-8")

    assert _kjor(fixture, arkiv) == 0
    assert fixture.read_text(encoding="utf-8") == fasit

    assert _kjor(fixture, arkiv) == 0
    assert fixture.read_text(encoding="utf-8") == fasit


def test_overstyring_overlever_kjoring_uten_flagget(tmp_path: Path) -> None:
    """Å utelate --overstyr angrer ingenting, og begrunnelsen blir stående."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _fylt_doegn_med_randtime(arkiv)
    overstyrt_time = DELMAALT_TIME
    maalt = hours[DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)
    grunn = "sensoren falt ut midt i timen; recorder-snittet dekker bare deler av den"

    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}={grunn}") == 0
    assert _kjor(fixture, arkiv) == 0

    ut = _les(fixture)
    assert ut["hours"][DELMAALT_INDEKS]["spot_kilde"] == "nordpool_publisert"
    overstyrt = ut["metadata"]["spothull"]["fylt_fra_nordpool"]["overstyrte_timer"][overstyrt_time]
    assert overstyrt["begrunnelse"] == grunn
    assert overstyrt["recorder_nok_kwh"] == maalt


def test_gjentatt_overstyr_arkiverer_ikke_arkivprisen(tmp_path: Path) -> None:
    """Samme flagg om igjen er en bekreftelse, ikke en ny måling.

    Recorder-verdien i metadata er målingen fra før overstyringen. Leses den av
    timen andre gangen, arkiveres arkivprisen som om den var recorderens.
    """
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _fylt_doegn_med_randtime(arkiv)
    overstyrt_time = DELMAALT_TIME
    maalt = hours[DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)
    grunn = "sensoren falt ut midt i timen"

    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}={grunn}") == 0
    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}={grunn}") == 0

    overstyrt = _les(fixture)["metadata"]["spothull"]["fylt_fra_nordpool"]["overstyrte_timer"][overstyrt_time]
    assert overstyrt["recorder_nok_kwh"] == maalt
    assert overstyrt["begrunnelse"] == grunn
    assert "tidligere_begrunnelser" not in overstyrt


def test_ny_begrunnelse_tar_vare_pa_den_gamle(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _fylt_doegn_med_randtime(arkiv)
    overstyrt_time = DELMAALT_TIME
    maalt = hours[DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}=gjetning") == 0
    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}=HA-loggen viser unavailable 05:12") == 0

    overstyrt = _les(fixture)["metadata"]["spothull"]["fylt_fra_nordpool"]["overstyrte_timer"][overstyrt_time]
    assert overstyrt["begrunnelse"] == "HA-loggen viser unavailable 05:12"
    assert overstyrt["tidligere_begrunnelser"] == ["gjetning"]
    assert overstyrt["recorder_nok_kwh"] == maalt


def test_angre_legger_recorder_maalingen_tilbake(tmp_path: Path) -> None:
    """--angre er den eksplisitte veien tilbake, for både overstyring og randtime."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    hours = _fylt_doegn_med_randtime(arkiv)
    overstyrt_time = DELMAALT_TIME
    randtime = str(hours[24]["start_local"])
    maalt = hours[DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"]
    baaret = hours[24]["spot_nok_kwh_eks_mva"]
    fixture = _fixture(tmp_path / "fixture.json", hours)

    assert _kjor(fixture, arkiv, "--overstyr", f"{overstyrt_time}=sensoren falt ut midt i timen") == 0
    assert _kjor(fixture, arkiv, "--angre", overstyrt_time) == 0

    ut = _les(fixture)
    assert ut["hours"][DELMAALT_INDEKS]["spot_nok_kwh_eks_mva"] == maalt
    assert "spot_kilde" not in ut["hours"][DELMAALT_INDEKS]
    assert ut["metadata"]["spothull"]["fylt_fra_nordpool"]["overstyrte_timer"] == {}

    # Randtimen fylles igjen i samme kjøring, for regelen treffer fortsatt.
    assert _kjor(fixture, arkiv, "--angre", randtime) == 0
    ut = _les(fixture)
    assert ut["hours"][24]["spot_kilde"] == "nordpool_publisert"
    assert list(ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"]) == [randtime]
    assert (
        ut["metadata"]["spothull"]["fylt_fra_nordpool"]["randtimer"][randtime]["recorder_nok_kwh"] == baaret
    )


def test_angre_uten_oppforing_avvises(tmp_path: Path) -> None:
    arkiv = _arkiv(tmp_path / "arkiv.json")
    fixture = _fixture(tmp_path / "fixture.json", _doegn(arkiv, 16, 24))

    assert _kjor(fixture, arkiv, "--angre", f"2026-08-16T05:00:00{TZ}") == 1


def test_overstyr_paa_alt_fylt_hulltime_avvises(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """En fylt hulltime har ingen recorder-måling å arkivere som original."""
    arkiv = _arkiv(tmp_path / "arkiv.json")
    fixture = _fixture(tmp_path / "fixture.json", _fylt_doegn_med_randtime(arkiv))
    hulltime = f"2026-08-17T05:00:00{TZ}"

    assert _kjor(fixture, arkiv) == 0
    assert _kjor(fixture, arkiv, "--overstyr", f"{hulltime}=vil overstyre en fylt time") == 1
    assert "alt fylt fra arkivet" in capsys.readouterr().out
