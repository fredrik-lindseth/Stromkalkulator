"""Inputadapteren og energibaselinen mot ekte Home Assistant.

Unit-testene under `tests/` stubber bort `homeassistant.*`, så de kan ikke
bevise at entity-registeret, Store-filen og config-flowen faktisk oppfører seg
slik koden antar. Kildebindingen på baselinen hviler på `unique_id` fra
entity-registeret, og runtime-enhetsendringen hviler på at HA leverer
`unit_of_measurement` slik vi leser den. Begge deler kjøres her, ekte.

Kjøres av `just test-ha target=minimum` og `target=current`.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.stromkalkulator.const import (
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DOMAIN,
)
from custom_components.stromkalkulator.dso import DSO_LIST
from custom_components.stromkalkulator.inputadapter import BASELINE_NOKKEL, Gyldig, Utilgjengelig

POWER_SENSOR = "sensor.input_power"
SPOT_SENSOR = "sensor.input_spot_price"
ENERGY_SENSOR = "sensor.input_energy"


def _entry_data(**overstyr) -> dict:
    dso = DSO_LIST["bkk"]
    data = {
        CONF_DSO: "bkk",
        CONF_BOLIGTYPE: "bolig",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: POWER_SENSOR,
        CONF_SPOT_PRICE_SENSOR: SPOT_SENSOR,
        CONF_ENERGY_SENSOR: ENERGY_SENSOR,
        CONF_SPOTPRIS_INKL_MVA: False,
        CONF_AVGIFTSSONE: "standard",
        CONF_ENERGILEDD_DAG: dso["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: dso["energiledd_natt_eks_mva"],
    }
    data.update(overstyr)
    return data


def _sett_states(hass: HomeAssistant, *, energi="1000", energienhet="kWh", speilenhet="NOK/kWh"):
    hass.states.async_set(POWER_SENSOR, "1500", {"unit_of_measurement": "W", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "1.20", {"unit_of_measurement": speilenhet})
    hass.states.async_set(
        ENERGY_SENSOR,
        energi,
        {
            "unit_of_measurement": energienhet,
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )


def _registrer_energimaaler(hass: HomeAssistant, unique_id: str) -> None:
    """Gi energisensoren en registeroppføring, slik en ekte integrasjon gjør.

    Det er `unique_id` herfra baselinen bindes til. Uten oppføring finnes ingen
    fysisk identitet, og da faller sammenligningen tilbake på entity-id-en.
    """
    registry = er.async_get(hass)
    registry.async_get_or_create("sensor", "test_ams", unique_id, suggested_object_id="input_energy")


async def _last(hass: HomeAssistant, entry: MockConfigEntry):
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry.runtime_data


async def test_enhetene_normaliseres_gjennom_ekte_states(hass: HomeAssistant) -> None:
    """kW, MWh og øre/kWh skal bli W, kWh og NOK/kWh på vei inn."""
    hass.states.async_set(POWER_SENSOR, "1.5", {"unit_of_measurement": "kW", "device_class": "power"})
    hass.states.async_set(SPOT_SENSOR, "120", {"unit_of_measurement": "øre/kWh"})
    hass.states.async_set(
        ENERGY_SENSOR,
        "1.0",
        {"unit_of_measurement": "MWh", "device_class": "energy", "state_class": "total"},
    )

    coordinator = await _last(hass, MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4))
    await coordinator.async_refresh()

    resultater = coordinator._input_resultater
    assert resultater["effekt"].verdi == 1500.0
    assert resultater["spotpris"].verdi == 1.20
    assert resultater["energi"].verdi == 1000.0
    assert coordinator.data["current_power_kw"] == 1.5


async def test_kildebytte_gir_delta_null_og_beholder_maanedsdata(hass: HomeAssistant) -> None:
    """1000 til 1020 på en ny måler er ikke 20 kWh forbruk.

    Dette er reproen fra stromkalkulator-40mbs7k, kjørt hele veien gjennom
    lagring og oppfriskning mot ekte HA.
    """
    _registrer_energimaaler(hass, "gammel-maaler")
    _sett_states(hass, energi="1000")

    coordinator = await _last(hass, MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4))
    await coordinator.async_refresh()

    # Litt ekte forbruk på den gamle måleren, så vi har noe å miste.
    hass.states.async_set(
        ENERGY_SENSOR,
        "1005",
        {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    )
    await coordinator.async_refresh()
    forbruk_for = coordinator.data["monthly_consumption_total_kwh"]
    assert forbruk_for > 0

    # Målerbytte: ny fysisk kilde på samme entity-id, og telleren står høyere.
    registry = er.async_get(hass)
    registry.async_remove(ENERGY_SENSOR)
    # Staten må vekk sammen med registeroppføringen, ellers gir HA den nye
    # måleren entity-id-en `_2` og reproen blir en annen enn den ekte.
    hass.states.async_remove(ENERGY_SENSOR)
    _registrer_energimaaler(hass, "ny-maaler")
    hass.states.async_set(
        ENERGY_SENSOR,
        "1020",
        {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    )
    await coordinator.async_refresh()

    assert coordinator.data["monthly_consumption_total_kwh"] == forbruk_for
    assert coordinator._baseline.value_kwh == 1020.0
    assert coordinator._baseline.source_identity is not None


async def test_samme_kilde_etter_omstart_gjenopptar(hass: HomeAssistant) -> None:
    """Baselinen overlever en reload av entryet, og forbruket telles videre."""
    _registrer_energimaaler(hass, "maaler-1")
    _sett_states(hass, energi="1000")

    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4)
    coordinator = await _last(hass, entry)
    await coordinator.async_refresh()
    assert coordinator._baseline.value_kwh == 1000.0

    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    gjenopptatt = entry.runtime_data

    hass.states.async_set(
        ENERGY_SENSOR,
        "1002.5",
        {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    )
    await gjenopptatt.async_refresh()

    assert gjenopptatt.data["monthly_consumption_total_kwh"] == 2.5
    assert gjenopptatt._baseline.value_kwh == 1002.5


async def test_baselinen_lagres_paa_skjema_v2(hass: HomeAssistant) -> None:
    """Store-filen skal ha kilde og normaliserte kWh, ikke en bar sensorverdi."""
    _registrer_energimaaler(hass, "maaler-1")
    _sett_states(hass, energi="1000000", energienhet="Wh")

    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4)
    coordinator = await _last(hass, entry)
    await coordinator.async_refresh()
    hass.states.async_set(
        ENERGY_SENSOR,
        "1001000",
        {"unit_of_measurement": "Wh", "device_class": "energy", "state_class": "total_increasing"},
    )
    await coordinator.async_refresh()
    await coordinator._save_stored_data()

    lagret = await coordinator._store.async_load()
    baseline = lagret[BASELINE_NOKKEL]
    assert baseline["schema_version"] == 2
    assert baseline["value_kwh"] == 1001.0, "verdien skal lagres i kWh, ikke i sensorens egen enhet"
    assert baseline["source_identity"]


async def test_runtime_enhetsendring_melder_seg(hass: HomeAssistant) -> None:
    """En sensor som bytter til EUR under drift er en ekte feil, ikke et utfall."""
    _sett_states(hass)
    coordinator = await _last(hass, MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4))
    await coordinator.async_refresh()
    assert not [p for p in coordinator.data["input_problemer"] if p["type"] == "enhet"]

    hass.states.async_set(SPOT_SENSOR, "0.11", {"unit_of_measurement": "EUR/kWh"})
    await coordinator.async_refresh()

    problem = next(p for p in coordinator.data["input_problemer"] if p["type"] == "enhet")
    assert problem["input"] == "spotpris"
    assert problem["raa_enhet"] == "EUR/kWh"


async def test_slettet_entitet_feller_ikke_oppdateringen(hass: HomeAssistant) -> None:
    """Entryet skal stå lastet, og energien skal telle videre."""
    _sett_states(hass, energi="1000")
    entry = MockConfigEntry(domain=DOMAIN, data=_entry_data(), version=4)
    coordinator = await _last(hass, entry)
    await coordinator.async_refresh()

    hass.states.async_remove(POWER_SENSOR)
    hass.states.async_set(
        ENERGY_SENSOR,
        "1003",
        {"unit_of_measurement": "kWh", "device_class": "energy", "state_class": "total_increasing"},
    )
    await coordinator.async_refresh()

    assert entry.state is ConfigEntryState.LOADED
    assert coordinator.last_update_success is True
    assert isinstance(coordinator._input_resultater["effekt"], Utilgjengelig)
    assert coordinator._input_resultater["effekt"].grunn == "finnes_ikke"
    assert isinstance(coordinator._input_resultater["energi"], Gyldig)
    assert coordinator.data["monthly_consumption_total_kwh"] == 3.0
