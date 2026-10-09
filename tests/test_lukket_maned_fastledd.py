"""En sen målerhale retter forrige fakturamåned, også etter omstart."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from stromkalkulator.dso import FASTLEDD_FEM_VEKTET_AR, FASTLEDD_MND_MAX

from tests.conftest import _make_entry, _make_hass, _make_state, _run_update

OSLO = ZoneInfo("Europe/Oslo")


def _oppsett(coord_module, dso="bkk"):
    states = {
        "sensor.power": _make_state(0, "W"),
        "sensor.spot_price": _make_state(1, "NOK/kWh"),
    }
    entry = _make_entry(
        dso_id=dso, energy_sensor="sensor.energy", extra_data={"sikringstrinn": "inntil_3x125a"}
    )
    hass = _make_hass()
    hass.states.get.side_effect = states.get
    coord = coord_module.NettleieCoordinator(hass, entry)
    coord._current_month = "2026-06"
    coord._store_loaded = True
    coord._daily_max_power = {
        "2026-06-10": coord_module.DailyMaxEntry(4.8, 12),
        "2026-06-11": coord_module.DailyMaxEntry(4.8, 13),
    }
    return coord, states


def _poll(coord_module, coord, states, iso, energy):
    now = datetime.fromisoformat(iso).astimezone(OSLO)
    states["sensor.energy"] = _make_state(energy, "kWh", last_updated=now)
    return _run_update(coord_module, coord, now=now)


def _lukk_med_hale_som_mangler(coord_module, coord, states):
    _poll(coord_module, coord, states, "2026-06-30T23:00:00+02:00", 100)
    _poll(coord_module, coord, states, "2026-06-30T23:50:00+02:00", 104.2)
    return _poll(coord_module, coord, states, "2026-07-01T00:01:00+02:00", "unavailable")


@pytest.mark.parametrize("restart", [False, True])
def test_sen_avlesning_retter_topper_fastledd_og_total_uten_junitopper_i_juli(coord_module, restart):
    coord, states = _oppsett(coord_module)
    foer = _lukk_med_hale_som_mangler(coord_module, coord, states)
    assert foer["previous_month_kapasitetsledd"] == 250
    assert foer["previous_month_top_3"]["2026-06-30"].kw == pytest.approx(4.2)
    if restart:
        asyncio.run(coord._save_stored_data())
        lagret = json.loads(json.dumps(coord._store.async_save.call_args.args[0], allow_nan=False))
        ny = coord_module.NettleieCoordinator(coord.hass, coord.entry)
        ny._store.async_load = AsyncMock(return_value=lagret)
        coord = ny
    etter = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 106.9)
    assert etter["previous_month_top_3"]["2026-06-30"].kw == pytest.approx(6)
    assert etter["previous_month_top_3"]["2026-06-30"].hour == 23
    assert etter["previous_month_kapasitetsledd"] == 415
    assert etter["previous_month_cost_kr"] - foer["previous_month_cost_kr"] >= 165
    assert etter["previous_month_consumption_total_kwh"] == pytest.approx(6)
    assert etter["monthly_consumption_total_kwh"] == pytest.approx(0.9)
    assert not coord._daily_max_power
    assert not etter["top_3_days"]
    # Samme avlesning på nytt må ikke legge på fastledd eller energi igjen.
    igjen = _poll(coord_module, coord, states, "2026-07-01T00:06:00+02:00", 106.9)
    assert igjen["previous_month_cost_kr"] == etter["previous_month_cost_kr"]
    assert igjen["previous_month_consumption_total_kwh"] == etter["previous_month_consumption_total_kwh"]


@pytest.mark.parametrize("dso", ["sor_aurdal_energi", "alut", "tinfos", "custom"])
def test_metodene_beholder_sitt_eget_fastledd_ved_sen_hale(coord_module, dso):
    coord, states = _oppsett(coord_module, dso)
    foer = _lukk_med_hale_som_mangler(coord_module, coord, states)
    etter = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 106.9)
    if coord.fastledd_metode == FASTLEDD_MND_MAX:
        assert etter["previous_month_kapasitetsledd"] == coord._get_kapasitetsledd(6)[0]
    elif dso == "tinfos":
        assert etter["previous_month_kapasitetsledd"] == coord._get_kapasitetsledd(5.2)[0]
    else:
        assert etter["previous_month_kapasitetsledd"] == foer["previous_month_kapasitetsledd"]
    assert etter["previous_month_top_3"]["2026-06-30"].kw == pytest.approx(6)
    assert not coord._daily_max_power


def test_arkiverte_trinnpriser_endres_ikke_med_nye_options(coord_module):
    coord, states = _oppsett(coord_module)
    _lukk_med_hale_som_mangler(coord_module, coord, states)
    coord.kapasitetstrinn = [(10, 999), (float("inf"), 1999)]
    coord.fastledd_metode = FASTLEDD_MND_MAX
    etter = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 106.9)
    assert etter["previous_month_kapasitetsledd"] == 415
    assert coord._previous_month_fastledd_snapshot["metode"] != coord.fastledd_metode


def test_fem_aarsuker_fryses_og_samme_uke_i_juli_blander_ikke_juni(coord_module):
    coord, states = _oppsett(coord_module, "fjellnett")
    assert coord.fastledd_metode == FASTLEDD_FEM_VEKTET_AR
    foer = _lukk_med_hale_som_mangler(coord_module, coord, states)
    # Ny måned har senere fått en større topp i samme lokale uke. Den må
    # ikke få gjøre juni dyrere når siste juniavlesning etterbokføres.
    coord._registrer_ukesmaks("2026-07-01", 20, 12)
    original_lineaer = dict(coord.fastledd_lineaer)
    coord.fastledd_lineaer = {"grunnbelop_aar_eks_mva": 9999, "sats_kw_aar_eks_mva": 9999}
    etter = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 106.9)
    snapshot = coord._previous_month_fastledd_snapshot
    assert snapshot["weekly_max"]["2026-06-29"]["kw"] == pytest.approx(6)
    assert coord._weekly_max_power["2026-06-29"].kw == 20
    assert snapshot["lineaer"] == original_lineaer
    assert etter["previous_month_kapasitetstrinn"] == "1.50 kW vektet årstopp"
    assert etter["previous_month_kapasitetsledd"] > foer["previous_month_kapasitetsledd"]
    assert not coord._daily_max_power


def test_eldre_topptre_fungerer_men_manglende_aarsuker_gjettes_ikke(coord_module):
    for dso in ("bkk", "fjellnett"):
        coord, states = _oppsett(coord_module, dso)
        foer = _lukk_med_hale_som_mangler(coord_module, coord, states)
        coord._previous_month_fastledd_snapshot = None
        etter = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 106.9)
        assert etter["previous_month_top_3"]["2026-06-30"].kw == pytest.approx(6)
        if dso == "bkk":
            assert etter["previous_month_kapasitetsledd"] == 415
        else:
            assert etter["previous_month_kapasitetsledd"] == foer["previous_month_kapasitetsledd"]
            assert not etter["previous_month_fastledd_grunnlag_bekreftet"]


@pytest.mark.parametrize("raw", [None, [], {"metode": "FEM_VEKTET_ÅR"}, {"metode": 1, "trinn": []}])
def test_skadet_snapshot_blir_ikke_et_nytt_prisgrunnlag(coord_module, raw):
    coord, _ = _oppsett(coord_module)
    assert coord._les_fastledd_snapshot(raw) is None
