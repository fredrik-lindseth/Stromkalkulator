"""Repairs-plattform for Strømkalkulator.

Home Assistant oppdager fix-flows via denne plattformfilen (repairs.py) og
`async_create_fix_flow`. Tre issues er fiksbare: DSO-fusjonen (dso_migration_*,
reist i __init__.py), forkastet energi-delta (energi_delta_forkastet_*, reist fra
coordinatoren når en avlesning hoppet så mye at den ble kastet) og den
feilmerkede energiledd-satsen (egendefinert_energiledd_*).

De to første trenger bare en bekreftelse, og ConfirmRepairFlow-helperen holder:
den viser et confirm-steg og lukker issuen når brukeren bekrefter. Tittel og
beskrivelse hentes fra issuens translation_key, seksjonene
`issues.tso_migrated.fix_flow` og `issues.energi_delta_forkastet.fix_flow` i
strings.json.

Den tredje trenger mer: varselet reises ved hver oppstart så lenge entryet
bruker egendefinerte satser, så en ren bekreftelse ville kommet tilbake ved
neste restart. EgendefinertSatserRepairFlow skriver derfor et flagg på config
entryet, og det er flagget __init__.py sjekker før den reiser varselet igjen.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.helpers import issue_registry as ir

from .const import CONF_EGENDEFINERT_SATSER_BEKREFTET, DOMAIN, EGENDEFINERT_ISSUE_PREFIX

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)


class EgendefinertSatserRepairFlow(RepairsFlow):
    """Lukker energiledd-varselet for godt når brukeren har sjekket satsen.

    Brukeren bekrefter at satsen er kontrollert mot nettselskapets prisliste. Vi
    kan ikke se om den er riktig, så bekreftelsen er alt vi har: den skrives på
    config entryet slik at varselet ikke dukker opp igjen ved neste omstart.
    """

    def __init__(self, issue_id: str, entry_id: str) -> None:
        """Ta vare på hvilken issue og hvilket anlegg flowen gjelder."""
        self._issue_id = issue_id
        self._entry_id = entry_id

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Send rett videre til bekreftelsessteget."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> Any:
        """Vis teksten, og merk satsen som sjekket når brukeren bekrefter."""
        if user_input is not None:
            self._merk_bekreftet()
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=self._plassholdere(),
        )

    def _plassholdere(self) -> dict[str, str] | None:
        """Hent issuens plassholdere, så satsene i teksten er brukerens egne."""
        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self._issue_id)
        if issue is None:
            return None
        plassholdere: dict[str, str] | None = issue.translation_placeholders
        return plassholdere

    def _merk_bekreftet(self) -> None:
        """Skriv bekreftelsen på config entryet."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            _LOGGER.debug("Fant ikke entry %s, hopper over bekreftelsen", self._entry_id)
            return
        if entry.data.get(CONF_EGENDEFINERT_SATSER_BEKREFTET):
            return
        self.hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_EGENDEFINERT_SATSER_BEKREFTET: True},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Lag fix-flow for en fiksbar repair-issue.

    Energiledd-varselet trenger sin egen flow for å huske bekreftelsen. De andre
    (dso_migration_*, energi_delta_forkastet_*) krever bare et klikk, så
    ConfirmRepairFlow er tilstrekkelig. Integrasjonen kan ikke gjenskape
    forbruket som gikk tapt, bare vise tallet.
    """
    if issue_id.startswith(EGENDEFINERT_ISSUE_PREFIX):
        entry_id = issue_id[len(EGENDEFINERT_ISSUE_PREFIX) :]
        return EgendefinertSatserRepairFlow(issue_id, entry_id)
    return ConfirmRepairFlow()
