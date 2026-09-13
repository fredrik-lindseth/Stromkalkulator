"""Enhet-, statistikk- og device-kontrakter slik ekte HA publiserer dem."""

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import DOMAIN


async def test_alle_plattformer_publiserer_metadata_og_beholder_identitet(hass, freezer):
    """Vokt HA-kontrakten, særlig NOK kontra satser og statistikkperioder."""
    freezer.move_to("2026-06-15T10:00:00+00:00")
    await hass.config.async_update(time_zone="Europe/Oslo")
    hass.states.async_set("sensor.meta_effekt", "1000", {"unit_of_measurement": "W"})
    hass.states.async_set("sensor.meta_pris", "0.8", {"unit_of_measurement": "NOK/kWh"})
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data={
            "tso": "bkk",
            "boligtype": "bolig",
            "avgiftssone": "standard",
            "tariffmodus": "catalog",
            "har_norgespris": True,
            "power_sensor": "sensor.meta_effekt",
            "spot_price_sensor": "sensor.meta_pris",
            "spotpris_inkl_mva": False,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    # Disabled-by-default diagnostics and export entities also have a public
    # metadata contract. Enable them through HA's registry before inspecting.
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.disabled_by is not None:
            registry.async_update_entity(entity.entity_id, disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    def snapshot():
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        result = {}
        for entity in entities:
            state = hass.states.get(entity.entity_id)
            assert state is not None, entity.entity_id
            assert entity.unique_id.startswith(f"{entry.entry_id}_")
            assert entity.has_entity_name
            assert entity.translation_key
            device = dr.async_get(hass).async_get(entity.device_id)
            assert device is not None
            assert entry.entry_id in device.config_entries
            assert all(
                domain == DOMAIN and identifier.startswith(f"{entry.entry_id}_")
                for domain, identifier in device.identifiers
            )
            result[entity.unique_id.removeprefix(f"{entry.entry_id}_")] = (
                entity.entity_id,
                entity.device_id,
                entity.entity_category,
                state.attributes.get("unit_of_measurement"),
                state.attributes.get("device_class"),
                state.attributes.get("state_class"),
                state.attributes.get("last_reset"),
            )
        return result

    before = snapshot()
    assert {key.split(".")[0] for key, *_ in before.values()} == {"sensor", "binary_sensor", "button"}
    # Representative exact contracts also ensure the generic checks cannot go
    # green after accidentally removing an entire family of entities.
    expected = {
        "energiledd": ("NOK/kWh", None, "measurement"),
        "energiledd_dag": ("NOK/kWh", None, "measurement"),
        "energiledd_natt": ("NOK/kWh", None, "measurement"),
        "kapasitetstrinn": ("kr/mnd", None, "measurement"),
        "maks_forbruk_1": ("kW", "power", "measurement"),
        "maanedlig_forbruk_total": ("kWh", "energy", "total_increasing"),
        "maanedlig_total": ("NOK", "monetary", "total"),
        "daily_cost": ("NOK", "monetary", "total"),
        "estimated_monthly_cost": ("NOK", "monetary", None),
        "forrige_maaned_forbruk_total": ("kWh", "energy", "total"),
        "maanedlig_eksport_kwh": ("kWh", "energy", "total_increasing"),
        "tariff": (None, "enum", None),
        "maaledata_problem": (None, "problem", None),
        "kapasitet_varsel": (None, "problem", None),
        "lag_fakturarapport": (None, None, None),
    }
    for suffix, contract in expected.items():
        assert before[suffix][3:6] == contract, suffix
    assert before["maaledata_problem"][2] == "diagnostic"
    assert before["maks_forbruk_1"][2] == "diagnostic"
    assert before["maanedlig_total"][6] == "2026-06-01T00:00:00+02:00"
    assert before["daily_cost"][6] == "2026-06-15T00:00:00+02:00"
    for suffix, (_, _, _, unit, device_class, state_class, _) in before.items():
        if unit in {"NOK/kWh", "kr/mnd"}:
            assert device_class is None, suffix
            assert state_class == "measurement", suffix
        if device_class == "monetary":
            assert unit == "NOK", suffix
            assert state_class in {"total", None}, suffix
    tariff = hass.states.get(before["tariff"][0])
    assert tariff.state in tariff.attributes["options"]

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert snapshot() == before
