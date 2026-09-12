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

TariffmodusRepairFlow er den eneste som ikke er en bekreftelse: den stiller et
spørsmål med to svar, og begge skriver en tariffmodus på entryet.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.helpers import issue_registry as ir

from .const import (
    CONF_EGENDEFINERT_SATSER_BEKREFTET,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_PRISENHET_BEKREFTET,
    CONF_TARIFFMODUS,
    DOMAIN,
    EGENDEFINERT_ISSUE_PREFIX,
    TARIFF_ISSUE_PREFIX,
    TARIFFMODUS_CATALOG,
    TARIFFMODUS_MANUAL,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Id-prefikset coordinatoren reiser prisenhet-varselet med.
PRISENHET_ISSUE_PREFIX: str = "prisenhet_ubekreftet_"


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


class PrisenhetRepairFlow(RepairsFlow):
    """Bekrefter at en prissensor uten enhet faktisk er i NOK/kWh.

    Vi godtar sensoren uansett, for integrasjonen skal virke fra første minutt,
    men antakelsen skal være synlig. Bekreftelsen skrives per rolle på config
    entryet, slik at den som senere legger til en leverandørprissensor uten
    enhet får spørsmålet om den òg.
    """

    def __init__(self, issue_id: str, entry_id: str, roller: list[str]) -> None:
        """Ta vare på hvilket anlegg og hvilke roller bekreftelsen gjelder."""
        self._issue_id = issue_id
        self._entry_id = entry_id
        self._roller = roller

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> Any:
        """Send rett videre til bekreftelsessteget."""
        return await self.async_step_confirm(user_input)

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> Any:
        """Vis teksten, og skriv bekreftelsen når brukeren har svart."""
        if user_input is not None:
            self._merk_bekreftet()
            return self.async_create_entry(title="", data={})

        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self._issue_id)
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({}),
            description_placeholders=issue.translation_placeholders if issue else None,
        )

    def _merk_bekreftet(self) -> None:
        """Legg rollene varselet gjaldt inn i flagget på entryet."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            _LOGGER.debug("Fant ikke entry %s, hopper over bekreftelsen", self._entry_id)
            return
        fra_for = entry.data.get(CONF_PRISENHET_BEKREFTET)
        bekreftet = list(fra_for) if isinstance(fra_for, list) else []
        nye = [rolle for rolle in self._roller if rolle not in bekreftet]
        if not nye:
            return
        self.hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_PRISENHET_BEKREFTET: [*bekreftet, *nye]},
        )


class TariffmodusRepairFlow(RepairsFlow):
    """Lar brukeren velge mellom nettselskapets katalog og sin egen sats.

    Entryet har en energiledd-sats lagret fra før 1.17, og den er en annen enn
    den `dso.py` fører i dag. Vi vet ikke om tallet var et bevisst valg eller
    bare katalogens sats slik den så ut den gangen oppsettet ble laget, for
    oppsettsflyten lagret den på alle. Derfor spør vi framfor å gjette, og
    begge svarene er endelige: etterpå står entryet i catalog eller manual, og
    varselet kommer ikke tilbake.

    Fram til brukeren svarer regner entryet med katalogen.
    """

    def __init__(self, issue_id: str, entry_id: str) -> None:
        """Ta vare på hvilken issue og hvilket anlegg valget gjelder."""
        self._issue_id = issue_id
        self._entry_id = entry_id

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> Any:
        """Vis de to valgene som hver sin knapp."""
        issue = ir.async_get(self.hass).async_get_issue(DOMAIN, self._issue_id)
        return self.async_show_menu(
            step_id="init",
            menu_options=["folg_katalog", "behold_manual"],
            description_placeholders=issue.translation_placeholders if issue else None,
        )

    async def async_step_folg_katalog(self, _user_input: dict[str, Any] | None = None) -> Any:
        """Nettselskapets prisliste gjelder, og den lagrede satsen fjernes."""
        self._skriv_modus(TARIFFMODUS_CATALOG, fjern_satser=True)
        return self.async_create_entry(title="", data={})

    async def async_step_behold_manual(self, _user_input: dict[str, Any] | None = None) -> Any:
        """Brukerens egen sats gjelder, og katalogen rører den ikke igjen."""
        self._skriv_modus(TARIFFMODUS_MANUAL, fjern_satser=False)
        return self.async_create_entry(title="", data={})

    def _skriv_modus(self, modus: str, *, fjern_satser: bool) -> None:
        """Skriv svaret på entryet. Oppdateringen laster integrasjonen på nytt."""
        entry = self.hass.config_entries.async_get_entry(self._entry_id)
        if entry is None:
            _LOGGER.debug("Fant ikke entry %s, hopper over tariffvalget", self._entry_id)
            return
        data = {**entry.data, CONF_TARIFFMODUS: modus}
        if fjern_satser:
            data.pop(CONF_ENERGILEDD_DAG, None)
            data.pop(CONF_ENERGILEDD_NATT, None)
        self.hass.config_entries.async_update_entry(entry, data=data)


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
    if issue_id.startswith(TARIFF_ISSUE_PREFIX):
        entry_id = str((data or {}).get("entry_id") or issue_id[len(TARIFF_ISSUE_PREFIX) :])
        return TariffmodusRepairFlow(issue_id, entry_id)
    if issue_id.startswith(PRISENHET_ISSUE_PREFIX):
        entry_id = str((data or {}).get("entry_id") or issue_id[len(PRISENHET_ISSUE_PREFIX) :])
        roller_raa = (data or {}).get("roller")
        roller = str(roller_raa).split(",") if roller_raa else []
        return PrisenhetRepairFlow(issue_id, entry_id, roller)
    if issue_id.startswith(EGENDEFINERT_ISSUE_PREFIX):
        entry_id = issue_id[len(EGENDEFINERT_ISSUE_PREFIX) :]
        return EgendefinertSatserRepairFlow(issue_id, entry_id)
    return ConfirmRepairFlow()
