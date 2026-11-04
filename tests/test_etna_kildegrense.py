"""Etna har kildebekreftet husholdningsfastledd bare til og med 25 kW."""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from tests.conftest import _make_entry, _make_hass, _run_update
from tests.test_lukket_maned_fastledd import _oppsett, _poll


@pytest.mark.parametrize("grunnlag,ukjent", [(25, False), (25.001, True), (40, True)])
def test_kildegrensen_bruker_fakturagrunnlaget(coord_module, grunnlag, ukjent):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="etna_nett"))
    coord._daily_max_power = {
        f"2026-06-{dag:02}": coord_module.DailyMaxEntry(grunnlag, 12) for dag in (10, 11, 12)
    }
    assert coord._fastledd_ukjent() is ukjent
    assert coord._get_kapasitetsledd(grunnlag)[0] == (0 if ukjent else 1269.2)


def test_enkelthoy_time_sperrer_ikke_gyldig_topptre(coord_module):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="etna_nett"))
    coord._daily_max_power = {
        "2026-06-10": coord_module.DailyMaxEntry(35, 12),
        "2026-06-11": coord_module.DailyMaxEntry(20, 12),
        "2026-06-12": coord_module.DailyMaxEntry(20, 12),
    }
    assert coord._fastledd_grunnlag() == 25
    assert not coord._fastledd_ukjent()


def test_ukjent_flagg_publiseres_og_custom_har_ingen_kataloggrense(coord_module):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="etna_nett"))
    coord._store_loaded = True
    coord._current_month = "2026-06"
    coord._daily_max_power = {"2026-06-10": coord_module.DailyMaxEntry(26, 12)}
    data = _run_update(coord_module, coord, now=datetime(2026, 6, 20, 12))
    assert data["fastledd_ukjent"]
    coord._daily_max_power.clear()
    data = _run_update(coord_module, coord, now=datetime(2026, 6, 20, 12, 1))
    assert not data["fastledd_ukjent"]
    custom = coord_module.NettleieCoordinator(
        _make_hass(),
        _make_entry(dso_id="custom", extra_data={"egendefinert_kapasitetstrinn": "25:100,50:200"}),
    )
    assert custom._get_kapasitetsledd(40)[0] == 200


@pytest.mark.parametrize("restart", [False, True])
def test_sen_hale_over_kildegrensen_gjor_lukket_maaned_ukjent(coord_module, restart):
    coord, states = _oppsett(coord_module, "etna_nett")
    coord._daily_max_power = {
        "2026-06-10": coord_module.DailyMaxEntry(25, 12),
        "2026-06-11": coord_module.DailyMaxEntry(25, 12),
    }
    _poll(coord_module, coord, states, "2026-06-30T23:00:00+02:00", 100)
    _poll(coord_module, coord, states, "2026-06-30T23:50:00+02:00", 121)
    _poll(coord_module, coord, states, "2026-07-01T00:01:00+02:00", "unavailable")
    assert coord._previous_month_fastledd_snapshot["kjent_fastledd_maks_kw"] == 25
    if restart:
        asyncio.run(coord._save_stored_data())
        lagret = json.loads(json.dumps(coord._store.async_save.call_args.args[0], allow_nan=False))
        ny = coord_module.NettleieCoordinator(coord.hass, coord.entry)
        ny._store.async_load = AsyncMock(return_value=lagret)
        coord = ny
    data = _poll(coord_module, coord, states, "2026-07-01T00:05:00+02:00", 127.9)
    assert not data["previous_month_fastledd_grunnlag_bekreftet"]
    assert data["previous_month_cost_kr"] is None
    assert data["previous_month_net_cost_kr"] is None
    assert data["previous_month_kapasitetsledd"] is None
    assert not data["fastledd_ukjent"]  # Ny måned har eget, gyldig grunnlag.


def test_gammelt_lukket_aapent_trinn_blir_ukjent_uten_ny_avlesning(coord_module):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="etna_nett"))
    coord._store.async_load = AsyncMock(
        return_value={
            "previous_month_name": "Mai",
            "previous_month_kapasitetsledd": 1269.2,
            "previous_month_top_3": {"2026-05-10": {"kw": 26, "hour": 12}},
            "previous_month_cost": 2000,
        }
    )
    asyncio.run(coord._load_stored_data())
    assert not coord._previous_month_fastledd_grunnlag_bekreftet
    assert coord._previous_month_kapasitetsledd == 1269.2
