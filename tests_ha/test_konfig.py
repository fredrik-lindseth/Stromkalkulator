"""Tariffmodus, config v5 og tømte valgfrie felt mot ekte Home Assistant.

Unit-testene under `tests/` stubber bort `homeassistant.*`, så de kan ikke
bevise at `async_migrate_entry` faktisk kalles av HA, at options- og
reconfigure-flowene oppfører seg slik når HA selv bygger skjemaet, eller at
entitetene beholder unique-id-ene sine gjennom en reload. Det kjøres her.

Kjøres av `just test-ha target=minimum` og `target=current`.
"""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import (
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    CONF_TARIFFMODUS,
    DOMAIN,
    TARIFF_ISSUE_PREFIX,
)
from custom_components.stromkalkulator.dso import DSO_LIST

POWER_SENSOR = "sensor.konfig_power"
SPOT_SENSOR = "sensor.konfig_spot_price"
ENERGY_SENSOR = "sensor.konfig_energy"
EKSPORT_SENSOR = "sensor.konfig_export"
LEVERANDOR_SENSOR = "sensor.konfig_leverandorpris"

BKK = DSO_LIST["bkk"]


def _sett_states(hass: HomeAssistant) -> None:
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(EKSPORT_SENSOR, "0", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})
    hass.states.async_set(LEVERANDOR_SENSOR, "0.05", {"unit_of_measurement": "NOK/kWh"})
    hass.states.async_set(
        ENERGY_SENSOR,
        "1000",
        {
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )


def _basisdata(**overstyr) -> dict:
    data = {
        CONF_DSO: "bkk",
        CONF_BOLIGTYPE: "bolig",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: POWER_SENSOR,
        CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
        CONF_SPOTPRIS_INKL_MVA: False,
        CONF_AVGIFTSSONE: "standard",
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    data.update(overstyr)
    return data


async def _last(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry.runtime_data


# ---------------------------------------------------------------------------
# Migrering
# ---------------------------------------------------------------------------


async def test_v1_migreres_helt_fram_til_v5(hass: HomeAssistant) -> None:
    """Hele kjeden skal komme fram når HA selv kaller migreringen.

    v1-entryet har energiledd lagret inkl. mva, slik feltet så ut den gangen.
    Underveis konverteres det til eks. mva, spotpris-flagget settes, unique_id
    blir entry_id, og til slutt får entryet en tariffmodus.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_AVGIFTSSONE: "standard",
            CONF_ENERGILEDD_DAG: 0.50,
            CONF_ENERGILEDD_NATT: 0.30,
        },
        unique_id="stromkalkulator_sensor.gammel",
    )

    await _last(hass, entry)

    assert entry.version == 5
    assert entry.unique_id == entry.entry_id
    assert entry.data[CONF_SPOTPRIS_INKL_MVA] is False
    # 0,50 inkl. mva blir 0,3187 eks. mva, og det er en annen sats enn BKKs
    # 0,2877. Brukeren skal få velge, og imens gjelder katalogen.
    assert entry.data[CONF_TARIFFMODUS] == "legacy_unconfirmed"
    assert entry.runtime_data.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]


async def test_katalogsats_paa_v4_gir_catalog_uten_varsel(hass: HomeAssistant) -> None:
    """Den som allerede ligger riktig skal ikke merke noe som helst."""
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data=_basisdata(
            **{
                CONF_ENERGILEDD_DAG: BKK["energiledd_dag_eks_mva"],
                CONF_ENERGILEDD_NATT: BKK["energiledd_natt_eks_mva"],
            }
        ),
    )

    await _last(hass, entry)

    assert entry.data[CONF_TARIFFMODUS] == "catalog"
    assert CONF_ENERGILEDD_DAG not in entry.data
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}") is None


async def test_avvikende_sats_gir_varsel_og_katalogberegning(hass: HomeAssistant) -> None:
    """Varselet reises der satsene spriker, og katalogen gjelder mens vi venter."""
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data=_basisdata(**{CONF_ENERGILEDD_DAG: 0.40, CONF_ENERGILEDD_NATT: 0.30}),
    )

    coordinator = await _last(hass, entry)

    assert entry.data[CONF_TARIFFMODUS] == "legacy_unconfirmed"
    assert entry.data[CONF_ENERGILEDD_DAG] == 0.40
    assert coordinator.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}")
    assert issue is not None
    assert issue.is_fixable is True


# ---------------------------------------------------------------------------
# Options og reconfigure
# ---------------------------------------------------------------------------


async def test_options_fjerner_tomte_valgfrie_felt(hass: HomeAssistant) -> None:
    """Tømt energisensor, eksportmåler og leverandørpris skal forsvinne.

    Coordinatoren skal falle til riktig fallback etterpå: uten energisensor
    regnes forbruket fra effektsensoren, og baselinen er nullstilt.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{
                CONF_TARIFFMODUS: "catalog",
                CONF_ENERGY_SENSOR: ENERGY_SENSOR,
                CONF_EXPORT_POWER_SENSOR: EKSPORT_SENSOR,
                CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: LEVERANDOR_SENSOR,
            }
        ),
    )
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_SPOTPRIS_INKL_MVA: False,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        },
    )
    await hass.async_block_till_done()

    assert CONF_ENERGY_SENSOR not in entry.data
    assert CONF_EXPORT_POWER_SENSOR not in entry.data
    assert CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR not in entry.data
    coordinator = entry.runtime_data
    assert coordinator.energy_sensor is None
    assert coordinator._baseline is None


async def test_reconfigure_fjerner_tomte_valgfrie_felt(hass: HomeAssistant) -> None:
    """Samme regel gjennom reconfigure-inngangen."""
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{
                CONF_TARIFFMODUS: "catalog",
                CONF_ENERGY_SENSOR: ENERGY_SENSOR,
                CONF_EXPORT_POWER_SENSOR: EKSPORT_SENSOR,
                CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: LEVERANDOR_SENSOR,
            }
        ),
    )
    await _last(hass, entry)

    resultat = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_SPOTPRIS_INKL_MVA: False,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        },
    )
    await hass.async_block_till_done()

    assert CONF_ENERGY_SENSOR not in entry.data
    assert CONF_EXPORT_POWER_SENSOR not in entry.data
    assert CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR not in entry.data


async def test_energiledd_er_valgfritt_i_options(hass: HomeAssistant) -> None:
    """Skjemaet skal ikke kreve et energiledd på et kjent nettselskap.

    Var feltet påkrevd, ville hver lagring fryst katalogens sats på entryet,
    og da er vi tilbake til feilen dette retter.
    """
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=_basisdata(**{CONF_TARIFFMODUS: "catalog"}))
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)

    felter = {str(nokkel): nokkel for nokkel in resultat["data_schema"].schema}
    assert type(felter[CONF_ENERGILEDD_DAG]).__name__ == "Optional"
    assert type(felter[CONF_ENERGILEDD_NATT]).__name__ == "Optional"
    # Negativ prøve på samme skjema: effektsensoren er fortsatt påkrevd, så
    # testen kan ikke gå grønn på at alt er valgfritt.
    assert type(felter[CONF_POWER_SENSOR]).__name__ == "Required"


async def test_utfylt_energiledd_gir_manual(hass: HomeAssistant) -> None:
    """Et tall i overstyringsfeltet er et bevisst valg og skal bli stående."""
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=_basisdata(**{CONF_TARIFFMODUS: "catalog"}))
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_SPOTPRIS_INKL_MVA: False,
            CONF_ENERGILEDD_DAG: 0.42,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        },
    )
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "manual"
    assert entry.data[CONF_ENERGILEDD_DAG] == 0.42
    assert entry.runtime_data.energiledd_dag_eks_mva == 0.42


# ---------------------------------------------------------------------------
# Reload
# ---------------------------------------------------------------------------


def _frontend_forhaandsutfylling(data_schema) -> dict:
    """Det HA-frontenden legger i feltene når skjemaet åpnes.

    Frontenden viser `suggested_value` der den finnes, ellers feltets `default`,
    og sender verdien tilbake ved lagring selv om brukeren ikke rørte feltet. Et
    felt uten begge deler står tomt og utelates fra `user_input`. Å regne det ut
    fra det ekte skjemaet, framfor å skrive opp en ordbok for hånd, er hele
    poenget: en test som fyller inn feltene selv kan aldri se hva skjemaet
    foreslo.
    """
    utfylt: dict = {}
    for nokkel in data_schema.schema:
        foreslatt = (getattr(nokkel, "description", None) or {}).get("suggested_value")
        if foreslatt is not None:
            utfylt[str(nokkel)] = foreslatt
            continue
        standard = getattr(nokkel, "default", None)
        if standard is not None and standard is not vol.UNDEFINED:
            verdi = standard()
            if verdi is not vol.UNDEFINED:
                utfylt[str(nokkel)] = verdi
    return utfylt


async def test_legacy_skjema_foreslaar_ikke_den_utdaterte_satsen(hass: HomeAssistant) -> None:
    """Energiledd-feltet skal stå tomt for en entry som venter på svar.

    Sto den utdaterte satsen som `suggested_value`, ville frontenden sendt den
    tilbake ved en helt vanlig lagring, og `_sett_tariffmodus` ville lest et
    utfylt felt som et bevisst valg.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{
                CONF_TARIFFMODUS: "legacy_unconfirmed",
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_ENERGILEDD_NATT: 0.30,
            }
        ),
    )
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    utfylt = _frontend_forhaandsutfylling(resultat["data_schema"])

    assert CONF_ENERGILEDD_DAG not in utfylt
    assert CONF_ENERGILEDD_NATT not in utfylt
    # Negativ prøve på samme skjema: de andre feltene er fortsatt fylt ut, så
    # testen kan ikke gå grønn på at skjemaet er tomt.
    assert utfylt[CONF_POWER_SENSOR] == POWER_SENSOR
    assert utfylt[CONF_DSO] == "bkk"


async def test_manual_skjema_foreslaar_brukerens_egen_sats(hass: HomeAssistant) -> None:
    """Den andre retningen: den som har skrevet et tall skal se det igjen.

    Uten forslaget måtte en manual-bruker skrive satsen på nytt hver gang han
    var innom innstillingene for å endre noe annet, ellers falt han til
    katalogen.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(**{CONF_TARIFFMODUS: "manual", CONF_ENERGILEDD_DAG: 0.42}),
    )
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    utfylt = _frontend_forhaandsutfylling(resultat["data_schema"])

    assert utfylt[CONF_ENERGILEDD_DAG] == 0.42


async def test_lagring_uten_endring_laaser_ikke_den_utdaterte_satsen(hass: HomeAssistant) -> None:
    """Åpne innstillingene, trykk lagre, ikke rør noe: katalogen skal fortsatt gjelde.

    Dette er hele poenget med tariffmodusen. Sendte skjemaet den utdaterte
    satsen tilbake, ble entryet stående i `manual` med den gamle satsen, og
    satsvarselet forsvant fordi modusen ikke lenger var legacy. Brukeren hadde
    da mistet både satsoppdateringen og varselet som skulle fortalt ham om den,
    uten å ha gjort annet enn å se på innstillingene.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{
                CONF_TARIFFMODUS: "legacy_unconfirmed",
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_ENERGILEDD_NATT: 0.30,
            }
        ),
    )
    await _last(hass, entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}")

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    utfylt = _frontend_forhaandsutfylling(resultat["data_schema"])
    await hass.config_entries.options.async_configure(resultat["flow_id"], user_input=utfylt)
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "catalog"
    assert CONF_ENERGILEDD_DAG not in entry.data
    assert CONF_ENERGILEDD_NATT not in entry.data
    assert entry.runtime_data.energiledd_dag_eks_mva == BKK["energiledd_dag_eks_mva"]
    # Varselet er borte fordi spørsmålet er besvart med «følg katalogen»
    # (kontrakt §6), ikke fordi satsen ble låst.
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}") is None


async def test_lagring_uten_endring_beholder_manual_satsen(hass: HomeAssistant) -> None:
    """Samme handling på en manual-entry skal ikke kaste satsen.

    Speilbildet av testen over: her *skal* skjemaet sende tallet tilbake, og
    entryet skal bli stående i manual med brukerens egen sats.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{CONF_TARIFFMODUS: "manual", CONF_ENERGILEDD_DAG: 0.42, CONF_ENERGILEDD_NATT: 0.31}
        ),
    )
    await _last(hass, entry)

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    utfylt = _frontend_forhaandsutfylling(resultat["data_schema"])
    await hass.config_entries.options.async_configure(resultat["flow_id"], user_input=utfylt)
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "manual"
    assert entry.data[CONF_ENERGILEDD_DAG] == 0.42
    assert entry.runtime_data.energiledd_dag_eks_mva == 0.42


async def test_reconfigure_uten_endring_laaser_ikke_den_utdaterte_satsen(hass: HomeAssistant) -> None:
    """Reconfigure tegner samme skjema og må svare likt."""
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_basisdata(
            **{
                CONF_TARIFFMODUS: "legacy_unconfirmed",
                CONF_ENERGILEDD_DAG: 0.40,
                CONF_ENERGILEDD_NATT: 0.30,
            }
        ),
    )
    await _last(hass, entry)

    resultat = await entry.start_reconfigure_flow(hass)
    utfylt = _frontend_forhaandsutfylling(resultat["data_schema"])
    await hass.config_entries.flow.async_configure(resultat["flow_id"], user_input=utfylt)
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "catalog"
    assert CONF_ENERGILEDD_DAG not in entry.data


async def test_reload_beholder_unique_ider(hass: HomeAssistant) -> None:
    """Migrering og options skal ikke kunne skifte ut entitetene.

    Nye unique-id-er ville gitt hver bruker et nytt sett sensorer og en tom
    historikk. Entryet startes her på v4, migreres, lastes på nytt, og
    registeret sammenlignes før og etter.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=4,
        data=_basisdata(**{CONF_ENERGILEDD_DAG: 0.40}),
    )
    await _last(hass, entry)

    registry = er.async_get(hass)
    entry_id = entry.entry_id
    foer = {oppforing.unique_id for oppforing in er.async_entries_for_config_entry(registry, entry_id)}
    assert foer

    await hass.config_entries.async_reload(entry_id)
    await hass.async_block_till_done()

    etter = {oppforing.unique_id for oppforing in er.async_entries_for_config_entry(registry, entry_id)}
    assert etter == foer
    assert entry.entry_id == entry_id


# ---------------------------------------------------------------------------
# Fix-flowen på tariffvarselet
# ---------------------------------------------------------------------------


async def _tariffvarsel_flow(hass: HomeAssistant, entry: MockConfigEntry):
    """Bygg fix-flowen mot HAs ekte RepairsFlow-baseklasse.

    Unit-testene stubber baseklassen, så de kan ikke si om `async_show_menu`
    finnes eller om den tar de argumentene vi gir den. Det avgjøres her.
    """
    from custom_components.stromkalkulator.repairs import async_create_fix_flow

    flow = await async_create_fix_flow(
        hass, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}", {"entry_id": entry.entry_id}
    )
    flow.hass = hass
    return flow


async def test_tariffvarselet_viser_to_valg(hass: HomeAssistant) -> None:
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=4, data=_basisdata(**{CONF_ENERGILEDD_DAG: 0.40}))
    await _last(hass, entry)

    resultat = await (await _tariffvarsel_flow(hass, entry)).async_step_init()

    assert resultat["type"] == "menu"
    assert resultat["menu_options"] == ["folg_katalog", "behold_manual"]


async def test_folg_katalog_skriver_modus_og_laster_paa_nytt(hass: HomeAssistant) -> None:
    """«Følg katalogen» fjerner satsen, og oppdateringen utløser en reload."""
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=4, data=_basisdata(**{CONF_ENERGILEDD_DAG: 0.40}))
    await _last(hass, entry)
    flow = await _tariffvarsel_flow(hass, entry)

    await flow.async_step_folg_katalog()
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "catalog"
    assert CONF_ENERGILEDD_DAG not in entry.data
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}") is None


async def test_behold_manual_gjor_satsen_gjeldende(hass: HomeAssistant) -> None:
    """«Behold mine satser» skal faktisk slå gjennom i beregningen etterpå."""
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=4, data=_basisdata(**{CONF_ENERGILEDD_DAG: 0.40}))
    await _last(hass, entry)
    flow = await _tariffvarsel_flow(hass, entry)

    await flow.async_step_behold_manual()
    await hass.async_block_till_done()

    assert entry.data[CONF_TARIFFMODUS] == "manual"
    assert entry.data[CONF_ENERGILEDD_DAG] == 0.40
    assert entry.runtime_data.energiledd_dag_eks_mva == 0.40
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}") is None
