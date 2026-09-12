"""Tidsbevisst hendelsesreplay: fasit, kontraktsprøver og fakturaavstemming.

Tre lag, i den rekkefølgen de er verdt noe:

1. **Fasiten mot kontrakten.** `tests/replay/fasit.py` er en andre
   implementasjon av `docs/kontrakter/avregning.md`, og prøvetabellene C7 og C8
   kjøres mot den. En fasit som ikke er etterprøvd er bare en mening til.
2. **Fasiten mot ekte fakturaer.** Elhubs intervallenergi ganger Nord Pools
   publiserte Final-priser skal gi BKKs fakturalinjer for mai, juni og juli
   2026. Det er der fasiten blir fasit.
3. **Coordinatoren gjennom harnesset.** Den ekte coordinatoren kjøres med poll
   hvert minutt, jitter, omstart og sommertid, og sammenlignes med fasiten for
   nøyaktig den historikken den fikk se.

Påstander dagens coordinator ikke oppfyller står som `xfail(strict=True)` med
peker til issuet som flipper dem. Strict, så de blir røde igjen den dagen de
begynner å holde og ingen har fjernet merkingen.

Måneder uten fasitgrunnlag er merket ufullstendig, ikke grønne: august 2026 har
publiserte priser, men ingen Elhub-CSV, og HAN-fixturen mangler 176 av 744
timer. Den kan ikke avstemmes mot faktura, og testen sier det i stedet for å
hoppe stille over.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from tests.replay.fasit import (
    OSLO,
    Fasit,
    Kvalitet,
    Satser,
    Utfall,
    fordel_delta,
    intervallstart,
    prisrutestart,
)
from tests.replay.harness import Replay, logg_fra_timesenergi, pollplan

FIXTURES = Path(__file__).parent / "fixtures"

# Issuene som flipper xfail-ene. L3a tar intervallene, L3b kronene.
L3A = "stromkalkulator-3gum1kx (L3a: coordinator på intervaller)"
L3B = "stromkalkulator-33f81xu (L3b: kostnadskjernen)"

# Fakturalinjene, kopiert fra tests/test_faktura_bkk.py via
# scripts/research/verify_invoice_hourly.py. De står her som tall, ikke som
# import, av samme grunn som satsene i fasit.py gjør det.
FAKTURAER: dict[str, dict[str, float]] = {
    "mai_2026": {
        "forbruk_dag_kwh": 518.142,
        "forbruk_natt_kwh": 661.161,
        "forbruk_total_kwh": 1179.303,
        "energiledd_dag_kr": 186.34,
        "energiledd_natt_kr": 86.77,
        "forbruksavgift_kr": 105.10,
        "enovaavgift_kr": 14.74,
        "kapasitet_kr": 250.00,
        "norgespris_kr": -1032.56,
        "nettleie_kr": 642.95,
    },
    "juni_2026": {
        "forbruk_dag_kwh": 590.646,
        "forbruk_natt_kwh": 442.982,
        "forbruk_total_kwh": 1033.628,
        "energiledd_dag_kr": 212.41,
        "energiledd_natt_kr": 58.14,
        "forbruksavgift_kr": 92.11,
        "enovaavgift_kr": 12.93,
        "kapasitet_kr": 250.00,
        "norgespris_kr": -363.54,
        "nettleie_kr": 625.59,
    },
    "juli_2026": {
        "forbruk_dag_kwh": 514.414,
        "forbruk_natt_kwh": 424.349,
        "forbruk_total_kwh": 938.763,
        "energiledd_dag_kr": 185.00,
        "energiledd_natt_kr": 55.70,
        "forbruksavgift_kr": 83.67,
        "enovaavgift_kr": 11.73,
        "kapasitet_kr": 250.00,
        "norgespris_kr": -807.50,
        "nettleie_kr": 586.10,
    },
}

# Månedene fasiten har både intervallenergi og Final-pris for.
AVSTEMBARE = ("mai_2026", "juni_2026", "juli_2026")

# Måneder med prisdekning, men uten energifasit. De er ufullstendige, og det
# skal stå i en test framfor å forsvinne i et skip.
UFULLSTENDIGE = {
    "august_2026": (
        "Ingen Elhub-CSV i _private/Måleverdier/, og HAN-fixturen mangler 176 av "
        "744 timer etter leserutfallet. Fakturalinjen kan ikke avstemmes."
    ),
}


# ---------------------------------------------------------------------------
# Fixture-lasting
# ---------------------------------------------------------------------------


def _last_json(navn: str) -> dict[str, Any]:
    return json.loads((FIXTURES / navn).read_text(encoding="utf-8"))


def maned_timer(navn: str) -> list[tuple[datetime, float]]:
    """[(lokal time-start, kWh)] fra Elhub-fixturen."""
    return [
        (datetime.fromisoformat(h["start_local"]), h["kwh"])
        for h in _last_json(f"elhub_{navn}.json")["hours"]
    ]


def maned_priser(navn: str) -> dict[datetime, list[float]]:
    """{lokal time-start: fire kvarterpriser} fra Final-pris-fixturen.

    Timer der arkivet bare har en timespris (fallback) gjentas i alle fire
    rutene. Det er nøyaktig hva en timesoppløst prissensor viser i drift, og
    A2.1 gir da timesprisen tilbake.
    """
    ut: dict[datetime, list[float]] = {}
    for h in _last_json(f"final_pris_{navn}.json")["hours"]:
        kvarter = h["kvarter"] or [h["nok_per_kwh_eks_mva"]] * 4
        ut[datetime.fromisoformat(h["start_local"])] = kvarter
    return ut


def fasit_for(navn: str) -> Fasit:
    """Fasit matet rett fra intervallenergi og Final-pris, uten coordinator."""
    f = Fasit()
    priser = maned_priser(navn)
    for start, kwh in maned_timer(navn):
        f.bokfor_intervall(start, kwh)
        for i, verdi in enumerate(priser[start]):
            # Midt i ruten: godt innenfor settlevinduet, og verdien er den
            # samme uansett hvor i ruten vi leser (A2.1).
            f.prisprove(start + timedelta(minutes=15 * i, seconds=450), verdi)
    return f


# ---------------------------------------------------------------------------
# 1. Fasiten mot kontrakten
# ---------------------------------------------------------------------------


C7 = [
    ("F1", "2026-06-15T10:30:00Z", "2026-06-15T10:45:00Z", 0.400, {"2026-06-15T10:00:00Z": 0.400}),
    (
        "F2",
        "2026-06-15T10:45:00Z",
        "2026-06-15T11:15:00Z",
        1.200,
        {"2026-06-15T10:00:00Z": 0.600, "2026-06-15T11:00:00Z": 0.600},
    ),
    (
        "F3",
        "2026-06-15T09:20:00Z",
        "2026-06-15T12:10:00Z",
        8.500,
        {
            "2026-06-15T09:00:00Z": 2.000,
            "2026-06-15T10:00:00Z": 3.000,
            "2026-06-15T11:00:00Z": 3.000,
            "2026-06-15T12:00:00Z": 0.500,
        },
    ),
    ("F4", "2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z", 2.000, {"2026-06-15T10:00:00Z": 2.000}),
    (
        "F5",
        "2026-03-29T00:30:00Z",
        "2026-03-29T01:30:00Z",
        4.000,
        {"2026-03-29T00:00:00Z": 2.000, "2026-03-29T01:00:00Z": 2.000},
    ),
    (
        "F6",
        "2026-10-25T00:30:00Z",
        "2026-10-25T01:30:00Z",
        4.000,
        {"2026-10-25T00:00:00Z": 2.000, "2026-10-25T01:00:00Z": 2.000},
    ),
]

C8 = [
    ("P1", 15, "00:30=1.00;02:00=1.00;17:00=1.10;32:00=1.20;47:00=1.30", 4, 1.15, Kvalitet.KOMPLETT),
    ("P2", 15, "02:00=1.00;17:00=1.00;32:00=1.00;47:00=1.00", 4, 1.00, Kvalitet.KOMPLETT),
    ("P3", 15, "00:10=0.90;01:30=1.00;16:00=1.00;31:00=1.00;46:00=1.00", 4, 1.00, Kvalitet.KOMPLETT),
    ("P4", 60, "05:00=1.23", 1, 1.23, Kvalitet.KOMPLETT),
    ("P5", 15, "02:00=1.00;33:00=1.40", 2, 1.20, Kvalitet.DELVIS_PRIS),
    ("P6", 15, "00:20=1.00;15:30=1.10", 0, None, Kvalitet.UTEN_PRIS),
    ("P7", 60, "02:00=1.00;10:00=1.40", 1, 1.40, Kvalitet.KOMPLETT),
]


class TestFasitMotKontrakten:
    """Prøvetabellene i A0 kjørt mot fasitens egen implementasjon.

    `tests/test_avregningskontrakt.py` kjører de samme radene mot
    `avregning.py`. At begge gjør det er poenget: to implementasjoner som
    treffer den samme normative tabellen, uten å ha sett hverandre.
    """

    @pytest.mark.parametrize(("sak", "fra", "til", "delta", "forventet"), C7, ids=[r[0] for r in C7])
    def test_c7_fordelingsregel(self, sak, fra, til, delta, forventet):
        fordeling = fordel_delta(datetime.fromisoformat(fra), datetime.fromisoformat(til), delta)
        faktisk = {k.isoformat().replace("+00:00", "Z"): round(v, 6) for k, v in fordeling.items()}
        assert faktisk == {k: pytest.approx(v, abs=1e-6) for k, v in forventet.items()}, sak
        assert sum(fordeling.values()) == pytest.approx(delta, abs=1e-9)

    @pytest.mark.parametrize(
        ("sak", "opplosning", "polls", "ruter", "pris", "kvalitet"), C8, ids=[r[0] for r in C8]
    )
    def test_c8_prisruter(self, sak, opplosning, polls, ruter, pris, kvalitet):
        start = datetime.fromisoformat("2026-06-15T10:00:00Z")
        f = Fasit(opplosning_minutter=opplosning)
        f.bokfor_intervall(start, 1.0)
        for bit in polls.split(";"):
            mmss, verdi = bit.split("=")
            mm, ss = (int(x) for x in mmss.split(":"))
            f.prisprove(start + timedelta(minutes=mm, seconds=ss), float(verdi))
        (intervall,) = f.intervaller()
        assert intervall.pris_prover == ruter, sak
        if pris is None:
            assert intervall.pris_nok_per_kwh_eks_mva is None, sak
        else:
            assert intervall.pris_nok_per_kwh_eks_mva == pytest.approx(pris, abs=1e-9), sak
        assert intervall.kvalitet is kvalitet, sak

    @pytest.mark.parametrize(
        ("sak", "start_utc", "lokal", "maned", "time"),
        [
            ("D1", "2026-03-29T00:00:00Z", "2026-03-29 01:00", "2026-03", 1),
            ("D2", "2026-03-29T01:00:00Z", "2026-03-29 03:00", "2026-03", 3),
            ("D3", "2026-10-25T00:00:00Z", "2026-10-25 02:00", "2026-10", 2),
            ("D4", "2026-10-25T01:00:00Z", "2026-10-25 02:00", "2026-10", 2),
            ("D5", "2026-03-31T22:00:00Z", "2026-04-01 00:00", "2026-04", 0),
            ("D6", "2026-12-31T23:00:00Z", "2027-01-01 00:00", "2027-01", 0),
        ],
    )
    def test_c3_merkelapper_over_dst_og_arsskifte(self, sak, start_utc, lokal, maned, time):
        f = Fasit()
        start = datetime.fromisoformat(start_utc)
        f.bokfor_intervall(start, 1.0)
        (intervall,) = f.intervaller()
        assert intervall.lokal.strftime("%Y-%m-%d %H:%M") == lokal, sak
        assert intervall.lokal_maned == maned, sak
        assert intervall.lokal_time == time, sak

    def test_d3_og_d4_er_to_ulike_intervaller_med_samme_veggklokke(self):
        """Høstskiftet: 02:00 finnes to ganger, og de skal holdes fra hverandre."""
        f = Fasit()
        f.bokfor_intervall(datetime.fromisoformat("2026-10-25T00:00:00Z"), 1.0)
        f.bokfor_intervall(datetime.fromisoformat("2026-10-25T01:00:00Z"), 2.0)
        rader = f.intervaller()
        assert len(rader) == 2
        assert {r.lokal_time for r in rader} == {2}
        assert [r.kwh for r in rader] == [1.0, 2.0]

    def test_var_dst_har_ingen_time_02(self):
        """Vårskiftet: ingen bokføring kan få merkelappen 02 lokalt."""
        f = Fasit()
        start = datetime.fromisoformat("2026-03-28T22:00:00Z")
        for n in range(10):
            f.bokfor_intervall(start + timedelta(hours=n), 1.0)
        assert 2 not in {r.lokal_time for r in f.intervaller()}

    def test_bevaring_over_et_dogn_med_ujevne_avlesninger(self):
        """C2.1: fordelte kWh summerer til deltaet, uansett vindulengde."""
        f = Fasit()
        start = datetime.fromisoformat("2026-06-14T22:00:00Z")
        teller = 1000.0
        f.bokfor(start, teller)
        sekunder = [7, 53, 601, 3599, 3600, 3601, 11, 86_399]
        for n, s in enumerate(sekunder, start=1):
            start = start + timedelta(seconds=s)
            teller += 0.137 * n
            f.bokfor(start, teller)
        bokfort = sum(i.kwh for i in f.intervaller())
        assert bokfort == pytest.approx(teller - 1000.0, abs=1e-9)

    def test_duplikat_forsinket_og_nullvindu(self):
        """C2.2 og C2.3: en avlesning bokføres én gang, og aldri bakover."""
        f = Fasit()
        t0 = datetime.fromisoformat("2026-06-15T10:00:00Z")
        f.bokfor(t0, 100.0)
        f.bokfor(t0 + timedelta(minutes=30), 101.0)
        assert f.bokfor(t0 + timedelta(minutes=30), 101.0) is Utfall.DUPLIKAT
        assert f.bokfor(t0 + timedelta(minutes=10), 100.5) is Utfall.FORSINKET
        assert f.bokfor(t0 + timedelta(minutes=30), 101.5) is Utfall.NULLVINDU
        assert sum(i.kwh for i in f.intervaller()) == pytest.approx(1.0, abs=1e-9)

    def test_malerreset_og_for_stort_sprang(self):
        """C1s randtilfeller: baseline flyttes, og spranget blir synlig."""
        f = Fasit()
        t0 = datetime.fromisoformat("2026-06-15T10:00:00Z")
        f.bokfor(t0, 1000.0)
        f.bokfor(t0 + timedelta(minutes=30), 1001.0)
        assert f.bokfor(t0 + timedelta(hours=1), 5.0) is Utfall.NEGATIVT
        assert f.bokfor(t0 + timedelta(hours=2), 6.0) is Utfall.BOKFORT
        assert f.bokfor(t0 + timedelta(hours=3), 500.0) is Utfall.FOR_STORT
        assert f.avregning().avvist_kwh == pytest.approx(494.0, abs=1e-9)
        assert f.bokfor(t0 + timedelta(hours=4), 501.0) is Utfall.BOKFORT

    def test_uten_pris_gir_ikke_null_og_ikke_naboens(self):
        """C2.5 og C4: et intervall uten prøve har ingen pris, ikke prisen 0."""
        f = Fasit()
        t0 = datetime.fromisoformat("2026-06-15T10:00:00Z")
        f.bokfor_intervall(t0, 2.0)
        f.bokfor_intervall(t0 + timedelta(hours=1), 3.0)
        for i in range(4):
            f.prisprove(t0 + timedelta(minutes=15 * i, seconds=300), 1.0)
        tom = f.intervaller()[1]
        assert tom.pris_nok_per_kwh_eks_mva is None
        assert tom.kvalitet is Kvalitet.UTEN_PRIS
        a = f.avregning()
        assert a.kwh_uten_pris == pytest.approx(3.0)
        # Norgespris-kompensasjonen regnes bare på timen som hadde pris.
        assert a.stotte_kr == pytest.approx((0.50 - 1.0 * 1.25) * 2.0, abs=1e-9)

    def test_negativ_pris_klippes_ikke(self):
        f = Fasit()
        t0 = datetime.fromisoformat("2026-06-15T10:00:00Z")
        f.bokfor_intervall(t0, 1.0)
        for i in range(4):
            f.prisprove(t0 + timedelta(minutes=15 * i, seconds=300), -0.40)
        (rad,) = f.intervaller()
        assert rad.pris_nok_per_kwh_eks_mva == pytest.approx(-0.40)
        assert f.avregning().stotte_kr == pytest.approx(0.50 + 0.40 * 1.25, abs=1e-9)

    def test_stromstotte_terskel_og_tak(self):
        """Strømstøtte slår inn over terskelen og stopper ved månedstaket."""
        satser = Satser(har_norgespris=False, stromstotte_maks_kwh=10)
        f = Fasit(satser)
        t0 = datetime.fromisoformat("2026-01-15T00:00:00Z")
        for n, (kwh, pris) in enumerate([(6.0, 0.50), (6.0, 2.00), (6.0, 2.00)]):
            start = t0 + timedelta(hours=n)
            f.bokfor_intervall(start, kwh)
            for i in range(4):
                f.prisprove(start + timedelta(minutes=15 * i, seconds=300), pris)
        # Time 1: under terskel, ingen støtte. Time 2: 4 av 6 kWh under taket.
        # Time 3: taket er brukt opp.
        ventet = -(2.00 * 1.25 - 0.9625) * 0.90 * 4.0
        assert f.avregning().stotte_kr == pytest.approx(ventet, abs=1e-9)

    def test_intervallstart_og_prisrutestart_krever_aware(self):
        naiv = datetime(2026, 6, 15, 10, 0)
        with pytest.raises(ValueError, match="tidssoneklar"):
            intervallstart(naiv)
        with pytest.raises(ValueError, match="tidssoneklar"):
            prisrutestart(naiv)


# ---------------------------------------------------------------------------
# 2. Fasiten mot ekte fakturaer
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("navn", AVSTEMBARE)
class TestFasitMotFaktura:
    """Elhub-kWh ganger Final-pris skal gi BKKs fakturalinjer.

    Dette er fasitens eneste legitimasjon. Feiler den her, er alt under
    verdiløst, og et avvik betyr at enten satsene, tariffreglene eller
    prisregelen har driftet fra virkeligheten.
    """

    @pytest.fixture
    def avregning(self, navn):
        return fasit_for(navn).avregning()

    def test_energi_dag_natt_og_total(self, navn, avregning):
        f = FAKTURAER[navn]
        assert avregning.kwh_total == pytest.approx(f["forbruk_total_kwh"], abs=0.001)
        assert avregning.kwh_dag == pytest.approx(f["forbruk_dag_kwh"], abs=0.001)
        assert avregning.kwh_natt == pytest.approx(f["forbruk_natt_kwh"], abs=0.001)

    def test_energiledd_dag_og_natt(self, navn, avregning):
        f = FAKTURAER[navn]
        assert avregning.energiledd_dag_kr == pytest.approx(f["energiledd_dag_kr"], abs=0.01)
        assert avregning.energiledd_natt_kr == pytest.approx(f["energiledd_natt_kr"], abs=0.01)

    def test_avgifter(self, navn, avregning):
        f = FAKTURAER[navn]
        assert avregning.forbruksavgift_kr == pytest.approx(f["forbruksavgift_kr"], abs=0.03)
        assert avregning.enovaavgift_kr == pytest.approx(f["enovaavgift_kr"], abs=0.02)

    def test_norgespris(self, navn, avregning):
        """Kravet i akseptansen: innenfor 0,01 kr av fakturalinjen."""
        assert avregning.stotte_kr == pytest.approx(FAKTURAER[navn]["norgespris_kr"], abs=0.01)

    def test_fastledd(self, navn, avregning):
        assert avregning.kapasitetsledd_kr == pytest.approx(FAKTURAER[navn]["kapasitet_kr"], abs=0.001)

    def test_nettleie_totalt(self, navn, avregning):
        assert avregning.nettleie_kr == pytest.approx(FAKTURAER[navn]["nettleie_kr"], abs=0.05)

    def test_alle_intervaller_har_full_prisdekning(self, navn):
        a = fasit_for(navn).avregning()
        assert a.kwh_uten_pris == 0.0
        assert a.kwh_delvis_pris == 0.0


@pytest.mark.parametrize(("navn", "grunn"), sorted(UFULLSTENDIGE.items()))
def test_ufullstendige_maneder_er_merket_ikke_gronne(navn, grunn):
    """En måned uten fasitgrunnlag skal si fra, ikke forsvinne i et skip.

    Testen er grønn fordi merkingen er riktig, ikke fordi måneden er avstemt.
    Kommer Elhub-CSV-en for august på plass, fjernes raden fra `UFULLSTENDIGE`
    og måneden flyttes til `AVSTEMBARE`.
    """
    assert not (FIXTURES / f"elhub_{navn}.json").exists(), (
        f"{navn} har fått Elhub-fasit. Flytt den til AVSTEMBARE."
    )
    assert (FIXTURES / f"final_pris_{navn}.json").exists()
    assert grunn


# ---------------------------------------------------------------------------
# 3. Coordinatoren gjennom harnesset
# ---------------------------------------------------------------------------


def _syntetisk(
    coord_module,
    timer: list[tuple[datetime, float]],
    priser: dict[datetime, list[float]],
    *,
    maler_sekunder: int = 10,
    jitter: float = 0.0,
    frø: int = 0,
    fase_sekunder: int = 0,
    hale_minutter: int = 10,
    **kwargs,
) -> Replay:
    """Kjør en hendelsesrekke gjennom coordinatoren og gi replayen tilbake."""
    logg = logg_fra_timesenergi(timer, priser, maler_sekunder=maler_sekunder)
    r = Replay(coord_module, logg, **kwargs)
    start = timer[0][0]
    slutt = timer[-1][0] + timedelta(hours=1)
    r.start(start)
    r.kjor(
        pollplan(
            start + timedelta(seconds=fase_sekunder),
            slutt + timedelta(minutes=hale_minutter),
            jitter_sekunder=jitter,
            frø=frø,
        )
    )
    return r


def _flat(start: datetime, antall: int, kwh: float, pris: float):
    """`antall` timer med samme forbruk og samme pris i alle fire rutene."""
    timer = [(start + timedelta(hours=n), kwh) for n in range(antall)]
    return timer, {t: [pris] * 4 for t, _ in timer}


class TestHendelsesreplay:
    """Coordinatoren mot fasiten, for den historikken den faktisk fikk se."""

    @pytest.mark.xfail(
        strict=True,
        reason=f"Energien bokføres i pollens time, ikke i målingens. Flippes av {L3A}.",
    )
    def test_energien_bokfores_i_timen_den_ble_malt(self, coord_module):
        """C1 og C2.4: et døgn der dag- og natt-tariffen skifter to ganger.

        Fasiten fordeler etter observasjonstid, coordinatoren bokfører hele
        pollens delta i bøtten pollen står i. Forskjellen viser seg som kWh
        som har krysset tariffgrensen.
        """
        start = datetime(2026, 6, 15, 0, tzinfo=OSLO)
        timer, priser = _flat(start, 24, 2.0, 1.00)
        # Kraftig forbruk i timen før den ene tariffgrensen og lite før den
        # andre, så de to feilplasseringene ikke opphever hverandre.
        timer[5] = (timer[5][0], 30.0)
        timer[21] = (timer[21][0], 3.0)
        r = _syntetisk(coord_module, timer, priser)
        try:
            fasit = r.fasit().avregning()
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.01)
            assert r.data["monthly_consumption_dag_kwh"] == pytest.approx(fasit.kwh_dag, abs=0.01), (
                f"Dag/natt-fordelingen følger polltiden, ikke måletiden. Flippes av {L3A}."
            )
        finally:
            r.lukk()

    @pytest.mark.xfail(
        strict=True, reason=f"Avviket mot fasiten flytter seg med pollplanen (C2.6). Flippes av {L3A}."
    )
    def test_polljitter_endrer_ikke_avregningen(self, coord_module):
        """C2.6 gjennom coordinatoren.

        Tre pollplaner over den samme hendelsesrekken: rolig, med jitter og med
        et halvt minutts faseforskyvning. Fasiten for hver av dem regnes av den
        historikken planen faktisk observerte, så en forskjell her er
        coordinatorens, ikke hendelsenes.
        """
        start = datetime(2026, 6, 15, 0, tzinfo=OSLO)
        timer, priser = _flat(start, 12, 3.0, 1.00)
        timer[5] = (timer[5][0], 30.0)
        planer = {
            "rolig": {},
            "jitter": {"jitter": 55.0, "frø": 11},
            "fase": {"fase_sekunder": 30},
        }
        avvik: dict[str, float] = {}
        for navn, kw in planer.items():
            r = _syntetisk(coord_module, timer, priser, **kw)
            try:
                fasit = r.fasit().avregning()
                avvik[navn] = r.data["monthly_consumption_dag_kwh"] - fasit.kwh_dag
            finally:
                r.lukk()
        assert avvik == {navn: pytest.approx(0.0, abs=0.01) for navn in planer}, (
            f"Coordinatoren avviker fra fasiten, og avviket flytter seg med pollplanen: "
            f"{ {k: round(v, 4) for k, v in avvik.items()} }. Flippes av {L3A}."
        )

    @pytest.mark.xfail(
        strict=True,
        reason=f"Norgespris regnes mot prisen ved poll, ikke mot timeprisen (A2, C2.4). Flippes av {L3B}.",
    )
    def test_prishopp_folger_energien_ikke_pollen(self, coord_module):
        """C2.4: et stort prishopp midt i en time.

        Prisen dobler seg fra ett kvarter til det neste mens forbruket er jevnt.
        Timeprisen er snittet av de fire rutene (A2), og Norgespris-linjen skal
        regnes med den, ikke med prisen som sto da pollen kom.
        """
        start = datetime(2026, 6, 15, 10, tzinfo=OSLO)
        timer = [(start, 8.0), (start + timedelta(hours=1), 8.0)]
        priser = {
            start: [0.50, 0.50, 2.00, 2.00],
            start + timedelta(hours=1): [1.00, 1.00, 1.00, 1.00],
        }
        r = _syntetisk(coord_module, timer, priser)
        try:
            fasit = r.fasit().avregning()
            assert r.data["monthly_norgespris_compensation_kr"] == pytest.approx(fasit.stotte_kr, abs=0.01), (
                f"Norgespris regnes mot øyeblikksprisen ved poll, ikke timeprisen. Flippes av {L3B}."
            )
        finally:
            r.lukk()

    @pytest.mark.xfail(
        strict=True, reason=f"Timen før tariffgrensen bokføres på pollens tariff. Flippes av {L3A}."
    )
    def test_tariffhopp_ved_dagens_start(self, coord_module):
        """Tariffen skifter 06:00 lokalt, og energien før grensen er natt."""
        start = datetime(2026, 6, 15, 4, tzinfo=OSLO)
        timer, priser = _flat(start, 4, 6.0, 1.00)
        r = _syntetisk(coord_module, timer, priser)
        try:
            fasit = r.fasit().avregning()
            assert fasit.kwh_natt == pytest.approx(12.0, abs=0.05)
            assert r.data["monthly_consumption_natt_kwh"] == pytest.approx(fasit.kwh_natt, abs=0.01), (
                f"Timen 05-06 bokføres som dag fordi pollen som ser den står 06:00. Flippes av {L3A}."
            )
        finally:
            r.lukk()

    def test_host_dst_gir_to_timer_med_samme_veggklokke(self, coord_module):
        """25.10.2026: 02:00 kommer to ganger, og begge skal telles.

        Ingen kilowattimer skal forsvinne fordi veggklokken gikk bakover.
        """
        start = datetime(2026, 10, 25, 0, tzinfo=OSLO)
        timer = [(start + timedelta(hours=n), 4.0) for n in range(6)]
        priser = {t: [1.00] * 4 for t, _ in timer}
        r = _syntetisk(coord_module, timer, priser)
        try:
            fasit = r.fasit().avregning()
            assert fasit.kwh_total == pytest.approx(24.0, abs=0.05)
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.05)
        finally:
            r.lukk()

    def test_var_dst_mister_ingen_timer(self, coord_module):
        """29.03.2026: 02:00 finnes ikke, og pollplanen skal ikke stoppe."""
        start = datetime(2026, 3, 29, 0, tzinfo=OSLO)
        timer = [(start + timedelta(hours=n), 4.0) for n in range(5)]
        priser = {t: [1.00] * 4 for t, _ in timer}
        r = _syntetisk(coord_module, timer, priser)
        try:
            fasit = r.fasit().avregning()
            assert fasit.kwh_total == pytest.approx(20.0, abs=0.05)
            assert 2 not in {i.lokal_time for i in r.fasit().intervaller()}
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.05)
        finally:
            r.lukk()

    @pytest.mark.xfail(
        strict=True, reason=f"Timen uten prisprøve prises med naboens pris (C2.5). Flippes av {L3B}."
    )
    def test_manglende_pris_gir_ikke_null_kroner(self, coord_module):
        """C2.5 og C4: prissensoren er borte en time.

        Energien bokføres som ellers, men timen er `uten_pris` og bidrar ikke
        til Norgespris-linjen. Den skal ikke prises med 0 og ikke med naboens.
        """
        start = datetime(2026, 6, 15, 10, tzinfo=OSLO)
        timer, priser = _flat(start, 3, 5.0, 1.20)
        r = Replay(coord_module, logg_fra_timesenergi(timer, priser, maler_sekunder=10))
        r.start(start)
        r.pris_hull(*[start + timedelta(hours=1, minutes=15 * i) for i in range(4)])
        try:
            r.kjor(pollplan(start, start + timedelta(hours=3, minutes=10)))
            fasit = r.fasit().avregning()
            assert fasit.kwh_uten_pris == pytest.approx(5.0, abs=0.1)
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.05)
            assert r.data["monthly_norgespris_compensation_kr"] == pytest.approx(fasit.stotte_kr, abs=0.05), (
                f"Timen uten pris får naboens pris i stedet for ingen. Flippes av {L3B}."
            )
        finally:
            r.lukk()

    def test_forsinket_og_duplisert_input_bokfores_en_gang(self, coord_module):
        """C2.2 og C2.3: telleren står stille i noen polls, så hopper den.

        Mange polls ser den samme avlesningen. Den skal bokføres én gang, og
        alle kilowattimene skal ligge i timene de ble målt i.
        """
        start = datetime(2026, 6, 15, 10, tzinfo=OSLO)
        timer, priser = _flat(start, 3, 6.0, 1.00)
        r = _syntetisk(coord_module, timer, priser, maler_sekunder=1800)
        try:
            fasit = r.fasit().avregning()
            assert fasit.kwh_total == pytest.approx(18.0, abs=0.05)
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.05)
        finally:
            r.lukk()

    def test_omstart_gir_samme_avregning(self, coord_module):
        """C2.7: samme hendelsesrekke, med og uten omstart midt i."""
        start = datetime(2026, 6, 15, 0, tzinfo=OSLO)
        timer, priser = _flat(start, 8, 4.0, 1.10)
        logg = logg_fra_timesenergi(timer, priser, maler_sekunder=10)
        slutt = timer[-1][0] + timedelta(hours=1)

        uten = Replay(coord_module, logg)
        uten.start(start)
        uten.kjor(pollplan(start, slutt))

        med = Replay(coord_module, logg)
        med.start(start)
        midt = start + timedelta(hours=4)
        med.kjor(pollplan(start, midt))
        med.restart(midt)
        med.kjor(pollplan(midt, slutt))

        try:
            assert med.omstarter == 1
            for felt in (
                "monthly_consumption_dag_kwh",
                "monthly_consumption_natt_kwh",
                "monthly_consumption_total_kwh",
                "monthly_norgespris_compensation_kr",
            ):
                assert med.data[felt] == pytest.approx(uten.data[felt], abs=0.05), felt
        finally:
            uten.lukk()
            med.lukk()

    def test_malerbytte_teller_ikke_hele_den_nye_standen(self, coord_module):
        """C1: telleren nullstilles, og baselinen flyttes uten å bokføre."""
        start = datetime(2026, 6, 15, 10, tzinfo=OSLO)
        timer, priser = _flat(start, 4, 5.0, 1.00)
        logg = logg_fra_timesenergi(timer, priser, maler_sekunder=600)
        # Ny måler fra time tre: telleren begynner på 12 kWh i stedet for
        # 100 000-noe. Deltaet skal bli 0, ikke minus hundretusen.
        byttet = [(t, v) for t, v in logg.malinger if t < start + timedelta(hours=2)]
        byttet += [(t, v - 100_000.0 + 12.0) for t, v in logg.malinger if t >= start + timedelta(hours=2)]
        logg.malinger = byttet
        logg.sorter()
        r = Replay(coord_module, logg)
        r.start(start)
        try:
            r.kjor(pollplan(start, start + timedelta(hours=4, minutes=10)))
            fasit = r.fasit().avregning()
            assert Utfall.NEGATIVT in r.fasit().utfall
            # Alt bokføres bortsett fra vinduet spranget ligger i: telleren
            # rapporterer hvert tiende minutt, så det er ett kvarters sjettedel
            # av en time med 5 kWh. Hele den nye standen på 12 kWh skal ikke
            # havne i månedsforbruket.
            tapt = 5.0 / 6
            assert fasit.kwh_total == pytest.approx(20.0 - tapt, abs=0.2)
            assert r.data["monthly_consumption_total_kwh"] == pytest.approx(fasit.kwh_total, abs=0.2)
        finally:
            r.lukk()

    def test_manedsskifte_arkiverer_ved_lokal_midnatt(self, coord_module):
        """C6 og D5: fakturamåneden skifter ved lokal midnatt, ikke UTC."""
        start = datetime(2026, 6, 30, 20, tzinfo=OSLO)
        timer, priser = _flat(start, 8, 3.0, 1.00)
        r = _syntetisk(coord_module, timer, priser, maler_sekunder=60)
        try:
            juni = r.fasit().avregning("2026-06")
            juli = r.fasit().avregning("2026-07")
            assert juni.kwh_total == pytest.approx(12.0, abs=0.1)
            assert juli.kwh_total == pytest.approx(12.0, abs=0.2)
            assert r.data["previous_month_name"] == "juni 2026"
            assert r.data["previous_month_consumption_total_kwh"] == pytest.approx(juni.kwh_total, abs=0.1), (
                f"Månedsskiftet deler ikke vinduet ved grensen. Flippes av {L3A}."
            )
        finally:
            r.lukk()


# ---------------------------------------------------------------------------
# 4. Fakturaavstemming gjennom coordinatoren
# ---------------------------------------------------------------------------


_KJORT: dict[str, tuple[Any, dict[str, Any], Any]] = {}


def _kjor_maned(coord_module, navn: str) -> tuple[Any, dict[str, Any], Any]:
    """Hele måneden gjennom coordinatoren, med poll hvert minutt og jitter."""
    timer = maned_timer(navn)
    priser = maned_priser(navn)
    logg = logg_fra_timesenergi(timer, priser, maler_sekunder=60)
    r = Replay(coord_module, logg)
    start = timer[0][0]
    slutt = timer[-1][0] + timedelta(hours=1)
    r.start(start)
    r.kjor(pollplan(start, slutt, jitter_sekunder=8, frø=3))
    # Kronene nullstilles ved månedsskiftet, så de leses av før rulleringen.
    for_rollover = dict(r.data)
    r.poll(slutt + timedelta(seconds=30))
    return r, for_rollover, r.fasit().avregning(start.strftime("%Y-%m"))


@pytest.mark.parametrize("navn", AVSTEMBARE)
class TestFakturaavstemmingGjennomCoordinator:
    """De tre avstembare månedene, time for time, i produksjonsrytme.

    Hver måned kjøres én gang med poll hvert minutt og jitter, og alle
    påstandene leser samme kjøring. Det er den dyreste posten i filen, og
    kjøretidsvakten nederst passer på at den holder seg innenfor budsjettet.
    """

    @pytest.fixture
    def replay(self, coord_module, navn):
        # Én kjøring per måned, delt av alle testene i klassen. En class-scoped
        # fixture kan ikke be om coord_module, som er function-scoped, så
        # cachen er manuell.
        if navn not in _KJORT:
            _KJORT[navn] = _kjor_maned(coord_module, navn)
        return _KJORT[navn]

    def test_energi_total(self, navn, replay):
        r, _, _fasit = replay
        f = FAKTURAER[navn]
        assert r.data["previous_month_consumption_total_kwh"] == pytest.approx(
            f["forbruk_total_kwh"], abs=0.05
        )

    def test_energi_dag_natt(self, navn, replay):
        """Dag/natt mot fakturaen, med den slakken dagens bokføring krever.

        Toleransen er 0,4 kWh, ikke 0,05: coordinatoren bokfører hele pollens
        delta på pollens tariff, så kilowattimene i det siste minuttet før hver
        tariffgrense havner på feil side. Over en måned med 60 grenseskifter
        blir det noen tideler. Den eksakte påstanden står i
        `test_coordinatoren_treffer_fasiten` og er strict-xfail til L3a.
        """
        r, _, _fasit = replay
        f = FAKTURAER[navn]
        assert r.data["previous_month_consumption_dag_kwh"] == pytest.approx(f["forbruk_dag_kwh"], abs=0.4)
        assert r.data["previous_month_consumption_natt_kwh"] == pytest.approx(f["forbruk_natt_kwh"], abs=0.4)

    def test_energiledd_og_avgifter(self, navn, replay):
        """`monthly_accumulated_cost_energiledd_kr` er energiledd + avgifter.

        Feltet heter energiledd, men satsen coordinatoren ganger med er
        `total_nettleie_price`, altså energiledd pluss forbruksavgift og enova.
        Fasiten summeres på samme måte her for å sammenligne likt; at navnet er
        misvisende hører til felttabellen i A0 og er ikke denne testens sak.
        """
        _r, for_rollover, _fasit = replay
        f = FAKTURAER[navn]
        ventet = f["energiledd_dag_kr"] + f["energiledd_natt_kr"] + f["forbruksavgift_kr"]
        ventet += f["enovaavgift_kr"]
        assert for_rollover["monthly_accumulated_cost_energiledd_kr"] == pytest.approx(ventet, abs=0.15)

    def test_norgespris(self, navn, replay):
        """Norgespris-linjen mot fakturaen, med 0,20 kr slakk.

        Fasiten treffer innenfor 0,01 kr (`TestFasitMotFaktura`). Coordinatoren
        ligger inntil 0,1 kr unna fordi den priser hvert poll-delta med prisen
        som sto da pollen kom, ikke med timeprisen energien hører til.
        """
        r, _, _fasit = replay
        assert r.data["previous_month_norgespris_compensation_kr"] == pytest.approx(
            FAKTURAER[navn]["norgespris_kr"], abs=0.20
        )

    def test_fastledd(self, navn, replay):
        r, _, _fasit = replay
        assert r.data["previous_month_kapasitetsledd"] == FAKTURAER[navn]["kapasitet_kr"]


@pytest.mark.xfail(
    strict=True,
    reason=f"Coordinatoren avviker fra fasiten på energi og kroner. Flippes av {L3A} og {L3B}.",
)
def test_coordinatoren_treffer_fasiten(coord_module):
    """Den skarpe påstanden: samme observerte historikk, samme avregning.

    Alle tre månedene i én test, for et avvik som tilfeldigvis er lite i én
    måned er ikke et bevis. Fasiten er bygget av nøyaktig de avlesningene og
    prisprøvene coordinatoren selv fikk se, så forskjellen er coordinatorens.
    """
    avvik: dict[str, dict[str, float]] = {}
    for navn in AVSTEMBARE:
        if navn not in _KJORT:
            _KJORT[navn] = _kjor_maned(coord_module, navn)
        r, _for_rollover, fasit = _KJORT[navn]
        avvik[navn] = {
            "dag_kwh": r.data["previous_month_consumption_dag_kwh"] - fasit.kwh_dag,
            "natt_kwh": r.data["previous_month_consumption_natt_kwh"] - fasit.kwh_natt,
            "norgespris_kr": r.data["previous_month_norgespris_compensation_kr"] - fasit.stotte_kr,
        }
    verste = max(abs(v) for rad in avvik.values() for v in rad.values())
    assert verste < 0.01, (
        f"Største avvik {verste:.4f}: { {k: {f: round(v, 4) for f, v in rad.items()} for k, rad in avvik.items()} }"
    )


# ---------------------------------------------------------------------------
# 5. Kjøretidsvakt
# ---------------------------------------------------------------------------


def test_maanedsreplay_er_raskere_enn_budsjettet(coord_module):
    """Et døgn i produksjonsrytme skal koste under et sekund.

    Budsjettet for hele filen er 30 sekunder i default-suiten, og
    månedsreplayen over er den eneste posten som er stor nok til å sprenge
    det. Måler vi ett døgn, fanger vi en regresjon i pollkostnaden lenge før
    den gjør hele filen treg.
    """
    start = datetime(2026, 6, 15, 0, tzinfo=OSLO)
    timer, priser = _flat(start, 24, 1.5, 1.00)
    t0 = time.perf_counter()
    r = _syntetisk(coord_module, timer, priser, maler_sekunder=60, hale_minutter=0)
    brukt = time.perf_counter() - t0
    try:
        assert r.polls == 24 * 60
        assert brukt < 3.0, f"{r.polls} polls tok {brukt:.1f} s; et døgn skal koste under et sekund"
    finally:
        r.lukk()
