"""Fast mirrors of named Docker scenarios (stromkalkulator-271siks).

These assert HA entity states and the real repairs registry with a frozen
clock. Docker still owns HTTP/onboarding, process restart and release packing;
historical prices and invoice totals belong to the deterministic replay suite.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from custom_components.stromkalkulator.const import DOMAIN

ENERGY = "sensor.e2e_energy"
POWER = "sensor.e2e_power"
ENERGY_ATTRS = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}


@pytest.fixture
async def lab(hass, freezer):
    """Use the user flow, then resolve outputs by their stable unique IDs."""
    freezer.move_to("2026-06-15T10:05:00+00:00")
    hass.states.async_set(ENERGY, "10000", ENERGY_ATTRS)
    hass.states.async_set(POWER, "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.e2e_spot", "0.8", {"unit_of_measurement": "NOK/kWh"})
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert flow["step_id"] == "user"
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"tso": "bkk", "boligtype": "bolig", "har_norgespris": True}
    )
    assert flow["step_id"] == "sensors"
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {
            "power_sensor": POWER,
            "energy_sensor": ENERGY,
            "spot_price_sensor": "sensor.e2e_spot",
            "spotpris_inkl_mva": False,
        },
    )
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    entry = result["result"]
    assert entry.state is ConfigEntryState.LOADED
    output = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_maanedlig_forbruk_total"
    )
    assert output is not None

    class Lab:
        def total(self):
            state = hass.states.get(output)
            assert state is not None
            return float(state.state)

        async def poll(self, counter=None):
            freezer.tick(timedelta(minutes=1))
            if counter is not None:
                hass.states.async_set(ENERGY, str(counter), ENERGY_ATTRS)
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            return self.total()

    instance = Lab()
    instance.entry = entry
    assert instance.total() == 0
    return instance


async def test_onboarding_and_energy_increase(lab):
    """Docker test_onboarding/test_energy_increase: baseline, then +1.25 kWh."""
    assert await lab.poll(10001.25) == 1.25
    assert await lab.poll() == 1.25


async def test_restart_no_double_booking(hass, lab):
    """Docker restart mirror: persisted positive consumption survives reload."""
    assert await lab.poll(10001.25) == 1.25
    await hass.config_entries.async_reload(lab.entry.entry_id)
    await hass.async_block_till_done()
    assert lab.total() == 1.25
    assert await lab.poll() == 1.25
    assert await lab.poll(10002.5) == 2.5


@pytest.mark.parametrize("missing", ["deleted", "unavailable", "unknown"])
async def test_missing_input_recovery(hass, lab, missing):
    """Missing energy cannot book phantom kWh or prevent subsequent recovery."""
    assert await lab.poll(10001.25) == 1.25
    if missing == "deleted":
        hass.states.async_remove(ENERGY)
    else:
        hass.states.async_set(ENERGY, missing, ENERGY_ATTRS)
    assert await lab.poll() == 1.25
    assert await lab.poll(10001.25) == 1.25
    assert await lab.poll(10002.5) == 2.5


async def test_meter_jump(lab):
    """Reject a 1000 kWh jump, then accept 1.25 kWh from the new baseline."""
    assert await lab.poll(10001.25) == 1.25
    assert await lab.poll(11001.25) == 1.25
    assert await lab.poll(11002.5) == 2.5


async def test_invalid_unit_recovery(hass, lab):
    """Docker unit repair: wrong dimension raises an issue; healthy input clears it."""
    issues = ir.async_get(hass)
    issue_id = f"input_enhet_{lab.entry.entry_id}"
    assert issues.async_get_issue(DOMAIN, issue_id) is None
    hass.states.async_set(POWER, "1000", {"unit_of_measurement": "bananas"})
    assert await lab.poll() == 0
    assert issues.async_get_issue(DOMAIN, issue_id) is not None
    hass.states.async_set(POWER, "1000", {"unit_of_measurement": "W"})
    assert await lab.poll() == 0
    assert issues.async_get_issue(DOMAIN, issue_id) is None
    assert await lab.poll(10001.25) == 1.25
