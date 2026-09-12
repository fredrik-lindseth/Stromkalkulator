"""Vakt for avregningskontrakten i docs/kontrakter/avregning.md.

Kontrakten er en tekst, og en tekst kan ikke feile. Derfor ligger
fordelingsregelen og sommertidsmerkelappene som normative tabeller i
dokumentet, og her kjøres de. Endrer noen tallene i tabellen uten å endre
regelen (eller omvendt), feller denne testen det.

`fordel_delta` under er kontraktens utførbare form, C1. L1 skal reprodusere
den samme fordelingen; avregningskjernen importerer ikke herfra, den måles mot
de samme tabellradene. Går de to fra hverandre, er det denne filen som sier
hvilken som har rett.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

ROT = Path(__file__).parent.parent
KONTRAKT = ROT / "docs" / "kontrakter" / "avregning.md"
OSLO = ZoneInfo("Europe/Oslo")
INTERVALL = timedelta(hours=1)


# ---------------------------------------------------------------------------
# Kontraktens utførbare form


def intervallstart(tidspunkt: datetime) -> datetime:
    """Starten på avregningsintervallet tidspunktet faller i (A1, halvåpent)."""
    if tidspunkt.tzinfo is None:
        raise ValueError("observasjonstid må være tidssoneklar")
    i_utc = tidspunkt.astimezone(UTC)
    return i_utc.replace(minute=0, second=0, microsecond=0)


def fordel_delta(fra: datetime, til: datetime, delta_kwh: float) -> dict[datetime, float]:
    """Fordel et målerdelta jevnt over tid på intervallene (fra, til] dekker.

    C1: prorata på sekunder i hvert intervall. Vinduet med lengde null kan ikke
    fordeles og er en avvist avlesning, ikke en bokføring.
    """
    if til <= fra:
        raise ValueError("vinduet må ha positiv lengde")
    varighet = (til - fra).total_seconds()
    fordeling: dict[datetime, float] = {}
    naa = fra
    while naa < til:
        start = intervallstart(naa)
        neste = min(til, start + INTERVALL)
        andel = (neste - naa).total_seconds() / varighet
        fordeling[start] = fordeling.get(start, 0.0) + delta_kwh * andel
        naa = neste
    return fordeling


# ---------------------------------------------------------------------------
# Dokumentet


def _kontrakttekst() -> str:
    assert KONTRAKT.exists(), f"{KONTRAKT} finnes ikke"
    return KONTRAKT.read_text(encoding="utf-8")


def _tabellrader(tekst: str, forste_kolonne: str) -> list[list[str]]:
    """Radene i markdown-tabellen der første kolonne i første rad matcher."""
    rader = []
    treff = False
    for linje in tekst.splitlines():
        if not linje.startswith("|"):
            treff = False
            continue
        celler = [c.strip() for c in linje.strip().strip("|").split("|")]
        if re.fullmatch(forste_kolonne, celler[0]):
            treff = True
        if treff:
            rader.append(celler)
    assert rader, f"fant ingen tabellrader med første kolonne {forste_kolonne!r}"
    return rader


@pytest.mark.parametrize(
    "overskrift",
    [
        "## A. Beslutningsport",
        "## B. Datakontrakt",
        "## C. Invarianter og fordelingsregel",
        "## D. Persistens og migrering",
        "## Felttabell for data-dicten",
    ],
)
def test_kontrakten_har_seksjonene(overskrift: str) -> None:
    """Akseptansen i A0: seksjonene A til D og felttabellen skal finnes."""
    assert overskrift in _kontrakttekst()


def test_kontrakten_navngir_de_tre_datatypene() -> None:
    """Datakontrakt B dekker avlesning, prisintervall og avregnet intervall."""
    tekst = _kontrakttekst()
    for overskrift in ("### B1 Energiavlesning", "### B2 Prisintervall", "### B3 Avregnet intervall"):
        assert overskrift in tekst


# ---------------------------------------------------------------------------
# Prøvetabellen (C6)


def _provetabell() -> list[tuple[str, datetime, datetime, float, dict[datetime, float]]]:
    saker = []
    for rad in _tabellrader(_kontrakttekst(), r"F\d+"):
        sak, fra, til, delta, fordeling = rad
        forventet = {}
        for ledd in fordeling.split(";"):
            start, kwh = ledd.split("=")
            forventet[datetime.fromisoformat(start.strip())] = float(kwh)
        saker.append((sak, datetime.fromisoformat(fra), datetime.fromisoformat(til), float(delta), forventet))
    return saker


PROVER = _provetabell()


def test_provetabellen_er_lest() -> None:
    """En tom tabell ville gjort alle radtestene under grønne uten å sjekke noe."""
    assert len(PROVER) >= 6


@pytest.mark.parametrize(("sak", "fra", "til", "delta", "forventet"), PROVER, ids=[p[0] for p in PROVER])
def test_fordelingsregelen_treffer_provetabellen(
    sak: str, fra: datetime, til: datetime, delta: float, forventet: dict[datetime, float]
) -> None:
    """C6: hver rad i den normative tabellen skal komme ut av regelen i C1."""
    fordelt = fordel_delta(fra, til, delta)
    assert set(fordelt) == set(forventet), sak
    for start, kwh in forventet.items():
        assert fordelt[start] == pytest.approx(kwh, abs=1e-9), f"{sak} {start.isoformat()}"


@pytest.mark.parametrize(("sak", "fra", "til", "delta", "forventet"), PROVER, ids=[p[0] for p in PROVER])
def test_provetabellen_bevarer_energien(
    sak: str, fra: datetime, til: datetime, delta: float, forventet: dict[datetime, float]
) -> None:
    """C2.1: tabellen selv skal summere til deltaet, ellers er fasiten feil."""
    assert sum(forventet.values()) == pytest.approx(delta, abs=1e-9), sak


# ---------------------------------------------------------------------------
# Sommertid (C3)


def _dst_tabell() -> list[tuple[str, datetime, str, str]]:
    rader = []
    for rad in _tabellrader(_kontrakttekst(), r"D\d+"):
        sak, utc, lokal, maaned = rad
        rader.append((sak, datetime.fromisoformat(utc.replace("Z", "+00:00")), lokal, maaned))
    return rader


DST = _dst_tabell()


def test_dst_tabellen_er_lest() -> None:
    assert len(DST) >= 5


@pytest.mark.parametrize(("sak", "utc", "lokal", "maaned"), DST, ids=[d[0] for d in DST])
def test_lokal_merkelapp_kommer_fra_utc_start(sak: str, utc: datetime, lokal: str, maaned: str) -> None:
    """C3: merkelappen er start_utc omregnet med zoneinfo, ikke veggklokke-regning."""
    i_oslo = utc.astimezone(OSLO)
    forventet = f"{i_oslo:%Y-%m-%d %H:%M} {'CEST' if i_oslo.utcoffset() == timedelta(hours=2) else 'CET'}"
    assert forventet == lokal, sak
    assert f"{i_oslo:%Y-%m}" == maaned, sak


def test_host_dst_gir_to_intervaller_med_samme_veggklokke() -> None:
    """C3: 02:00 lokal tid finnes to ganger 25.10.2026, som to ulike intervaller."""
    forste = datetime(2026, 10, 25, 0, 0, tzinfo=UTC)
    andre = datetime(2026, 10, 25, 1, 0, tzinfo=UTC)
    assert forste != andre
    assert f"{forste.astimezone(OSLO):%H:%M}" == f"{andre.astimezone(OSLO):%H:%M}" == "02:00"
    assert forste.astimezone(OSLO).utcoffset() != andre.astimezone(OSLO).utcoffset()


def test_var_dst_har_ingen_lokal_time_02() -> None:
    """C3: 29.03.2026 finnes ingen lokal time 02, og intervallene hopper over den."""
    timer = [
        (datetime(2026, 3, 29, 0, 0, tzinfo=UTC) + timedelta(hours=t)).astimezone(OSLO).hour for t in range(4)
    ]
    assert timer == [1, 3, 4, 5]


def test_fakturamaneden_skifter_ved_lokal_midnatt() -> None:
    """C3 D5: 31.03 kl. 22 UTC er allerede april lokalt."""
    assert f"{datetime(2026, 3, 31, 22, 0, tzinfo=UTC).astimezone(OSLO):%Y-%m}" == "2026-04"
    assert f"{datetime(2026, 3, 31, 21, 0, tzinfo=UTC).astimezone(OSLO):%Y-%m}" == "2026-03"


# ---------------------------------------------------------------------------
# Invariantene (C2)

_TID = st.datetimes(
    min_value=datetime(2026, 3, 28, 0, 0),
    max_value=datetime(2026, 10, 26, 0, 0),
    timezones=st.just(UTC),
)


@given(fra=_TID, sekunder=st.integers(min_value=1, max_value=48 * 3600), delta=st.floats(0.0, 100.0))
@settings(max_examples=300, deadline=None)
def test_c2_1_fordelingen_bevarer_deltaet(fra: datetime, sekunder: int, delta: float) -> None:
    """Summen av fordelte kWh er nøyaktig det godkjente målerdeltaet."""
    fordelt = fordel_delta(fra, fra + timedelta(seconds=sekunder), delta)
    assert sum(fordelt.values()) == pytest.approx(delta, abs=1e-9, rel=1e-12)


@given(fra=_TID, sekunder=st.integers(min_value=2, max_value=48 * 3600), delta=st.floats(0.0, 100.0))
@settings(max_examples=300, deadline=None)
def test_c2_6_polltid_endrer_ikke_avregningen(fra: datetime, sekunder: int, delta: float) -> None:
    """En ekstra poll midt i vinduet gir samme fordeling som ingen poll gjorde.

    Dette er invarianten hele kontrakten står på. Snapping til start- eller
    sluttintervallet feller denne testen; jevn fordeling over tid gjør ikke.
    """
    til = fra + timedelta(seconds=sekunder)
    en_poll = fordel_delta(fra, til, delta)

    midt = fra + timedelta(seconds=sekunder // 2)
    andel = (midt - fra).total_seconds() / sekunder
    to_poll: dict[datetime, float] = {}
    for bit in (fordel_delta(fra, midt, delta * andel), fordel_delta(midt, til, delta * (1 - andel))):
        for start, kwh in bit.items():
            to_poll[start] = to_poll.get(start, 0.0) + kwh

    assert set(en_poll) == set(to_poll)
    for start, kwh in en_poll.items():
        assert to_poll[start] == pytest.approx(kwh, abs=1e-9, rel=1e-9)


def test_c1_vindu_uten_lengde_kan_ikke_fordeles() -> None:
    """To avlesninger med samme observasjonstid er avvist, ikke bokført."""
    naa = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="positiv lengde"):
        fordel_delta(naa, naa, 1.0)


def test_naiv_observasjonstid_kaster() -> None:
    """B1: en naiv datetime er en programmeringsfeil, ikke lokal tid."""
    with pytest.raises(ValueError, match="tidssoneklar"):
        intervallstart(datetime(2026, 6, 15, 10, 0))


# ---------------------------------------------------------------------------
# Felttabellen mot koden


def _felt_med_uendret_betydning() -> list[str]:
    tekst = _kontrakttekst()
    etter = tekst.split("Felt som beholdes med samme navn")[1]
    return [rad[0].strip("`") for rad in _tabellrader(etter, r"`[a-z_]+`")]


@pytest.mark.parametrize("felt", _felt_med_uendret_betydning())
def test_beholdte_felt_finnes_i_coordinator(felt: str) -> None:
    """Felttabellen skal navngi felt som faktisk finnes i dagens data-dict."""
    kilde = (ROT / "custom_components" / "stromkalkulator" / "coordinator.py").read_text(encoding="utf-8")
    assert f'"{felt}"' in kilde, f"{felt} står i felttabellen, men finnes ikke i coordinator.py"
