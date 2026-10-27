"""Midtnetts FB22-fritidstariff velges uavhengig av støttevilkår."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from stromkalkulator.dso import DSO_LIST, hent_kapasitetstrinn

from tests.conftest import _make_entry, _make_hass


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


def test_glitre_orebelop_bevares_i_lagring_og_omstart(coord_module):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="glitre"))
    assert coord._get_kapasitetsledd(30)[0] == 2062.50
    coord._previous_month_kapasitetsledd = coord._get_kapasitetsledd(30)[0]
    asyncio.run(coord._save_stored_data())
    lagret = coord._store.async_save.call_args.args[0]
    ny = coord_module.NettleieCoordinator(coord.hass, coord.entry)
    ny._store.async_load = AsyncMock(return_value=lagret)
    asyncio.run(ny._load_stored_data())
    assert ny._previous_month_kapasitetsledd == 2062.50
