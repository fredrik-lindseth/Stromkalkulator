"""Ekte-HA-bevis for opprydding etter sensor -> binary_sensor-migrering."""

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import DOMAIN


async def test_legacy_sensor_entries_are_removed_before_binary_sensors_are_created(hass):
    """Oppgradering rydder kun de tre foreldede sensor.*-oppføringene."""
    hass.states.async_set("sensor.migrering_effekt", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.migrering_spot", "0.8", {"unit_of_measurement": "NOK/kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            "tso": "bkk",
            "boligtype": "bolig",
            "avgiftssone": "standard",
            "tariffmodus": "catalog",
            "har_norgespris": True,
            "power_sensor": "sensor.migrering_effekt",
            "spot_price_sensor": "sensor.migrering_spot",
            "spotpris_inkl_mva": False,
        },
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    legacy_ids = {
        suffix: registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"{entry.entry_id}_{suffix}",
            config_entry=entry,
            suggested_object_id=f"gammelt_{suffix}",
        ).entity_id
        for suffix in ("kapasitet_varsel", "norgespris_aktiv", "stromstotte_aktiv")
    }
    untouched = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{entry.entry_id}_maanedlig_total",
        config_entry=entry,
        suggested_object_id="behold_meg",
    ).entity_id

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    for suffix, entity_id in legacy_ids.items():
        assert registry.async_get(entity_id) is None
        assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{entry.entry_id}_{suffix}") is not None
    assert registry.async_get(untouched) is not None
