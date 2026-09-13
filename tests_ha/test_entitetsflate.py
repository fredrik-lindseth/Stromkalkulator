"""Golden snapshot av brukerflaten: entitets-ID-er, enheter og ikoner.

Entitets-ID-en er kontrakten mot brukerens automasjoner og dashbord, og enheten
er kontrakten mot recorderens statistikk. Endres en av dem uten at noen vil det,
knekker automasjoner stille hos alle, eller hver bruker får en repair. Denne
fila laster integrasjonen i en ekte Home Assistant og sammenligner hele flaten
mot `tests_ha/entitetsflate.json`.

Ikonet leses via samme vei som frontenden bruker: `icon`-attributtet om det
finnes, ellers ikonoversettelsen fra `icons.json`. Da fanger snapshotet at et
ikon flyttet fra `_attr_icon` til `icons.json` uten å endre seg, i stedet for å
bare se at attributtet forsvant.

Entiteter som er deaktivert som standard har ingen tilstand, så `navn`,
`enhet` og resten står som null for dem. Registeroppføringen er fortsatt
med, så entitets-ID-en og ikonet deres er like godt låst.

Endrer du flaten med vilje, regenerer med:

    SKRIV_ENTITETSFLATE=1 just test-ha target=current tests_ha/test_entitetsflate.py

og les diffen i git før du committer den.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import icon as ic
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import DOMAIN
from tests_ha.test_smoke import POWER_SENSOR, SPOT_SENSOR, _entry_data

FLATE = Path(__file__).parent / "entitetsflate.json"


async def test_entitetsflaten_er_uendret(hass: HomeAssistant) -> None:
    """Hele entitetsflaten skal være bit for bit lik snapshotet."""
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

    ikoner = await ic.async_get_icons(hass, "entity", integrations=[DOMAIN])
    oversatte = ikoner.get(DOMAIN, {})

    registry = er.async_get(hass)
    flate = {}
    for oppf in er.async_entries_for_config_entry(registry, entry.entry_id):
        tilstand = hass.states.get(oppf.entity_id)
        attributter = tilstand.attributes if tilstand else {}
        oversatt = oversatte.get(oppf.domain, {}).get(oppf.translation_key or "", {})
        flate[oppf.entity_id] = {
            "unique_id_suffiks": oppf.unique_id.removeprefix(f"{entry.entry_id}_"),
            "translation_key": oppf.translation_key,
            "navn": attributter.get("friendly_name"),
            "enhet": attributter.get("unit_of_measurement"),
            "device_class": attributter.get("device_class"),
            "state_class": attributter.get("state_class"),
            "entity_category": oppf.entity_category.value if oppf.entity_category else None,
            "deaktivert_som_standard": oppf.disabled_by is not None,
            "ikon": attributter.get("icon") or oversatt.get("default"),
        }

    if os.environ.get("SKRIV_ENTITETSFLATE"):
        FLATE.write_text(
            json.dumps(flate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    assert FLATE.is_file(), f"{FLATE} mangler. Regenerer med SKRIV_ENTITETSFLATE=1."
    forventet = json.loads(FLATE.read_text(encoding="utf-8"))

    assert sorted(flate) == sorted(forventet), (
        "entitets-ID-ene har endret seg. Lagt til: "
        f"{sorted(set(flate) - set(forventet))}, borte: {sorted(set(forventet) - set(flate))}"
    )
    avvik = {eid: (forventet[eid], flate[eid]) for eid in forventet if forventet[eid] != flate[eid]}
    assert not avvik, f"entitetsflaten har endret seg (forventet, faktisk): {avvik}"
