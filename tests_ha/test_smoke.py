"""Røyktest mot ekte Home Assistant (ikke mocket).

Unit-testene under `tests/` stubber bort `homeassistant.*`, så config-flow-
rendering, entitetsregistrering og plattform-setup blir aldri kjørt mot ekte HA
der. Denne fila laster integrasjonen i en ekte HomeAssistant-instans via
pytest-homeassistant-custom-component.

Kjøres av `just test-ha target=minimum` og `target=current`. sys.path og
`enable_custom_integrations` settes i tests_ha/conftest.py.
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import icon
from homeassistant.loader import async_get_custom_components
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import (
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_HAR_NORGESPRIS,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DOMAIN,
)
from custom_components.stromkalkulator.dso import DSO_LIST

POWER_SENSOR = "sensor.smoke_power"
SPOT_SENSOR = "sensor.smoke_spot_price"


def _entry_data() -> dict:
    dso = DSO_LIST["bkk"]
    return {
        CONF_DSO: "bkk",
        CONF_BOLIGTYPE: "bolig",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: POWER_SENSOR,
        CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
        CONF_SPOTPRIS_INKL_MVA: False,
        CONF_AVGIFTSSONE: "standard",
        CONF_ENERGILEDD_DAG: dso["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: dso["energiledd_natt_eks_mva"],
    }


async def test_setup_entry_loads_and_registers_entities(hass: HomeAssistant) -> None:
    """async_setup_entry laster og oppretter forventet antall entiteter."""
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_entry_data(),
        version=3,
        unique_id=f"{DOMAIN}_{POWER_SENSOR}",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)

    # Én knapp, fire binærsensorer og resten sensorer. Nedre grense heller enn
    # eksakt tall for å tåle at sensorlista utvides, men høy nok til å fange en
    # ødelagt plattform-setup.
    assert len(entities) >= 50, f"forventet >=50 entiteter, fikk {len(entities)}"
    domains = {e.domain for e in entities}
    assert "sensor" in domains
    assert "button" in domains

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_config_flow_user_step_renders_form(hass: HomeAssistant) -> None:
    """Bruker-steget i config-flow rendrer et skjema uten feil."""
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result.get("errors") in (None, {})


async def test_lokale_brandbilder_oppdages_av_current_home_assistant(hass: HomeAssistant) -> None:
    """HA 2026.3+ skal foretrekke integrationens ``brand/`` over Brands-CDN.

    Minimumsmiljøet er HA 2026.1, før ``Integration.has_branding`` og lokale
    brandbilder fantes. Det skal fortsatt laste integrasjonen, men kan ikke
    verifisere et API som ikke eksisterer der.
    """
    custom_components = await async_get_custom_components(hass)
    integration = custom_components[DOMAIN]

    if not hasattr(integration, "has_branding"):
        pytest.skip("Lokale brandbilder kom i Home Assistant 2026.3")

    assert integration.has_branding
    assert integration.file_path.name == DOMAIN
    assert integration.file_path.parent.name == "custom_components"


async def test_ikonene_naar_fram_via_icons_json(hass: HomeAssistant) -> None:
    """Hver registrerte entitet får ikonet sitt fra icons.json.

    Ikonene lå som `_attr_icon` i entitetsklassene fram til september 2026.
    Etter flyttingen til icons.json er det Home Assistant som slår dem opp per
    translation_key, og en feilstavet nøkkel eller en glemt plattform gir en
    entitet uten ikon uten at noe annet blir rødt. Unit-testene ser bare på
    filene; dette er beviset på at HA faktisk finner dem.
    """
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_entry_data(),
        version=3,
        unique_id=f"{DOMAIN}_{POWER_SENSOR}",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    ikoner = await icon.async_get_icons(hass, "entity", integrations=[DOMAIN])
    entitetsikoner = ikoner[DOMAIN]

    registry = er.async_get(hass)
    uten: list[str] = []
    for oppforing in er.async_entries_for_config_entry(registry, entry.entry_id):
        assert oppforing.translation_key, f"{oppforing.entity_id} mangler translation_key"
        oppslag = entitetsikoner.get(oppforing.domain, {}).get(oppforing.translation_key, {})
        if not oppslag.get("default"):
            uten.append(f"{oppforing.domain}.{oppforing.translation_key}")

    assert not uten, f"entiteter uten ikon i icons.json: {sorted(set(uten))}"
