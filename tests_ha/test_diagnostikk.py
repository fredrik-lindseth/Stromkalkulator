"""Diagnostikken mot et ekte issue-register.

`tests/test_diagnostics.py` bygger issue-registeret av en dataklasse vi har
skrevet selv, og den vil alltid ha de feltnavnene vi ga den. Bytter HA navn på
`dismissed_version` eller `active`, står det bare `None` i dumpen, og ingen
unit-test ser det. Derfor denne: samme seksjon, men mot HAs egen `IssueEntry`
og et ekte config entry med ekte entry_id.
"""

from __future__ import annotations

import json

import pytest
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.diagnostics import async_get_config_entry_diagnostics

HEMMELIG_ENTITET = "sensor.fredrik_lindseth_nesttunveien_hovedmaaler"


@pytest.fixture
def entry(hass):
    """Et anlegg som finnes i HA, men ikke er satt opp."""
    oppforing = MockConfigEntry(
        domain="stromkalkulator",
        title="Strømkalkulator Nesttunveien 42",
        version=4,
        data={
            "tso": "bkk",
            "power_sensor": HEMMELIG_ENTITET,
            "spot_price_sensor": "sensor.spot",
            "avgiftssone": "standard",
            "har_norgespris": False,
            "spotpris_inkl_mva": True,
        },
    )
    oppforing.add_to_hass(hass)
    return oppforing


async def test_repairs_leses_fra_ekte_register(hass, entry):
    """Feltnavnene på HAs IssueEntry er de diagnostikken leser."""
    ir.async_create_issue(
        hass,
        "stromkalkulator",
        f"input_utfall_{entry.entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="vakthold_utfall",
        translation_placeholders={"input": "effekt", "entity_id": HEMMELIG_ENTITET},
    )
    ir.async_create_issue(
        hass,
        "stromkalkulator",
        "satser_utdatert",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="satser_utdatert",
        translation_placeholders={"aar": "2026"},
    )

    dump = await async_get_config_entry_diagnostics(hass, entry)
    repairs = dump["repairs"]

    assert repairs["tilgjengelig"] is True
    assert {rad["sort"]: rad["gjelder"] for rad in repairs["issues"]} == {
        "input_utfall": "dette_anlegget",
        "satser_utdatert": "hele_integrasjonen",
    }
    for rad in repairs["issues"]:
        assert rad["alvorlighet"] == "warning"
        assert rad["aktiv"] is True
        assert rad["fiksbar"] is False
        assert rad["avvist_i_versjon"] is None
        # ISO-tidspunkt, ikke markør: formatet må slippe gjennom tekstvakten.
        assert rad["opprettet"].startswith("20")


async def test_ingen_raa_identifikatorer_i_en_ekte_dump(hass, entry):
    """Entry_id, tittel og entity-id er ekte her, ikke vår egen streng."""
    ir.async_create_issue(
        hass,
        "stromkalkulator",
        f"input_utfall_{entry.entry_id}",
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="vakthold_utfall",
        translation_placeholders={"input": "effekt", "entity_id": HEMMELIG_ENTITET},
    )
    tekst = json.dumps(
        await async_get_config_entry_diagnostics(hass, entry), allow_nan=False, ensure_ascii=False
    )
    for raa in (entry.entry_id, entry.title, HEMMELIG_ENTITET, "Nesttunveien"):
        assert raa not in tekst, f"{raa} sto rått i dumpen"


async def test_ulastet_entry_gir_snapshot_i_ekte_ha(hass, entry):
    """Den som ber om en dump har ofte et oppsett som nettopp feilet."""
    dump = await async_get_config_entry_diagnostics(hass, entry)
    assert dump["lastet"] is False
    assert dump["baseline"] is None
    assert dump["integration"]["ha_version"]
    assert dump["input_roller"]["effekt"]["konfigurert"] is True
    json.dumps(dump, allow_nan=False)
