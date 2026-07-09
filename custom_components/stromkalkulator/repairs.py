"""Repairs-plattform for Strømkalkulator.

Home Assistant oppdager fix-flows via denne plattformfilen (repairs.py) og
`async_create_fix_flow`. Fiksbare issues registreres med `async_create_issue`
i __init__.py; den eneste fiksbare issuen er DSO-fusjonen (dso_migration_*),
som bare trenger en bekreftelse for å lukkes. ConfirmRepairFlow-helperen viser
et confirm-steg og lukker issuen når brukeren bekrefter. Tittel og beskrivelse
hentes fra issuens translation_key (tso_migrated), seksjon
`issues.tso_migrated.fix_flow` i strings.json.
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

    Kun DSO-fusjons-issuen (dso_migration_*) er fiksbar, og den krever bare en
    bekreftelse for å lukkes, så ConfirmRepairFlow er tilstrekkelig.
    """
    return ConfirmRepairFlow()
