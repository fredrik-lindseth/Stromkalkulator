"""Midtnetts FB22-fritidstariff velges og arkiveres uavhengig av støttevilkår."""

import asyncio
import json
from unittest.mock import AsyncMock

import pytest
from stromkalkulator.dso import DSO_LIST, hent_kapasitetstrinn

from tests.conftest import _make_entry, _make_hass
from tests.test_lukket_maned_fastledd import _lukk_med_hale_som_mangler, _oppsett, _poll


@pytest.mark.parametrize(
    "boligtype,pris", [("bolig", 275), ("fritidsbolig", 330), ("fritidsbolig_fast", 330)]
)
def test_entry_velger_kundens_faktiske_trinn(coord_module, boligtype, pris):
    coord = coord_module.NettleieCoordinator(
        _make_hass(), _make_entry(dso_id="midtnett", extra_data={"boligtype": boligtype})
    )
    assert coord._get_kapasitetsledd(4.9)[0] == pris


def test_fritidstabell_fra_offisiell_fb22():
    assert hent_kapasitetstrinn(DSO_LIST["midtnett"], "fritidsbolig") == [
        (5, 330),
        (10, 495),
        (15, 750),
        (20, 1125),
        (25, 1500),
        (50, 2096),
        (75, 3144),
        (100, 3900),
        (float("inf"), 4500),
    ]
    for boligtype in ("bolig", "fritidsbolig", "fritidsbolig_fast", "ukjent"):
        assert hent_kapasitetstrinn(DSO_LIST["bkk"], boligtype) == DSO_LIST["bkk"]["kapasitetstrinn"]


@pytest.mark.parametrize(
    "foer,etter,ny_pris", [("fritidsbolig", "bolig", 275), ("bolig", "fritidsbolig", 330)]
)
def test_options_omlast_velger_nye_trinn(coord_module, foer, etter, ny_pris):
    entry = _make_entry(dso_id="midtnett", extra_data={"boligtype": foer})
    gammel = coord_module.NettleieCoordinator(_make_hass(), entry)
    entry.data = {**entry.data, "boligtype": etter}
    ny = coord_module.NettleieCoordinator(gammel.hass, entry)
    assert ny._get_kapasitetsledd(4.9)[0] == ny_pris
    assert gammel.kapasitetstrinn != ny.kapasitetstrinn


def test_lukket_fritidsmaaned_beholder_fb22_etter_options_og_restart(coord_module):
    coord, states = _oppsett(coord_module, "midtnett")
    entry = coord.entry
    entry.data = {**entry.data, "boligtype": "fritidsbolig"}
    fritid = coord_module.NettleieCoordinator(coord.hass, entry)
    fritid._current_month = coord._current_month
    fritid._store_loaded = True
    fritid._daily_max_power = coord._daily_max_power
    _lukk_med_hale_som_mangler(coord_module, fritid, states)
    asyncio.run(fritid._save_stored_data())
    lagret = json.loads(json.dumps(fritid._store.async_save.call_args.args[0], allow_nan=False))
    entry.data = {**entry.data, "boligtype": "bolig"}
    ny = coord_module.NettleieCoordinator(coord.hass, entry)
    ny._store.async_load = AsyncMock(return_value=lagret)
    result = _poll(coord_module, ny, states, "2026-07-01T00:05:00+02:00", 106.9)
    assert ny._get_kapasitetsledd(5.2)[0] == 413
    # (4.8 + 4.8 + 6) / 3 = 5.2 kW: den lukkede måneden bruker FB22.
    assert result["previous_month_kapasitetsledd"] == 495
    assert ny._previous_month_fastledd_snapshot["trinn"][0][1] == 330
