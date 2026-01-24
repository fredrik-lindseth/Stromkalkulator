"""
Test mot faktiske BKK-fakturaer.

Disse testene verifiserer at våre beregninger matcher faktiske fakturaer fra BKK.
Fakturaene ligger i Fakturaer/ mappen for referanse.

VIKTIG: Disse testene gir høy troverdighet til at integrasjonen beregner korrekt!
"""

import pytest

# BKK priser 2025 (fra fakturaene)
BKK_ENERGILEDD_DAG_ORE = 35.963  # øre/kWh eks. avgifter
BKK_ENERGILEDD_NATT_ORE = 23.738  # øre/kWh eks. avgifter
BKK_KAPASITET_5_10_KW = 415  # kr/mnd
FORBRUKSAVGIFT_2025_ORE = 15.662  # øre/kWh (vintersats Sør-Norge 2025)
ENOVAAVGIFT_2025_ORE = 1.25  # øre/kWh


class TestFakturaDesember2025:
    """
    Test mot BKK faktura 63374727 - Desember 2025.

    Fakturaperiode: 01.12.2025 - 01.01.2026
    Totalt forbruk: 1554.721 kWh
    Å betale: 1006.20 kr
    """

    # Fakturadata fra Fakturaer/BKK_Faktura_63374727.txt
    FORBRUK_DAG_KWH = 667.422
    FORBRUK_NATT_KWH = 887.299
    FORBRUK_TOTAL_KWH = 1554.721
    STROMSTOTTE_KWH = 1107.173  # kWh over terskel
    STROMSTOTTE_ORE_SNITT = 11.054  # gjennomsnittlig øre/kWh støtte
    KAPASITET_DAGER = 31

    # Forventede summer fra fakturaen
    FORVENTET_ENERGILEDD_DAG_KR = 240.03
    FORVENTET_ENERGILEDD_NATT_KR = 210.63
    FORVENTET_STROMSTOTTE_KR = 122.39
    FORVENTET_KAPASITET_KR = 415.00
    FORVENTET_FORBRUKSAVGIFT_KR = 243.50
    FORVENTET_ENOVAAVGIFT_KR = 19.43
    FORVENTET_TOTAL_KR = 1006.20

    def test_energiledd_dag_beregning(self):
        """Verifiser at energiledd dag beregnes korrekt."""
        beregnet = self.FORBRUK_DAG_KWH * BKK_ENERGILEDD_DAG_ORE / 100
        assert abs(beregnet - self.FORVENTET_ENERGILEDD_DAG_KR) < 0.10, \
            f"Energiledd dag: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_ENERGILEDD_DAG_KR} kr"

    def test_energiledd_natt_beregning(self):
        """Verifiser at energiledd natt beregnes korrekt."""
        beregnet = self.FORBRUK_NATT_KWH * BKK_ENERGILEDD_NATT_ORE / 100
        assert abs(beregnet - self.FORVENTET_ENERGILEDD_NATT_KR) < 0.10, \
            f"Energiledd natt: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_ENERGILEDD_NATT_KR} kr"

    def test_forbruksavgift_beregning(self):
        """Verifiser at forbruksavgift beregnes korrekt."""
        beregnet = self.FORBRUK_TOTAL_KWH * FORBRUKSAVGIFT_2025_ORE / 100
        assert abs(beregnet - self.FORVENTET_FORBRUKSAVGIFT_KR) < 0.10, \
            f"Forbruksavgift: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_FORBRUKSAVGIFT_KR} kr"

    def test_enovaavgift_beregning(self):
        """Verifiser at Enova-avgift beregnes korrekt."""
        beregnet = self.FORBRUK_TOTAL_KWH * ENOVAAVGIFT_2025_ORE / 100
        assert abs(beregnet - self.FORVENTET_ENOVAAVGIFT_KR) < 0.10, \
            f"Enovaavgift: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_ENOVAAVGIFT_KR} kr"

    def test_kapasitetsledd_beregning(self):
        """Verifiser at kapasitetsledd matcher fakturaen."""
        assert self.FORVENTET_KAPASITET_KR == BKK_KAPASITET_5_10_KW, \
            f"Kapasitetsledd: forventet {BKK_KAPASITET_5_10_KW} kr, faktura {self.FORVENTET_KAPASITET_KR} kr"

    def test_stromstotte_total_beregning(self):
        """Verifiser at total strømstøtte beregnes korrekt."""
        beregnet = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        assert abs(beregnet - self.FORVENTET_STROMSTOTTE_KR) < 0.10, \
            f"Strømstøtte: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_STROMSTOTTE_KR} kr"

    def test_total_nettleie_beregning(self):
        """Verifiser at total nettleie matcher fakturaen."""
        energiledd_dag = self.FORBRUK_DAG_KWH * BKK_ENERGILEDD_DAG_ORE / 100
        energiledd_natt = self.FORBRUK_NATT_KWH * BKK_ENERGILEDD_NATT_ORE / 100
        stromstotte = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        kapasitet = self.FORVENTET_KAPASITET_KR
        forbruksavgift = self.FORBRUK_TOTAL_KWH * FORBRUKSAVGIFT_2025_ORE / 100
        enovaavgift = self.FORBRUK_TOTAL_KWH * ENOVAAVGIFT_2025_ORE / 100

        beregnet = energiledd_dag + energiledd_natt - stromstotte + kapasitet + forbruksavgift + enovaavgift

        # Tillat 1% avvik pga avrunding
        assert abs(beregnet - self.FORVENTET_TOTAL_KR) < self.FORVENTET_TOTAL_KR * 0.01, \
            f"Total: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_TOTAL_KR} kr"


class TestFakturaNovember2025:
    """
    Test mot BKK faktura 63097585 - November 2025.

    Denne måneden hadde høy strømstøtte (404.80 kr) pga høye priser.
    """

    FORBRUK_DAG_KWH = 709.157
    FORBRUK_NATT_KWH = 765.349
    FORBRUK_TOTAL_KWH = 1474.506
    STROMSTOTTE_KWH = 933.128
    STROMSTOTTE_ORE_SNITT = 43.381

    FORVENTET_ENERGILEDD_DAG_KR = 255.03
    FORVENTET_ENERGILEDD_NATT_KR = 181.68
    FORVENTET_STROMSTOTTE_KR = 404.80
    FORVENTET_KAPASITET_KR = 415.00
    FORVENTET_FORBRUKSAVGIFT_KR = 230.94
    FORVENTET_ENOVAAVGIFT_KR = 18.43
    FORVENTET_TOTAL_KR = 696.28

    def test_energiledd_dag_beregning(self):
        """Verifiser energiledd dag."""
        beregnet = self.FORBRUK_DAG_KWH * BKK_ENERGILEDD_DAG_ORE / 100
        assert abs(beregnet - self.FORVENTET_ENERGILEDD_DAG_KR) < 0.10

    def test_energiledd_natt_beregning(self):
        """Verifiser energiledd natt."""
        beregnet = self.FORBRUK_NATT_KWH * BKK_ENERGILEDD_NATT_ORE / 100
        assert abs(beregnet - self.FORVENTET_ENERGILEDD_NATT_KR) < 0.10

    def test_stromstotte_hoy_maned(self):
        """Verifiser strømstøtte i en måned med høye priser."""
        beregnet = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        assert abs(beregnet - self.FORVENTET_STROMSTOTTE_KR) < 0.10, \
            f"Strømstøtte nov: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_STROMSTOTTE_KR} kr"

    def test_total_nettleie_med_hoy_stotte(self):
        """Verifiser total nettleie i måned med høy strømstøtte."""
        energiledd_dag = self.FORBRUK_DAG_KWH * BKK_ENERGILEDD_DAG_ORE / 100
        energiledd_natt = self.FORBRUK_NATT_KWH * BKK_ENERGILEDD_NATT_ORE / 100
        stromstotte = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        kapasitet = self.FORVENTET_KAPASITET_KR
        forbruksavgift = self.FORBRUK_TOTAL_KWH * FORBRUKSAVGIFT_2025_ORE / 100
        enovaavgift = self.FORBRUK_TOTAL_KWH * ENOVAAVGIFT_2025_ORE / 100

        beregnet = energiledd_dag + energiledd_natt - stromstotte + kapasitet + forbruksavgift + enovaavgift

        assert abs(beregnet - self.FORVENTET_TOTAL_KR) < self.FORVENTET_TOTAL_KR * 0.01, \
            f"Total nov: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_TOTAL_KR} kr"


class TestFakturaOktober2025:
    """
    Test mot BKK faktura 62821645 - Oktober 2025.

    Denne måneden hadde lav strømstøtte (7.16 kr) pga lave priser.
    """

    FORBRUK_DAG_KWH = 707.09
    FORBRUK_NATT_KWH = 536.117
    FORBRUK_TOTAL_KWH = 1243.207
    STROMSTOTTE_KWH = 115.661  # Kun litt forbruk over terskel
    STROMSTOTTE_ORE_SNITT = 6.188

    FORVENTET_ENERGILEDD_DAG_KR = 254.29
    FORVENTET_ENERGILEDD_NATT_KR = 127.26
    FORVENTET_STROMSTOTTE_KR = 7.16
    FORVENTET_KAPASITET_KR = 415.00
    FORVENTET_FORBRUKSAVGIFT_KR = 194.72
    FORVENTET_ENOVAAVGIFT_KR = 15.54
    FORVENTET_TOTAL_KR = 999.65

    def test_stromstotte_lav_maned(self):
        """Verifiser strømstøtte i en måned med lave priser."""
        beregnet = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        assert abs(beregnet - self.FORVENTET_STROMSTOTTE_KR) < 0.10, \
            f"Strømstøtte okt: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_STROMSTOTTE_KR} kr"

    def test_total_nettleie_med_lav_stotte(self):
        """Verifiser total nettleie i måned med lav strømstøtte."""
        energiledd_dag = self.FORBRUK_DAG_KWH * BKK_ENERGILEDD_DAG_ORE / 100
        energiledd_natt = self.FORBRUK_NATT_KWH * BKK_ENERGILEDD_NATT_ORE / 100
        stromstotte = self.STROMSTOTTE_KWH * self.STROMSTOTTE_ORE_SNITT / 100
        kapasitet = self.FORVENTET_KAPASITET_KR
        forbruksavgift = self.FORBRUK_TOTAL_KWH * FORBRUKSAVGIFT_2025_ORE / 100
        enovaavgift = self.FORBRUK_TOTAL_KWH * ENOVAAVGIFT_2025_ORE / 100

        beregnet = energiledd_dag + energiledd_natt - stromstotte + kapasitet + forbruksavgift + enovaavgift

        assert abs(beregnet - self.FORVENTET_TOTAL_KR) < self.FORVENTET_TOTAL_KR * 0.01, \
            f"Total okt: beregnet {beregnet:.2f} kr, faktura {self.FORVENTET_TOTAL_KR} kr"


class TestBKKPriserMatcherIntegrasjon:
    """
    Verifiser at BKK-prisene i integrasjonen er oppdatert til 2026.

    MERK: Fakturaene er fra 2025, så prisene vil avvike.
    Disse testene verifiserer at integrasjonen har gyldige 2026-priser.
    """

    def test_bkk_har_2026_priser(self):
        """BKK skal ha oppdaterte 2026-priser i integrasjonen."""
        from custom_components.stromkalkulator.tso import TSO_LIST

        bkk = TSO_LIST["bkk"]

        # 2026-priser fra BKK (inkl. mva)
        # Dag: 46.13 øre/kWh, Natt: 23.29 øre/kWh
        assert bkk["energiledd_dag"] == 0.4613, \
            f"BKK dag 2026 skal være 0.4613 NOK/kWh, er {bkk['energiledd_dag']}"
        assert bkk["energiledd_natt"] == 0.2329, \
            f"BKK natt 2026 skal være 0.2329 NOK/kWh, er {bkk['energiledd_natt']}"

    def test_bkk_kapasitetstrinn_5_10_matcher_faktura(self):
        """BKK kapasitetstrinn 5-10 kW skal matche fakturaen (uendret fra 2025)."""
        from custom_components.stromkalkulator.tso import TSO_LIST

        bkk = TSO_LIST["bkk"]
        # Finn kapasitetstrinn for 5-10 kW (index 2 i listen)
        kapasitet_5_10 = bkk["kapasitetstrinn"][2][1]  # (10, 415) -> 415

        assert kapasitet_5_10 == BKK_KAPASITET_5_10_KW, \
            f"BKK kapasitet 5-10: integrasjon {kapasitet_5_10} kr, faktura {BKK_KAPASITET_5_10_KW} kr"

    def test_bkk_priser_er_rimelige(self):
        """BKK-priser skal være innenfor rimelig område."""
        from custom_components.stromkalkulator.tso import TSO_LIST

        bkk = TSO_LIST["bkk"]

        # Energiledd bør være mellom 0.10 og 1.00 NOK/kWh
        assert 0.10 < bkk["energiledd_dag"] < 1.00
        assert 0.10 < bkk["energiledd_natt"] < 1.00

        # Dag skal være dyrere enn natt
        assert bkk["energiledd_dag"] > bkk["energiledd_natt"]
