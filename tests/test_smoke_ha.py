"""Røyktest mot ekte Home Assistant (ikke mocket).

Resten av testpakken (tests/) mocker bort homeassistant.* i sys.modules via
tests/conftest.py, så config-flow-rendering, entity-registrering og
plattform-setup blir aldri kjørt mot ekte HA. Denne testen bruker
pytest-homeassistant-custom-component sitt rammeverk til å laste integrasjonen
i en ekte HomeAssistant-instans.

Conftest-kollisjon: tests/conftest.py stubber homeassistant.* på modulnivå for
HELE tests/-mappen, og pytest laster den så snart en test under tests/ samles
inn. En ekte-HA-test tåler ikke det. Løsningen er å kjøre denne fila med
`--noconftest` i en egen CI-jobb (se .github/workflows/ci.yml, jobb `smoke-ha`).
`--noconftest` slår kun av conftest.py-filene; entry-point-pluginen
pytest-homeassistant-custom-component lastes fortsatt og gir hass-fixturene.
Den ordinære jobben kjører `pytest tests/ --ignore=tests/test_smoke_ha.py`.

Krever `asyncio_mode=auto` (hass-fixturen er en async generator dekorert med
@pytest.fixture); CI-jobben sender `-o asyncio_mode=auto`.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Repo-roten på sys.path så både `import custom_components.stromkalkulator` og
# HA-loaderens interne `import custom_components` finner integrasjonen. Uten
# tests/conftest.py (kjøres med --noconftest) settes ikke dette ellers.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
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


@pytest.fixture(autouse=True)
def _enable_custom(enable_custom_integrations):
    """Slå på lasting av custom_components/ for alle tester i fila."""
    yield


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

    # 53 sensorer + 1 knapp. Nedre grense heller enn eksakt tall for å tåle at
    # sensorlista utvides, men høy nok til å fange en ødelagt plattform-setup.
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
