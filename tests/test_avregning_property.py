"""Egenskapstester for avregningskjernen (L1).

Eksemplene i `test_avregning.py` viser at kjernen treffer kontraktens
prøvetabeller. Filen her prøver å felle den: hypothesis genererer historikker
og pollplaner, og hver test er formulert slik at en gal implementasjon blir
rød.

De to som betyr mest:

- `test_bevaring_...` feller enhver fordeling som mister eller finner på kWh.
- `test_polltid_endrer_ikke_intervallene` feller snapping til start- eller
  sluttintervallet. Den er invarianten hele kontrakten står på (C2.6), og den
  er derfor kjørt mot en simulert måler med kjent tidsprofil, ikke mot et
  tilfeldig delta.

Prøv å bryte koden og se at disse blir røde før du stoler på dem.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st
from stromkalkulator.avregning import (
    AVREGNINGSINTERVALL,
    PRIS_SETTLE_SEKUNDER,
    PRISRUTE_MINUTTER,
    Avlesning,
    Avregningsbok,
    Intervallkvalitet,
    Prisadapter,
    fordel_delta,
    intervallstart,
    lokal_maned,
    lokal_time,
    prisrutestart,
    varighet_sekunder,
)

if TYPE_CHECKING:
    from random import Random

OSLO = ZoneInfo("Europe/Oslo")

# Vinduet dekker begge sommertidsskiftene i 2026, så generatoren treffer dem
# uten at testene må be om dem.
TIDSROM = st.datetimes(
    min_value=datetime(2026, 3, 28, 0, 0),
    max_value=datetime(2026, 10, 26, 0, 0),
    timezones=st.just(UTC),
)
DELTA = st.floats(min_value=0.0, max_value=90.0, allow_nan=False, allow_infinity=False)
SEKUNDER = st.integers(min_value=1, max_value=48 * 3600)


# ---------------------------------------------------------------------------
# Fordelingsregelen (C1, C2.1)


@given(fra=TIDSROM, sekunder=SEKUNDER, delta=DELTA)
@settings(max_examples=400, deadline=None)
def test_bevaring_summen_er_deltaet(fra: datetime, sekunder: int, delta: float) -> None:
    """C2.1: summen av fordelte kWh er nøyaktig det godkjente målerdeltaet."""
    fordelt = fordel_delta(fra, fra + timedelta(seconds=sekunder), delta)
    assert sum(fordelt.values()) == pytest.approx(delta, abs=1e-9, rel=1e-12)


@given(fra=TIDSROM, sekunder=SEKUNDER, delta=DELTA)
@settings(max_examples=300, deadline=None)
def test_fordelingen_treffer_bare_intervallene_vinduet_dekker(
    fra: datetime, sekunder: int, delta: float
) -> None:
    """C1: energien lander i intervallene `(fra, til]` dekker, og ingen andre.

    Snapping til ett intervall ville bestått bevaringen, men ikke denne.
    """
    til = fra + timedelta(seconds=sekunder)
    fordelt = fordel_delta(fra, til, delta)
    forventet = []
    naa = intervallstart(fra)
    while naa < til:
        forventet.append(naa)
        naa += AVREGNINGSINTERVALL
    assert sorted(fordelt) == forventet
    assert all(kwh >= 0 for kwh in fordelt.values())


@given(fra=TIDSROM, sekunder=SEKUNDER, delta=DELTA)
@settings(max_examples=300, deadline=None)
def test_hvert_intervall_faar_sin_andel_av_tiden(fra: datetime, sekunder: int, delta: float) -> None:
    """C1: prorata på sekunder, ikke på antall intervaller.

    En jevn fordeling over antall intervaller ville bestått bevaringen og
    truffet de samme intervallene, men ikke denne.
    """
    assume(delta > 0)
    til = fra + timedelta(seconds=sekunder)
    fordelt = fordel_delta(fra, til, delta)
    for start, kwh in fordelt.items():
        overlapp = varighet_sekunder(max(start, fra), min(start + AVREGNINGSINTERVALL, til))
        assert kwh == pytest.approx(delta * overlapp / sekunder, abs=1e-9, rel=1e-9)


# ---------------------------------------------------------------------------
# Merkelappene over sommertidsskiftene (C3)


@given(fra=TIDSROM, sekunder=SEKUNDER)
@settings(max_examples=300, deadline=None)
def test_hvert_intervall_er_eksakt_en_time_ogsa_over_dst(fra: datetime, sekunder: int) -> None:
    """C3: i UTC er sommertidsskiftene vanlige timer.

    Regnet på veggklokken ville 29.03 kl. 01 lokal tid vært to timer lang og
    25.10 kl. 02 vært null.
    """
    fordelt = fordel_delta(fra, fra + timedelta(seconds=sekunder), 1.0)
    for start in fordelt:
        assert varighet_sekunder(start, start + AVREGNINGSINTERVALL) == 3600.0


@given(sekunder=st.integers(min_value=0, max_value=23 * 3600))
@settings(max_examples=200, deadline=None)
def test_var_dst_har_ingen_lokal_time_02(sekunder: int) -> None:
    """C3: 29.03.2026 finnes ikke lokal time 02, uansett hvor vi ser."""
    start = datetime(2026, 3, 28, 23, 0, tzinfo=UTC) + timedelta(seconds=sekunder)
    assert lokal_time(start) != 2
    assert lokal_maned(start) == "2026-03"


@given(offset=st.integers(min_value=0, max_value=3599))
@settings(max_examples=100, deadline=None)
def test_host_dst_holder_de_to_timene_fra_hverandre(offset: int) -> None:
    """C3: de to intervallene med lokal 02:00 skilles av `start_utc`."""
    forste = datetime(2026, 10, 25, 0, 0, tzinfo=UTC) + timedelta(seconds=offset)
    andre = forste + AVREGNINGSINTERVALL
    assert lokal_time(forste) == lokal_time(andre) == 2
    assert intervallstart(forste) != intervallstart(andre)
    assert forste.astimezone(OSLO).utcoffset() != andre.astimezone(OSLO).utcoffset()
    assert f"{forste.astimezone(OSLO):%H:%M}" == f"{andre.astimezone(OSLO):%H:%M}"


# ---------------------------------------------------------------------------
# Polltidsuavhengighet gjennom boken (C2.6)


def _maalerprofil(
    start: datetime, segmenter: list[tuple[int, float]]
) -> tuple[list[datetime], dict[datetime, float]]:
    """En måler med konstant effekt i hvert segment.

    Gir bruddpunktene og tellerstanden i hvert av dem. Mellom to bruddpunkt er
    telleren lineær i tid, og da er jevn fordeling eksakt. Det er nettopp den
    egenskapen som gjør at ekstra polls ikke skal endre noe.
    """
    bruddpunkt = [start]
    stand = {start: 0.0}
    naa = start
    teller = 0.0
    for sekunder, kw in segmenter:
        naa = naa + timedelta(seconds=sekunder)
        teller += kw * sekunder / 3600
        bruddpunkt.append(naa)
        stand[naa] = teller
    return bruddpunkt, stand


def _stand_ved(bruddpunkt: list[datetime], stand: dict[datetime, float], naar: datetime) -> float:
    """Tellerstanden ved et vilkårlig tidspunkt, lineært mellom bruddpunktene."""
    for foer, etter in pairwise(bruddpunkt):
        if foer <= naar <= etter:
            spenn = varighet_sekunder(foer, etter)
            andel = varighet_sekunder(foer, naar) / spenn if spenn else 0.0
            return stand[foer] + (stand[etter] - stand[foer]) * andel
    return stand[bruddpunkt[-1]]


def _spill_av(pollplan: list[datetime], bruddpunkt: list[datetime], stand: dict[datetime, float]) -> dict:
    bok = Avregningsbok(dso_id="bkk")
    for naar in pollplan:
        bok.bokfor(Avlesning("meter-1", _stand_ved(bruddpunkt, stand, naar), naar))
    return {i.start_utc: i.kwh for i in bok.intervaller()}


@given(
    start=st.datetimes(
        min_value=datetime(2026, 6, 1, 0, 0), max_value=datetime(2026, 6, 25, 0, 0), timezones=st.just(UTC)
    ),
    segmenter=st.lists(
        st.tuples(st.integers(min_value=300, max_value=9000), st.floats(min_value=0.0, max_value=8.0)),
        min_size=1,
        max_size=5,
    ),
    ekstra_a=st.lists(st.floats(min_value=0.0, max_value=1.0), max_size=12),
    ekstra_b=st.lists(st.floats(min_value=0.0, max_value=1.0), max_size=12),
)
@settings(max_examples=200, deadline=None)
def test_polltid_endrer_ikke_intervallene(
    start: datetime,
    segmenter: list[tuple[int, float]],
    ekstra_a: list[float],
    ekstra_b: list[float],
) -> None:
    """C2.6: samme observerte historikk, to ulike pollplaner, samme avregning.

    Begge planene leser den samme måleren, og begge treffer bruddpunktene der
    effekten skifter. Alt annet er ekstra polls med ulik plassering. Snapping
    til start- eller sluttintervallet feller denne; jevn fordeling gjør ikke.
    """
    bruddpunkt, stand = _maalerprofil(start, segmenter)
    spenn = varighet_sekunder(bruddpunkt[0], bruddpunkt[-1])
    assume(spenn > 0)

    def plan(ekstra: list[float]) -> list[datetime]:
        tider = set(bruddpunkt)
        for andel in ekstra:
            tider.add(bruddpunkt[0] + timedelta(seconds=round(spenn * andel)))
        return sorted(tider)

    a = _spill_av(plan(ekstra_a), bruddpunkt, stand)
    b = _spill_av(plan(ekstra_b), bruddpunkt, stand)

    assert set(a) == set(b)
    for nokkel, kwh in a.items():
        assert b[nokkel] == pytest.approx(kwh, abs=1e-9, rel=1e-9)


@given(
    start=st.datetimes(
        min_value=datetime(2026, 6, 1, 0, 0), max_value=datetime(2026, 6, 25, 0, 0), timezones=st.just(UTC)
    ),
    segmenter=st.lists(
        st.tuples(st.integers(min_value=300, max_value=9000), st.floats(min_value=0.0, max_value=8.0)),
        min_size=1,
        max_size=5,
    ),
    gjentakelser=st.integers(min_value=1, max_value=4),
)
@settings(max_examples=150, deadline=None)
def test_dupliserte_avlesninger_bokfores_bare_en_gang(
    start: datetime, segmenter: list[tuple[int, float]], gjentakelser: int
) -> None:
    """C2.2: en avlesning som kommer igjen er en duplikat, ikke nytt forbruk."""
    bruddpunkt, stand = _maalerprofil(start, segmenter)
    en_gang = _spill_av(bruddpunkt, bruddpunkt, stand)

    med_gjentakelser: list[datetime] = []
    for naar in bruddpunkt:
        med_gjentakelser.extend([naar] * gjentakelser)
    mange = _spill_av(med_gjentakelser, bruddpunkt, stand)

    assert set(en_gang) == set(mange)
    for nokkel, kwh in en_gang.items():
        assert mange[nokkel] == pytest.approx(kwh, abs=1e-9, rel=1e-9)
    assert sum(mange.values()) == pytest.approx(stand[bruddpunkt[-1]], abs=1e-9, rel=1e-9)


# ---------------------------------------------------------------------------
# Prisadapteren (A2.1, C2.5, C2.6)

TIME = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)
KVARTERVERDIER = {0: 1.00, 15: 1.10, 30: 1.20, 45: 1.30}


def _pris_i_ruten(polltid: datetime) -> float:
    return KVARTERVERDIER[prisrutestart(polltid, PRISRUTE_MINUTTER).minute]


@given(
    forskyvning=st.integers(min_value=0, max_value=599),
    poll_sekunder=st.integers(min_value=10, max_value=PRISRUTE_MINUTTER * 60 - PRIS_SETTLE_SEKUNDER),
)
@settings(max_examples=300, deadline=None)
def test_prisen_er_polltidsuavhengig_nar_hver_rute_pollet(forskyvning: int, poll_sekunder: int) -> None:
    """C2.6 for pris: verdien i en rute er den samme uansett når i ruten den ble lest.

    En tidsvektet trinnfunksjon av polltiden ville ikke bestått denne: da ville
    forskyvningen flyttet prisen.
    """
    adapter = Prisadapter()
    naa = TIME + timedelta(seconds=forskyvning)
    while naa < TIME + AVREGNINGSINTERVALL:
        adapter.registrer(naa, _pris_i_ruten(naa))
        naa += timedelta(seconds=poll_sekunder)
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == 4
    assert pris.kvalitet is Intervallkvalitet.KOMPLETT
    assert pris.nok_per_kwh_eks_mva == pytest.approx(sum(KVARTERVERDIER.values()) / 4, abs=1e-12)


@given(
    prover=st.lists(
        st.tuples(st.integers(min_value=0, max_value=3599), st.floats(min_value=-1.0, max_value=10.0)),
        min_size=1,
        max_size=20,
        unique_by=lambda p: p[0],
    ),
    stokking=st.randoms(use_true_random=False),
)
@settings(max_examples=300, deadline=None)
def test_prisen_er_uavhengig_av_registreringsrekkefolgen(
    prover: list[tuple[int, float]], stokking: Random
) -> None:
    """A2.1 punkt 3: polltiden avgjør hvem som vinner ruten, ikke kallrekkefølgen."""

    def avspilling(rekke: list[tuple[int, float]]) -> tuple[float | None, int]:
        adapter = Prisadapter()
        for sekund, verdi in rekke:
            adapter.registrer(TIME + timedelta(seconds=sekund), verdi)
        pris = adapter.prisintervall(TIME)
        return pris.nok_per_kwh_eks_mva, pris.pris_prover

    stokket = list(prover)
    stokking.shuffle(stokket)
    assert avspilling(sorted(prover)) == avspilling(stokket)


@given(
    sekunder=st.lists(st.integers(min_value=0, max_value=PRIS_SETTLE_SEKUNDER - 1), min_size=1, max_size=8),
    verdi=st.floats(min_value=0.1, max_value=5.0),
)
@settings(max_examples=200, deadline=None)
def test_bare_prover_i_settlevinduet_gir_ingen_pris_og_aldri_null(sekunder: list[int], verdi: float) -> None:
    """C8 P6 og C2.5: en sensor som bare ble lest for tidlig gir ingen pris, ikke en halv."""
    adapter = Prisadapter()
    for sekund in sekunder:
        for minutt in (0, 15, 30, 45):
            adapter.registrer(TIME + timedelta(minutes=minutt, seconds=sekund), verdi)
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == 0
    assert pris.nok_per_kwh_eks_mva is None
    assert pris.kvalitet is Intervallkvalitet.UTEN_PRIS


@given(
    ruter=st.lists(st.sampled_from([0, 15, 30, 45]), min_size=1, max_size=4, unique=True),
    verdier=st.lists(st.floats(min_value=-2.0, max_value=12.0), min_size=4, max_size=4),
)
@settings(max_examples=300, deadline=None)
def test_timeprisen_er_snittet_av_rutene_som_fikk_prove(ruter: list[int], verdier: list[float]) -> None:
    """A2.1: 1 til 4 prøver, uvektet snitt, og kvaliteten følger antallet."""
    adapter = Prisadapter()
    valgt = []
    for minutt in ruter:
        verdi = verdier[minutt // 15]
        adapter.registrer(TIME + timedelta(minutes=minutt, seconds=90), verdi)
        valgt.append(verdi)
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == len(ruter)
    assert pris.nok_per_kwh_eks_mva == pytest.approx(sum(valgt) / len(valgt), abs=1e-12)
    ventet = Intervallkvalitet.KOMPLETT if len(ruter) == 4 else Intervallkvalitet.DELVIS_PRIS
    assert pris.kvalitet is ventet


@given(minutt=st.integers(min_value=0, max_value=59), sekund=st.integers(min_value=0, max_value=59))
@settings(max_examples=200, deadline=None)
def test_en_prove_pavirker_bare_sin_egen_time(minutt: int, sekund: int) -> None:
    """C2.5: prisen bæres ikke inn i naboens intervall, og blir ikke 0 der."""
    adapter = Prisadapter()
    adapter.registrer(TIME + timedelta(minutes=minutt, seconds=sekund), 1.5)
    for naboskift in (-2, -1, 1, 2):
        nabo = adapter.prisintervall(TIME + naboskift * AVREGNINGSINTERVALL)
        assert nabo.nok_per_kwh_eks_mva is None
        assert nabo.pris_prover == 0
