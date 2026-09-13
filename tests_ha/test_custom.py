"""Egendefinert nettselskap gjennom hele oppsettsreisen mot ekte Home Assistant.

Unit-testene under `tests/` driver stegene direkte med stubbede flow-baser. De
kan ikke vise at HA selv tegner skjemaet, sender brukeren videre til riktig
steg, tar imot feilnøkkelen på riktig felt eller lar entryet lastes etterpå.
Det kjøres her.

Kapasitetstrinnene for Egendefinert er brukerens egne, fordi det ikke finnes
noen prisliste å lese dem fra. Uten dem er fastleddet ukjent, ikke null, og det
er hele poenget: et beløp uten kilde ser ut som en pris. Se
docs/incidents/006-kapasitetstrinn-uten-kilde.md.

Kjøres av `just test-ha target=minimum` og `target=current`.
"""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import (
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_EGENDEFINERT_KAPASITETSTRINN,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SIKRINGSTRINN,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    CONF_TARIFFMODUS,
    DOMAIN,
)

POWER_SENSOR = "sensor.custom_power"
SPOT_SENSOR = "sensor.custom_spot_price"


def _sett_states(hass: HomeAssistant) -> None:
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": "NOK/kWh"})


async def _til_prissteget(hass: HomeAssistant, dso: str = "custom") -> dict:
    """Kjør oppsettet fram til steget etter sensorvalget."""
    resultat = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={CONF_DSO: dso, CONF_BOLIGTYPE: "bolig", CONF_HAR_NORGESPRIS: False},
    )
    assert resultat["step_id"] == "sensors"
    return await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_SPOTPRIS_INKL_MVA: False,
        },
    )


def _entry_data(**overstyr) -> dict:
    data = {
        CONF_DSO: "custom",
        CONF_BOLIGTYPE: "bolig",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: POWER_SENSOR,
        CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
        CONF_SPOTPRIS_INKL_MVA: False,
        CONF_AVGIFTSSONE: "standard",
        CONF_ENERGILEDD_DAG: 0.24,
        CONF_ENERGILEDD_NATT: 0.08,
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        CONF_TARIFFMODUS: "manual",
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
# Pricing-steget
# ---------------------------------------------------------------------------


async def test_pricing_steget_tar_imot_trinntabellen(hass: HomeAssistant) -> None:
    """Hele reisen: nettselskap, sensorer, priser, ferdig entry som laster."""
    _sett_states(hass)
    resultat = await _til_prissteget(hass)
    assert resultat["step_id"] == "pricing"

    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_AVGIFTSSONE: "standard",
            CONF_ENERGILEDD_DAG: 0.24,
            CONF_ENERGILEDD_NATT: 0.08,
            CONF_EGENDEFINERT_KAPASITETSTRINN: "2:155,5:250,10:415",
        },
    )
    assert resultat["type"] == "create_entry"
    assert resultat["data"][CONF_EGENDEFINERT_KAPASITETSTRINN] == "2:155,5:250,10:415"

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is ConfigEntryState.LOADED
    coordinator = entry.runtime_data
    assert coordinator.kapasitetstrinn == [(2.0, 155), (5.0, 250), (10.0, 415)]
    assert coordinator.data["fastledd_ukjent"] is False
    assert coordinator.data["kapasitetsledd"] == 155
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"egendefinert_fastledd_{entry.entry_id}") is None


async def test_pricing_steget_er_valgfritt(hass: HomeAssistant) -> None:
    """Uten tabell skal oppsettet fullføres, men fastleddet være ukjent."""
    _sett_states(hass)
    resultat = await _til_prissteget(hass)

    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_AVGIFTSSONE: "standard",
            CONF_ENERGILEDD_DAG: 0.24,
            CONF_ENERGILEDD_NATT: 0.08,
        },
    )
    assert resultat["type"] == "create_entry"
    assert CONF_EGENDEFINERT_KAPASITETSTRINN not in resultat["data"]

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data
    assert coordinator.data["fastledd_ukjent"] is True
    assert coordinator.data["kapasitetsledd"] == 0
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"egendefinert_fastledd_{entry.entry_id}")
    assert issue is not None
    assert issue.is_fixable is False


async def test_pricing_steget_avviser_ulesbar_tabell(hass: HomeAssistant) -> None:
    """Feilnøkkelen skal havne på riktig felt, ikke på skjemaet som helhet."""
    _sett_states(hass)
    resultat = await _til_prissteget(hass)

    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_AVGIFTSSONE: "standard",
            CONF_ENERGILEDD_DAG: 0.24,
            CONF_ENERGILEDD_NATT: 0.08,
            CONF_EGENDEFINERT_KAPASITETSTRINN: "2 kW koster 155 kr",
        },
    )
    assert resultat["type"] == "form"
    assert resultat["step_id"] == "pricing"
    assert resultat["errors"] == {CONF_EGENDEFINERT_KAPASITETSTRINN: "trinntabell_ugyldig"}


async def test_trinnfeltet_er_valgfritt_i_skjemaet(hass: HomeAssistant) -> None:
    """HA skal tegne feltet som valgfritt, ellers kan ingen la det stå tomt."""
    _sett_states(hass)
    resultat = await _til_prissteget(hass)

    felter = {str(nokkel): nokkel for nokkel in resultat["data_schema"].schema}
    assert type(felter[CONF_EGENDEFINERT_KAPASITETSTRINN]).__name__ == "Optional"
    # Negativ prøve på samme skjema: avgiftssonen er fortsatt påkrevd.
    assert type(felter[CONF_AVGIFTSSONE]).__name__ == "Required"


# ---------------------------------------------------------------------------
# Sikringssteget
# ---------------------------------------------------------------------------


async def test_sikringssteget_kommer_for_sikringsbasert_nettselskap(hass: HomeAssistant) -> None:
    """Alut fakturerer etter hovedsikring, og da kommer et annet steg enn pricing."""
    _sett_states(hass)
    resultat = await _til_prissteget(hass, dso="alut")
    assert resultat["step_id"] == "sikring"

    resultat = await hass.config_entries.flow.async_configure(
        resultat["flow_id"],
        user_input={CONF_SIKRINGSTRINN: "inntil_3x125a"},
    )
    assert resultat["type"] == "create_entry"

    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    coordinator = entry.runtime_data
    # NO4-husholdning har mva-fritak: 3500 kr/år / 12 = 292 kr/mnd.
    assert coordinator.data["kapasitetsledd"] == 292
    assert coordinator.data["fastledd_ukjent"] is False


# ---------------------------------------------------------------------------
# Innstillingene og sensorene
# ---------------------------------------------------------------------------


async def test_options_lar_brukeren_fylle_inn_tabellen(hass: HomeAssistant) -> None:
    """Veien varselet peker på: Konfigurer, fyll inn, varselet forsvinner."""
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=_entry_data())
    await _last(hass, entry)
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"egendefinert_fastledd_{entry.entry_id}") is not None

    resultat = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        resultat["flow_id"],
        user_input={
            CONF_DSO: "custom",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: POWER_SENSOR,
            CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
            CONF_SPOTPRIS_INKL_MVA: False,
            CONF_ENERGILEDD_DAG: 0.24,
            CONF_ENERGILEDD_NATT: 0.08,
            CONF_EGENDEFINERT_KAPASITETSTRINN: "2:155,5:250,10:415",
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        },
    )
    await hass.async_block_till_done()

    assert entry.data[CONF_EGENDEFINERT_KAPASITETSTRINN] == "2:155,5:250,10:415"
    assert entry.runtime_data.data["fastledd_ukjent"] is False
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"egendefinert_fastledd_{entry.entry_id}") is None


async def test_sensorene_staar_som_ukjent_uten_tabell(hass: HomeAssistant) -> None:
    """Slik brukeren faktisk ser det: Ukjent der fastleddet inngår, tall ellers.

    Bare sensorer som er slått på by default har en state å lese; trinn-nummer,
    månedlig nettleie og akkumulert kostnad er diagnostiske eller avslåtte, og
    dekkes av unit-testene i tests/test_sensor_classes.py.
    """
    _sett_states(hass)
    entry = MockConfigEntry(domain=DOMAIN, version=5, data=_entry_data())
    await _last(hass, entry)

    for entity_id in (
        "sensor.nettleie_egendefinert_capacity_tier",
        "sensor.nettleie_egendefinert_margin_to_next_tier",
        "sensor.manedlig_forbruk_monthly_grid_tariff_total",
        "sensor.manedlig_forbruk_estimated_monthly_cost",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} finnes ikke"
        assert state.state == "unknown", f"{entity_id} er {state.state}"

    # Uavhengige sensorer har tall som før: energileddet er per kWh og har
    # ingenting med fastleddet å gjøre.
    for entity_id in (
        "sensor.nettleie_egendefinert_energy_tariff",
        "sensor.manedlig_forbruk_monthly_consumption_total",
        "sensor.stromstotte_electricity_subsidy",
    ):
        state = hass.states.get(entity_id)
        assert state is not None, f"{entity_id} finnes ikke"
        assert state.state not in ("unknown", "unavailable"), f"{entity_id} er {state.state}"

    # Prisene per kWh regnes uten fastledd, men sier fra at de gjør det.
    pris = hass.states.get("sensor.nettleie_egendefinert_total_price_before_subsidy")
    assert pris is not None
    assert pris.state not in ("unknown", "unavailable")
    assert pris.attributes.get("fastledd_ukjent") is True
    assert (
        hass.states.get("sensor.nettleie_egendefinert_energy_tariff").attributes.get("fastledd_ukjent")
        is None
    )


async def test_ulesbar_tabell_gir_sitt_eget_varsel(hass: HomeAssistant) -> None:
    """En lagret tabell coordinatoren forkaster skal ikke gå stille forbi.

    Config-flowen validerer det som tastes inn, men `.storage` kan være
    håndredigert, og da regner coordinatoren fastleddet som ukjent. Sto varselet
    på «nøkkelen finnes», satt brukeren med ukjente sensorer og ingen beskjed.
    """
    _sett_states(hass)
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=5,
        data=_entry_data(**{CONF_EGENDEFINERT_KAPASITETSTRINN: "5:250,2:155"}),
    )
    await _last(hass, entry)

    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"egendefinert_fastledd_{entry.entry_id}")
    assert issue is not None
    assert issue.translation_key == "egendefinert_fastledd_ulesbar"
    assert entry.runtime_data.data["fastledd_ukjent"] is True
    assert hass.states.get("sensor.nettleie_egendefinert_capacity_tier").state == "unknown"
