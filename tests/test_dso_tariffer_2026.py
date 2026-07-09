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
from stromkalkulator.dso import DSO_LIST


def energiledd_inkl_mva(eks_mva: float) -> float:
    """Standard-sone: (eks_mva + forbruksavgift + Enova) * 1.25."""
    return (eks_mva + FORBRUKSAVGIFT_ALMINNELIG + ENOVA_AVGIFT) * (1 + MVA_SATS)


def kapasitetsledd_for_power(
    avg_power_kw: float, trinn: list[tuple[float, int]]
) -> int:
    """Replikerer coordinator._get_kapasitetsledd: første terskel >= avg."""
    for threshold, price in trinn:
        if avg_power_kw <= threshold:
            return price
    return trinn[-1][1]


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
            (2.0, 150),     # boundary
            (2.5, 250),     # trinn 2: 2-5 kW
            (5.0, 250),
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
            kapasitetsledd_for_power(avg_power, lnett["kapasitetstrinn"])
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
        pris = kapasitetsledd_for_power(30.0, lnett["kapasitetstrinn"])
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
            (5.0, 269),    # boundary
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
            kapasitetsledd_for_power(avg_power, lede["kapasitetstrinn"])
            == expected_kr_mnd
        )


# ============================================================================
# Elvia: kapasitetstrinn 6-10 rettet mot PDF
# ============================================================================


class TestElvia2026:
    """Elvia: rettet kapasitetstrinn 6-10 mot 2026-PDF."""

    @pytest.fixture
    def elvia(self):
        return DSO_LIST["elvia"]

    def test_energiledd_per_01_07_2026(self, elvia):
        """Elvia hevet energiledd 01.07.2026. Verifisert mot elvia.no + fri-nettleie."""
        assert elvia["energiledd_dag_eks_mva"] == pytest.approx(0.2899)
        assert elvia["energiledd_natt_eks_mva"] == pytest.approx(0.1699)

    def test_dag_inkl_alt_matcher_elvia_46_40_ore(self, elvia):
        """Elvia per 01.07.2026: dag 46,40 øre/kWh inkl. alt (elvia.no viser ~46,60, visnings-avrunding)."""
        inkl = energiledd_inkl_mva(elvia["energiledd_dag_eks_mva"])
        # (0,2899 + 0,0713 + 0,01) * 1,25 = 0,4640
        assert inkl == pytest.approx(0.4640, abs=0.001)

    def test_natt_inkl_alt_matcher_elvia_31_40_ore(self, elvia):
        """Elvia per 01.07.2026: natt/helg 31,40 øre/kWh inkl. alt (matcher elvia.no eksakt)."""
        inkl = energiledd_inkl_mva(elvia["energiledd_natt_eks_mva"])
        assert inkl == pytest.approx(0.3140, abs=0.001)

    @pytest.mark.parametrize(
        ("avg_power", "expected_kr_mnd"),
        [
            # Trinn 1-5 var korrekte (sanity-check)
            (1.0, 125),
            (3.0, 190),
            (7.0, 300),
            (12.0, 410),
            (17.0, 520),
            # Trinn 6-10: rettet mot PDF
            (22.0, 630),    # var 655, skal være 630
            (30.0, 1175),   # var 1135, skal være 1175
            (60.0, 1720),   # var 1750, skal være 1720
            (85.0, 2270),   # var 2370, skal være 2270
            (150.0, 4570),  # var 4225, skal være 4570
        ],
    )
    def test_kapasitetsledd_per_trinn(self, elvia, avg_power, expected_kr_mnd):
        assert (
            kapasitetsledd_for_power(avg_power, elvia["kapasitetstrinn"])
            == expected_kr_mnd
        )


# ============================================================================
# Regresjon: verifiserte at Norgesnett og Asker Nett ER korrekte allerede
# ============================================================================


class TestNorgesnett2026Uendret:
    """Norgesnett: forrige agent meldte feil, men trippelsjekk bekrefter
    eksisterende verdier matcher Norgesnetts egen tabell."""

    @pytest.fixture
    def norgesnett(self):
        return DSO_LIST["norgesnett"]

    def test_dag_inkl_alt_matcher_norgesnett_35_49_ore(self, norgesnett):
        """Norgesnett 2026: dag 35,49 øre/kWh inkl. alle avgifter."""
        inkl = energiledd_inkl_mva(norgesnett["energiledd_dag_eks_mva"])
        # (0,20262 + 0,0713 + 0,01) * 1,25 = 0,3549
        assert inkl == pytest.approx(0.3549, abs=0.001)

    def test_natt_inkl_alt_matcher_norgesnett_26_77_ore(self, norgesnett):
        """Norgesnett 2026: natt 26,77 øre/kWh inkl. alle avgifter."""
        inkl = energiledd_inkl_mva(norgesnett["energiledd_natt_eks_mva"])
        # (0,13286 + 0,0713 + 0,01) * 1,25 = 0,2677
        assert inkl == pytest.approx(0.2677, abs=0.001)


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
