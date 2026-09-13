"""Kalendergrenser gjennom HAs planlagte polling og publiserte entiteter.

Klokken styres i UTC, mens HA bruker Europe/Oslo. Ingen coordinator-metoder
kalles direkte: tidshendelsene må selv utløse polling, bokføring og publisering.
Dette er kalenderbeviset komprimert Docker-avspilling ikke kan gi.
"""

from __future__ import annotations

from datetime import datetime

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.stromkalkulator.const import DOMAIN

ENERGY = "sensor.kalender_energi"
ENERGY_ATTRS = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}


async def _last(hass, *, energimaaler=True):
    await hass.config.async_update(time_zone="Europe/Oslo")
    hass.states.async_set("sensor.kalender_effekt", "6000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.kalender_spot", "0.8", {"unit_of_measurement": "NOK/kWh"})
    data = {
        "tso": "bkk",
        "boligtype": "bolig",
        "avgiftssone": "standard",
        "har_norgespris": True,
        "tariffmodus": "catalog",
        "power_sensor": "sensor.kalender_effekt",
        "spot_price_sensor": "sensor.kalender_spot",
        "spotpris_inkl_mva": False,
    }
    if energimaaler:
        hass.states.async_set(ENERGY, "1000", ENERGY_ATTRS)
        data["energy_sensor"] = ENERGY
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=data)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def _state(hass, entry, suffix):
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{suffix}")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    return state


async def _tid(hass, freezer, iso, *, kwh=None):
    tidspunkt = datetime.fromisoformat(iso)
    freezer.move_to(tidspunkt)
    if kwh is not None:
        hass.states.async_set(ENERGY, str(kwh), ENERGY_ATTRS)
    async_fire_time_changed(hass, tidspunkt)
    await hass.async_block_till_done()


async def test_forsinket_poll_deler_maaned_og_reload_bevarer_begge(hass, freezer):
    """En poll 00:05 fordeler 2 kWh likt rundt lokal midnatt; reload teller ikke om."""
    freezer.move_to("2026-06-30T21:55:00+00:00")  # 23:55 i Oslo, fortsatt juni i UTC.
    entry = await _last(hass)
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 0

    await _tid(hass, freezer, "2026-06-30T22:05:00+00:00", kwh=1002)
    assert dt_util.now().month == 7
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 1
    previous = _state(hass, entry, "forrige_maaned_forbruk_total")
    assert float(previous.state) == 1
    assert previous.attributes["maaned"] == "juni 2026"
    assert previous.attributes["dag_kwh"] == 0
    assert previous.attributes["natt_kwh"] == 1
    assert float(_state(hass, entry, "maanedlig_forbruk_natt").state) == 1

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 1
    assert float(_state(hass, entry, "forrige_maaned_forbruk_total").state) == 1
    await _tid(hass, freezer, "2026-06-30T22:06:00+00:00", kwh=1002.1)
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 1.1
    assert float(_state(hass, entry, "forrige_maaned_forbruk_total").state) == 1


@pytest.mark.parametrize(
    ("start", "etter", "neste", "lokal_time", "fold"),
    [
        ("2026-03-29T00:59:00+00:00", "2026-03-29T01:01:00+00:00", "2026-03-29T01:02:00+00:00", 3, 0),
        ("2026-10-25T00:59:00+00:00", "2026-10-25T01:01:00+00:00", "2026-10-25T01:02:00+00:00", 2, 1),
    ],
    ids=["vaartid_hopper_over_time", "hoesttid_gjentar_time"],
)
async def test_dst_poller_etter_absolutt_tid(hass, freezer, start, etter, neste, lokal_time, fold):
    """6 kW i to ekte minutter er 0,2 kWh selv om veggklokken hopper +62/-58 min."""
    freezer.move_to(start)
    entry = await _last(hass, energimaaler=False)
    await _tid(hass, freezer, etter)
    assert dt_util.now().hour == lokal_time
    assert dt_util.now().fold == fold
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 0.2
    assert float(_state(hass, entry, "maanedlig_forbruk_natt").state) == 0.2
    assert float(_state(hass, entry, "maanedlig_forbruk_dag").state) == 0

    # Neste planlagte poll må fortsatt kjøre, også i den gjentatte høsttimen.
    await _tid(hass, freezer, neste)
    assert float(_state(hass, entry, "maanedlig_forbruk_total").state) == 0.3
