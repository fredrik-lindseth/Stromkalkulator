"""Publiser ikke en komplett historisk regning uten det historiske fastleddet."""

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import DOMAIN


async def test_manglende_historisk_aarsgrunnlag_gir_unknown_nettleie(hass):
    hass.states.async_set("sensor.arkiv_power", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.arkiv_spot", "1", {"unit_of_measurement": "NOK/kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            "tso": "fjellnett",
            "tariffmodus": "catalog",
            "power_sensor": "sensor.arkiv_power",
            "spot_price_sensor": "sensor.arkiv_spot",
            "spotpris_inkl_mva": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    nettleie = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_forrige_maaned_nettleie")
    coordinator = entry.runtime_data
    data = {
        **coordinator.data,
        "previous_month_name": "juni 2026",
        "previous_month_bokforte_kroner": True,
        "previous_month_energiledd_dag_kr": 130,
        "previous_month_kapasitetsledd": 415,
        "previous_month_fastledd_grunnlag_bekreftet": True,
    }
    coordinator.async_set_updated_data(data)
    await hass.async_block_till_done()
    assert hass.states.get(nettleie).state != STATE_UNKNOWN
    coordinator.async_set_updated_data({**data, "previous_month_fastledd_grunnlag_bekreftet": False})
    await hass.async_block_till_done()
    state = hass.states.get(nettleie)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["fastledd_grunnlag_bekreftet"] is False
    assert "kapasitetsledd_kr" not in state.attributes


async def test_fastledd_med_ore_publiseres_uten_helkroneavrunding(hass):
    hass.states.async_set("sensor.ore_power", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.ore_spot", "1", {"unit_of_measurement": "NOK/kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            "tso": "custom",
            "tariffmodus": "manual",
            "power_sensor": "sensor.ore_power",
            "spot_price_sensor": "sensor.ore_spot",
            "spotpris_inkl_mva": False,
            "egendefinert_kapasitetstrinn": "5:623,70,50:2062.50",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    kapasitet = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_kapasitetstrinn")
    coordinator = entry.runtime_data
    assert coordinator.data["kapasitetsledd"] == 623.70
    assert float(hass.states.get(kapasitet).state) == 623.70
    nettleie = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_forrige_maaned_nettleie")
    coordinator.async_set_updated_data(
        {
            **coordinator.data,
            "previous_month_name": "juni 2026",
            "previous_month_bokforte_kroner": True,
            "previous_month_energiledd_dag_kr": 130,
            "previous_month_energiledd_natt_kr": 0,
            "previous_month_avgifter_kr": 0,
            "previous_month_kapasitetsledd": 2062.50,
            "previous_month_fastledd_grunnlag_bekreftet": True,
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get(nettleie)
    assert float(state.state) == 2192.50
    assert state.attributes["kapasitetsledd_kr"] == 2062.50
