"""Ekte HA viser ukjent kapasitet og kostnad utenfor Etna-kildens omfang."""

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import DOMAIN
from custom_components.stromkalkulator.coordinator import DailyMaxEntry


@pytest.mark.parametrize(
    "dso,gyldig_kw,ukjent_kw,pris", [("etna_nett", 25, 25.001, 1269.2), ("nettselskapet", 74.999, 75, 3325)]
)
async def test_sensorer_blir_ukjent_utenfor_kilden_og_kommer_tilbake(
    hass, freezer, dso, gyldig_kw, ukjent_kw, pris
):
    freezer.move_to("2026-10-09T12:00:00+00:00")
    hass.states.async_set("sensor.etna_power", "0", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.etna_spot", "1", {"unit_of_measurement": "NOK/kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            "tso": dso,
            "tariffmodus": "catalog",
            "power_sensor": "sensor.etna_power",
            "spot_price_sensor": "sensor.etna_spot",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    registry = er.async_get(hass)
    capacity = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_kapasitetstrinn")
    totals = [
        registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_{suffix}")
        for suffix in ("maanedlig_total", "estimated_monthly_cost")
    ]
    for kw, ukjent in [(gyldig_kw, False), (ukjent_kw, True), (gyldig_kw, False)]:
        coordinator._daily_max_power = {f"2026-10-{dag:02}": DailyMaxEntry(kw, 12) for dag in (1, 2, 3)}
        coordinator.async_set_updated_data(await coordinator._async_update_data())
        await hass.async_block_till_done()
        state = hass.states.get(capacity)
        assert (state.state == STATE_UNKNOWN) is ukjent
        for entity_id in totals:
            total = hass.states.get(entity_id)
            assert total is not None
            assert (total.state == STATE_UNKNOWN) is ukjent
        if ukjent:
            assert state.attributes["fastledd_ukjent"]
        else:
            assert float(state.state) == pris
