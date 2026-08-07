"""Verifisering av 2026-tariffer for nettselskaper som ble fikset etter
trippelsjekk mot offisielle kilder (se docs/research/dso-trippelverifisering.md).

Test-stil: gitt energi X og effekt Y, returner kostnad Z kr. Speiler
faktura-kalkylen brukerne ser. Bruker samme inkl-mva-formel som
coordinator (energiledd_eks_mva + forbruksavgift + Enova) * (1 + mva).
"""

from __future__ import annotations

import pytest
from stromkalkulator.const import (
    ENOVA_AVGIFT,
    FORBRUKSAVGIFT_ALMINNELIG,
    MVA_SATS,
)
from stromkalkulator.dso import DSO_LIST, finn_kapasitetstrinn


def energiledd_inkl_mva(eks_mva: float) -> float:
    """Standard-sone: (eks_mva + forbruksavgift + Enova) * 1.25."""
    return (eks_mva + FORBRUKSAVGIFT_ALMINNELIG + ENOVA_AVGIFT) * (1 + MVA_SATS)


def kapasitetsledd_for_power(avg_power_kw: float, dso: dict) -> int:
    """Fastledd i kr/mnd, via produksjonskodens eget grenseoppslag.

    Tidligere var dette en lokal kopi med `<=` for alle nettselskap. Den
    bekreftet motsatt oppførsel av produksjonen ved eksakt grensetreff, så
    testene var grønne mens BKK-kunden på nøyaktig 5,0 kW fikk feil trinn i
    påstandene våre. Nå kalles `finn_kapasitetstrinn` direkte.
    """
    pris, _, _ = finn_kapasitetstrinn(
        dso["kapasitetstrinn"], avg_power_kw, dso.get("terskel_inkludert", True)
    )
    return pris


# ============================================================================
# Lnett: energiledd 25,60/13,60 + 10 kapasitetstrinn (rettet 2026-05-23)
# ============================================================================


class TestLnett2026:
    """Lnett: rettet manglende trinn 7-10 og energiledd-feil."""

    @pytest.fixture
    def lnett(self):
        return DSO_LIST["lnett"]

    def test_energiledd_dag_eks_mva_er_25_60_ore(self, lnett):
        """Lnett 2026 PDF: dag 25,60 øre/kWh eks. mva og avgifter."""
        assert lnett["energiledd_dag_eks_mva"] == pytest.approx(0.256)

    def test_energiledd_natt_eks_mva_er_13_60_ore(self, lnett):
        """Lnett 2026 PDF: natt/helg 13,60 øre/kWh eks. mva og avgifter."""
        assert lnett["energiledd_natt_eks_mva"] == pytest.approx(0.136)

    def test_dag_inkl_mva_matcher_pdf_32_ore(self, lnett):
        """Inkl. alt skal være 32 øre/kWh (matcher Lnett PDF inkl. mva)."""
        inkl = energiledd_inkl_mva(lnett["energiledd_dag_eks_mva"])
        assert inkl == pytest.approx(0.4216, abs=0.001)  # 32 øre/kWh ÷ 1,25 * 1,25... PDF: 32 inkl. mva (uten forbruks/Enova?)
        # PDF viser 32 inkl. mva = 25,60 eks. mva (ren nettleie + mva).
        # Vår inkl-mva-pris er 25,60 + 7,13 + 1,0 = 33,73 eks. mva, * 1,25 = 42,16 inkl. alt.

    def test_har_alle_10_trinn(self, lnett):
        """Lnett har 10 kapasitetstrinn ifølge PDF og kraftsystemet."""
        assert len(lnett["kapasitetstrinn"]) == 10

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            (1.0, 150),     # trinn 1: 0-2 kW
            (2.0, 250),     # eksakt grensetreff -> høyere trinn (terskel_inkludert)
            (2.5, 250),     # trinn 2: 2-5 kW
            (5.0, 400),     # eksakt grensetreff -> høyere trinn
            (7.0, 400),     # trinn 3: 5-10 kW
            (12.0, 650),    # trinn 4: 10-15 kW
            (17.5, 900),    # trinn 5: 15-20 kW
            (22.0, 1150),   # trinn 6: 20-25 kW
            (30.0, 2150),   # trinn 7: 25-50 kW (var manglende!)
            (60.0, 3150),   # trinn 8: 50-75 kW (var manglende!)
            (85.0, 4150),   # trinn 9: 75-100 kW (var manglende!)
            (150.0, 7000),  # trinn 10: 100+ kW (var manglende!)
        ],
    )
    def test_kapasitetsledd_per_trinn(self, lnett, avg_power, expected_kr_mnd):
        assert (
            kapasitetsledd_for_power(avg_power, lnett)
            == expected_kr_mnd
        )

    def test_eksempel_husstand_30_kwh_dagforbruk(self, lnett):
        """Husholdning forbruker 30 kWh på dag-tid:
        30 * 25,60 / 100 = 7,68 kr ren nettleie eks. mva og avgifter.
        Inkl. alt: 30 * 0,4216 = 12,648 kr.
        """
        forbruk_kwh = 30
        dag_inkl = energiledd_inkl_mva(lnett["energiledd_dag_eks_mva"])
        kostnad = forbruk_kwh * dag_inkl
        # 30 * ((0,256 + 0,0713 + 0,01) * 1,25) = 30 * 0,42162... = 12,649
        assert kostnad == pytest.approx(12.65, abs=0.01)

    def test_husstand_pa_30_kw_far_trinn_7(self, lnett):
        """Stor husholdning med snitt-effekt 30 kW skal lande på trinn 7
        (25-50 kW = 2150 kr/mnd), ikke det gamle taket på 1150."""
        pris = kapasitetsledd_for_power(30.0, lnett)
        assert pris == 2150
        assert pris != 1150  # gammelt feil tak


# ============================================================================
# Lede: flat 11,41 øre eks. mva (rettet fra 24,38) + kapasitetstrinn
# ============================================================================


class TestLede2026:
    """Lede: rettet energiledd og kapasitetstrinn fra 2025-data."""

    @pytest.fixture
    def lede(self):
        return DSO_LIST["lede"]

    def test_energiledd_er_11_41_ore_flat(self, lede):
        """Lede 2026: flat 11,41 øre/kWh eks. mva og avgifter."""
        assert lede["energiledd_dag_eks_mva"] == pytest.approx(0.1141)
        assert lede["energiledd_natt_eks_mva"] == pytest.approx(0.1141)

    def test_dag_lik_natt_flat_sats(self, lede):
        """Lede har flat sats - dag og natt skal være like."""
        assert lede["energiledd_dag_eks_mva"] == lede["energiledd_natt_eks_mva"]

    def test_inkl_alle_avgifter_matcher_lede_faktura(self, lede):
        """Lede oppgir 24,42 øre/kWh inkl. alle avgifter på sin egen side."""
        inkl = energiledd_inkl_mva(lede["energiledd_dag_eks_mva"])
        # (0,1141 + 0,0713 + 0,01) * 1,25 = 0,24425
        assert inkl == pytest.approx(0.2442, abs=0.001)

    def test_kapasitetsledd_trinn_har_korrekte_priser(self, lede):
        """Lede 2026 priser fra lede.no/priser/nettleie-privatkunder/."""
        trinn = dict(lede["kapasitetstrinn"][:6])
        assert trinn[5] == 269     # 0-5 kW: 268,75 ≈ 269
        assert trinn[10] == 459    # 5-10 kW: 458,75 ≈ 459
        assert trinn[15] == 648    # 10-15 kW: 647,50 ≈ 648
        assert trinn[20] == 838    # 15-20 kW: 837,50 ≈ 838
        assert trinn[25] == 1028   # 20-25 kW: 1027,50 ≈ 1028
        assert trinn[50] == 1596   # 25-50 kW: 1596,25 ≈ 1596

    def test_har_trinn_over_50_kw_via_kraftsystemet(self, lede):
        """Lede har trinn også for 50-200+ kW (fra kraftsystemet.no)."""
        # Tidligere stoppet vi på 25-50 kW; nå skal vi dekke videre.
        assert len(lede["kapasitetstrinn"]) >= 7
        # Siste trinn skal være float('inf')
        assert lede["kapasitetstrinn"][-1][0] == float("inf")

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            (3.0, 269),    # 0-5 kW
            (5.0, 459),    # eksakt grensetreff -> høyere trinn
            (7.5, 459),    # 5-10 kW
            (12.0, 648),   # 10-15 kW
            (17.0, 838),   # 15-20 kW
            (22.0, 1028),  # 20-25 kW
            (35.0, 1596),  # 25-50 kW
            (60.0, 2545),  # 50-75 kW (ny)
            (90.0, 3493),  # 75-100 kW (ny)
        ],
    )
    def test_kapasitetsledd_per_trinn(self, lede, avg_power, expected_kr_mnd):
        assert (
            kapasitetsledd_for_power(avg_power, lede)
            == expected_kr_mnd
        )


# ============================================================================
# Elvia: kapasitetstrinn 6-10 rettet mot PDF
# ============================================================================


class TestElvia2026:
    """Elvia hevet både energiledd og fastledd 01.07.2026 (GitHub-issue #12).

    Kilde: tariffblad_1_0_standard-tariff_privat_20260701.pdf, som stemmer
    eksakt med fri-nettleie og elvia.no. Alle priser der er oppgitt inkl.
    Enova, elavgift og mva - vi lagrer den rene nettleiedelen.
    """

    @pytest.fixture
    def elvia(self):
        return DSO_LIST["elvia"]

    def test_energiledd_per_01_07_2026(self, elvia):
        """Elvia hevet energiledd 01.07.2026: dag 36,40 -> 46,40, natt 26,40 -> 31,40 inkl. alt."""
        assert elvia["energiledd_dag_eks_mva"] == pytest.approx(0.2899)
        assert elvia["energiledd_natt_eks_mva"] == pytest.approx(0.1699)

    def test_dag_inkl_alt_matcher_elvia_46_40_ore(self, elvia):
        """Elvia per 01.07.2026: dag 46,40 øre/kWh inkl. alt."""
        inkl = energiledd_inkl_mva(elvia["energiledd_dag_eks_mva"])
        # (0,2899 + 0,0713 + 0,01) * 1,25 = 0,4640
        assert inkl == pytest.approx(0.4640, abs=0.001)

    def test_natt_inkl_alt_matcher_elvia_31_40_ore(self, elvia):
        """Elvia per 01.07.2026: natt/helg 31,40 øre/kWh inkl. alt."""
        inkl = energiledd_inkl_mva(elvia["energiledd_natt_eks_mva"])
        assert inkl == pytest.approx(0.3140, abs=0.001)

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            (1.0, 150),     # trinn 1: 0-2 kW   (var 125)
            (3.0, 250),     # trinn 2: 2-5 kW   (var 190)
            (7.0, 420),     # trinn 3: 5-10 kW  (var 300)
            (12.0, 585),    # trinn 4: 10-15 kW (var 410)
            (17.0, 755),    # trinn 5: 15-20 kW (var 520)
            (22.0, 925),    # trinn 6: 20-25 kW (var 630)
            (30.0, 1760),   # trinn 7: 25-50 kW (var 1175)
            (60.0, 2600),   # trinn 8: 50-75 kW (var 1720)
            (85.0, 3440),   # trinn 9: 75-100 kW (var 2270)
            (150.0, 6800),  # trinn 10: over 100 kW (var 4570)
        ],
    )
    def test_kapasitetsledd_per_trinn(self, elvia, avg_power, expected_kr_mnd):
        assert (
            kapasitetsledd_for_power(avg_power, elvia)
            == expected_kr_mnd
        )

    def test_rakkestad_folger_elvia(self):
        """Rakkestad Energi er del av Elvia og skal ha identisk tariff."""
        rakkestad = DSO_LIST["rakkestad_energi"]
        elvia = DSO_LIST["elvia"]
        assert rakkestad["energiledd_dag_eks_mva"] == elvia["energiledd_dag_eks_mva"]
        assert rakkestad["energiledd_natt_eks_mva"] == elvia["energiledd_natt_eks_mva"]
        assert rakkestad["kapasitetstrinn"] == elvia["kapasitetstrinn"]


# ============================================================================
# Nettselskapet: kapasitetsledd hevet 01.07.2026 + ingen helgetariff
# ============================================================================


class TestNettselskapet2026:
    """Nettselskapet AS hevet kapasitetsleddet 01.07.2026 (GitHub-issue #11).

    Energileddet står stille, men fastleddet gikk opp ~18%. Prislisten deres
    skiller kun på klokkeslett, ikke ukedag.
    Kilde: nettselskapet.as/strompris (priser inkl. mva i egen kolonne).
    """

    @pytest.fixture
    def nettselskapet(self):
        return DSO_LIST["nettselskapet"]

    def test_energiledd_uendret_ved_prisendringen(self, nettselskapet):
        """Sesongsatsene sto stille 01.07.2026: vinter 12,70/2,70, sommer 11,60/1,60."""
        perioder = {p["fra"]: p for p in nettselskapet["energiledd_perioder"]}
        assert perioder["11-01"]["dag_eks_mva"] == pytest.approx(0.127)
        assert perioder["11-01"]["natt_eks_mva"] == pytest.approx(0.027)
        assert perioder["05-01"]["dag_eks_mva"] == pytest.approx(0.116)
        assert perioder["05-01"]["natt_eks_mva"] == pytest.approx(0.016)

    def test_ingen_helgetariff(self, nettselskapet):
        """Prislisten har kun dag 06-22 og natt 22-06, ingen helgepris."""
        assert nettselskapet["helg_som_natt"] is False

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            (1.0, 163),    # 0-2 kW: 162,50   (var 137,50)
            (3.0, 300),    # 2-5 kW: 300      (var 250)
            (7.0, 513),    # 5-10 kW: 512,50  (var 425)
            (12.0, 763),   # 10-15 kW: 762,50 (var 625)
            (17.0, 988),   # 15-20 kW: 987,50 (var 812,50)
            (22.0, 1238),  # 20-25 kW: 1237,50 (var 1025)
            (30.0, 2125),  # 25-50 kW: 2125   (var 1750)
            (60.0, 3325),  # 50-75 kW: 3325   (var 2750)
        ],
    )
    def test_kapasitetsledd_per_trinn(self, nettselskapet, avg_power, expected_kr_mnd):
        assert (
            kapasitetsledd_for_power(avg_power, nettselskapet)
            == expected_kr_mnd
        )


# ============================================================================
# Norgesnett: ny tariff 01.07.2026. Asker Nett: verifisert uendret.
# ============================================================================


class TestNorgesnett2026:
    """Norgesnett hevet energiledd og alle ti kapasitetstrinn 01.07.2026.
    Satsene er verifisert mot norgesnett.no 2026-08-07."""

    @pytest.fixture
    def norgesnett(self):
        return DSO_LIST["norgesnett"]

    def test_dag_inkl_alt_matcher_norgesnett_42_16_ore(self, norgesnett):
        """Norgesnett per 01.07.2026: dag 42,16 øre/kWh inkl. alle avgifter."""
        inkl = energiledd_inkl_mva(norgesnett["energiledd_dag_eks_mva"])
        # (0,25598 + 0,0713 + 0,01) * 1,25 = 0,4216
        assert inkl == pytest.approx(0.4216, abs=0.001)

    def test_natt_inkl_alt_matcher_norgesnett_27_16_ore(self, norgesnett):
        """Norgesnett per 01.07.2026: natt 27,16 øre/kWh inkl. alle avgifter."""
        inkl = energiledd_inkl_mva(norgesnett["energiledd_natt_eks_mva"])
        # (0,13598 + 0,0713 + 0,01) * 1,25 = 0,2716
        assert inkl == pytest.approx(0.2716, abs=0.001)

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            (1.0, 140),
            (3.0, 233),  # 232,50
            (7.0, 390),
            (12.0, 695),
            (17.0, 935),
            (22.0, 1145),
            (30.0, 1813),  # 1812,50
            (60.0, 2813),  # 2812,50
            (80.0, 3813),  # 3812,50
            (120.0, 6113),  # 6112,50
        ],
    )
    def test_kapasitetsledd_per_trinn(self, norgesnett, avg_power, expected_kr_mnd):
        assert kapasitetsledd_for_power(avg_power, norgesnett) == expected_kr_mnd


class TestAskerNett2026Uendret:
    """Asker Nett: trippelsjekk bekrefter at eksisterende tariff er korrekt."""

    @pytest.fixture
    def asker(self):
        return DSO_LIST["asker_nett"]

    def test_dag_inkl_alt_matcher_asker_40_ore(self, asker):
        """Asker Nett 2026: dag 40 øre/kWh inkl. alt."""
        inkl = energiledd_inkl_mva(asker["energiledd_dag_eks_mva"])
        # (0,2387 + 0,0713 + 0,01) * 1,25 = 0,40
        assert inkl == pytest.approx(0.40, abs=0.001)

    def test_natt_inkl_alt_matcher_asker_30_ore(self, asker):
        """Asker Nett 2026: natt 30 øre/kWh inkl. alt."""
        inkl = energiledd_inkl_mva(asker["energiledd_natt_eks_mva"])
        # (0,1587 + 0,0713 + 0,01) * 1,25 = 0,30
        assert inkl == pytest.approx(0.30, abs=0.001)


# ============================================================================
# Grensetreff: eksakt terskel hører til det høyere trinnet
# ============================================================================


class TestEksaktGrensetreff:
    """Snitt på nøyaktig en terskel skal gi trinnet over, ikke under.

    Testfilen hadde en lokal kopi av oppslaget med `<=` for alle nettselskap,
    som bekreftet motsatt oppførsel av produksjonen. Testene var grønne mens
    påstandene beskrev feil trinn. Nå kalles `finn_kapasitetstrinn` direkte.
    """

    def test_bkk_paa_eksakt_5_kw_gir_hoyere_trinn(self):
        """BKK: 5,0 kW er 5-10 kW-trinnet (415 kr/mnd), ikke 2-5 (250)."""
        bkk = DSO_LIST["bkk"]
        assert kapasitetsledd_for_power(5.0, bkk) == 415
        assert kapasitetsledd_for_power(4.99, bkk) == 250

    def test_terskel_inkludert_false_gir_lavere_trinn(self):
        """Sør Aurdal skriver trinnene "til og med", så 5,0 kW hører til trinn 1."""
        sae = DSO_LIST["sor_aurdal_energi"]
        assert sae["terskel_inkludert"] is False
        assert kapasitetsledd_for_power(5.0, sae) == sae["kapasitetstrinn"][0][1]


# ============================================================================
# Area Nett: tre prisområder, kilde area.no prisblad 2026
# ============================================================================


class TestAreaNettOmrader:
    """Area Nett har tre områder med ulik pris, delt etter kommune.

    Én oppføring lagret tidligere 250/350/500/... kr/mnd, tall som ikke finnes
    i noe område. Kilde: area.no "Nettleietariffer 2026 inkl enovavgift",
    kryssjekket mot fri-nettleie. Prisbladet er inkl. Enova, og tiltakssonen
    har verken mva eller forbruksavgift, så ren sats = publisert minus 1,00 øre.
    """

    @pytest.mark.parametrize(
        ("dso_id", "laveste_trinn", "vinter_dag", "sommer_dag"),
        [
            ("area_nett_omrade1", 525, 0.2989, 0.2689),
            ("area_nett_omrade2", 390, 0.2989, 0.2689),
            ("area_nett_omrade3", 358, 0.269, 0.239),
        ],
    )
    def test_omrade_har_egen_tariff(self, dso_id, laveste_trinn, vinter_dag, sommer_dag):
        dso = DSO_LIST[dso_id]
        assert kapasitetsledd_for_power(1.0, dso) == laveste_trinn
        perioder = {p["fra"]: p for p in dso["energiledd_perioder"]}
        assert perioder["01-01"]["dag_eks_mva"] == pytest.approx(vinter_dag)
        assert perioder["04-01"]["dag_eks_mva"] == pytest.approx(sommer_dag)

    def test_publisert_sats_er_ren_pluss_enova(self):
        """Område 1 vinter dag: 29,89 + 1,00 Enova = 30,89 øre, som prisbladet."""
        dso = DSO_LIST["area_nett_omrade1"]
        assert dso["energiledd_dag_eks_mva"] + ENOVA_AVGIFT == pytest.approx(0.3089)

    def test_omradene_har_ulikt_fastledd(self):
        """Hele grunnen til splitten: prisene spriker med 167 kr/mnd."""
        laveste = [
            kapasitetsledd_for_power(1.0, DSO_LIST[d])
            for d in ("area_nett_omrade1", "area_nett_omrade2", "area_nett_omrade3")
        ]
        assert len(set(laveste)) == 3
        assert max(laveste) - min(laveste) == 167

    def test_gammel_oppforing_er_utfaset_og_peker_videre(self):
        gammel = DSO_LIST["area_nett"]
        assert gammel["supported"] is False
        assert gammel["delt_i"] == [
            "area_nett_omrade1",
            "area_nett_omrade2",
            "area_nett_omrade3",
        ]
        assert all(nytt in DSO_LIST for nytt in gammel["delt_i"])

    def test_alle_omrader_er_tiltakssone(self):
        """Finnmark og Nord-Troms: fritak for både forbruksavgift og mva."""
        for d in ("area_nett_omrade1", "area_nett_omrade2", "area_nett_omrade3"):
            assert DSO_LIST[d]["tiltakssone"] is True
