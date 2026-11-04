"""Et dokumentert 50-75-trinn skal ikke prises som et åpent topptrinn."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from tests.conftest import _make_entry, _make_hass


@pytest.mark.parametrize("grunnlag,ukjent", [(74.999, False), (75, True), (75.001, True), (100, True)])
def test_nettselskapet_kildegrense_75(coord_module, grunnlag, ukjent):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="nettselskapet"))
    coord._daily_max_power = {
        f"2026-10-{dag:02}": coord_module.DailyMaxEntry(grunnlag, 12) for dag in (1, 2, 3)
    }
    assert coord._fastledd_ukjent() is ukjent
    assert coord._get_kapasitetsledd(grunnlag)[0] == (0 if ukjent else 3325)
    assert coord._fastledd_snapshot(coord._daily_max_power)["kjent_fastledd_maks_kw"] == 75
    assert not coord._fastledd_snapshot(coord._daily_max_power)["kjent_fastledd_maks_kw_inkludert"]
    snapshot = coord._fastledd_snapshot(coord._daily_max_power)
    belop, _ = coord._lukket_fastledd(snapshot, coord._daily_max_power, {})
    assert belop == (0 if ukjent else 3325)
    assert coord._previous_month_fastledd_grunnlag_bekreftet is not ukjent


def test_gammelt_snapshot_uten_grenseinklusjon_gjetter_ikke_75(coord_module):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="nettselskapet"))
    daily = {"2026-09-10": coord_module.DailyMaxEntry(75, 12)}
    snapshot = coord._fastledd_snapshot(daily)
    del snapshot["kjent_fastledd_maks_kw_inkludert"]
    coord._store.async_load = AsyncMock(
        return_value={
            "previous_month_fastledd_snapshot": snapshot,
            "previous_month_top_3": coord._serialize_daily_max(daily),
            "previous_month_fastledd_grunnlag_bekreftet": True,
        }
    )
    asyncio.run(coord._load_stored_data())
    assert not coord._previous_month_fastledd_snapshot["kjent_fastledd_maks_kw_inkludert"]
    assert not coord._previous_month_fastledd_grunnlag_bekreftet
