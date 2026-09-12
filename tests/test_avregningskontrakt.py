"""Vakt for avregningskontrakten i docs/kontrakter/avregning.md.

Kontrakten er en tekst, og en tekst kan ikke feile. Derfor ligger
fordelingsregelen og sommertidsmerkelappene som normative tabeller i
dokumentet, og her kjøres de. Endrer noen tallene i tabellen uten å endre
regelen (eller omvendt), feller denne testen det.

`fordel_delta` under er kontraktens utførbare form, C1. L1 skal reprodusere
den samme fordelingen; avregningskjernen importerer ikke herfra, den måles mot
de samme tabellradene. Går de to fra hverandre, er det denne filen som sier
hvilken som har rett.

Nederst måles i tillegg `avregning.py` direkte mot de paragrafene som avgjør
noe om ett intervall (B3 og D). Det er den delen L1 måtte velge selv fordi
kontrakten tidde, og et valg uten vakt drifter.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from stromkalkulator.avregning import (
    Avlesning,
    AvregnetIntervall,
    Avregningsbok,
    Energikvalitet,
    Intervallkvalitet,
    med_pris,
)

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
        "### A2.1 Prisruten",
        "### C6 Åpent, lukket og uforanderlig",
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
# Prøvetabellen for fordelingen (C7)


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
    """C7: hver rad i den normative tabellen skal komme ut av regelen i C1."""
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


def _dst_tabell() -> list[tuple[str, datetime, str, str, str]]:
    rader = []
    for rad in _tabellrader(_kontrakttekst(), r"D\d+"):
        sak, utc, lokal, maaned, avgiftsaar = rad
        rader.append((sak, datetime.fromisoformat(utc.replace("Z", "+00:00")), lokal, maaned, avgiftsaar))
    return rader


DST = _dst_tabell()


def test_dst_tabellen_er_lest() -> None:
    assert len(DST) >= 6


@pytest.mark.parametrize(("sak", "utc", "lokal", "maaned", "avgiftsaar"), DST, ids=[d[0] for d in DST])
def test_lokal_merkelapp_kommer_fra_utc_start(
    sak: str, utc: datetime, lokal: str, maaned: str, avgiftsaar: str
) -> None:
    """C3: merkelappen er start_utc omregnet med zoneinfo, ikke veggklokke-regning."""
    i_oslo = utc.astimezone(OSLO)
    forventet = f"{i_oslo:%Y-%m-%d %H:%M} {'CEST' if i_oslo.utcoffset() == timedelta(hours=2) else 'CET'}"
    assert forventet == lokal, sak
    assert f"{i_oslo:%Y-%m}" == maaned, sak
    assert f"{i_oslo:%Y}" == avgiftsaar, f"{sak}: regelkilde følger start_utc, også over årsskiftet"


def test_arsskiftet_er_dekket() -> None:
    """C3: årsskiftet sto ikke i tabellen, og avgiftssatsene skifter der."""
    assert any(sak == "D6" and maaned == "2027-01" for sak, _, _, maaned, _ in DST)


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


# ---------------------------------------------------------------------------
# Prisruter (A2.1 og C8)


def _settlevindu() -> int:
    """`PRIS_SETTLE_SEKUNDER` slik kontrakten oppgir den."""
    treff = re.search(r"`PRIS_SETTLE_SEKUNDER` \((\d+)\)", _kontrakttekst())
    assert treff, "A2.1 må oppgi settlevinduet i sekunder"
    return int(treff.group(1))


SETTLE = _settlevindu()
PRISINTERVALL = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def prisrutestart(tidspunkt: datetime, opplosning_minutter: int) -> datetime:
    """Starten på prisruten tidspunktet faller i (A2.1, forankret i klokketimen)."""
    if tidspunkt.tzinfo is None:
        raise ValueError("polltid må være tidssoneklar")
    i_utc = tidspunkt.astimezone(UTC)
    minutt = (i_utc.minute // opplosning_minutter) * opplosning_minutter
    return i_utc.replace(minute=minutt, second=0, microsecond=0)


def prisprover(polls: list[tuple[datetime, float]], opplosning_minutter: int) -> dict[datetime, float]:
    """Kontraktens utførbare form av A2.1: polls inn, én verdi per prisrute ut.

    Prøven tilordnes ruten polltiden faller i, godtas først når polltiden ligger
    minst `PRIS_SETTLE_SEKUNDER` etter rutestart, og siste godkjente prøve i en
    rute gjelder. Verdien bæres aldri inn i en annen rute.
    """
    ruter: dict[datetime, float] = {}
    for polltid, verdi in sorted(polls):
        start = prisrutestart(polltid, opplosning_minutter)
        if (polltid - start).total_seconds() < SETTLE:
            continue
        ruter[start] = verdi
    return ruter


def intervallpris(
    polls: list[tuple[datetime, float]], opplosning_minutter: int
) -> tuple[float | None, int, int]:
    """(pris, antall ruter med prøve, ventet antall) for avregningsintervallet."""
    ventet = 60 // opplosning_minutter
    ruter = {
        start: verdi
        for start, verdi in prisprover(polls, opplosning_minutter).items()
        if PRISINTERVALL <= start < PRISINTERVALL + INTERVALL
    }
    if not ruter:
        return None, 0, ventet
    return sum(ruter.values()) / len(ruter), len(ruter), ventet


def _pristabell() -> list[tuple[str, int, list[tuple[datetime, float]], int, float | None, str]]:
    saker = []
    for rad in _tabellrader(_kontrakttekst(), r"P\d+"):
        sak, opplosning, polls, ruter, pris, kvalitet = rad
        avlesninger = []
        for ledd in polls.split(";"):
            naar, verdi = ledd.split("=")
            minutt, sekund = (int(d) for d in naar.strip().split(":"))
            avlesninger.append((PRISINTERVALL + timedelta(minutes=minutt, seconds=sekund), float(verdi)))
        forventet = None if pris.strip() in {"—", "-"} else float(pris)
        saker.append((sak, int(opplosning), avlesninger, int(ruter), forventet, kvalitet))
    return saker


PRISER = _pristabell()


def test_pristabellen_er_lest() -> None:
    """En tom tabell ville gjort radtestene under grønne uten å sjekke noe."""
    assert len(PRISER) >= 7


@pytest.mark.parametrize(
    ("sak", "opplosning", "polls", "ruter", "forventet", "kvalitet"), PRISER, ids=[p[0] for p in PRISER]
)
def test_prisregelen_treffer_provetabellen(
    sak: str,
    opplosning: int,
    polls: list[tuple[datetime, float]],
    ruter: int,
    forventet: float | None,
    kvalitet: str,
) -> None:
    """C8: hver rad i den normative tabellen skal komme ut av regelen i A2.1."""
    pris, antall, ventet = intervallpris(polls, opplosning)
    assert antall == ruter, sak
    if forventet is None:
        assert pris is None, sak
    else:
        assert pris == pytest.approx(forventet, abs=1e-9), sak
    maalt = "uten_pris" if antall == 0 else ("komplett" if antall == ventet else "delvis_pris")
    assert maalt == kvalitet, sak


def test_like_priser_pa_rad_gir_en_prove_per_rute() -> None:
    """A2.1: feilen som gjorde seksjonen nødvendig.

    En prissensor med samme pris i fire kvarter på rad oppdaterer ikke
    `last_updated`. Regelen leser polltiden og ruten, ikke staten, så alle fire
    rutene får prøve likevel.
    """
    polls = [(PRISINTERVALL + timedelta(minutes=m, seconds=90), 1.0) for m in (0, 15, 30, 45)]
    pris, antall, ventet = intervallpris(polls, 15)
    assert (pris, antall, ventet) == (1.0, 4, 4)


def test_prove_baeres_aldri_inn_i_neste_rute() -> None:
    """C2.5: en rute uten egen prøve får ikke naboens pris."""
    polls = [(PRISINTERVALL + timedelta(minutes=2), 1.0)]
    assert prisprover(polls, 15) == {PRISINTERVALL: 1.0}


def test_prove_i_settlevinduet_teller_ikke() -> None:
    """A2.1 punkt 2: den første pollen etter rutegrensen har forrige rutes pris."""
    tidlig = [(PRISINTERVALL + timedelta(seconds=SETTLE - 1), 0.9)]
    assert prisprover(tidlig, 15) == {}
    sent = [(PRISINTERVALL + timedelta(seconds=SETTLE), 0.9)]
    assert prisprover(sent, 15) == {PRISINTERVALL: 0.9}


@given(
    forskyvning=st.integers(min_value=0, max_value=599),
    poll_sekunder=st.integers(min_value=10, max_value=300),
)
@settings(max_examples=200, deadline=None)
def test_prisen_er_polltidsuavhengig_nar_hver_rute_pollet(forskyvning: int, poll_sekunder: int) -> None:
    """C2.6 for pris: prisen er snittet av rutene, uansett når i rutene det ble pollet.

    Så lenge pollintervallet er kortere enn ruten minus settlevinduet, treffer
    enhver pollplan alle fire rutene, og svaret er det samme uvektede snittet.
    Tidsvekting av polltiden ville ikke bestått denne.
    """
    verdier = {0: 1.00, 15: 1.10, 30: 1.20, 45: 1.30}

    def pris_i_ruten(polltid: datetime) -> float:
        return verdier[prisrutestart(polltid, 15).minute]

    polls = []
    naa = PRISINTERVALL + timedelta(seconds=forskyvning)
    slutt = PRISINTERVALL + INTERVALL
    while naa < slutt:
        polls.append((naa, pris_i_ruten(naa)))
        naa += timedelta(seconds=poll_sekunder)

    pris, antall, ventet = intervallpris(polls, 15)
    assert (antall, ventet) == (4, 4)
    assert pris == pytest.approx(sum(verdier.values()) / 4, abs=1e-12)


def test_uvektet_snitt_er_samme_regning_som_forskningsskriptene() -> None:
    """A2: `verify_norgespris_eksakt.py` og `maal_fordelingsregel.py` regner sum/len/1000.

    Fire kvarterpriser i NOK/MWh gjennom prisregelen skal gi nøyaktig samme tall
    som arkivregningen, ellers regner drift og etterkontroll ulikt.
    """
    kvarter_nok_mwh = [1266.45, 1288.36, 1299.42, 1301.11]
    polls = [
        (PRISINTERVALL + timedelta(minutes=m, seconds=90), verdi / 1000)
        for m, verdi in zip((0, 15, 30, 45), kvarter_nok_mwh, strict=True)
    ]
    pris, _, _ = intervallpris(polls, 15)
    assert pris == pytest.approx(sum(kvarter_nok_mwh) / len(kvarter_nok_mwh) / 1000, abs=1e-15)


# ---------------------------------------------------------------------------
# Bruker uten energisensor (B1) og avviste deltaer (C1)


def _seksjon(overskrift: str) -> str:
    """Teksten fra en overskrift til den neste på samme eller høyere nivå."""
    tekst = _kontrakttekst()
    assert overskrift in tekst, f"kontrakten mangler {overskrift!r}"
    rest = tekst.split(overskrift, 1)[1]
    linjer = []
    for linje in rest.splitlines():
        if linje.startswith("## ") or linje.startswith("### "):
            break
        linjer.append(linje)
    return "\n".join(linjer)


_PUNKTSTART = re.compile(r"^(?:- |\d+\. )")


def _punkter(tekst: str) -> list[str]:
    """Punktene i en liste, med fortsettelseslinjene slått sammen til én streng.

    Både kulepunkter og nummererte punkter, siden C2 bruker det siste. Et punkt
    lest linje for linje ville delt en setning i to og gjort vaktene under
    blinde for alt som står etter første linjeskift.
    """
    punkter: list[str] = []
    for linje in tekst.splitlines():
        if _PUNKTSTART.match(linje):
            punkter.append(_PUNKTSTART.sub("", linje).strip())
        elif punkter and linje.startswith("  ") and linje.strip():
            punkter[-1] += " " + linje.strip()
    return punkter


B1 = _seksjon("### B1 Energiavlesning")


def _syntetisk_tabell() -> dict[str, str]:
    """Feltene i B1s tabell for den syntetiske avlesningen."""
    rader = {}
    treff = False
    for linje in B1.splitlines():
        if not linje.startswith("|"):
            treff = False
            continue
        celler = [c.strip() for c in linje.strip().strip("|").split("|")]
        if celler[1].startswith("Verdi for en syntetisk avlesning"):
            treff = True
            continue
        if treff and celler[0].startswith("`"):
            rader[celler[0].strip("`")] = celler[1]
    return rader


def test_brukeren_uten_energisensor_er_beskrevet() -> None:
    """Funn 1: en bruker med effekt og spot, men uten teller, må ha et svar.

    Uten avsnittet ville L1 og L3a landet ulikt: den ene lar effektbrukeren
    stå utenfor boken på dagens akkumulatorer, den andre finner opp en
    syntetisk avlesning og gjetter på `observed_at`.
    """
    assert "Bruker uten energisensor" in B1
    tabell = _syntetisk_tabell()
    assert set(tabell) == {"source_identity", "entity_id", "value_kwh", "observed_at", "kvalitet"}, (
        f"den syntetiske avlesningen må fylle alle feltene i B1, fant {sorted(tabell)}"
    )
    assert "estimert" in tabell["kvalitet"], "B1s `estimert` er nettopp denne stien"
    assert "olltid" in tabell["observed_at"], "observasjonstiden for en effektprøve må stå"
    assert "unique_id" in tabell["source_identity"]


@pytest.mark.parametrize(
    ("emne", "krav"),
    [
        ("C2.6", "at estimatet ikke er polltidsuavhengig"),
        ("MAX_ELAPSED_HOURS", "hva et for langt vindu gjør"),
        ("konfigurert", "hvilken sti som gjelder når begge sensorene finnes"),
    ],
)
def test_effektstien_svarer_pa_det_en_utforer_ellers_ville_gjettet(emne: str, krav: str) -> None:
    """De tre følgene som ikke kan utledes av tabellen alene."""
    punkter = [p for p in _punkter(B1) if emne in p]
    assert punkter, f"B1 sier ikke {krav} ({emne})"


def test_c2_6_innrommer_unntaket_for_effektstien() -> None:
    """To steder med hver sin sannhet er feilen som felte kontraktene første gang.

    B1 sier at invarianten ikke holder uten teller. Står ikke det samme i C2.6,
    lover invariantlisten noe B1 tar tilbake.
    """
    invarianter = _seksjon("### C2 Invariantene")
    punkt = next(p for p in _punkter(invarianter) if p.startswith("**Polltidsuavhengighet"))
    assert "uten energisensor" in punkt and "B1" in punkt, (
        "C2.6 må si at effektstien er unntatt, og vise til B1"
    )


def _randtilfeller() -> list[str]:
    c1 = _seksjon("### C1 Fordelingsregel: jevnt over tid")
    punkter = _punkter(c1.split("Randtilfeller:", 1)[1])
    assert len(punkter) >= 3, "C1 må fortsatt liste randtilfellene"
    return punkter


@pytest.mark.parametrize("nokkel", ["MAX_ENERGY_DELTA_KWH", "Negativt delta"])
def test_avvist_delta_sier_hva_som_skjer_med_baselinen(nokkel: str) -> None:
    """Funn 3: står ikke flyttingen der, implementerer en utfører det motsatte.

    Blir baselinen stående etter et avvist sprang, ligger hver senere avlesning
    også over grensen, og boken står stille for godt etter étt sprang. Koden i
    dag flytter den (`_compute_energy_delta` skriver `_last_tpi_kwh` uansett
    gren), og kontrakten skal si det samme.
    """
    punkt = next((p for p in _randtilfeller() if nokkel in p), None)
    assert punkt, f"C1 mangler randtilfellet for {nokkel}"
    assert "baseline" in punkt.lower(), f"C1 sier ikke hva som skjer med baselinen ved {nokkel}"


def test_avvist_sprang_er_synlig_i_data_dicten() -> None:
    """Et avvist delta skal telles, ikke forsvinne."""
    punkt = next(p for p in _randtilfeller() if "MAX_ENERGY_DELTA_KWH" in p)
    assert "avregning_avvist_kwh" in punkt
    assert "`avregning_avvist_kwh`" in _kontrakttekst().split("Nye felt:")[1]


# ---------------------------------------------------------------------------
# Kvaliteten på et avregnet intervall (B3, D)
#
# B3 hadde `ufullstendig` i enumet uten at noen paragraf sa når et intervall
# får den, og ingen plass til om energien var målt eller estimert. L1 måtte
# velge selv. Valgene står i kontrakten nå, og her måles de mot koden, slik at
# den neste ikke lander et annet sted.


B3 = _seksjon("### B3 Avregnet intervall")
D = _seksjon("## D. Persistens og migrering")
START = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def _b3_felt() -> dict[str, str]:
    """Feltnavn til betydning i B3s felttabell."""
    felt = {}
    for linje in B3.splitlines():
        if not linje.startswith("|"):
            continue
        # `\|` er en pipe i en celle, ikke en cellegrense: `prisintervall | None`.
        celler = [c.strip() for c in linje.strip().strip("|").replace("\\|", "§").split("|")]
        if len(celler) == 3 and celler[0].startswith("`"):
            felt[celler[0].strip("`")] = celler[2]
    assert felt, "B3 har ingen felttabell"
    return felt


def _enumverdier(celle: str) -> set[str]:
    return set(re.findall(r"`([a-z_]+)`", celle))


def test_b3_har_alle_feltene_koden_har() -> None:
    """Felttabellen er grensesnittet L2, L3a, L3b og L3c bygger mot.

    Et felt som bare finnes i koden er et felt ingen andre vet om, og det var
    nettopp det som skjedde med `energikvalitet`.
    """
    assert set(_b3_felt()) == set(AvregnetIntervall.__dataclass_fields__), (
        "B3s felttabell og AvregnetIntervall skal ha nøyaktig de samme feltene"
    )


def test_b3_lister_kvalitetsverdiene_koden_kan_gi() -> None:
    assert _enumverdier(_b3_felt()["kvalitet"]) == {str(k) for k in Intervallkvalitet}


def test_b3_sier_at_energien_er_malt_eller_estimert() -> None:
    """Funn 2: planen ba om energikvalitet per intervall, tabellen hadde den ikke."""
    verdier = _enumverdier(_b3_felt()["energikvalitet"])
    assert verdier == {"malt", "estimert"}, (
        "B3 skal love målt eller estimert, og bare de to; `avvist` bokføres aldri"
    )
    assert verdier < {str(k) for k in Energikvalitet}


def test_b3_sier_nar_et_intervall_er_ufullstendig() -> None:
    """Funn 1: enumet hadde verdien, men ingen paragraf sa når den gjelder."""
    avsnitt = next((a for a in B3.split("\n\n") if "Når `kvalitet` er `ufullstendig`" in a), None)
    assert avsnitt, "B3 må ha avsnittet som avgjør når et intervall er `ufullstendig`"
    assert "bare når" in avsnitt, "regelen skal være uttømmende, ikke en av flere grunner"
    assert "migreringen" in avsnitt
    assert "`pris.kvalitet`" in B3, "priskvaliteten skal fortsatt være å få tak i"


def test_d_gir_intervallene_flagget_maneden_har() -> None:
    """Måneden merkes i D, og intervallene arver det. Ellers er de to uenige."""
    punkt = next((p for p in _punkter(D) if "avregning_ufullstendig" in p), None)
    assert punkt, "D må fortsatt merke måneden"
    assert "kvalitet = ufullstendig" in punkt, "D skal si at flagget også gjelder hvert intervall (B3)"


def _avlesning(kwh: float, naar: datetime, **kwargs: Any) -> Avlesning:
    return Avlesning(source_identity="meter-1", value_kwh=kwh, observed_at=naar, **kwargs)


def test_ufullstendig_vinner_over_en_komplett_pris() -> None:
    """B3: en overstyring, ikke en fjerde priskvalitet.

    Et intervall med alle fire prisrutene er `komplett` som pris og likevel
    `ufullstendig` som intervall, for måneden mangler historikk.
    """
    bok = Avregningsbok.fra_lagring({"version": 2}, dso_id="bkk")
    for minutt in (2, 17, 32, 47):
        bok.pris.registrer(START + timedelta(minutes=minutt), 1.0)
    bok.bokfor(_avlesning(100.0, START))
    bok.bokfor(_avlesning(101.0, START + INTERVALL))
    intervall = bok.intervall(START)
    assert intervall is not None
    assert intervall.pris is not None
    assert intervall.pris.kvalitet is Intervallkvalitet.KOMPLETT
    assert intervall.kvalitet is Intervallkvalitet.UFULLSTENDIG
    assert med_pris(intervall, intervall.pris).kvalitet is Intervallkvalitet.UFULLSTENDIG


def test_ufullstendig_gjelder_ingen_andre_intervaller() -> None:
    """«Bare når» i B3: en bok som aldri krysset migreringen merker ingenting."""
    bok = Avregningsbok.fra_lagring(None, dso_id="bkk")
    bok.bokfor(_avlesning(100.0, START))
    bok.bokfor(_avlesning(101.0, START + INTERVALL))
    intervall = bok.intervall(START)
    assert intervall is not None
    assert intervall.kvalitet is Intervallkvalitet.UTEN_PRIS


def test_estimert_smitter_og_vaskes_aldri_bort() -> None:
    """B3: den svakeste kilden gjelder for hele intervallet."""
    bok = Avregningsbok(dso_id="bkk")
    bok.bokfor(_avlesning(100.0, START))
    bok.bokfor(_avlesning(101.0, START + timedelta(minutes=20)))
    # Effektstien starter med en baseline på sin egen kilde, og vinduet må
    # holde seg innenfor MAX_ELAPSED_HOURS for å bli bokført i det hele tatt.
    bok.bokfor(Avlesning("effekt", 0.0, START + timedelta(minutes=20), kvalitet=Energikvalitet.ESTIMERT))
    bok.bokfor(Avlesning("effekt", 0.2, START + timedelta(minutes=25), kvalitet=Energikvalitet.ESTIMERT))
    intervall = bok.intervall(START)
    assert intervall is not None
    assert intervall.energikvalitet is Energikvalitet.ESTIMERT


def test_avvist_energi_har_ikke_noe_intervall_a_sta_pa() -> None:
    """B3: `avvist` er en avlesning som ikke ble bokført, ikke en intervallkvalitet."""
    bok = Avregningsbok(dso_id="bkk")
    bok.bokfor(_avlesning(100.0, START))
    bok.bokfor(_avlesning(105.0, START + INTERVALL, kvalitet=Energikvalitet.AVVIST))
    assert bok.intervaller() == []


# ---------------------------------------------------------------------------
# Store-versjonen (D)


def test_versjonen_er_et_felt_i_dataene_ikke_i_store_konstruktoren() -> None:
    """K1 måtte velge dette selv, og valget skal ikke gjøres om på nytt.

    Står det ikke her, bumper den neste `Store`-konstruktøren og får et
    testmiljø som ikke lar seg laste.
    """
    assert "`skjema_versjon`" in D
    assert "Store(hass, 1, ...)" in D, "D må si at konstruktørens versjon blir stående"
    assert "input-og-konfig.md#5-energibaseline" in D, "begrunnelsen eies i K0 §5"


def test_store_konstrueres_aldri_med_en_annen_major_versjon() -> None:
    """Regelen er verdiløs om koden får bumpe den likevel."""
    komponent = ROT / "custom_components" / "stromkalkulator"
    funn = [
        (sti.name, versjon)
        for sti in komponent.glob("*.py")
        for versjon in re.findall(r"Store\(\s*(?:self\.)?hass,\s*(\d+)", sti.read_text(encoding="utf-8"))
    ]
    assert funn, "fant ingen Store-konstruksjon å vokte"
    feil = [f for f in funn if f[1] != "1"]
    assert not feil, f"D: Store-versjonen blir stående på 1, skjemaet står i dataene. {feil}"
