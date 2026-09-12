"""Repairs-plattform for Strømkalkulator.

Home Assistant oppdager fix-flows via denne plattformfilen (repairs.py) og
`async_create_fix_flow`. To issues er fiksbare, og begge trenger bare en
bekreftelse for å lukkes: DSO-fusjonen (dso_migration_*, reist i __init__.py) og
forkastet energi-delta (energi_delta_forkastet_*, reist fra coordinatoren når en
avlesning hoppet så mye at den ble kastet). ConfirmRepairFlow-helperen viser et
confirm-steg og lukker issuen når brukeren bekrefter. Tittel og beskrivelse
hentes fra issuens translation_key, seksjonene `issues.tso_migrated.fix_flow` og
`issues.energi_delta_forkastet.fix_flow` i strings.json.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Lag fix-flow for en fiksbar repair-issue.

    Begge de fiksbare issuene (dso_migration_*, energi_delta_forkastet_*) krever
    bare en bekreftelse for å lukkes, så ConfirmRepairFlow er tilstrekkelig.
    Integrasjonen kan ikke gjenskape forbruket som gikk tapt, bare vise tallet.
    """
    return ConfirmRepairFlow()
