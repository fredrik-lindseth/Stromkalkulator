"""Én fastleddregel for åpen måned, lukket måned og lasting.

Regelen sto tidligere i tre kopier i coordinatoren: grunnlaget (maks eller
snitt av topp-3) og kildegrensen («over grensen, eller på grensen når den
ikke er inkludert») var skrevet på nytt for inneværende måned, for en lukket
måned som får en sen hale, og for lasting av et lukket grunnlag. Testene her
låser at de tre veiene gir samme svar for samme tariff og topper.
"""

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest
from stromkalkulator.dso import (
    FASTLEDD_FEM_VEKTET_AR,
    FASTLEDD_MND_MAX,
    FASTLEDD_TRE_DOGNMAX_MND,
)
from stromkalkulator.fastledd import (
    FASTLEDD_UKJENT_TEKST,
    Fastleddtariff,
    fastledd_for_grunnlag,
    fastledd_grunnlag,
    fastledd_ukjent,
    utenfor_kildegrense,
)

from tests.conftest import _make_entry, _make_hass, _run_update

TRINN = ((2.0, 100.0), (5.0, 200.0), (float("inf"), 300.0))


@pytest.mark.parametrize(
    "metode,forventet",
    [(FASTLEDD_TRE_DOGNMAX_MND, 4.0), (FASTLEDD_MND_MAX, 5.0)],
)
def test_grunnlaget_er_snitt_eller_maks_av_doegnmaks(metode, forventet):
    tariff = Fastleddtariff(metode=metode, mva_sats=0.25, trinn=TRINN)
    assert fastledd_grunnlag(tariff, [3.0, 1.0, 5.0, 4.0], ()) == forventet


def test_grunnlaget_uten_maalinger_er_null():
    tariff = Fastleddtariff(metode=FASTLEDD_TRE_DOGNMAX_MND, mva_sats=0.25, trinn=TRINN)
    assert fastledd_grunnlag(tariff, [], ()) == 0.0


def test_fem_vektet_vekter_med_mandagens_maaned():
    # 2026-03-31 er en tirsdag i uken som starter mandag 30. mars.
    tariff = Fastleddtariff(metode=FASTLEDD_FEM_VEKTET_AR, mva_sats=0.25, sesongfaktor={3: 0.5, 4: 1.0})
    assert fastledd_grunnlag(tariff, [99.0], [(8.0, "2026-03-31"), (6.0, "2026-04-07")]) == 5.0


@pytest.mark.parametrize(
    "grunnlag,inkludert,utenfor",
    [(24.999, True, False), (25.0, True, False), (25.0, False, True), (25.001, True, True)],
)
def test_kildegrensen(grunnlag, inkludert, utenfor):
    tariff = Fastleddtariff(
        metode=FASTLEDD_TRE_DOGNMAX_MND,
        mva_sats=0.25,
        trinn=TRINN,
        kildegrense_kw=25.0,
        kildegrense_inkludert=inkludert,
    )
    assert utenfor_kildegrense(tariff, grunnlag) is utenfor
    assert fastledd_ukjent(tariff, grunnlag) is utenfor
    assert fastledd_for_grunnlag(tariff, grunnlag)[2] == (FASTLEDD_UKJENT_TEKST if utenfor else ">5 kW")


@pytest.mark.parametrize("dso_id", ["bkk", "etna_nett", "nettselskapet", "fjellnett", "sor_aurdal_energi"])
def test_snapshot_rundtur_gir_samme_beloep(coord_module, dso_id):
    """Tariffen som fryses ved månedsslutt regner likt etter JSON og omstart."""
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id=dso_id))
    levende = coord._fastleddtariff()
    lagret = Fastleddtariff.fra_snapshot(json.loads(json.dumps(levende.til_snapshot(), allow_nan=False)))
    for kw in (0.0, 1.9, 2.0, 4.99, 5.0, 20.0, 25.0, 25.001, 74.999, 75.0, 120.0):
        assert fastledd_for_grunnlag(lagret, kw) == fastledd_for_grunnlag(levende, kw), kw


@pytest.mark.parametrize(
    "dso_id,topper",
    [
        ("etna_nett", (25.0, 25.0, 25.0)),
        ("etna_nett", (26.0, 25.0, 24.5)),
        ("nettselskapet", (75.0, 75.0, 75.0)),
        ("nettselskapet", (80.0, 70.0, 74.0)),
        ("bkk", (6.0, 4.0, 3.0)),
    ],
)
def test_aapen_lukket_og_lastet_maaned_er_enige(coord_module, dso_id, topper):
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id=dso_id))
    daily = {f"2026-09-{dag:02}": coord_module.DailyMaxEntry(kw, 12) for dag, kw in enumerate(topper, 1)}
    coord._daily_max_power = dict(daily)

    aapen_belop, _, aapen_tekst = coord._get_kapasitetsledd(coord._fastledd_grunnlag())
    aapen_ukjent = coord._fastledd_ukjent()

    snapshot = coord._fastledd_snapshot(daily)
    lukket_belop, lukket_tekst = coord._lukket_fastledd(snapshot, daily, {})
    assert (lukket_belop, lukket_tekst) == (aapen_belop, aapen_tekst)
    assert coord._previous_month_fastledd_grunnlag_bekreftet is not aapen_ukjent

    lastet = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id=dso_id))
    lastet._store.async_load = AsyncMock(
        return_value={
            "previous_month_fastledd_snapshot": snapshot,
            "previous_month_top_3": coord._serialize_daily_max(daily),
            "previous_month_fastledd_grunnlag_bekreftet": True,
        }
    )
    asyncio.run(lastet._load_stored_data())
    assert lastet._previous_month_fastledd_grunnlag_bekreftet is not aapen_ukjent


def test_grunnlaget_regnes_en_gang_per_poll(coord_module, monkeypatch):
    """Grunnlaget sorterer alle døgnmaks, så det sendes videre i stedet for å regnes om."""
    kall = []
    ekte = coord_module.fastledd_grunnlag

    def tell(*args, **kwargs):
        kall.append(1)
        return ekte(*args, **kwargs)

    monkeypatch.setattr(coord_module, "fastledd_grunnlag", tell)
    coord = coord_module.NettleieCoordinator(_make_hass(), _make_entry(dso_id="bkk"))
    coord._store_loaded = True
    coord._current_month = "2026-06"
    _run_update(coord_module, coord, now=datetime(2026, 6, 20, 12))
    assert len(kall) == 1
