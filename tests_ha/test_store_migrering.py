"""Historisk Store-format gjennom ekte HAs setup, lagring og reload."""

from datetime import datetime

import pytest
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.stromkalkulator.const import DOMAIN


@pytest.mark.parametrize("gammel_dso_nokkel", [True, False], ids=["dso-til-entry", "entry-format-v1"])
async def test_gammel_store_bevarer_maaned_og_migrerer_en_gang(hass, freezer, gammel_dso_nokkel):
    """Ukjent råmåler forkastes; historisk energi og koståpning overlever."""
    freezer.move_to("2026-06-15T10:00:00+00:00")
    await hass.config.async_update(time_zone="Europe/Oslo")
    hass.states.async_set("sensor.migrering_effekt", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.migrering_pris", "0.8", {"unit_of_measurement": "NOK/kWh"})
    energy_attrs = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}
    hass.states.async_set("sensor.migrering_energi", "9000", energy_attrs)
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
            "spot_price_sensor": "sensor.migrering_pris",
            "energy_sensor": "sensor.migrering_energi",
            "spotpris_inkl_mva": False,
        },
    )
    old_store = Store(hass, 1, f"{DOMAIN}_{'bkk' if gammel_dso_nokkel else entry.entry_id}")
    await old_store.async_save(
        {
            "current_month": 6,
            "current_date": "2026-06-15",
            "daily_max_power": {"2026-06-12": 4.5, "2026-06-13": 3.5, "2026-06-14": 2.5},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "monthly_accumulated_cost_strom": 60.0,
            "monthly_accumulated_cost_energiledd": 45.0,
            "monthly_norgespris_compensation": 15.0,
            "previous_month_name": "Mai 2026",
            "previous_month_consumption": {"dag": 200.0, "natt": 80.0},
            "previous_month_top_3": {"2026-05-10": 4.0},
            "previous_month_cost": 321.0,
            "last_tpi_kwh": 123.0,
        }
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    assert coordinator.data["current_month"] == "2026-06"
    assert coordinator.data["monthly_consumption_total_kwh"] == 150.0
    assert coordinator.data["monthly_consumption_dag_kwh"] == 100.0
    assert coordinator.data["monthly_consumption_natt_kwh"] == 50.0
    assert coordinator.data["previous_month_consumption_total_kwh"] == 280.0
    assert coordinator.data["previous_month_cost_kr"] == 321.0
    assert coordinator.data["avregning_ufullstendig"] is True
    if gammel_dso_nokkel:
        assert await old_store.async_load() is None

    # The next scheduled observation saves through the integration's real
    # dirty-cycle path; unloading itself does not perform a Store write.
    first_poll = datetime.fromisoformat("2026-06-15T10:01:00+00:00")
    freezer.move_to(first_poll)
    hass.states.async_set("sensor.migrering_energi", "9000.1", energy_attrs)
    async_fire_time_changed(hass, first_poll)
    await hass.async_block_till_done()
    assert coordinator.data["monthly_consumption_total_kwh"] == pytest.approx(150.1)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    store = Store(hass, 1, f"{DOMAIN}_{entry.entry_id}")
    saved = await store.async_load()
    assert saved["current_month"] == "2026-06"
    assert saved["daily_max_power"]["2026-06-12"] == {"kw": 4.5, "hour": None}
    assert saved["previous_month_top_3"]["2026-05-10"] == {"kw": 4.0, "hour": None}
    assert saved["monthly_energiledd_apning"] == 45.0
    assert saved["energi_baseline"]["schema_version"] == 2
    assert saved["energi_baseline"]["value_kwh"] == 9000.1
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data is not coordinator
    assert entry.runtime_data.data["monthly_consumption_total_kwh"] == pytest.approx(150.1)

    # A scheduled HA poll resumes only the new meter delta, never the old
    # untyped raw value, and never imports the old monthly totals twice.
    later = datetime.fromisoformat("2026-06-15T10:02:00+00:00")
    freezer.move_to(later)
    hass.states.async_set("sensor.migrering_energi", "9000.2", energy_attrs)
    async_fire_time_changed(hass, later)
    await hass.async_block_till_done()
    assert entry.runtime_data.data["monthly_consumption_total_kwh"] == pytest.approx(150.2)
    assert entry.runtime_data.data["previous_month_cost_kr"] == 321.0
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert (await store.async_load())["monthly_energiledd_apning"] == 45.0
