"""Tester for fastledd-metoder som ikke er snitt av tre døgnmakser.

NVE-modellen (`TRE_DØGNMAX_MND`) dekker 68 av 73 nettselskap. Fem gjør noe annet,
og for dem var beregningen vår feil uansett hvor riktige trinnprisene var. Se
[incident 006](../docs/incidents/006-kapasitetstrinn-uten-kilde.md) og
[begrensninger.md](../docs/begrensninger.md) punkt 9.

Metodenavnene er fri-nettleies, slik at drift-vakten kan sammenligne dem direkte.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from stromkalkulator.const import CONF_SIKRINGSTRINN, resolve_avgiftssone
from stromkalkulator.dso import (
    DSO_LIST,
    FASTLEDD_FEM_VEKTET_AR,
    FASTLEDD_METODER,
    FASTLEDD_MND_MAX,
    FASTLEDD_OV_TREFASE,
    FASTLEDD_TRE_DOGNMAX_MND,
    FASTLEDD_UKJENT,
    hent_fastledd_metode,
)

from tests.conftest import _make_entry, _make_hass, _run_update


def _last_init():
    """Last __init__ på nytt med rene ir-mocker.

    ir er en delt MagicMock i sys.modules (conftest), så call_args_list
    akkumulerer på tvers av tester uten dette. Samme mønster som test_satsvakt.
    """
    import stromkalkulator.__init__ as init_mod

    importlib.reload(init_mod)
    init_mod.ir.async_create_issue.reset_mock()
    init_mod.ir.async_delete_issue.reset_mock()
    return init_mod


def _lag_coordinator(coord_module, dso_id, *, extra_data=None):
    """Coordinator for et nettselskap, uten forbruk registrert ennå."""
    entry = _make_entry(
        dso_id=dso_id,
        avgiftssone=resolve_avgiftssone(DSO_LIST[dso_id]),
        extra_data=extra_data,
    )
    return coord_module.NettleieCoordinator(_make_hass(), entry)


class TestFastleddMetodeIDsoData:
    """dso.py skal bære metoden, og metode-spesifikke data skal henge sammen."""

    def test_alle_dsoer_har_gyldig_metode(self):
        for dso_id, data in DSO_LIST.items():
            metode = hent_fastledd_metode(data)
            assert metode in FASTLEDD_METODER, f"{dso_id}: ukjent fastledd-metode {metode!r}"

    def test_default_er_nve_modellen(self):
        """68 nettselskap skal oppføre seg helt som før, uten å nevne metoden."""
        assert hent_fastledd_metode(DSO_LIST["bkk"]) == FASTLEDD_TRE_DOGNMAX_MND
        assert "fastledd_metode" not in DSO_LIST["bkk"]

    @pytest.mark.parametrize(
        ("dso_id", "metode"),
        [
            ("alut", FASTLEDD_OV_TREFASE),
            ("netera", FASTLEDD_OV_TREFASE),
            ("fjellnett", FASTLEDD_FEM_VEKTET_AR),
            ("sor_aurdal_energi", FASTLEDD_MND_MAX),
            ("tinfos", FASTLEDD_UKJENT),
        ],
    )
    def test_de_fem_avvikende_er_merket(self, dso_id, metode):
        assert hent_fastledd_metode(DSO_LIST[dso_id]) == metode

    def test_sikringsbaserte_har_valgbare_trinn(self):
        for dso_id, data in DSO_LIST.items():
            if hent_fastledd_metode(data) != FASTLEDD_OV_TREFASE:
                continue
            trinn = data.get("fastledd_sikringstrinn")
            assert trinn, f"{dso_id}: OV_TREFASE krever fastledd_sikringstrinn"
            ider = [t["id"] for t in trinn]
            assert len(set(ider)) == len(ider), f"{dso_id}: duplikate trinn-id-er"
            for t in trinn:
                assert t["label"].strip(), f"{dso_id}: trinn {t['id']} mangler label"
                assert t["kr_mnd"] > 0, f"{dso_id}: trinn {t['id']} har ikke positiv pris"
            assert not data["kapasitetstrinn"], (
                f"{dso_id}: sikringsbasert fastledd har ingen kW-trinn, la listen stå tom"
            )

    def test_lineaere_har_sats_og_sesongfaktor(self):
        for dso_id, data in DSO_LIST.items():
            if hent_fastledd_metode(data) != FASTLEDD_FEM_VEKTET_AR:
                continue
            lineaer = data.get("fastledd_lineaer")
            assert lineaer, f"{dso_id}: FEM_VEKTET_ÅR krever fastledd_lineaer"
            assert lineaer["grunnbelop_aar_eks_mva"] > 0
            assert lineaer["sats_kw_aar_eks_mva"] > 0
            faktorer = data.get("fastledd_sesongfaktor")
            assert faktorer and set(faktorer) == set(range(1, 13)), (
                f"{dso_id}: sesongfaktor må dekke alle tolv månedene"
            )
            assert all(0 < v <= 1 for v in faktorer.values())
            assert not data["kapasitetstrinn"], (
                f"{dso_id}: lineært fastledd har ingen trinn, la listen stå tom"
            )

    def test_trinnbaserte_metoder_har_trinn(self):
        for dso_id, data in DSO_LIST.items():
            if hent_fastledd_metode(data) in (FASTLEDD_OV_TREFASE, FASTLEDD_FEM_VEKTET_AR):
                continue
            assert data["kapasitetstrinn"], f"{dso_id}: mangler kapasitetstrinn"

    def test_ingen_delte_fastledd_data(self):
        """Samme mal-symptom som incident 006, men for de trinnløse metodene.

        Trinnløse nettselskap slipper unna
        test_ingen_utilsiktet_delte_kapasitetstrinn fordi listene deres er tomme.
        Uten denne sjekken kunne to av dem fått samme kopierte prisliste.
        """
        sett: dict[tuple, set[str]] = {}
        for dso_id, data in DSO_LIST.items():
            metode = hent_fastledd_metode(data)
            if metode == FASTLEDD_OV_TREFASE:
                nokkel = tuple(sorted((t["label"], t["kr_mnd"]) for t in data["fastledd_sikringstrinn"]))
            elif metode == FASTLEDD_FEM_VEKTET_AR:
                lineaer = data["fastledd_lineaer"]
                nokkel = (
                    lineaer["grunnbelop_aar_eks_mva"],
                    lineaer["sats_kw_aar_eks_mva"],
                )
            else:
                continue
            sett.setdefault(nokkel, set()).add(dso_id)
        delt = [gruppe for gruppe in sett.values() if len(gruppe) > 1]
        assert not delt, f"Nettselskap deler fastledd-data uten begrunnelse: {delt}"


class TestMndMax:
    """Sør Aurdal fakturerer månedsmaksen, ikke snittet av tre døgnmakser.

    Kilde: sae.no "KUNDEINFORMASJON: Satser for nettleie fra 1.1.2026",
    "Fastledd fastsettes på bakgrunn av den timen i måneden du har høyest
    gjennomsnittlig forbruk (månedsmaksimal)".
    """

    def test_hoyeste_dogn_bestemmer_trinnet(self, coord_module):
        coord = _lag_coordinator(coord_module, "sor_aurdal_energi")
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=9.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=2.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=1.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        # Snitt av topp-3 er 4 kW (trinn 0-5, 563 kr). Månedsmaks 9 kW gir 8-15 kW.
        assert data["fastledd_grunnlag_kw"] == 9.0
        assert data["kapasitetsledd"] == 775

    def test_eksakt_grensetreff_hoerer_til_lavere_trinn(self, coord_module):
        """SAE skriver "fra 0 til og med 5 kW", så 5,0 kW er trinn 1."""
        coord = _lag_coordinator(coord_module, "sor_aurdal_energi")
        coord._daily_max_power = {"2026-06-01": coord_module.DailyMaxEntry(kw=5.0, hour=8)}
        data = _run_update(coord_module, coord)
        assert data["kapasitetsledd"] == 563

    def test_uten_maalinger_gir_laveste_trinn(self, coord_module):
        coord = _lag_coordinator(coord_module, "sor_aurdal_energi")
        data = _run_update(coord_module, coord)
        assert data["fastledd_grunnlag_kw"] == 0.0
        assert data["kapasitetsledd"] == 563


class TestOvTrefase:
    """Alut og Netera fakturerer etter sikringsstørrelse, ikke målt effekt."""

    def test_valgt_trinn_styrer_beloepet(self, coord_module):
        coord = _lag_coordinator(
            coord_module, "netera", extra_data={"sikringstrinn": "400v_40_80"}
        )
        coord._daily_max_power = {"2026-06-01": coord_module.DailyMaxEntry(kw=0.1, hour=8)}
        data = _run_update(coord_module, coord)
        # 8000 kr/år inkl. mva / 12 = 666,67 -> 667 kr/mnd, uavhengig av effekt.
        assert data["kapasitetsledd"] == 667
        assert data["fastledd_mangler_sikringsvalg"] is False

    def test_maalt_effekt_paavirker_ikke(self, coord_module):
        coord = _lag_coordinator(
            coord_module, "netera", extra_data={"sikringstrinn": "230v_0_10"}
        )
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=40.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=39.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=38.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        assert data["kapasitetsledd"] == 167

    def test_alut_trinn_fra_egen_prisliste(self, coord_module):
        coord = _lag_coordinator(
            coord_module, "alut", extra_data={"sikringstrinn": "inntil_3x125a"}
        )
        data = _run_update(coord_module, coord)
        # NO4 husholdning har mva-fritak: 3500 kr/år / 12 = 291,67 -> 292 kr/mnd.
        assert data["kapasitetsledd"] == 292

    def test_manglende_valg_gir_hoerbar_feil_ikke_gjetning(self, coord_module):
        """Uten sikringsstørrelse kan beløpet ikke utledes. Da skal det ikke gjettes."""
        coord = _lag_coordinator(coord_module, "alut")
        data = _run_update(coord_module, coord)
        assert data["fastledd_mangler_sikringsvalg"] is True
        assert data["kapasitetsledd"] == 0
        assert data["kapasitetstrinn_nummer"] is None

    def test_ugyldig_lagret_id_teller_som_manglende(self, coord_module):
        coord = _lag_coordinator(
            coord_module, "alut", extra_data={"sikringstrinn": "trinn_fra_et_annet_selskap"}
        )
        data = _run_update(coord_module, coord)
        assert data["fastledd_mangler_sikringsvalg"] is True

    def test_ingen_trinnvarsel_paa_sikringsbasert_fastledd(self, coord_module):
        """Fastleddet endrer seg ikke med forbruket, så et varsel er meningsløst."""
        coord = _lag_coordinator(
            coord_module, "netera", extra_data={"sikringstrinn": "230v_11_63"}
        )
        coord._daily_max_power = {"2026-06-01": coord_module.DailyMaxEntry(kw=9.9, hour=8)}
        data = _run_update(coord_module, coord)
        assert data["kapasitet_varsel"] is False
        assert data["margin_neste_trinn_kw"] == 0.0


class TestFemVektetAr:
    """Fjellnett bruker fem vektede ukestopper over løpende tolv måneder.

    Kilde: fjellnett.no/nettleie/nettleiepriser/ "Privatkunder fra 1.7.2026".
    """

    def _coord(self, coord_module):
        return _lag_coordinator(coord_module, "fjellnett")

    def test_ukesmaks_vektes_med_sesongfaktor(self, coord_module):
        coord = self._coord(coord_module)
        coord._weekly_max_power = {
            "2026-01-05": coord_module.WeeklyMaxEntry(kw=10.0, dato="2026-01-08", hour=8),
            "2026-06-08": coord_module.WeeklyMaxEntry(kw=10.0, dato="2026-06-10", hour=8),
        }
        # Januar vektes 100 %, juni 25 %. Snitt = (10,0 + 2,5) / 2 = 6,25.
        assert coord._fastledd_grunnlag() == pytest.approx(6.25)

    def test_snitt_av_de_fem_hoeyeste(self, coord_module):
        coord = self._coord(coord_module)
        mandager = ["01-05", "01-12", "01-19", "01-26", "02-02", "02-09", "02-16"]
        coord._weekly_max_power = {
            f"2026-{mandag}": coord_module.WeeklyMaxEntry(
                kw=float(kw), dato=f"2026-{mandag}", hour=8
            )
            for mandag, kw in zip(mandager, [9, 8, 7, 6, 5, 4, 3], strict=True)
        }
        # Januar og februar vektes 100 %, så snittet er (9+8+7+6+5)/5 = 7,0.
        assert coord._fastledd_grunnlag() == pytest.approx(7.0)

    def test_faerre_enn_fem_uker_bruker_det_som_finnes(self, coord_module):
        coord = self._coord(coord_module)
        coord._weekly_max_power = {
            "2026-01-05": coord_module.WeeklyMaxEntry(kw=6.0, dato="2026-01-08", hour=8),
            "2026-01-12": coord_module.WeeklyMaxEntry(kw=4.0, dato="2026-01-15", hour=8),
        }
        assert coord._fastledd_grunnlag() == pytest.approx(5.0)

    def test_kapasitetsledd_er_grunnbeloep_pluss_sats(self, coord_module):
        coord = self._coord(coord_module)
        coord._weekly_max_power = {
            "2026-01-05": coord_module.WeeklyMaxEntry(kw=4.0, dato="2026-01-08", hour=8),
        }
        data = _run_update(coord_module, coord)
        # (2000 + 589 * 4) kr/år eks. mva * 1,25 / 12 = 453,75 -> 454 kr/mnd.
        assert data["fastledd_grunnlag_kw"] == pytest.approx(4.0)
        assert data["kapasitetsledd"] == 454

    def test_uten_historikk_er_bare_grunnbeloepet_igjen(self, coord_module):
        coord = self._coord(coord_module)
        data = _run_update(coord_module, coord)
        # 2000 * 1,25 / 12 = 208,33 -> 208 kr/mnd.
        assert data["kapasitetsledd"] == 208

    def test_uker_eldre_enn_tolv_maaneder_faller_ut(self, coord_module):
        coord = self._coord(coord_module)
        coord._weekly_max_power = {
            "2024-12-30": coord_module.WeeklyMaxEntry(kw=20.0, dato="2025-01-02", hour=8),
            "2026-06-08": coord_module.WeeklyMaxEntry(kw=4.0, dato="2026-06-10", hour=8),
        }
        _run_update(coord_module, coord)
        assert "2024-12-30" not in coord._weekly_max_power

    def test_timesmaks_registreres_som_ukesmaks(self, coord_module):
        coord = self._coord(coord_module)
        coord._current_hour_energy = 3.5
        coord._current_hour = 11
        coord._current_date = "2026-06-15"
        _run_update(coord_module, coord, now=datetime(2026, 6, 15, 12, 0))
        uke = coord._weekly_max_power["2026-06-15"]
        assert uke.kw == pytest.approx(3.5)
        assert uke.dato == "2026-06-15"

    def test_ingen_trinnvarsel_uten_trinn(self, coord_module):
        coord = self._coord(coord_module)
        data = _run_update(coord_module, coord)
        assert data["kapasitet_varsel"] is False
        assert data["kapasitetstrinn_nummer"] is None


class TestUkjentMetode:
    """Tinfos publiserer ikke tariffen sin. Da skal vi si det, ikke gjette."""

    def test_regner_som_nve_modellen_men_flagges(self, coord_module):
        coord = _lag_coordinator(coord_module, "tinfos")
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=6.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=6.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=6.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        assert data["fastledd_metode"] == FASTLEDD_UKJENT
        assert data["fastledd_grunnlag_kw"] == pytest.approx(6.0)
        assert data["kapasitetsledd"] == 516


class TestBaklengskompatibilitet:
    """De 68 andre nettselskapene skal oppføre seg helt uendret."""

    def test_bkk_bruker_snitt_av_topp_tre(self, coord_module):
        coord = _lag_coordinator(coord_module, "bkk")
        coord._daily_max_power = {
            "2026-06-01": coord_module.DailyMaxEntry(kw=9.0, hour=8),
            "2026-06-02": coord_module.DailyMaxEntry(kw=2.0, hour=8),
            "2026-06-03": coord_module.DailyMaxEntry(kw=1.0, hour=8),
        }
        data = _run_update(coord_module, coord)
        assert data["fastledd_metode"] == FASTLEDD_TRE_DOGNMAX_MND
        assert data["fastledd_grunnlag_kw"] == pytest.approx(4.0)
        assert data["avg_top_3_kw"] == pytest.approx(4.0)
        assert data["kapasitetsledd"] == 250

    def test_ingen_ukesmaks_lagres_for_vanlige_dsoer(self, coord_module):
        """Ukeshistorikk er bare Fjellnetts behov og skal ikke vokse hos andre."""
        coord = _lag_coordinator(coord_module, "bkk")
        coord._current_hour_energy = 3.5
        coord._current_hour = 11
        coord._current_date = "2026-06-15"
        _run_update(coord_module, coord, now=datetime(2026, 6, 15, 12, 0))
        assert coord._weekly_max_power == {}


class TestMaanedsskifte:
    """Forrige måneds kapasitetsledd skal arkiveres med DSO-ens egen metode."""

    def test_mnd_max_arkiverer_maanedsmaks(self, coord_module):
        coord = _lag_coordinator(coord_module, "sor_aurdal_energi")
        coord._current_month = "2026-05"
        coord._daily_max_power = {
            "2026-05-01": coord_module.DailyMaxEntry(kw=9.0, hour=8),
            "2026-05-02": coord_module.DailyMaxEntry(kw=2.0, hour=8),
            "2026-05-03": coord_module.DailyMaxEntry(kw=1.0, hour=8),
        }
        _run_update(coord_module, coord, now=datetime(2026, 6, 1, 0, 30))
        assert coord._previous_month_kapasitetsledd == 775

    def test_fem_vektet_beholder_ukeshistorikk_over_maanedsskifte(self, coord_module):
        coord = _lag_coordinator(coord_module, "fjellnett")
        coord._current_month = "2026-05"
        coord._weekly_max_power = {
            "2026-05-04": coord_module.WeeklyMaxEntry(kw=8.0, dato="2026-05-06", hour=8),
        }
        _run_update(coord_module, coord, now=datetime(2026, 6, 1, 0, 30))
        assert "2026-05-04" in coord._weekly_max_power


class TestUkesmaksPersistens:
    """Tolv måneders ukeshistorikk må overleve omstart, ellers nullstilles den."""

    def test_lagres_og_leses_tilbake(self, coord_module):
        coord = _lag_coordinator(coord_module, "fjellnett")
        coord._weekly_max_power = {
            "2026-01-05": coord_module.WeeklyMaxEntry(kw=7.5, dato="2026-01-08", hour=17),
        }
        lagret = {}
        coord._store.async_save.side_effect = lambda data: lagret.update(data)
        asyncio.run(coord._save_stored_data())
        assert lagret["weekly_max_power"] == {
            "2026-01-05": {"kw": 7.5, "dato": "2026-01-08", "hour": 17}
        }

        ny = _lag_coordinator(coord_module, "fjellnett")
        ny._store.async_load.return_value = lagret
        asyncio.run(ny._load_stored_data())
        assert ny._weekly_max_power["2026-01-05"].kw == pytest.approx(7.5)
        assert ny._weekly_max_power["2026-01-05"].dato == "2026-01-08"

    @pytest.mark.parametrize(
        "post",
        [
            {"kw": 5.0},  # mangler dato, og dato bærer sesongvekten
            {"kw": 5.0, "dato": "ikke-en-dato"},
            {"kw": "tekst", "dato": "2026-01-08"},
            {"kw": -1.0, "dato": "2026-01-08"},
            "ikke et dict",
        ],
    )
    def test_ubrukelige_poster_forkastes(self, coord_module, post):
        assert coord_module.NettleieCoordinator._validate_weekly_max_power({"x": post}) == {}

    def test_ugyldig_time_nullstilles_men_posten_beholdes(self, coord_module):
        resultat = coord_module.NettleieCoordinator._validate_weekly_max_power(
            {"2026-01-05": {"kw": 5.0, "dato": "2026-01-08", "hour": 99}}
        )
        assert resultat["2026-01-05"].hour is None


class TestBrukereFraFoerFeltetFantes:
    """Alut- og Netera-brukere som lå der før sikringsfeltet fantes.

    Config-entryet deres har ingen `sikringstrinn`-nøkkel. Da skal integrasjonen
    laste som normalt, vise Ukjent i stedet for et gjettet beløp, og varsle via
    Repairs. Ingen skjemaversjon endres, så ingen migrering kan feile.
    """

    def test_entry_uten_noekkelen_laster(self, coord_module):
        coord = _lag_coordinator(coord_module, "alut")
        assert CONF_SIKRINGSTRINN not in coord.entry.data
        assert coord.sikringstrinn_valg is None
        data = _run_update(coord_module, coord)
        assert data["fastledd_mangler_sikringsvalg"] is True

    def test_tom_streng_teller_som_ikke_valgt(self, coord_module):
        coord = _lag_coordinator(coord_module, "alut", extra_data={"sikringstrinn": ""})
        assert coord.sikringstrinn_valg is None

    def test_repair_varsel_naar_valget_mangler(self):
        init_mod = _last_init()
        init_mod._check_sikringstrinn(MagicMock(), _make_entry(dso_id="alut"))
        assert any(
            call.args[2].startswith("sikringstrinn_mangler")
            for call in init_mod.ir.async_create_issue.call_args_list
        )

    def test_ingen_varsel_naar_valget_finnes(self):
        init_mod = _last_init()
        init_mod._check_sikringstrinn(
            MagicMock(), _make_entry(dso_id="alut", extra_data={"sikringstrinn": "over_3x125a"})
        )
        assert not init_mod.ir.async_create_issue.call_args_list
        assert any(
            call.args[2].startswith("sikringstrinn_mangler")
            for call in init_mod.ir.async_delete_issue.call_args_list
        )

    def test_ingen_varsel_for_vanlig_nettselskap(self):
        init_mod = _last_init()
        init_mod._check_sikringstrinn(MagicMock(), _make_entry(dso_id="bkk"))
        assert not init_mod.ir.async_create_issue.call_args_list


class TestKapasitetstrinnSensor:
    """Sensoren skal stå som Ukjent framfor å vise et gjettet beløp."""

    def _sensor(self, data):
        from stromkalkulator.sensor import KapasitetstrinnSensor

        coordinator = MagicMock()
        coordinator.data = data
        return KapasitetstrinnSensor(coordinator, _make_entry())

    def test_ukjent_naar_sikringsvalg_mangler(self):
        sensor = self._sensor(
            {"kapasitetsledd": 0, "fastledd_mangler_sikringsvalg": True}
        )
        assert sensor.native_value is None
        assert sensor.extra_state_attributes["mangler_sikringsstorrelse"] is True

    def test_viser_beloepet_naar_valget_finnes(self):
        sensor = self._sensor(
            {
                "kapasitetsledd": 292,
                "fastledd_mangler_sikringsvalg": False,
                "fastledd_metode": FASTLEDD_OV_TREFASE,
            }
        )
        assert sensor.native_value == 292
        assert "mangler_sikringsstorrelse" not in sensor.extra_state_attributes

    def test_uverifisert_metode_flagges(self):
        sensor = self._sensor(
            {"kapasitetsledd": 516, "fastledd_metode": FASTLEDD_UKJENT}
        )
        assert sensor.extra_state_attributes["metode_uverifisert"] is True

    def test_vanlig_dso_har_ingen_ekstra_flagg(self):
        sensor = self._sensor(
            {"kapasitetsledd": 250, "fastledd_metode": FASTLEDD_TRE_DOGNMAX_MND}
        )
        attrs = sensor.extra_state_attributes
        assert "metode_uverifisert" not in attrs
        assert "mangler_sikringsstorrelse" not in attrs
        assert attrs["fastledd_metode"] == FASTLEDD_TRE_DOGNMAX_MND
