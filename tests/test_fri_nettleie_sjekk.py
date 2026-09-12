"""Tester for parseren i scripts/sjekk_mot_fri_nettleie.py.

Scriptet er drift-vakten for satsene til over 70 nettselskap, og en vakt som tar
feil i stillhet er verre enn ingen vakt. Sør Aurdals sesongunntak ble ignorert
fordi det manglet `timer`-nøkkel, og ga et falskt 4-øres avvik hver vinter (se
incident 006).

Kun de rene funksjonene testes, med YAML-strukturer på formen fri-nettleie
bruker. Ingen nettverkstilgang.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import ClassVar

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

try:
    import yaml  # noqa: F401
except ModuleNotFoundError as feil:  # pragma: no cover
    raise ModuleNotFoundError(
        "pyyaml mangler, og da kan ikke drift-vakten for satsene sjekkes. "
        "Kjør suiten med `pipx run --with hypothesis --with pyyaml pytest ...`, "
        "eller installer pyyaml i miljøet. Denne filen skal feile, ikke skippe: "
        "en vakt som hopper over seg selv vakter ingenting."
    ) from feil
sjekk = importlib.import_module("sjekk_mot_fri_nettleie")

import json  # noqa: E402
from datetime import date  # noqa: E402

JANUAR = date(2027, 1, 15)
JULI = date(2026, 7, 15)


class TestEnergileddParsing:
    """hent_satser_aktiv_dato skal gi (dag, natt) i NOK/kWh."""

    def test_grunnpris_uten_unntak_gir_flat_sats(self):
        tariff = {"energiledd": {"grunnpris": 21.52}}
        assert sjekk.hent_satser_aktiv_dato(tariff, JULI) == (0.2152, 0.2152)

    def test_tidsstyrt_unntak_hever_kun_dag(self):
        tariff = {
            "energiledd": {
                "grunnpris": 16.99,
                "unntak": [{"navn": "Virkedag", "timer": "6-21", "pris": 28.99}],
            }
        }
        dag, natt = sjekk.hent_satser_aktiv_dato(tariff, JULI)
        assert dag == pytest.approx(0.2899)
        assert natt == pytest.approx(0.1699)

    def test_sesongunntak_uten_timer_gjelder_hele_dognet(self):
        """Sør Aurdal-tilfellet: "Vinter" uten timer skal treffe både dag og natt.

        Uten dette ble unntaket ignorert, og januar-kjøringen rapporterte 21,52
        der riktig vintersats er 25,52.
        """
        tariff = {
            "energiledd": {
                "grunnpris": 21.52,
                "unntak": [
                    {
                        "navn": "Vinter",
                        "pris": 25.52,
                        "måneder": ["januar", "februar", "mars", "oktober", "november", "desember"],
                    }
                ],
            }
        }
        assert sjekk.hent_satser_aktiv_dato(tariff, JANUAR) == (0.2552, 0.2552)
        assert sjekk.hent_satser_aktiv_dato(tariff, JULI) == (0.2152, 0.2152)

    def test_tidsstyrt_unntak_overstyrer_sesongunntak(self):
        """Sesongprisen setter grunnlinjen, dag/natt-unntak legges oppå."""
        tariff = {
            "energiledd": {
                "grunnpris": 1.6,
                "unntak": [
                    # Rekkefølgen her er bevisst omvendt av ønsket presedens.
                    {"navn": "Høylast vinter", "timer": "6-21", "pris": 12.7, "måneder": ["januar"]},
                    {"navn": "Vinter", "pris": 2.7, "måneder": ["januar"]},
                ],
            }
        }
        dag, natt = sjekk.hent_satser_aktiv_dato(tariff, JANUAR)
        assert dag == pytest.approx(0.127)
        assert natt == pytest.approx(0.027)

    def test_manglende_energiledd_gir_none(self):
        assert sjekk.hent_satser_aktiv_dato({}, JULI) is None


class TestFastleddKonvertering:
    """deres_trinn: kr/år eks. mva og nedre grense -> kr/mnd inkl. mva og øvre grense."""

    def test_konverterer_elvias_trinn(self):
        """Elvia 01.07.2026: 1440 kr/år eks. mva for 0-2 kW = 150 kr/mnd inkl. mva."""
        tariff = {
            "fastledd": {
                "metode": "TRE_DØGNMAX_MND",
                "terskler": [
                    {"terskel": 0, "pris": 1440},
                    {"terskel": 2, "pris": 2400},
                    {"terskel": 5, "pris": 4032},
                ],
            }
        }
        assert sjekk.deres_trinn(tariff, 1.25) == [
            (2.0, 150),
            (5.0, 250),
            (float("inf"), 420),
        ]

    def test_mva_fri_sone_bruker_faktor_1(self):
        tariff = {"fastledd": {"metode": "TRE_DØGNMAX_MND", "terskler": [{"terskel": 0, "pris": 1200}]}}
        assert sjekk.deres_trinn(tariff, 1.0) == [(float("inf"), 100)]

    def test_halve_kroner_rundes_opp(self):
        """232,50 kr/mnd skal bli 233, som i dso.py. Innebygd round() gir 232."""
        tariff = {"fastledd": {"metode": "TRE_DØGNMAX_MND", "terskler": [{"terskel": 0, "pris": 2232}]}}
        assert sjekk.deres_trinn(tariff, 1.25) == [(float("inf"), 233)]

    @pytest.mark.parametrize("metode", ["OV_TREFASE", "FEM_VEKTET_ÅR"])
    def test_metoder_uten_kw_trinn_gir_none(self, metode):
        """Tersklene er ampere eller punkter på en lineær sats, ikke kW-trinn."""
        tariff = {"fastledd": {"metode": metode, "terskler": [{"terskel": 0, "pris": 3500}]}}
        assert sjekk.deres_trinn(tariff, 1.25) is None

    @pytest.mark.parametrize("metode", ["MND_MAX", "UKJENT"])
    def test_kw_trinn_sammenlignes_selv_om_metoden_avviker(self, metode):
        """Sør Aurdal og Tinfos har kW-trinn, og skal ha drift-vakt som de andre."""
        tariff = {
            "fastledd": {
                "metode": metode,
                "terskler": [{"terskel": 0, "pris": 5400}, {"terskel": 5, "pris": 6240}],
            }
        }
        assert sjekk.deres_trinn(tariff, 1.25) == [(5.0, 563), (float("inf"), 650)]


class TestSammenlignSikringstrinn:
    """OV_TREFASE: settet av distinkte kr/mnd-priser skal stemme."""

    TARIFF: ClassVar = {
        "fastledd": {
            "metode": "OV_TREFASE",
            "terskler": [
                {"terskel": 0, "pris": 1600},
                {"terskel": 10, "pris": 3200},
                {"terskel": 63, "pris": 6400},
            ],
        }
    }

    def test_flere_rader_hos_oss_er_greit(self):
        """Netera har egne rader for 230 V og 400 V med samme priser."""
        entry = {
            "fastledd_sikringstrinn": [
                {"id": "a", "label": "0-10 A (230 V)", "kr_mnd": 167},
                {"id": "b", "label": "11-63 A (230 V)", "kr_mnd": 333},
                {"id": "c", "label": "63-125 A (230 V)", "kr_mnd": 667},
                {"id": "d", "label": "0-40 A (400 V)", "kr_mnd": 333},
                {"id": "e", "label": "40-80 A (400 V)", "kr_mnd": 667},
            ]
        }
        assert sjekk.sammenlign_sikringstrinn(entry, self.TARIFF, 1.25) is None

    def test_prisavvik_rapporteres(self):
        entry = {
            "fastledd_sikringstrinn": [
                {"id": "a", "label": "0-10 A", "kr_mnd": 167},
                {"id": "b", "label": "11-63 A", "kr_mnd": 300},
                {"id": "c", "label": "63-125 A", "kr_mnd": 667},
            ]
        }
        assert "300" in sjekk.sammenlign_sikringstrinn(entry, self.TARIFF, 1.25)

    def test_mva_fri_sone_bruker_faktor_1(self):
        """Alut i NO4: 3500 og 4500 kr/år uten mva-påslag."""
        tariff = {
            "fastledd": {
                "metode": "OV_TREFASE",
                "terskler": [{"terskel": 0, "pris": 3500}, {"terskel": 125, "pris": 4500}],
            }
        }
        entry = {
            "fastledd_sikringstrinn": [
                {"id": "a", "label": "Inntil 3 x 125 A", "kr_mnd": 292},
                {"id": "b", "label": "Over 3 x 125 A", "kr_mnd": 375},
            ]
        }
        assert sjekk.sammenlign_sikringstrinn(entry, tariff, 1.0) is None

    def test_manglende_trinn_hos_oss_rapporteres(self):
        assert sjekk.sammenlign_sikringstrinn({}, self.TARIFF, 1.25) is not None


class TestSammenlignLineaer:
    """FEM_VEKTET_ÅR: grunnbeløp + sats per kW skal treffe hver terskel."""

    def test_lineaer_sats_treffer_alle_terskler(self):
        """Fjellnett 01.01.2026: 2000 + 534 kr/kW/år eks. mva."""
        tariff = {
            "fastledd": {
                "metode": "FEM_VEKTET_ÅR",
                "terskler": [
                    {"terskel": 0, "pris": 2000},
                    {"terskel": 1, "pris": 2534},
                    {"terskel": 20, "pris": 12680},
                    {"terskel": 25, "pris": 15350},
                ],
            }
        }
        entry = {"fastledd_lineaer": {"grunnbelop_aar_eks_mva": 2000, "sats_kw_aar_eks_mva": 534}}
        assert sjekk.sammenlign_lineaer(entry, tariff) is None

    def test_endret_sats_rapporteres(self):
        """01.07.2026 hevet satsen til 589. Da skal 534-tabellen slå ut."""
        tariff = {
            "fastledd": {
                "metode": "FEM_VEKTET_ÅR",
                "terskler": [{"terskel": 0, "pris": 2000}, {"terskel": 1, "pris": 2534}],
            }
        }
        entry = {"fastledd_lineaer": {"grunnbelop_aar_eks_mva": 2000, "sats_kw_aar_eks_mva": 589}}
        assert "2589 vs 2534" in sjekk.sammenlign_lineaer(entry, tariff)

    def test_endret_grunnbeloep_rapporteres(self):
        tariff = {"fastledd": {"metode": "FEM_VEKTET_ÅR", "terskler": [{"terskel": 0, "pris": 2400}]}}
        entry = {"fastledd_lineaer": {"grunnbelop_aar_eks_mva": 2000, "sats_kw_aar_eks_mva": 534}}
        assert sjekk.sammenlign_lineaer(entry, tariff) is not None

    def test_en_krone_per_maaned_slack_tolereres(self):
        """Samme slack som trinnsammenligningen, oppgitt i kr/år."""
        tariff = {"fastledd": {"metode": "FEM_VEKTET_ÅR", "terskler": [{"terskel": 0, "pris": 2010}]}}
        entry = {"fastledd_lineaer": {"grunnbelop_aar_eks_mva": 2000, "sats_kw_aar_eks_mva": 534}}
        assert sjekk.sammenlign_lineaer(entry, tariff) is None

    def test_manglende_sats_hos_oss_rapporteres(self):
        tariff = {"fastledd": {"metode": "FEM_VEKTET_ÅR", "terskler": [{"terskel": 0, "pris": 2000}]}}
        assert sjekk.sammenlign_lineaer({}, tariff) is not None


class TestDeresMetode:
    """Metoden er en sats: bytter nettselskapet modell, skal vakten si det."""

    def test_leser_metoden(self):
        assert sjekk.deres_metode({"fastledd": {"metode": "MND_MAX"}}) == "MND_MAX"

    def test_manglende_fastledd_gir_tom_streng(self):
        assert sjekk.deres_metode({}) == ""


class TestVaareMetoderErISynk:
    """Hvert nettselskaps metode i dso.py skal matche fri-nettleies navn."""

    def test_metodenavn_er_identiske_med_fri_nettleie(self):
        """Navnene brukes som sammenligningsnøkkel, så de må være ordrett like.

        Verdiene er hentet fra fri-nettleies tariff.cue (#Fastledd.metode).
        """
        assert sjekk.FASTLEDD_OV_TREFASE == "OV_TREFASE"
        assert sjekk.FASTLEDD_FEM_VEKTET_AR == "FEM_VEKTET_ÅR"
        assert sjekk.FASTLEDD_UKJENT == "UKJENT"
        assert set(sjekk.FASTLEDD_TRINNBASERTE) == {"TRE_DØGNMAX_MND", "MND_MAX", "UKJENT"}


class TestSammenlignFastledd:
    """sammenlign_fastledd returnerer None ved match, ellers en forklaring."""

    TRINN: ClassVar = [(2.0, 150), (5.0, 250), (float("inf"), 420)]

    def test_identiske_lister_gir_none(self):
        assert sjekk.sammenlign_fastledd(list(self.TRINN), list(self.TRINN)) is None

    def test_en_krone_slack_tolereres(self):
        """dso.py og fri-nettleie kan avrunde ulikt uten at det er drift."""
        vaare = [(2.0, 151), (5.0, 249), (float("inf"), 420)]
        assert sjekk.sammenlign_fastledd(vaare, list(self.TRINN)) is None

    def test_prisavvik_over_toleranse_rapporteres(self):
        vaare = [(2.0, 125), (5.0, 250), (float("inf"), 420)]
        assert "125 vs 150" in sjekk.sammenlign_fastledd(vaare, list(self.TRINN))

    def test_grenseavvik_rapporteres(self):
        vaare = [(3.0, 150), (5.0, 250), (float("inf"), 420)]
        assert "grense" in sjekk.sammenlign_fastledd(vaare, list(self.TRINN))

    def test_kortere_liste_sammenlignes_kun_saa_langt_den_rekker(self):
        """Vi kollapser topptrinnene der DSO-en ikke publiserer dem for privat."""
        vaare = [(2.0, 150), (float("inf"), 250)]
        deres = [(2.0, 150), (5.0, 250), (10.0, 420), (float("inf"), 900)]
        assert sjekk.sammenlign_fastledd(vaare, deres) is None

    def test_flere_trinn_enn_fri_nettleie_rapporteres(self):
        vaare = [(2.0, 150), (5.0, 250), (10.0, 420), (float("inf"), 900)]
        deres = [(2.0, 150), (5.0, 250)]
        assert sjekk.sammenlign_fastledd(vaare, deres) is not None


class TestVaareTrinn:
    """vaare_trinn normaliserer begge lagringsformatene i dso.py."""

    def test_tuppelformat(self):
        entry = {"kapasitetstrinn": [(2, 150), (float("inf"), 250)]}
        assert sjekk.vaare_trinn(entry) == [(2.0, 150), (float("inf"), 250)]

    def test_dictformat(self):
        entry = {
            "kapasitetstrinn": [
                {"min": 0, "max": 2, "pris": 517},
                {"min": 2, "max": 999, "pris": 931},
            ]
        }
        assert sjekk.vaare_trinn(entry) == [(2.0, 517), (999.0, 931)]


class TestAktivTariff:
    """aktiv_tariff velger perioden som gjelder på datoen."""

    DATA: ClassVar = {
        "tariffer": [
            {
                "kundegrupper": ["husholdning"],
                "gyldig_fra": "2026-01-01",
                "gyldig_til": "2026-07-01",
                "id": "gammel",
            },
            {"kundegrupper": ["husholdning"], "gyldig_fra": "2026-07-01", "id": "ny"},
            {"kundegrupper": ["liten_næring"], "gyldig_fra": "2026-07-01", "id": "naering"},
        ]
    }

    def test_velger_gjeldende_periode(self):
        assert sjekk.aktiv_tariff(self.DATA, date(2026, 7, 28))["id"] == "ny"

    def test_gyldig_til_er_eksklusiv(self):
        """Byttedagen hører til den nye tariffen, ikke den gamle."""
        assert sjekk.aktiv_tariff(self.DATA, date(2026, 7, 1))["id"] == "ny"
        assert sjekk.aktiv_tariff(self.DATA, date(2026, 6, 30))["id"] == "gammel"

    def test_filtrerer_paa_kundegruppe(self):
        assert sjekk.aktiv_tariff(self.DATA, date(2026, 7, 28), "liten_næring")["id"] == "naering"

    def test_ingen_treff_gir_none(self):
        assert sjekk.aktiv_tariff(self.DATA, date(2020, 1, 1)) is None


def _fjellnett_yaml(grunnpris_ore: float = 14.8) -> dict:
    """fri-nettleie-fil som matcher vår Fjellnett-oppføring, med justerbart energiledd.

    Fjellnett er FEM_VEKTET_ÅR med 2000 + 589 kr/kW/år eks. mva og flat sats
    14,8 øre. Tersklene er funksjonen samplet på hele kW, slik fri-nettleie
    koder lineære fastledd.
    """
    return {
        "tariffer": [
            {
                "kundegrupper": ["husholdning"],
                "gyldig_fra": "2026-07-01",
                "energiledd": {"grunnpris": grunnpris_ore},
                "fastledd": {
                    "metode": "FEM_VEKTET_ÅR",
                    "terskler": [
                        {"terskel": 0, "pris": 2000},
                        {"terskel": 10, "pris": 2000 + 5890},
                    ],
                },
            }
        ]
    }


@pytest.fixture
def stub_nett(monkeypatch):
    """Bytt ut all nettverkstilgang i scriptet. Ingen test treffer GitHub."""

    def installer(yaml_per_slug: dict, slugs: list[str] | None = None):
        tilgjengelige = sorted(yaml_per_slug) if slugs is None else sorted(slugs)
        monkeypatch.setattr(sjekk, "list_remote_dsoer", lambda: tilgjengelige)
        monkeypatch.setattr(sjekk, "hent_yaml", lambda slug: yaml_per_slug.get(slug))

    return installer


class TestUtfallOgExitKode:
    """Tre utfall, tre exit-koder. Vakten skal si hva den ikke fikk sjekket."""

    ARGS: ClassVar = ["--dso", "fjellnett", "--bare-avvik", "--dato", "2026-09-12"]

    def test_alt_stemmer_gir_null(self, stub_nett):
        """Vakten skal tie når den skal tie. Ellers blir den slått av."""
        stub_nett({"fjellnett": _fjellnett_yaml()})
        assert sjekk.main(self.ARGS) == 0

    def test_injisert_energiledd_gir_avvik(self, stub_nett, capsys):
        """100 kr/kWh hos Fjellnett var grønt før: KJENTE_AVVIK dempet hele DSO-en."""
        stub_nett({"fjellnett": _fjellnett_yaml(grunnpris_ore=10000)})
        assert sjekk.main(self.ARGS) == 1
        assert "fjellnett" in capsys.readouterr().out

    def test_manglende_aktiv_tariff_gir_ufullstendig(self, stub_nett, capsys):
        data = _fjellnett_yaml()
        data["tariffer"][0]["kundegrupper"] = ["liten_næring"]
        stub_nett({"fjellnett": data})
        assert sjekk.main(self.ARGS) == 2
        assert "ingen aktiv tariff" in capsys.readouterr().out

    def test_manglende_energiledd_gir_ufullstendig(self, stub_nett, capsys):
        data = _fjellnett_yaml()
        del data["tariffer"][0]["energiledd"]
        stub_nett({"fjellnett": data})
        assert sjekk.main(self.ARGS) == 2
        assert "mangler energiledd" in capsys.readouterr().out

    def test_404_gir_ufullstendig(self, stub_nett, capsys):
        """Filen er listet, men borte. Før ble den talt og glemt."""
        stub_nett({}, slugs=["fjellnett"])
        assert sjekk.main(self.ARGS) == 2
        assert "404" in capsys.readouterr().out

    def test_ingen_match_gir_ufullstendig(self, stub_nett, capsys):
        stub_nett({}, slugs=[])
        assert sjekk.main(self.ARGS) == 2
        assert "ingen match" in capsys.readouterr().out

    def test_nettverksfeil_pa_en_dso_stopper_ikke_kjoringen(self, stub_nett, monkeypatch, capsys):
        stub_nett({"fjellnett": _fjellnett_yaml()})

        def feil(slug):
            raise OSError("connection reset")

        monkeypatch.setattr(sjekk, "hent_yaml", feil)
        assert sjekk.main(self.ARGS) == 2
        assert "henting feilet" in capsys.readouterr().out

    def test_ufullstendig_slar_avvik_i_exit_koden(self, stub_nett):
        """En kjøring som ikke vet hva den ikke sjekket, får ikke si «bare avvik»."""
        data = _fjellnett_yaml(grunnpris_ore=10000)
        del data["tariffer"][0]["fastledd"]
        stub_nett({"fjellnett": data, "bkk": _fjellnett_yaml()})
        assert sjekk.main(["--dso", "fjellnett", "--bare-avvik", "--dato", "2026-09-12"]) == 1
        stub_nett({}, slugs=[])
        assert sjekk.main(["--dso", "fjellnett,bkk", "--bare-avvik", "--dato", "2026-09-12"]) == 2


class TestFilterValidering:
    """--dso skal valideres mot DSO_LIST før vi bruker et nettkall på den."""

    def test_ukjent_dso_gir_to_og_melding(self, monkeypatch, capsys):
        def aldri():
            raise AssertionError("skal ikke røre nettverket ved ugyldig filter")

        monkeypatch.setattr(sjekk, "list_remote_dsoer", aldri)
        assert sjekk.main(["--dso", "bkkk"]) == 2
        assert "ukjent DSO-ID" in capsys.readouterr().err

    def test_custom_avvises(self):
        with pytest.raises(ValueError, match="custom"):
            sjekk.parse_filter("custom")

    def test_tomt_filter_avvises(self):
        with pytest.raises(ValueError):
            sjekk.parse_filter(" , ")

    def test_gyldig_filter_beholdes(self):
        assert sjekk.parse_filter("bkk, elvia") == {"bkk", "elvia"}

    def test_delvis_kjoring_merkes_i_json(self, stub_nett, tmp_path):
        stub_nett({"fjellnett": _fjellnett_yaml()})
        ut = tmp_path / "res.json"
        sjekk.main(["--dso", "fjellnett", "--bare-avvik", "--json-ut", str(ut)])
        data = json.loads(ut.read_text())
        assert data["fullstendig"] is False
        assert data["status"] == "verifisert"
        assert data["verifisert"] == ["fjellnett"]


def _funn(dso_id: str, felt: str, signatur: str, utfall=sjekk.Utfall.AVVIK) -> sjekk.Funn:
    return sjekk.Funn(dso_id, felt, signatur, f"[X] {dso_id} {felt} {signatur}", utfall)


class TestUnntak:
    """Unntak demper ett felt, med én signatur, fram til én dato."""

    I_DAG = date(2026, 9, 12)

    def _kjor(self, monkeypatch, unntak: sjekk.Unntak, funn: list[sjekk.Funn]):
        monkeypatch.setattr(sjekk, "KJENTE_AVVIK", {"testnett": (unntak,)})
        resultat = sjekk.Resultat("testnett", "testnett", funn)
        status = sjekk.anvend_unntak([resultat], self.I_DAG)
        return resultat, status

    def test_matchende_signatur_dempes(self, monkeypatch):
        unntak = sjekk.Unntak("dag", "20.00 vs 19.00 øre", date(2027, 1, 1), "venter på fri-nettleie")
        resultat, status = self._kjor(monkeypatch, unntak, [_funn("testnett", "dag", "20.00 vs 19.00 øre")])
        assert resultat.utfall is sjekk.Utfall.VERIFISERT
        assert resultat.dempet is True
        assert status.brukte == [("testnett", unntak)]

    def test_annen_verdi_i_samme_felt_dempes_ikke(self, monkeypatch):
        """Dette er Fjellnett-100-tilfellet: unntaket gjaldt et annet tall."""
        unntak = sjekk.Unntak("dag", "20.00 vs 19.00 øre", date(2027, 1, 1), "venter på fri-nettleie")
        resultat, status = self._kjor(
            monkeypatch, unntak, [_funn("testnett", "dag", "10000.00 vs 19.00 øre")]
        )
        assert resultat.utfall is sjekk.Utfall.AVVIK
        assert status.brukte == []

    def test_annet_felt_dempes_ikke(self, monkeypatch):
        unntak = sjekk.Unntak("natt", "9.00 vs 8.00 øre", date(2027, 1, 1), "venter på fri-nettleie")
        resultat, _ = self._kjor(
            monkeypatch,
            unntak,
            [_funn("testnett", "natt", "9.00 vs 8.00 øre"), _funn("testnett", "dag", "20.00 vs 19.00 øre")],
        )
        assert resultat.utfall is sjekk.Utfall.AVVIK

    def test_utlopt_unntak_demper_ikke(self, monkeypatch):
        unntak = sjekk.Unntak("dag", "20.00 vs 19.00 øre", date(2026, 9, 12), "utløper i dag")
        resultat, status = self._kjor(monkeypatch, unntak, [_funn("testnett", "dag", "20.00 vs 19.00 øre")])
        assert resultat.utfall is sjekk.Utfall.AVVIK
        assert status.utlopte == [("testnett", unntak)]

    def test_ubrukt_unntak_rapporteres_men_feller_ikke(self, monkeypatch):
        unntak = sjekk.Unntak("dag", "20.00 vs 19.00 øre", date(2027, 1, 1), "venter på fri-nettleie")
        resultat, status = self._kjor(monkeypatch, unntak, [])
        assert resultat.utfall is sjekk.Utfall.VERIFISERT
        assert status.ubrukte == [("testnett", unntak)]

    def test_utlopt_og_ubrukt_unntak_gir_ufullstendig(self, monkeypatch):
        """Slik kan listen ikke gro seg full av oppføringer ingen rydder."""
        unntak = sjekk.Unntak("dag", "20.00 vs 19.00 øre", date(2026, 1, 1), "glemt")
        resultat, status = self._kjor(monkeypatch, unntak, [])
        assert resultat.utfall is sjekk.Utfall.UFULLSTENDIG
        assert status.utlopte == [("testnett", unntak)]

    def test_unntak_utenfor_filteret_teller_verken_brukt_eller_ubrukt(self, monkeypatch):
        monkeypatch.setattr(
            sjekk,
            "KJENTE_AVVIK",
            {"testnett": (sjekk.Unntak("dag", "x", date(2026, 1, 1), "utløpt"),)},
        )
        status = sjekk.anvend_unntak([sjekk.Resultat("annet", "annet", [])], self.I_DAG)
        assert status.utlopte == [] and status.ubrukte == []


class TestKjenteAvvikListen:
    """Selve listen skal være typo-fri og ha en dato på hver oppføring."""

    FELT: ClassVar = {
        sjekk.FELT_DAG,
        sjekk.FELT_NATT,
        sjekk.FELT_FASTLEDD,
        sjekk.FELT_METODE,
        sjekk.FELT_MATCH,
        sjekk.FELT_HENTING,
        sjekk.FELT_TARIFF,
        sjekk.FELT_ENERGILEDD,
        sjekk.FELT_FASTLEDD_METODE_UKJENT,
    }

    def test_hver_oppforing_er_velformet(self):
        for dso_id, unntak_liste in sjekk.KJENTE_AVVIK.items():
            assert dso_id in sjekk.DSO_LIST, f"{dso_id} finnes ikke i DSO_LIST"
            for unntak in unntak_liste:
                assert unntak.felt in self.FELT, f"{dso_id}: ukjent felt {unntak.felt}"
                assert unntak.grunn.strip(), f"{dso_id}: unntak uten begrunnelse"
                assert isinstance(unntak.gyldig_til, date)
