"""To anlegg hos samme nettselskap gjennom HAs registre, lagring og reload.

Incident 001 skyldtes delt lagringsnøkkel. Her bruker begge anlegg BKK, men
har hver sin måler. Vi observerer forbruk og entiteter etter ekte unload/setup,
og repairs i HAs issue-register. Ingen lagrede summer eller baseliner settes
manuelt. Tidsstegene er korte og innen samme time; kalenderskifter dekkes ikke.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import (
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ENERGY_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    CONF_TARIFFMODUS,
    DOMAIN,
)


def _energi(hass: HomeAssistant, navn: str, kwh: float) -> None:
    hass.states.async_set(
        f"sensor.{navn}_energi",
        str(kwh),
        {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    )


async def _last(hass: HomeAssistant, navn: str, kwh: float) -> MockConfigEntry:
    hass.states.async_set(f"sensor.{navn}_effekt", "1500", {"unit_of_measurement": "W"})
    hass.states.async_set(f"sensor.{navn}_spot", "1.20", {"unit_of_measurement": "NOK/kWh"})
    _energi(hass, navn, kwh)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        title=navn,
        data={
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_TARIFFMODUS: "catalog",
            CONF_POWER_SENSOR: f"sensor.{navn}_effekt",
            CONF_ENERGY_SENSOR: f"sensor.{navn}_energi",
            CONF_SPOT_PRICE_SENSOR: f"sensor.{navn}_spot",
            CONF_SPOTPRIS_INKL_MVA: False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


def _entiteter(hass: HomeAssistant, entry: MockConfigEntry) -> dict:
    """Identitet og eierskap, også for entiteter som er deaktivert som standard."""
    return {
        e.unique_id: (e.entity_id, e.device_id)
        for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
    }


async def test_to_bkk_anlegg_beholder_egen_energi_og_identitet_etter_reload(hass, freezer) -> None:
    """Unload av huset lar hytta telle videre; gjenlasting gjenopptar huset."""
    freezer.move_to("2026-06-15 10:00:00+00:00")
    hus = await _last(hass, "hus", 1000)
    hytte = await _last(hass, "hytte", 5000)
    hus_entiteter = _entiteter(hass, hus)
    hytte_entiteter = _entiteter(hass, hytte)
    assert hus_entiteter and hytte_entiteter
    assert hus_entiteter.keys().isdisjoint(hytte_entiteter)
    assert {d for _, d in hus_entiteter.values()}.isdisjoint(d for _, d in hytte_entiteter.values())
    assert {e.split(".")[0] for e, _ in hus_entiteter.values()} == {"sensor", "binary_sensor", "button"}

    freezer.tick(timedelta(seconds=10))
    _energi(hass, "hus", 1002)
    _energi(hass, "hytte", 5007)
    await hus.runtime_data.async_refresh()
    await hytte.runtime_data.async_refresh()
    assert hus.runtime_data.data["monthly_consumption_total_kwh"] == 2
    assert hytte.runtime_data.data["monthly_consumption_total_kwh"] == 7

    gammel_hus_coordinator = hus.runtime_data
    hytte_coordinator = hytte.runtime_data
    assert await hass.config_entries.async_unload(hus.entry_id)
    await hass.async_block_till_done()
    assert hus.state is ConfigEntryState.NOT_LOADED
    assert hytte.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(seconds=10))
    _energi(hass, "hytte", 5010)
    await hytte.runtime_data.async_refresh()
    assert hytte.runtime_data.data["monthly_consumption_total_kwh"] == 10
    assert hytte.runtime_data is hytte_coordinator
    assert _entiteter(hass, hytte) == hytte_entiteter

    assert await hass.config_entries.async_setup(hus.entry_id)
    await hass.async_block_till_done()
    assert hus.state is ConfigEntryState.LOADED
    assert hus.runtime_data is not gammel_hus_coordinator
    assert hus.runtime_data.data["monthly_consumption_total_kwh"] == 2
    assert _entiteter(hass, hus) == hus_entiteter

    freezer.tick(timedelta(seconds=10))
    _energi(hass, "hus", 1003.5)
    await hus.runtime_data.async_refresh()
    assert hus.runtime_data.data["monthly_consumption_total_kwh"] == 3.5
    assert hytte.runtime_data.data["monthly_consumption_total_kwh"] == 10

    # Også sist lagrede anlegg må overleve reload uten å overta husets data.
    assert await hass.config_entries.async_reload(hytte.entry_id)
    await hass.async_block_till_done()
    assert hytte.runtime_data is not hytte_coordinator
    assert hytte.runtime_data.data["monthly_consumption_total_kwh"] == 10
    assert _entiteter(hass, hytte) == hytte_entiteter


@pytest.mark.parametrize("handling", ["rett_enhet", "fjern_entry"])
async def test_input_repair_ryddes_bare_for_riktig_anlegg(hass, freezer, handling) -> None:
    """Recovery og sletting av én entry må bevare naboens repair og entiteter."""
    freezer.move_to("2026-06-15 10:00:00+00:00")
    hus = await _last(hass, "hus", 1000)
    hytte = await _last(hass, "hytte", 5000)
    registry = er.async_get(hass)
    issues = ir.async_get(hass)
    varsler = {}
    for navn, entry in (("hus", hus), ("hytte", hytte)):
        hass.states.async_set(f"sensor.{navn}_spot", "0.11", {"unit_of_measurement": "EUR/kWh"})
        await entry.runtime_data.async_refresh()
        issue = issues.async_get_issue(DOMAIN, f"input_enhet_{entry.entry_id}")
        assert issue is not None
        assert issue.translation_placeholders["entity_id"] == f"sensor.{navn}_spot"
        entity_id = registry.async_get_entity_id(
            "binary_sensor", DOMAIN, f"{entry.entry_id}_maaledata_problem"
        )
        assert entity_id is not None
        varsler[navn] = entity_id
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == "on"
        assert state.attributes["device_class"] == "problem"
        assert registry.async_get(entity_id).entity_category == "diagnostic"

    hytte_entiteter = _entiteter(hass, hytte)
    if handling == "rett_enhet":
        hass.states.async_set("sensor.hus_spot", "1.20", {"unit_of_measurement": "NOK/kWh"})
        await hus.runtime_data.async_refresh()
        assert hass.states.get(varsler["hus"]).state == "off"
    else:
        assert await hass.config_entries.async_remove(hus.entry_id)
        await hass.async_block_till_done()
        assert not _entiteter(hass, hus)

    assert issues.async_get_issue(DOMAIN, f"input_enhet_{hus.entry_id}") is None
    assert issues.async_get_issue(DOMAIN, f"input_enhet_{hytte.entry_id}") is not None
    assert hytte.state is ConfigEntryState.LOADED
    assert _entiteter(hass, hytte) == hytte_entiteter
    assert hass.states.get(varsler["hytte"]).state == "on"
