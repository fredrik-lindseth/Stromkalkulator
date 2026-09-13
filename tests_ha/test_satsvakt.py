"""Satsvakten mot ekte Home Assistant: demping over omstart og deaktiverte anlegg.

Unit-testene under `tests/` stubber `homeassistant.*`, så de kan ikke si noe om
hva HA faktisk tar vare på når den lagrer et repair-varsel. Og det er nettopp
der forrige utgave av vakten røk: den la året varselet gjaldt i `data` på issuen
og trodde det sto der etter en omstart, men `IssueEntry.to_json` skriver bare
`created`, `dismissed_version`, `domain`, `is_persistent` og `issue_id` for et
varsel uten `is_persistent`, og lastingen leser dem inn igjen med `data=None`.
Vakten leste da et tomt felt, dømte det som et nytt år, slettet varselet, og
slettingen tok brukerens «ignorer» med seg.

`_omstart` gjør derfor det HA gjør ved oppstart: skriver registeret til lager,
kaster det (også ut av lru_cachen i `ir.async_get`, se `_omstart`) og bygger et
nytt fra lageret. Testene asserter `active is False` etter omstarten, for det er
tilstanden bare et varsel som er lastet fra lager kan ha; et register hentet ut
av minnet igjen ville stått med `active=True` og ikke målt noen omstart. Hvert
varsel prøves i begge retninger.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry, flush_store

from custom_components.stromkalkulator import (
    _SATSVAKT_UNSUB,
    NORGESPRIS_ISSUE_PREFIX,
    SATSER_ISSUE_ID,
    _sjekk_satsvakt,
)
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
    SATSER_GJELDER_AAR,
)
from custom_components.stromkalkulator.dso import DSO_LIST

OSLO = ZoneInfo("Europe/Oslo")
POWER_SENSOR = "sensor.satsvakt_power"
SPOT_SENSOR = "sensor.satsvakt_spot_price"

# Året varselet handler om. Ett år etter satsene er verifisert for, altså det
# første året vakten skal si fra.
UTDATERT = datetime(SATSER_GJELDER_AAR + 1, 1, 1, 0, 5, tzinfo=OSLO)
SENERE_SAMME_AAR = datetime(SATSER_GJELDER_AAR + 1, 6, 1, 0, 5, tzinfo=OSLO)
NESTE_AAR = datetime(SATSER_GJELDER_AAR + 2, 1, 2, 0, 5, tzinfo=OSLO)


def _entry_data(*, norgespris: bool = False) -> dict:
    dso = DSO_LIST["bkk"]
    return {
        CONF_DSO: "bkk",
        CONF_BOLIGTYPE: "bolig",
        CONF_HAR_NORGESPRIS: norgespris,
        CONF_POWER_SENSOR: POWER_SENSOR,
        CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
        CONF_SPOTPRIS_INKL_MVA: False,
        CONF_AVGIFTSSONE: "standard",
        CONF_ENERGILEDD_DAG: dso["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: dso["energiledd_natt_eks_mva"],
    }


def _legg_til(hass: HomeAssistant, *, norgespris: bool = False, disabled: bool = False) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_entry_data(norgespris=norgespris),
        version=5,
        disabled_by=ConfigEntryDisabler.USER if disabled else None,
    )
    entry.add_to_hass(hass)
    return entry


async def _omstart(hass: HomeAssistant) -> None:
    """Bytt ut issue-registeret med et som er lastet fra lager, slik HA gjør.

    Dette er hele poenget med filen: registeret i minnet vet mer enn det som
    overlever en omstart, så en test som bare kaller vakten to ganger på rad
    ville sagt grønt om feilen som felte forrige utgave.

    Fire steg, og alle fire trengs:

    1. `flush_store` tvinger ut den utsatte lagringen. `async_schedule_save`
       venter 10 eller 180 sekunder, så uten dette ville lageret vært tomt eller
       stått på et eldre innhold.
    2. `hass.data.pop(ir.DATA_REGISTRY)` fjerner det gamle registeret fra
       hass.data, som er der `async_get` slår opp.
    3. `ir.async_get.cache_clear()` er steget som er lett å hoppe over, og det
       som felte forrige utgave av denne helperen. `async_get` er
       `@singleton(DATA_REGISTRY)`, og singleton legger en
       `functools.lru_cache(maxsize=1)` utenpå oppslaget i hass.data. Å sette
       `hass.data[ir.DATA_REGISTRY]` til et friskt register er derfor uvirksomt:
       cachen leverer det gamle objektet videre, og testene måler ingen omstart.
       Uten dette steget ville steg 4 lastet lageret inn i det gamle objektet og
       latt hass.data stå uten nøkkelen, altså en tilstand HA aldri er i.
    4. `ir.async_load(hass)` bygger et nytt register og leser lageret. Modulens
       egen funksjon brukes framfor `IssueRegistry(hass).async_load()`, siden
       signaturen på klassemetoden er ulik i 2025.1 og 2026.9.

    Etterpå er varslene lastet som HA laster ikke-persistente issues: `active`
    er False, `data` er None, og `created` og `dismissed_version` står som før.
    Testene asserter `active is False` nettopp for å se at det faktisk ble
    lastet fra lager og ikke bare hentet ut av minnet igjen.
    """
    await flush_store(ir.async_get(hass)._store)
    hass.data.pop(ir.DATA_REGISTRY)
    ir.async_get.cache_clear()
    await ir.async_load(hass)


async def _ignorer(hass: HomeAssistant, issue_id: str) -> None:
    ir.async_get(hass).async_ignore(DOMAIN, issue_id, True)


def _issue(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id)


def _lastet_fra_lager(hass: HomeAssistant, issue_id: str) -> ir.IssueEntry:
    """Hent et varsel og slå fast at det kom fra lageret, ikke fra minnet.

    HA laster ikke-persistente issues med `active=False`. Sto registeret igjen i
    minnet etter `_omstart`, ville varselet vært aktivt, og testen som følger
    ville ikke målt noen omstart.
    """
    issue = _issue(hass, issue_id)
    assert issue is not None, f"{issue_id} skulle overlevd omstarten"
    assert issue.active is False, "omstarten var ikke ekte: varselet står fortsatt aktivt"
    return issue


# ---------------------------------------------------------------------------
# Premisset: hva HA faktisk tar vare på
# ---------------------------------------------------------------------------


async def test_data_forsvinner_over_omstart_men_created_staar(hass: HomeAssistant) -> None:
    """Grunnlaget for hele løsningen, målt framfor antatt.

    Går denne rød, er det HA som har endret seg, og da må utløpsnøkkelen velges
    på nytt.
    """
    await hass.config.async_set_time_zone("Europe/Oslo")
    _legg_til(hass)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()

    foer = _issue(hass, SATSER_ISSUE_ID)
    assert foer is not None
    assert foer.created.astimezone(OSLO).year == UTDATERT.year

    await _omstart(hass)

    etter = _issue(hass, SATSER_ISSUE_ID)
    assert etter is not None
    assert etter is not foer, "registeret skal være bygget på nytt, ikke gjenbrukt"
    assert etter.active is False, "et varsel lastet fra lager er inaktivt til det reises igjen"
    assert etter.data is None, "HA lagrer ikke data for ikke-persistente issues"
    assert etter.created == foer.created, "created er det eneste tidsfeltet som holder over omstart"


# ---------------------------------------------------------------------------
# Dempingen over en omstart
# ---------------------------------------------------------------------------


async def test_ignorert_satsvarsel_staar_ignorert_etter_omstart(hass: HomeAssistant) -> None:
    """Brukeren trykket «ignorer» i januar. Det skal holde ut året."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    _legg_til(hass)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()
    await _ignorer(hass, SATSER_ISSUE_ID)
    dempet = _issue(hass, SATSER_ISSUE_ID)
    assert dempet is not None and dempet.dismissed_version is not None

    await _omstart(hass)
    assert _lastet_fra_lager(hass, SATSER_ISSUE_ID).dismissed_version is not None

    with freeze_time(SENERE_SAMME_AAR):
        _sjekk_satsvakt(hass, SENERE_SAMME_AAR)
    await hass.async_block_till_done()

    etter = _issue(hass, SATSER_ISSUE_ID)
    assert etter is not None, "varselet skal fortsatt finnes"
    assert etter.dismissed_version is not None, "dempingen røk over omstarten"


async def test_ignorert_norgespris_varsel_staar_ignorert_etter_omstart(hass: HomeAssistant) -> None:
    """Samme prøve på anleggsvarselet."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    entry = _legg_til(hass, norgespris=True)
    issue_id = f"{NORGESPRIS_ISSUE_PREFIX}{entry.entry_id}"

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()
    await _ignorer(hass, issue_id)

    await _omstart(hass)
    assert _lastet_fra_lager(hass, issue_id).dismissed_version is not None

    with freeze_time(SENERE_SAMME_AAR):
        _sjekk_satsvakt(hass, SENERE_SAMME_AAR)
    await hass.async_block_till_done()

    etter = _issue(hass, issue_id)
    assert etter is not None
    assert etter.dismissed_version is not None


async def test_dempingen_taaler_flere_omstarter_samme_aar(hass: HomeAssistant) -> None:
    """Én omstart er ikke et bevis, og en HA-installasjon startes mange ganger i året."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    _legg_til(hass)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()
    await _ignorer(hass, SATSER_ISSUE_ID)

    for _ in range(3):
        await _omstart(hass)
        _lastet_fra_lager(hass, SATSER_ISSUE_ID)
        with freeze_time(SENERE_SAMME_AAR):
            _sjekk_satsvakt(hass, SENERE_SAMME_AAR)
        await hass.async_block_till_done()

    etter = _issue(hass, SATSER_ISSUE_ID)
    assert etter is not None
    assert etter.dismissed_version is not None


async def test_dempingen_utloper_ved_neste_aarsskifte_over_omstart(hass: HomeAssistant) -> None:
    """Motsatt vei: et nytt år er et nytt varsel, og fjorårets «ignorer» følger ikke med."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    _legg_til(hass)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()
    await _ignorer(hass, SATSER_ISSUE_ID)

    await _omstart(hass)
    _lastet_fra_lager(hass, SATSER_ISSUE_ID)

    with freeze_time(NESTE_AAR):
        _sjekk_satsvakt(hass, NESTE_AAR)
    await hass.async_block_till_done()

    etter = _issue(hass, SATSER_ISSUE_ID)
    assert etter is not None, "varselet skal reises på nytt for det nye året"
    assert etter.dismissed_version is None, "dempingen skulle utløpt med årsskiftet"
    assert etter.created.astimezone(OSLO).year == NESTE_AAR.year


# ---------------------------------------------------------------------------
# Deaktiverte anlegg
# ---------------------------------------------------------------------------


async def test_deaktivert_anlegg_faar_ikke_norgespris_varsel(hass: HomeAssistant) -> None:
    """Et anlegg brukeren har slått av regner ingenting, og skal ikke mase."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    av = _legg_til(hass, norgespris=True, disabled=True)
    paa = _legg_til(hass, norgespris=True)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()

    assert _issue(hass, f"{NORGESPRIS_ISSUE_PREFIX}{av.entry_id}") is None
    assert _issue(hass, f"{NORGESPRIS_ISSUE_PREFIX}{paa.entry_id}") is not None


async def test_ingen_varsel_naar_alle_anlegg_er_deaktiverte(hass: HomeAssistant) -> None:
    """Ingen påslåtte anlegg er ingen å varsle, like fullt som ingen anlegg."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    _legg_til(hass, norgespris=True, disabled=True)

    with freeze_time(UTDATERT):
        _sjekk_satsvakt(hass, UTDATERT)
    await hass.async_block_till_done()

    assert _issue(hass, SATSER_ISSUE_ID) is None


async def test_vakten_meldes_av_naar_bare_deaktivert_anlegg_staar_igjen(hass: HomeAssistant) -> None:
    """Registeret er ikke tomt, men det er ingen igjen å holde vakt for.

    Telte avmeldingen alle entries i registeret, ville den daglige timeren stått
    og tikket for alltid. HAs testrigg feller det som en «lingering timer», og
    på en ekte installasjon er det en vakt som aldri kan si noe fornuftig.
    """
    await hass.config.async_set_time_zone("Europe/Oslo")
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})

    _legg_til(hass, disabled=True)
    aktiv = _legg_til(hass)

    assert await hass.config_entries.async_setup(aktiv.entry_id)
    await hass.async_block_till_done()
    assert aktiv.state is ConfigEntryState.LOADED
    assert _SATSVAKT_UNSUB in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(aktiv.entry_id)
    await hass.async_block_till_done()

    assert _SATSVAKT_UNSUB not in hass.data[DOMAIN]


async def test_vakten_staar_saa_lenge_et_paaslaatt_anlegg_er_igjen(hass: HomeAssistant) -> None:
    """Motsatt vei: det andre anlegget holder vakten i live."""
    await hass.config.async_set_time_zone("Europe/Oslo")
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})

    foerste = _legg_til(hass)
    andre = _legg_til(hass)

    # Å sette opp det ene setter opp hele domenet, altså begge anleggene.
    assert await hass.config_entries.async_setup(foerste.entry_id)
    await hass.async_block_till_done()
    assert andre.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(foerste.entry_id)
    await hass.async_block_till_done()

    assert _SATSVAKT_UNSUB in hass.data[DOMAIN]

    # Rydd etter oss, så testriggen ikke ser en timer som lever videre.
    assert await hass.config_entries.async_unload(andre.entry_id)
    await hass.async_block_till_done()
    assert _SATSVAKT_UNSUB not in hass.data[DOMAIN]
