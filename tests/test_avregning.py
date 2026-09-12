"""Eksempeltester for avregningskjernen (`avregning.py`, L1).

Testene her måler modulen mot de normative tabellene i
`docs/kontrakter/avregning.md`. Tabellene leses ut av dokumentet, ikke skrevet
av på nytt: endres en rad i kontrakten uten at koden følger etter, skal det
felle noe her.

Egenskapene som ikke lar seg uttømme med eksempler ligger i
`test_avregning_property.py`.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from stromkalkulator.avregning import (
    AVREGNINGSINTERVALL,
    PRIS_SETTLE_SEKUNDER,
    SKJEMA_VERSJON,
    Avlesning,
    Avregningsbok,
    Energikvalitet,
    Intervallkvalitet,
    Prisadapter,
    Prisintervall,
    Priskilde,
    Revisjon,
    Tariff,
    Tariffregel,
    Utfall,
    avgiftsaar,
    fordel_delta,
    intervallstart,
    lokal_maned,
    lokal_time,
    med_pris,
    migrer_lagring,
    prisrutestart,
    regelkilde,
    varighet_sekunder,
)

KONTRAKT = Path(__file__).parent.parent / "docs" / "kontrakter" / "avregning.md"
OSLO = ZoneInfo("Europe/Oslo")
TIME = datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Tabellene i kontrakten


def _kontrakttekst() -> str:
    assert KONTRAKT.exists(), f"{KONTRAKT} finnes ikke"
    return KONTRAKT.read_text(encoding="utf-8")


def _tabellrader(forste_kolonne: str) -> list[list[str]]:
    rader: list[list[str]] = []
    treff = False
    for linje in _kontrakttekst().splitlines():
        if not linje.startswith("|"):
            treff = False
            continue
        celler = [c.strip() for c in linje.strip().strip("|").split("|")]
        if re.fullmatch(forste_kolonne, celler[0]):
            treff = True
        if treff:
            rader.append(celler)
    assert rader, f"fant ingen rader med første kolonne {forste_kolonne!r}"
    return rader


def _fordelingstabell() -> list[tuple[str, datetime, datetime, float, dict[datetime, float]]]:
    saker = []
    for sak, fra, til, delta, fordeling in _tabellrader(r"F\d+"):
        forventet = {}
        for ledd in fordeling.split(";"):
            start, kwh = ledd.split("=")
            forventet[datetime.fromisoformat(start.strip())] = float(kwh)
        saker.append((sak, datetime.fromisoformat(fra), datetime.fromisoformat(til), float(delta), forventet))
    return saker


def _pristabell() -> list[tuple[str, int, list[tuple[datetime, float]], int, float | None, str]]:
    saker = []
    for sak, opplosning, polls, ruter, pris, kvalitet in _tabellrader(r"P\d+"):
        avlesninger = []
        for ledd in polls.split(";"):
            naar, verdi = ledd.split("=")
            minutt, sekund = (int(d) for d in naar.strip().split(":"))
            avlesninger.append((TIME + timedelta(minutes=minutt, seconds=sekund), float(verdi)))
        forventet = None if pris.strip() in {"—", "-"} else float(pris)
        saker.append((sak, int(opplosning), avlesninger, int(ruter), forventet, kvalitet))
    return saker


def _dst_tabell() -> list[tuple[str, datetime, str, str, str]]:
    return [
        (sak, datetime.fromisoformat(utc.replace("Z", "+00:00")), lokal, maaned, aar)
        for sak, utc, lokal, maaned, aar in _tabellrader(r"D\d+")
    ]


FORDELING = _fordelingstabell()
PRISER = _pristabell()
DST = _dst_tabell()


def test_tabellene_er_lest() -> None:
    """Tomme tabeller ville gjort radtestene under grønne uten å sjekke noe."""
    assert len(FORDELING) >= 6
    assert len(PRISER) >= 7
    assert len(DST) >= 6


@pytest.mark.parametrize(
    ("sak", "fra", "til", "delta", "forventet"), FORDELING, ids=[f[0] for f in FORDELING]
)
def test_fordelingen_treffer_c7(
    sak: str, fra: datetime, til: datetime, delta: float, forventet: dict[datetime, float]
) -> None:
    """C7: kjernen skal gi nøyaktig fordelingen kontrakten oppgir."""
    fordelt = fordel_delta(fra, til, delta)
    assert set(fordelt) == set(forventet), sak
    for start, kwh in forventet.items():
        assert fordelt[start] == pytest.approx(kwh, abs=1e-9), f"{sak} {start.isoformat()}"


@pytest.mark.parametrize(
    ("sak", "opplosning", "polls", "ruter", "forventet", "kvalitet"), PRISER, ids=[p[0] for p in PRISER]
)
def test_prisadapteren_treffer_c8(
    sak: str,
    opplosning: int,
    polls: list[tuple[datetime, float]],
    ruter: int,
    forventet: float | None,
    kvalitet: str,
) -> None:
    """C8: timeprisen av 1 til 4 kvarterprøver, settlevindu og alt."""
    adapter = Prisadapter(opplosning_minutter=opplosning)
    for polltid, verdi in polls:
        adapter.registrer(polltid, verdi)
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == ruter, sak
    if forventet is None:
        assert pris.nok_per_kwh_eks_mva is None, sak
    else:
        assert pris.nok_per_kwh_eks_mva == pytest.approx(forventet, abs=1e-9), sak
    assert str(pris.kvalitet) == kvalitet, sak


@pytest.mark.parametrize(("sak", "utc", "lokal", "maaned", "aar"), DST, ids=[d[0] for d in DST])
def test_merkelappene_treffer_c3(sak: str, utc: datetime, lokal: str, maaned: str, aar: str) -> None:
    """C3: lokal time, fakturamåned og avgiftsår kommer alle fra `start_utc`."""
    time_i_lokal = int(lokal.split()[1].split(":")[0])
    assert lokal_time(utc) == time_i_lokal, sak
    assert lokal_maned(utc) == maaned, sak
    assert avgiftsaar(utc) == int(aar), sak


# ---------------------------------------------------------------------------
# Tid og aware datetimes


def test_naiv_tid_kaster_overalt() -> None:
    """B1: en naiv datetime er en programmeringsfeil, ikke lokal tid."""
    naiv = datetime(2026, 6, 15, 10, 0)
    with pytest.raises(ValueError, match="tidssoneklar"):
        intervallstart(naiv)
    with pytest.raises(ValueError, match="tidssoneklar"):
        prisrutestart(naiv)
    with pytest.raises(ValueError, match="tidssoneklar"):
        fordel_delta(naiv, naiv + timedelta(hours=1), 1.0)
    with pytest.raises(ValueError, match="tidssoneklar"):
        Avlesning("meter", 1.0, naiv)


def test_lokal_tid_gir_samme_intervall_som_utc() -> None:
    """A1: intervallgrensene faller sammen med klokketimen i Europe/Oslo."""
    i_oslo = datetime(2026, 6, 15, 12, 30, tzinfo=OSLO)
    assert intervallstart(i_oslo) == datetime(2026, 6, 15, 10, 0, tzinfo=UTC)


def test_vindu_uten_lengde_kan_ikke_fordeles() -> None:
    """C1: to avlesninger med samme observasjonstid er avvist, ikke bokført."""
    with pytest.raises(ValueError, match="positiv lengde"):
        fordel_delta(TIME, TIME, 1.0)


# ---------------------------------------------------------------------------
# Sommertid med eksakte varigheter


def test_var_dst_gir_23_intervaller_med_eksakt_3600_sekunder() -> None:
    """29.03.2026 mangler en lokal time, men hvert UTC-intervall er en hel time.

    Døgnet er 23 intervaller langt, lokal time 02 finnes ikke, og summen av
    varighetene er 23 timer. Regnet på veggklokken ville dette blitt 24.
    """
    start = datetime(2026, 3, 28, 23, 0, tzinfo=UTC)  # lokal midnatt CET
    slutt = datetime(2026, 3, 29, 22, 0, tzinfo=UTC)  # lokal midnatt CEST dagen etter
    assert varighet_sekunder(start, slutt) == 23 * 3600

    fordelt = fordel_delta(start, slutt, 23.0)
    assert len(fordelt) == 23
    for intervall_start in fordelt:
        assert varighet_sekunder(intervall_start, intervall_start + AVREGNINGSINTERVALL) == 3600.0
        assert fordelt[intervall_start] == pytest.approx(1.0, abs=1e-9)

    timer = [lokal_time(s) for s in sorted(fordelt)]
    assert 2 not in timer, "lokal time 02 finnes ikke 29.03.2026"
    assert timer == [0, 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
    assert {lokal_maned(s) for s in fordelt} == {"2026-03"}


def test_host_dst_gir_25_intervaller_og_to_ganger_lokal_time_02() -> None:
    """25.10.2026 har lokal time 02 to ganger, som to ulike UTC-intervaller."""
    start = datetime(2026, 10, 24, 22, 0, tzinfo=UTC)  # lokal midnatt CEST
    slutt = datetime(2026, 10, 25, 23, 0, tzinfo=UTC)  # lokal midnatt CET dagen etter
    assert varighet_sekunder(start, slutt) == 25 * 3600

    fordelt = fordel_delta(start, slutt, 25.0)
    assert len(fordelt) == 25
    timer = [lokal_time(s) for s in sorted(fordelt)]
    assert timer.count(2) == 2, "den doble timen skal være to intervaller"

    forste, andre = (s for s in sorted(fordelt) if lokal_time(s) == 2)
    assert forste != andre
    assert forste.astimezone(OSLO).utcoffset() != andre.astimezone(OSLO).utcoffset()
    for intervall_start in fordelt:
        assert varighet_sekunder(intervall_start, intervall_start + AVREGNINGSINTERVALL) == 3600.0


def test_fakturamaneden_skifter_ved_lokal_midnatt() -> None:
    """C3 D5: 31.03 kl. 22 UTC er allerede april lokalt."""
    assert lokal_maned(datetime(2026, 3, 31, 21, 0, tzinfo=UTC)) == "2026-03"
    assert lokal_maned(datetime(2026, 3, 31, 22, 0, tzinfo=UTC)) == "2026-04"


def test_regelkilden_folger_start_utc_over_arsskiftet() -> None:
    """C3 D6: intervallet 31.12 kl. 23 UTC er januar lokalt og nytt avgiftsår."""
    assert regelkilde("catalog", "bkk", datetime(2026, 12, 31, 23, 0, tzinfo=UTC)) == "catalog:bkk:2027"
    assert regelkilde("catalog", "bkk", datetime(2026, 12, 31, 22, 0, tzinfo=UTC)) == "catalog:bkk:2026"


# ---------------------------------------------------------------------------
# Tariff


def test_tariffen_avgjores_av_intervallets_start_i_oslo() -> None:
    """B3: dag 06 til 22 lokal tid. Grensen er intervallets start, ikke slutt."""
    regel = Tariffregel()
    # 03:00Z i juni er 05:00 CEST (natt), 04:00Z er 06:00 CEST (dag).
    assert regel.tariff(datetime(2026, 6, 15, 3, 0, tzinfo=UTC)) is Tariff.NATT
    assert regel.tariff(datetime(2026, 6, 15, 4, 0, tzinfo=UTC)) is Tariff.DAG
    # 19:00Z er 21:00 CEST (siste dagtime), 20:00Z er 22:00 CEST (natt).
    assert regel.tariff(datetime(2026, 6, 15, 19, 0, tzinfo=UTC)) is Tariff.DAG
    assert regel.tariff(datetime(2026, 6, 15, 20, 0, tzinfo=UTC)) is Tariff.NATT


def test_helg_og_helligdag_er_natt_nar_dso_en_sier_det() -> None:
    """Helg, fast helligdag og bevegelig helligdag, og motsatt for DSO-er uten regelen."""
    regel = Tariffregel()
    lordag = datetime(2026, 6, 13, 10, 0, tzinfo=UTC)
    forste_mai = datetime(2026, 5, 1, 10, 0, tzinfo=UTC)
    andre_paskedag = datetime(2026, 4, 6, 10, 0, tzinfo=UTC)
    for tid in (lordag, forste_mai, andre_paskedag):
        assert regel.tariff(tid) is Tariff.NATT, tid.isoformat()

    kun_klokke = Tariffregel(helg_som_natt=False)
    for tid in (lordag, forste_mai, andre_paskedag):
        assert kun_klokke.tariff(tid) is Tariff.DAG, tid.isoformat()


def test_dso_ens_ekstra_helligdager_teller() -> None:
    """AGENTS.md: `helligdager_ekstra` er kun for dager en faktura bekrefter."""
    uten = Tariffregel()
    med = Tariffregel(helligdager_ekstra=("12-24", "12-31"))
    julaften = datetime(2026, 12, 24, 10, 0, tzinfo=UTC)  # torsdag, lokal 11:00
    assert uten.tariff(julaften) is Tariff.DAG
    assert med.tariff(julaften) is Tariff.NATT


# ---------------------------------------------------------------------------
# Prisadapteren


def test_manglende_pris_er_none_og_aldri_null() -> None:
    """C2.5 og C4: et intervall uten prøve får ikke prisen 0."""
    pris = Prisadapter().prisintervall(TIME)
    assert pris.nok_per_kwh_eks_mva is None
    assert pris.nok_per_kwh_eks_mva != 0
    assert pris.kvalitet is Intervallkvalitet.UTEN_PRIS
    assert pris.pris_prover == 0
    assert pris.pris_prover_ventet == 4


def test_prisintervall_med_prover_men_uten_pris_kaster() -> None:
    """B2s to felt kan ikke si hver sin ting om hvorvidt prisen finnes."""
    with pytest.raises(ValueError, match="uten prøver finnes ingen pris"):
        Prisintervall(TIME, TIME + AVREGNINGSINTERVALL, 1.0, pris_prover=0)
    with pytest.raises(ValueError, match="med prøver skal prisen finnes"):
        Prisintervall(TIME, TIME + AVREGNINGSINTERVALL, None, pris_prover=2)


@pytest.mark.parametrize("antall", [1, 2, 3, 4])
def test_timeprisen_er_uvektet_snitt_av_rutene_som_kom(antall: int) -> None:
    """A2.1: 1 til 4 kvarterprøver, snittet uvektet, uten mellomavrunding."""
    verdier = [1.00, 1.10, 1.20, 1.30][:antall]
    adapter = Prisadapter()
    for nummer, verdi in enumerate(verdier):
        adapter.registrer(TIME + timedelta(minutes=15 * nummer, seconds=90), verdi)
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == antall
    assert pris.nok_per_kwh_eks_mva == pytest.approx(sum(verdier) / antall, abs=1e-12)
    ventet = Intervallkvalitet.KOMPLETT if antall == 4 else Intervallkvalitet.DELVIS_PRIS
    assert pris.kvalitet is ventet


def test_fire_like_priser_er_fire_prover() -> None:
    """A2.1 og C8 P2: feilen som gjorde prisruteseksjonen nødvendig.

    En prissensor som står stille oppdaterer ikke `last_updated`. Leste vi
    observasjonstiden av staten, ville dette blitt én prøve og tre hull.
    """
    adapter = Prisadapter()
    for minutt in (0, 15, 30, 45):
        adapter.registrer(TIME + timedelta(minutes=minutt, seconds=90), 1.0)
    pris = adapter.prisintervall(TIME)
    assert (pris.pris_prover, pris.nok_per_kwh_eks_mva) == (4, 1.0)
    assert pris.kvalitet is Intervallkvalitet.KOMPLETT


def test_prove_i_settlevinduet_teller_ikke() -> None:
    """A2.1 punkt 2: første poll etter rutegrensen bærer forrige rutes pris."""
    tidlig = Prisadapter()
    assert tidlig.registrer(TIME + timedelta(seconds=PRIS_SETTLE_SEKUNDER - 1), 0.9) is None
    assert tidlig.prisintervall(TIME).pris_prover == 0

    presis = Prisadapter()
    assert presis.registrer(TIME + timedelta(seconds=PRIS_SETTLE_SEKUNDER), 0.9) == TIME
    assert presis.prisintervall(TIME).nok_per_kwh_eks_mva == 0.9


def test_proven_baeres_aldri_inn_i_en_annen_rute() -> None:
    """C2.5: en rute uten egen prøve får ikke naboens pris, og ikke 0."""
    adapter = Prisadapter()
    adapter.registrer(TIME + timedelta(minutes=2), 1.0)
    assert adapter.ruter_i(TIME) == {TIME: 1.0}
    pris = adapter.prisintervall(TIME)
    assert pris.pris_prover == 1
    assert pris.nok_per_kwh_eks_mva == 1.0  # snittet av den ene ruten, ikke 0.25
    assert adapter.prisintervall(TIME + AVREGNINGSINTERVALL).nok_per_kwh_eks_mva is None


def test_seneste_prove_i_ruten_vinner_uansett_registreringsrekkefolge() -> None:
    """A2.1 punkt 3, og rekkefølgeuavhengighet: polltiden avgjør, ikke kallet."""
    tidlig = (TIME + timedelta(minutes=2), 1.0)
    sen = (TIME + timedelta(minutes=10), 1.4)
    framover = Prisadapter()
    bakover = Prisadapter()
    for polltid, verdi in (tidlig, sen):
        framover.registrer(polltid, verdi)
    for polltid, verdi in (sen, tidlig):
        bakover.registrer(polltid, verdi)
    assert framover.ruter_i(TIME) == bakover.ruter_i(TIME) == {TIME: 1.4}


def test_prisadapteren_avviser_ikke_endelige_tall() -> None:
    """En NaN-pris ville forgiftet snittet uten å si fra."""
    with pytest.raises(ValueError, match="endelig tall"):
        Prisadapter().registrer(TIME + timedelta(minutes=2), float("nan"))


def test_negativ_pris_er_gyldig() -> None:
    """B2: negative priser klippes ikke."""
    adapter = Prisadapter()
    for minutt in (0, 15, 30, 45):
        adapter.registrer(TIME + timedelta(minutes=minutt, seconds=90), -0.4)
    assert adapter.prisintervall(TIME).nok_per_kwh_eks_mva == pytest.approx(-0.4)


def test_uvektet_snitt_er_samme_regning_som_forskningsskriptene() -> None:
    """A2: `verify_norgespris_eksakt.py` regner `sum(kvarter) / len(kvarter) / 1000`."""
    kvarter_nok_mwh = [1266.45, 1288.36, 1299.42, 1301.11]
    adapter = Prisadapter()
    for minutt, verdi in zip((0, 15, 30, 45), kvarter_nok_mwh, strict=True):
        adapter.registrer(TIME + timedelta(minutes=minutt, seconds=90), verdi / 1000)
    assert adapter.prisintervall(TIME).nok_per_kwh_eks_mva == pytest.approx(
        sum(kvarter_nok_mwh) / len(kvarter_nok_mwh) / 1000, abs=1e-15
    )


def test_timesopplost_sensor_gir_timesprisen_selv() -> None:
    """A2.1: samme regel for kvartersnativ og timesoppløst sensor.

    En sensor som holder samme verdi gjennom timen fyller alle fire rutene med
    det samme tallet, og det uvektede snittet av fire like tall er tallet selv.
    """
    adapter = Prisadapter()
    naa = TIME + timedelta(seconds=70)
    while naa < TIME + AVREGNINGSINTERVALL:
        adapter.registrer(naa, 1.23)
        naa += timedelta(minutes=1)
    pris = adapter.prisintervall(TIME)
    assert (pris.pris_prover, pris.nok_per_kwh_eks_mva) == (4, 1.23)
    assert pris.kvalitet is Intervallkvalitet.KOMPLETT


# ---------------------------------------------------------------------------
# Boken: bokføring og dobbeltbokføring


def _bok(**kwargs: object) -> Avregningsbok:
    return Avregningsbok(dso_id="bkk", **kwargs)  # type: ignore[arg-type]


def _les(kwh: float, naar: datetime, kilde: str = "meter-1") -> Avlesning:
    return Avlesning(source_identity=kilde, value_kwh=kwh, observed_at=naar)


def test_forste_avlesning_er_baseline_og_bokforer_ingenting() -> None:
    """C5: baselinen er en stand, ikke et forbruk."""
    bok = _bok()
    svar = bok.bokfor(_les(100.0, TIME))
    assert svar.utfall is Utfall.BASELINE
    assert bok.intervaller() == []
    assert bok.sist_observert is not None
    assert bok.sist_observert.value_kwh == 100.0


def test_duplisert_avlesning_bokfores_ikke_to_ganger() -> None:
    """C2.2: identiteten er (kilde, observasjonstid, verdi)."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    forste = bok.bokfor(_les(102.0, TIME + timedelta(hours=1)))
    assert forste.utfall is Utfall.BOKFORT

    for _ in range(3):
        igjen = bok.bokfor(_les(102.0, TIME + timedelta(hours=1)))
        assert igjen.utfall is Utfall.DUPLIKAT
        assert igjen.bokfort_kwh == 0.0

    assert sum(i.kwh for i in bok.intervaller()) == pytest.approx(2.0, abs=1e-9)


def test_forsinket_avlesning_bokfores_ikke_pa_nytt() -> None:
    """C2.3: eldre observasjonstid enn siste behandlede er forsinket."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(102.0, TIME + timedelta(hours=2)))
    svar = bok.bokfor(_les(101.0, TIME + timedelta(hours=1)))
    assert svar.utfall is Utfall.FORSINKET
    assert sum(i.kwh for i in bok.intervaller()) == pytest.approx(2.0, abs=1e-9)


def test_samme_observasjonstid_med_ulik_stand_er_avvist() -> None:
    """C1: vinduet har lengde null og kan ikke fordeles."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(102.0, TIME + timedelta(hours=1)))
    svar = bok.bokfor(_les(103.0, TIME + timedelta(hours=1)))
    assert svar.utfall is Utfall.AVVIST_NULLVINDU
    assert sum(i.kwh for i in bok.intervaller()) == pytest.approx(2.0, abs=1e-9)
    assert bok.sist_observert is not None
    assert bok.sist_observert.value_kwh == 102.0, "baselinen skal stå ved et nullvindu"


def test_negativt_delta_flytter_baselinen_uten_a_bokfore() -> None:
    """C1: målerreset eller kildebytte gir delta 0 og ny baseline."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    svar = bok.bokfor(_les(3.0, TIME + timedelta(hours=1)))
    assert svar.utfall is Utfall.AVVIST_NEGATIV
    assert bok.intervaller() == []
    assert bok.sist_observert is not None
    assert bok.sist_observert.value_kwh == 3.0


def test_sprang_over_grensen_avvises_og_boken_gaar_videre() -> None:
    """C1: uten at baselinen flyttes ville boken stått stille for godt.

    Hytta som har stått tom kommer tilbake med 150 kWh på telleren. De 150 blir
    avvist og synlige, og neste avlesning regner videre fra den nye standen.
    """
    bok = _bok(maks_delta_kwh=100.0)
    bok.bokfor(_les(100.0, TIME))
    sprang = bok.bokfor(_les(250.0, TIME + timedelta(hours=1)))
    assert sprang.utfall is Utfall.AVVIST_SPRANG
    assert sprang.avvist_kwh == pytest.approx(150.0)
    assert bok.avvist_kwh == pytest.approx(150.0)
    assert bok.intervaller() == []

    etterpaa = bok.bokfor(_les(252.0, TIME + timedelta(hours=2)))
    assert etterpaa.utfall is Utfall.BOKFORT
    assert etterpaa.bokfort_kwh == pytest.approx(2.0, abs=1e-9)


def test_kildebytte_gir_ny_baseline_og_ingen_bokforing() -> None:
    """K1 og C5: en annen kilde er ikke et delta."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    svar = bok.bokfor(_les(5.0, TIME + timedelta(hours=1), kilde="meter-2"))
    assert svar.utfall is Utfall.BASELINE
    assert bok.intervaller() == []
    assert bok.sist_observert is not None
    assert bok.sist_observert.source_identity == "meter-2"


def test_delta_fordeles_over_intervallene_det_tilhorer() -> None:
    """C1 og C6: en avlesning kl. 11:00:03 bokfører inn i 10:00-intervallet."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME + timedelta(minutes=30)))
    bok.bokfor(_les(101.2, TIME + timedelta(minutes=75)))
    fordelt = {i.start_utc: i.kwh for i in bok.intervaller()}
    assert set(fordelt) == {TIME, TIME + AVREGNINGSINTERVALL}
    assert fordelt[TIME] == pytest.approx(0.8, abs=1e-9)
    assert fordelt[TIME + AVREGNINGSINTERVALL] == pytest.approx(0.4, abs=1e-9)


# ---------------------------------------------------------------------------
# Boken: den syntetiske stien (B1)


def test_estimert_avlesning_er_energi_i_vinduet_ikke_en_stand() -> None:
    """B1: uten teller er `value_kwh` energien i pollvinduet."""
    bok = _bok()
    bok.bokfor(Avlesning("effekt", 0.0, TIME, kvalitet=Energikvalitet.ESTIMERT))
    svar = bok.bokfor(
        Avlesning("effekt", 0.05, TIME + timedelta(minutes=3), kvalitet=Energikvalitet.ESTIMERT)
    )
    assert svar.utfall is Utfall.BOKFORT
    assert svar.bokfort_kwh == pytest.approx(0.05, abs=1e-12)
    intervall = bok.intervall(TIME)
    assert intervall is not None
    assert intervall.energikvalitet is Energikvalitet.ESTIMERT


def test_for_langt_estimatvindu_bokfores_ikke() -> None:
    """B1: antakelsen om konstant effekt holder ikke, og energien gjettes ikke.

    Intervallene i gapet får ingen energi. De er «uten data» etter C4, ikke
    null forbruk, og finnes derfor ikke i boken.
    """
    bok = _bok(maks_estimert_vindu_timer=0.1)
    bok.bokfor(Avlesning("effekt", 0.0, TIME, kvalitet=Energikvalitet.ESTIMERT))
    svar = bok.bokfor(Avlesning("effekt", 9.0, TIME + timedelta(hours=3), kvalitet=Energikvalitet.ESTIMERT))
    assert svar.utfall is Utfall.AVVIST_FOR_LANGT_VINDU
    assert bok.intervaller() == []
    assert bok.intervall(TIME + timedelta(hours=1)) is None


def test_avvist_avlesning_rorer_ikke_boken() -> None:
    """B1: `kvalitet = avvist` er en måling vi ikke har lov til å regne på."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    svar = bok.bokfor(Avlesning("meter-1", 105.0, TIME + timedelta(hours=1), kvalitet=Energikvalitet.AVVIST))
    assert svar.utfall is Utfall.AVVIST_NULLVINDU
    assert bok.intervaller() == []
    assert bok.sist_observert is not None
    assert bok.sist_observert.value_kwh == 100.0


# ---------------------------------------------------------------------------
# Boken: pris, kvalitet og merkelapper


def test_intervall_med_energi_uten_pris_er_uten_pris_og_aldri_null() -> None:
    """C4: kWh bokføres, prisen står `None`, og energien er synlig."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(102.0, TIME + AVREGNINGSINTERVALL))
    intervall = bok.intervall(TIME)
    assert intervall is not None
    assert intervall.kwh == pytest.approx(2.0, abs=1e-9)
    assert intervall.nok_per_kwh_eks_mva is None
    assert intervall.har_pris is False
    assert intervall.kvalitet is Intervallkvalitet.UTEN_PRIS
    assert bok.maanedssum().kwh_uten_pris == pytest.approx(2.0, abs=1e-9)
    assert bok.maanedssum().kwh_delvis_pris == 0.0


def test_delvis_pris_teller_som_delvis_og_ikke_som_uten() -> None:
    """C4: prisen er rett for rutene vi så, og vi later ikke som vi så resten."""
    bok = _bok()
    bok.registrer_prisprove(TIME + timedelta(minutes=2), 1.0)
    bok.registrer_prisprove(TIME + timedelta(minutes=33), 1.4)
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(102.0, TIME + AVREGNINGSINTERVALL))
    intervall = bok.intervall(TIME)
    assert intervall is not None
    assert intervall.kvalitet is Intervallkvalitet.DELVIS_PRIS
    assert intervall.nok_per_kwh_eks_mva == pytest.approx(1.2)
    sum_ = bok.maanedssum()
    assert sum_.kwh_delvis_pris == pytest.approx(2.0, abs=1e-9)
    assert sum_.kwh_uten_pris == 0.0


def test_intervallet_faar_tariff_maaned_og_regelkilde_fra_sin_egen_start() -> None:
    """B3: alle merkelappene avgjøres av `start_utc`, ikke av polltiden."""
    natt = datetime(2026, 6, 15, 1, 0, tzinfo=UTC)  # 03:00 CEST, mandag
    bok = _bok()
    bok.bokfor(_les(100.0, natt))
    bok.bokfor(_les(101.0, natt + AVREGNINGSINTERVALL))
    intervall = bok.intervall(natt)
    assert intervall is not None
    assert intervall.tariff is Tariff.NATT
    assert intervall.lokal_maned == "2026-06"
    assert intervall.lokal_time == 3
    assert intervall.regelkilde == "catalog:bkk:2026"


def test_dag_og_natt_summeres_hver_for_seg() -> None:
    """Felttabellen: `monthly_consumption_dag_kwh` er sum over intervaller."""
    bok = _bok()
    start = datetime(2026, 6, 15, 3, 0, tzinfo=UTC)  # 05:00 CEST, natt
    bok.bokfor(_les(0.0, start))
    bok.bokfor(_les(2.0, start + timedelta(hours=2)))  # dekker 05 (natt) og 06 (dag)
    sum_ = bok.maanedssum()
    assert sum_.kwh_natt == pytest.approx(1.0, abs=1e-9)
    assert sum_.kwh_dag == pytest.approx(1.0, abs=1e-9)
    assert sum_.kwh_total == pytest.approx(2.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Boken: åpent, lukket og månedsrullering


def test_apen_avgjores_av_tiden_alene() -> None:
    """C6: lukkingen skjer av klokken, ikke av en poll."""
    bok = _bok()
    bok.bokfor(_les(100.0, TIME + timedelta(minutes=10)))
    bok.bokfor(_les(101.0, TIME + timedelta(minutes=50)))
    assert bok.intervall(TIME, naa=TIME + timedelta(minutes=50)).apen is True  # type: ignore[union-attr]
    assert bok.intervall(TIME, naa=TIME + AVREGNINGSINTERVALL).apen is False  # type: ignore[union-attr]
    assert bok.apne_intervaller(TIME + timedelta(minutes=50)) != []
    assert bok.apne_intervaller(TIME + AVREGNINGSINTERVALL) == []


def test_maanedsskiftet_deler_vinduet_ved_lokal_midnatt() -> None:
    """C6 og C3 D5: delen før grensen bokføres i den gamle måneden."""
    bok = _bok()
    fra = datetime(2026, 3, 31, 21, 30, tzinfo=UTC)  # lokal 23:30 CEST, mars
    til = datetime(2026, 3, 31, 22, 30, tzinfo=UTC)  # lokal 00:30 CEST, april
    bok.bokfor(_les(100.0, fra))
    svar = bok.bokfor(_les(102.0, til))
    assert svar.arkiverte_maneder == ("2026-03",)
    assert bok.aktiv_maned == "2026-04"

    mars = bok.arkiverte_maneder()["2026-03"]
    assert mars.kwh_total == pytest.approx(1.0, abs=1e-9)
    assert bok.maanedssum().kwh_total == pytest.approx(1.0, abs=1e-9)
    assert {i.lokal_maned for i in bok.intervaller()} == {"2026-04"}


def test_en_arkivert_maaned_tar_ikke_imot_mer_energi() -> None:
    """C6: et intervall blir uforanderlig når måneden arkiveres."""
    bok = _bok()
    bok.bokfor(_les(100.0, datetime(2026, 3, 31, 21, 30, tzinfo=UTC)))
    bok.bokfor(_les(102.0, datetime(2026, 3, 31, 22, 30, tzinfo=UTC)))
    assert bok.aktiv_maned == "2026-04"
    # Boken er i april. Et forsøk på å nå bakenfor må avvises, ikke bokføres.
    tilbake = bok.bokfor(_les(103.0, datetime(2026, 3, 31, 21, 45, tzinfo=UTC)))
    assert tilbake.utfall is Utfall.FORSINKET
    assert bok.arkiverte_maneder()["2026-03"].kwh_total == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Statusfelt og persistens


def test_statusfeltene_er_de_i_felttabellen() -> None:
    """Felttabellen i kontrakten: de ni nye feltene, med riktige navn."""
    bok = _bok()
    bok.registrer_prisprove(TIME + timedelta(minutes=2), 1.0)
    bok.bokfor(_les(100.0, TIME + timedelta(minutes=10)))
    bok.bokfor(_les(101.0, TIME + timedelta(minutes=50)))
    felt = bok.statusfelt(naa=TIME + timedelta(minutes=50))
    assert set(felt) == {
        "avregning_skjema",
        "avregning_ufullstendig",
        "avregning_sist_observert",
        "avregning_kilde",
        "avregning_siste_intervall",
        "avregning_apne_intervaller",
        "avregning_avvist_kwh",
        "kwh_uten_pris",
        "kwh_delvis_pris",
    }
    assert felt["avregning_skjema"] == SKJEMA_VERSJON
    assert felt["avregning_kilde"] == "meter-1"
    assert felt["avregning_apne_intervaller"] == 1
    assert felt["avregning_siste_intervall"] is None
    assert felt["kwh_delvis_pris"] == pytest.approx(1.0, abs=1e-9)


def test_omstart_gjenopptar_energi_pris_og_baseline() -> None:
    """C5: uten prisrutene ville en omstart gjort komplett til delvis_pris."""
    bok = _bok()
    for minutt in (0, 15, 30, 45):
        bok.registrer_prisprove(TIME + timedelta(minutes=minutt, seconds=90), 1.0 + minutt / 100)
    bok.bokfor(_les(100.0, TIME + timedelta(minutes=5)))
    bok.bokfor(_les(101.0, TIME + timedelta(minutes=55)))

    etter = Avregningsbok.fra_lagring(bok.til_lagring(), dso_id="bkk")
    assert etter.ufullstendig is False
    assert etter.aktiv_maned == bok.aktiv_maned
    assert etter.sist_observert is not None
    assert etter.sist_observert.value_kwh == 101.0
    for foer, bak in zip(bok.intervaller(), etter.intervaller(), strict=True):
        assert foer == bak

    # Og boken regner videre fra baselinen, uten å bokføre standen på nytt.
    svar = etter.bokfor(_les(102.0, TIME + timedelta(minutes=115)))
    assert svar.utfall is Utfall.BOKFORT
    assert svar.bokfort_kwh == pytest.approx(1.0, abs=1e-9)


def test_migrering_fra_v2_gir_tom_bok_merket_ufullstendig() -> None:
    """D: månedssummene fra v2 kan ikke gjøres om til intervallhistorikk."""
    v2 = {"version": 2, "monthly_consumption_total_kwh": 412.0, "source_identity": "meter-1"}
    migrert = migrer_lagring(v2)
    assert migrert["skjema_versjon"] == SKJEMA_VERSJON
    assert migrert["ufullstendig"] is True
    assert migrert["intervaller"] == []
    assert migrert["sist_observert"] is None
    assert migrert["ovrige"] == v2, "v2-feltene skal følge med uendret"

    bok = Avregningsbok.fra_lagring(v2)
    assert bok.ufullstendig is True
    assert bok.sist_observert is None
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(101.0, TIME + AVREGNINGSINTERVALL))
    intervall = bok.intervall(TIME)
    assert intervall is not None
    assert intervall.kvalitet is Intervallkvalitet.UFULLSTENDIG


def test_ufullstendig_flagget_forsvinner_ved_forste_maanedsskifte() -> None:
    """D: flagget gjelder måneden migreringen skjedde i, ikke for alltid."""
    bok = Avregningsbok.fra_lagring({"version": 2})
    assert bok.ufullstendig is True
    bok.bokfor(_les(100.0, datetime(2026, 3, 31, 21, 30, tzinfo=UTC)))
    bok.bokfor(_les(102.0, datetime(2026, 3, 31, 22, 30, tzinfo=UTC)))
    assert bok.ufullstendig is False
    assert bok.statusfelt(naa=datetime(2026, 4, 1, 0, 0, tzinfo=UTC))["avregning_ufullstendig"] is False


def test_fersk_installasjon_er_ikke_en_migrering() -> None:
    """D: ingenting mangler når det aldri har vært noen bok."""
    bok = Avregningsbok.fra_lagring(None)
    assert bok.ufullstendig is False
    assert bok.aktiv_maned is None


def test_lagringen_er_json_vennlig() -> None:
    """Store skriver JSON, så boken må kunne serialiseres uten datetimes."""
    import json

    bok = _bok()
    bok.registrer_prisprove(TIME + timedelta(minutes=2), 1.0)
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(101.0, TIME + AVREGNINGSINTERVALL))
    rundtur = json.loads(json.dumps(bok.til_lagring()))
    assert Avregningsbok.fra_lagring(rundtur, dso_id="bkk").intervaller() == bok.intervaller()


def test_arkivert_maaned_overlever_en_omstart() -> None:
    """C6 og D: den arkiverte måneden er uforanderlig, også gjennom Store."""
    import json

    bok = _bok()
    bok.bokfor(_les(100.0, datetime(2026, 3, 31, 21, 30, tzinfo=UTC)))
    bok.bokfor(_les(102.0, datetime(2026, 3, 31, 22, 30, tzinfo=UTC)))

    etter = Avregningsbok.fra_lagring(json.loads(json.dumps(bok.til_lagring())), dso_id="bkk")
    assert etter.aktiv_maned == "2026-04"
    assert etter.arkiverte_maneder() == bok.arkiverte_maneder()
    assert etter.arkiverte_maneder()["2026-03"].kwh_total == pytest.approx(1.0, abs=1e-9)
    assert etter.arkiverte_maneder()["2026-03"].intervaller == 1


def test_med_pris_setter_pris_for_etterkontroll_uten_a_rore_ufullstendig() -> None:
    """L2 bytter prisen mot arkivet; `ufullstendig` er en egenskap ved boken."""
    bok = Avregningsbok.fra_lagring({"version": 2})
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(101.0, TIME + AVREGNINGSINTERVALL))
    intervall = bok.intervall(TIME)
    assert intervall is not None
    arkivpris = Prisintervall(
        TIME,
        TIME + AVREGNINGSINTERVALL,
        1.2345,
        omrade="NO5",
        kilde=Priskilde.ARKIV,
        revisjon=Revisjon.FINAL,
        pris_prover=4,
    )
    med = med_pris(intervall, arkivpris)
    assert med.nok_per_kwh_eks_mva == 1.2345
    assert med.kvalitet is Intervallkvalitet.UFULLSTENDIG

    vanlig = med_pris(_bok_med_energi().intervall(TIME), arkivpris)  # type: ignore[arg-type]
    assert vanlig.kvalitet is Intervallkvalitet.KOMPLETT


def _bok_med_energi() -> Avregningsbok:
    bok = _bok()
    bok.bokfor(_les(100.0, TIME))
    bok.bokfor(_les(101.0, TIME + AVREGNINGSINTERVALL))
    return bok


# ---------------------------------------------------------------------------
# Ingen HA-import


def test_modulen_importerer_ikke_home_assistant() -> None:
    """Poenget med L1: kjernen skal kunne kjøres uten Home Assistant.

    Testene her kjører mot conftests HA-stubs, så en `import homeassistant`
    ville ikke feilet av seg selv. Derfor leses kilden.
    """
    kilde = (
        Path(__file__).parent.parent / "custom_components" / "stromkalkulator" / "avregning.py"
    ).read_text(encoding="utf-8")
    assert "homeassistant" not in kilde
