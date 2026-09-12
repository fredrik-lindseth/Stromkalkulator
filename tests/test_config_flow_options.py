"""Tests for NettleieOptionsFlow and config flow duplicate sensor guards.

Covers:
- Options flow: valid reconfiguration merges data and creates entry
- Options flow: duplicate power sensor across entries is rejected
- Options flow: same-entry power sensor is allowed (not a conflict)
- Config flow async_step_sensors: duplicate power sensor guard
- MaanedligNorgesprisKompensasjonSensor and ForrigeMaanedNorgesprisKompensasjonSensor
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import MagicMock

import pytest

# ---- Mock voluptuous before config_flow import ----
# voluptuous is not installed in the test environment, so we provide a
# functional stub that lets config_flow.py parse without errors.
if "voluptuous" not in sys.modules:
    _vol = MagicMock()
    # vol.Schema(dict) must return a callable; the actual schema is unused in tests
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    # vol.Required / vol.Optional used as dict keys - must return hashable values
    _vol.Required = lambda name, **kw: name
    _vol.Optional = lambda name, **kw: name
    sys.modules["voluptuous"] = _vol

# ---- HA sensor/entity/coordinator stubs live in conftest._install_ha_class_stubs ----

# ---- Provide real base classes for ConfigFlow / OptionsFlow ----
# config_entries is a MagicMock. Inheriting from a MagicMock attribute
# produces MagicMock instances, not real classes. We need proper stubs.
#
# Critical: `from homeassistant import config_entries` resolves via
# getattr(sys.modules['homeassistant'], 'config_entries'), NOT via
# sys.modules['homeassistant.config_entries']. So we must set the
# attribute on the parent mock AND update the sys.modules entry.


class _FakeConfigFlow:
    """Stub for config_entries.ConfigFlow."""

    def __init_subclass__(cls, domain=None, **kwargs):
        pass

    def __init__(self):
        self._data = {}


class _FakeOptionsFlow:
    """Stub for config_entries.OptionsFlow."""

    pass


class _FakeConfigEntry:
    """Stub for type annotations."""

    pass


_ce_mod = sys.modules["homeassistant.config_entries"]
_ce_mod.ConfigFlow = _FakeConfigFlow
_ce_mod.OptionsFlow = _FakeOptionsFlow
_ce_mod.ConfigEntry = _FakeConfigEntry

# Wire the same object as an attribute on the parent homeassistant mock
sys.modules["homeassistant"].config_entries = _ce_mod

# callback decorator (used by @callback on async_get_options_flow)
sys.modules["homeassistant.core"].callback = lambda f: f

# ---- selector stubs ----
# _dso_options() calls selector.SelectOptionDict(value=..., label=...) and
# sorts the results by x["label"]. MagicMock returns can't be sorted, so we
# need SelectOptionDict to return a real dict.
_selector_mod = sys.modules["homeassistant.helpers.selector"]
_selector_mod.SelectOptionDict = lambda **kw: kw
# Wire selector as attribute on helpers mock (same parent-attribute issue)
sys.modules["homeassistant.helpers"].selector = _selector_mod


from stromkalkulator.const import (  # noqa: E402
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGI_FROSSEN_TIMER,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_TARIFFMODUS,
    DEFAULT_ENERGI_FROSSEN_TIMER,
    DOMAIN,
)
from stromkalkulator.sensor import (  # noqa: E402
    ForrigeMaanedNorgesprisKompensasjonSensor,
    MaanedligNorgesprisKompensasjonSensor,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reload_config_flow():
    """Reload config_flow module with proper base class stubs."""
    # Ensure stubs are in place before reload
    _ce_mod.ConfigFlow = _FakeConfigFlow
    _ce_mod.OptionsFlow = _FakeOptionsFlow
    import stromkalkulator.config_flow as cf_mod

    importlib.reload(cf_mod)
    return cf_mod


def _make_entry(
    entry_id: str = "entry1",
    power_sensor: str = "sensor.power_1",
    dso: str = "bkk",
) -> MagicMock:
    """Create a mock config entry with standard data."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.unique_id = f"{DOMAIN}_{power_sensor}"
    entry.data = {
        CONF_DSO: dso,
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: "standard",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: power_sensor,
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_ENERGILEDD_DAG: 0.4613,
        CONF_ENERGILEDD_NATT: 0.2329,
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    return entry


def _full_entry(entry_id: str = "entry1", dso: str = "bkk") -> MagicMock:
    """Entry med alle tre valgfrie bindingene satt, klar til å tømmes."""
    entry = _make_entry(entry_id=entry_id, dso=dso)
    entry.data = {
        **entry.data,
        CONF_ENERGY_SENSOR: "sensor.energy_1",
        CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: "sensor.leverandorpris",
        CONF_EXPORT_POWER_SENSOR: "sensor.export_power",
    }
    return entry


def _skjema_uten_valgfrie() -> dict:
    """Submit der de valgfrie feltene er tømt.

    Home Assistant sender ikke med et tomt `vol.Optional`-felt i det hele tatt,
    så et tømt felt ser ut som et felt brukeren aldri rørte. Det er nettopp
    derfor `{**current, **user_input}` ikke holder.
    """
    return {
        CONF_DSO: "bkk",
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: "standard",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: "sensor.power_1",
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }


def _rolle_state(entity_id: str) -> MagicMock:
    """State med en enhet og state_class som passer rollen entity-id-en antyder."""
    state = MagicMock()
    state.last_updated = None
    if "power" in entity_id or "export" in entity_id:
        state.state = "5000"
        state.attributes = {"unit_of_measurement": "W"}
    elif "energy" in entity_id:
        state.state = "1000"
        state.attributes = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}
    else:
        state.state = "1.2"
        state.attributes = {"unit_of_measurement": "NOK/kWh"}
    return state


def _make_options_flow(config_entry: MagicMock, existing_entries: list[MagicMock] | None = None):
    """Set up an options flow instance with mocked hass."""
    cf_mod = _reload_config_flow()

    flow = cf_mod.NettleieOptionsFlow()
    flow.config_entry = config_entry
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries.return_value = existing_entries or [config_entry]
    flow.hass.config_entries.async_update_entry = MagicMock()

    # async_create_entry / async_show_form return result dicts
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry", "title": "", "data": {}})
    flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "init"})

    return flow


def _make_config_flow(existing_entries: list[MagicMock] | None = None):
    """Set up a config flow instance with mocked hass for async_step_sensors."""
    cf_mod = _reload_config_flow()

    flow = cf_mod.NettleieConfigFlow()
    flow.hass = MagicMock()

    # States: begge sensorene finnes, med enheter som passer rollen sin.
    def get_state(entity_id):
        state = MagicMock()
        state.last_updated = None
        if "power" in entity_id or "export" in entity_id:
            state.state = "5000"
            state.attributes = {"unit_of_measurement": "W"}
        elif "energy" in entity_id:
            state.state = "1000"
            state.attributes = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}
        else:
            state.state = "1.2"
            state.attributes = {"unit_of_measurement": "NOK/kWh"}
        return state

    flow.hass.states.get = MagicMock(side_effect=get_state)
    flow._async_current_entries = MagicMock(return_value=existing_entries or [])
    flow._data = {CONF_DSO: "bkk"}

    # Mock the methods called after successful validation
    flow.async_set_unique_id = MagicMock()
    flow._abort_if_unique_id_configured = MagicMock()
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "sensors"})

    return flow


def _make_reconfigure_flow(config_entry: MagicMock, existing_entries: list[MagicMock] | None = None):
    """Set up a config flow instance for async_step_reconfigure.

    conftest stubber HA, så _get_reconfigure_entry og async_update_reload_and_abort
    finnes ikke på baseklassen. Vi stubber dem på instansen (samme mønster som
    _make_options_flow stubber async_create_entry) slik at den delte skjema-,
    validerings- og DSO-avlednings-logikken kan drives. Full HA-integrasjon
    (menyoppføring, faktisk reload) gjenstår å verifisere mot ekte HA.
    """
    cf_mod = _reload_config_flow()

    flow = cf_mod.NettleieConfigFlow()
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries.return_value = existing_entries or [config_entry]

    def get_state(entity_id):
        state = MagicMock()
        state.last_updated = None
        if "power" in entity_id or "export" in entity_id:
            state.state = "5000"
            state.attributes = {"unit_of_measurement": "W"}
        elif "energy" in entity_id:
            state.state = "1000"
            state.attributes = {"unit_of_measurement": "kWh", "state_class": "total_increasing"}
        else:
            state.state = "1.2"
            state.attributes = {"unit_of_measurement": "NOK/kWh"}
        return state

    flow.hass.states.get = MagicMock(side_effect=get_state)
    flow._get_reconfigure_entry = MagicMock(return_value=config_entry)
    flow.async_update_reload_and_abort = MagicMock(
        return_value={"type": "abort", "reason": "reconfigure_successful"}
    )
    flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "reconfigure"})
    return flow


def _make_sensor_entry() -> MagicMock:
    """Create a mock config entry for sensor tests."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {CONF_DSO: "bkk", CONF_AVGIFTSSONE: "standard"}
    return entry


# ===========================================================================
# 1. NettleieOptionsFlow.async_step_init - valid reconfiguration
# ===========================================================================


class TestOptionsFlowValidReconfiguration:
    """Options flow merges user_input with existing data and creates entry."""

    def test_valid_reconfiguration_updates_entry(self):
        entry = _make_entry()
        flow = _make_options_flow(entry)

        user_input = {
            CONF_DSO: "custom",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "nord_norge",
            CONF_HAR_NORGESPRIS: True,
            CONF_POWER_SENSOR: "sensor.power_1",
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.3500,
            CONF_ENERGILEDD_NATT: 0.1500,
            CONF_KAPASITET_VARSEL_TERSKEL: 3.0,
        }

        asyncio.run(flow.async_step_init(user_input))

        # async_update_entry should have been called with merged data
        flow.hass.config_entries.async_update_entry.assert_called_once()
        call_args = flow.hass.config_entries.async_update_entry.call_args
        updated_data = call_args.kwargs.get("data") or call_args[1].get("data") or call_args[0][1]
        assert updated_data[CONF_DSO] == "custom"
        assert updated_data[CONF_AVGIFTSSONE] == "nord_norge"
        assert updated_data[CONF_ENERGILEDD_DAG] == 0.3500
        assert updated_data[CONF_ENERGILEDD_NATT] == 0.1500
        assert updated_data[CONF_HAR_NORGESPRIS] is True

        # Flow should create entry (completion)
        flow.async_create_entry.assert_called_once()


class TestFrossenTerskelFelt:
    """Frossen-terskelen skal kunne settes fra både options og reconfigure.

    Feltet er konfigurerbart fordi en hytte med hovedbryteren av står stille i
    dagevis uten at noe er galt. Skjemaet bygges av samme funksjon for begge
    inngangene, så én sjekk dekker begge.
    """

    def test_feltet_finnes_i_skjemaet(self):
        cf_mod = _reload_config_flow()
        felter = cf_mod._config_data_schema(_make_entry().data)
        assert CONF_ENERGI_FROSSEN_TIMER in felter

    def test_verdien_lagres_paa_entryet(self):
        entry = _make_entry()
        flow = _make_options_flow(entry)

        user_input = {
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: "sensor.power_1",
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.4613,
            CONF_ENERGILEDD_NATT: 0.2329,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
            CONF_ENERGI_FROSSEN_TIMER: 12,
        }
        asyncio.run(flow.async_step_init(user_input))

        call_args = flow.hass.config_entries.async_update_entry.call_args
        updated_data = call_args.kwargs.get("data") or call_args[1].get("data") or call_args[0][1]
        assert updated_data[CONF_ENERGI_FROSSEN_TIMER] == 12

    def test_entry_uten_feltet_bruker_default(self):
        """Eksisterende oppsett har ikke feltet, og skal lande på tre timer."""
        entry = _make_entry()
        assert CONF_ENERGI_FROSSEN_TIMER not in entry.data
        assert DEFAULT_ENERGI_FROSSEN_TIMER == 3.0


# ===========================================================================
# 2. NettleieOptionsFlow.async_step_init - duplicate power sensor
# ===========================================================================


class TestOptionsFlowDuplicatePowerSensor:
    """Changing power sensor to one used by another entry is rejected."""

    def test_duplicate_power_sensor_returns_error(self):
        entry1 = _make_entry(entry_id="entry1", power_sensor="sensor.power_1")
        entry2 = _make_entry(entry_id="entry2", power_sensor="sensor.power_2")

        flow = _make_options_flow(entry2, existing_entries=[entry1, entry2])

        # Try to change entry2's power sensor to entry1's sensor
        user_input = {
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: "sensor.power_1",  # Already used by entry1
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.4613,
            CONF_ENERGILEDD_NATT: 0.2329,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        }

        asyncio.run(flow.async_step_init(user_input))

        # Should NOT update the entry
        flow.hass.config_entries.async_update_entry.assert_not_called()
        flow.async_create_entry.assert_not_called()

        # Should show form with error
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"][CONF_POWER_SENSOR] == "already_configured"


# ===========================================================================
# 3. NettleieOptionsFlow.async_step_init - same entry power sensor OK
# ===========================================================================


class TestOptionsFlowSameEntrySensorAllowed:
    """Submitting the same power sensor the entry already uses is not a conflict."""

    def test_same_power_sensor_is_allowed(self):
        entry = _make_entry(entry_id="entry1", power_sensor="sensor.power_1")
        flow = _make_options_flow(entry, existing_entries=[entry])

        user_input = {
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: "sensor.power_1",  # Same as current - should be OK
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.4613,
            CONF_ENERGILEDD_NATT: 0.2329,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        }

        asyncio.run(flow.async_step_init(user_input))

        # Should succeed: update entry and create entry
        flow.hass.config_entries.async_update_entry.assert_called_once()
        flow.async_create_entry.assert_called_once()


# ===========================================================================
# 4. async_step_sensors - duplicate power sensor guard
# ===========================================================================


class TestConfigFlowSensorsDuplicateGuard:
    """Config flow async_step_sensors rejects power sensor already in use."""

    def test_duplicate_power_sensor_in_new_flow(self):
        existing = _make_entry(entry_id="existing", power_sensor="sensor.power_used")
        flow = _make_config_flow(existing_entries=[existing])

        user_input = {
            CONF_POWER_SENSOR: "sensor.power_used",  # Already taken
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        }

        asyncio.run(flow.async_step_sensors(user_input))

        # Should show form again with error (not create entry)
        flow.async_show_form.assert_called_once()
        call_kwargs = flow.async_show_form.call_args[1]
        assert call_kwargs["errors"][CONF_POWER_SENSOR] == "already_configured"


# ===========================================================================
# 4b. NettleieConfigFlow.async_step_reconfigure
# ===========================================================================


class TestReconfigureFlow:
    """Reconfigure-steget deler skjema/validering/DSO-avledning med options-flowen,
    men persisterer via async_update_reload_and_abort. unique_id er entry_id og
    røres ikke ved reconfigure.
    """

    def test_initial_step_shows_reconfigure_form(self):
        entry = _make_entry()
        flow = _make_reconfigure_flow(entry)

        asyncio.run(flow.async_step_reconfigure(None))

        flow.async_update_reload_and_abort.assert_not_called()
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["step_id"] == "reconfigure"

    def test_valid_reconfigure_persists_via_reload_and_abort(self):
        entry = _make_entry()
        flow = _make_reconfigure_flow(entry)

        # Bytt til custom (beholder brukerens energiledd) og endre flere felter.
        user_input = {
            CONF_DSO: "custom",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "nord_norge",
            CONF_HAR_NORGESPRIS: True,
            CONF_POWER_SENSOR: "sensor.power_1",
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.3500,
            CONF_ENERGILEDD_NATT: 0.1500,
            CONF_KAPASITET_VARSEL_TERSKEL: 3.0,
        }

        asyncio.run(flow.async_step_reconfigure(user_input))

        flow.async_show_form.assert_not_called()
        flow.async_update_reload_and_abort.assert_called_once()
        call = flow.async_update_reload_and_abort.call_args
        updated = call.kwargs["data"]
        assert updated[CONF_DSO] == "custom"
        assert updated[CONF_AVGIFTSSONE] == "nord_norge"
        assert updated[CONF_HAR_NORGESPRIS] is True
        # custom beholder brukerens energiledd (ingen DSO-avledning)
        assert updated[CONF_ENERGILEDD_DAG] == 0.3500
        assert updated[CONF_ENERGILEDD_NATT] == 0.1500
        # unique_id er entry_id og skal ikke sendes med (uendret ved reconfigure)
        assert "unique_id" not in call.kwargs

    def test_reconfigure_rejects_duplicate_power_sensor(self):
        entry1 = _make_entry(entry_id="entry1", power_sensor="sensor.power_1")
        entry2 = _make_entry(entry_id="entry2", power_sensor="sensor.power_2")
        flow = _make_reconfigure_flow(entry2, existing_entries=[entry1, entry2])

        user_input = {
            CONF_DSO: "bkk",
            CONF_BOLIGTYPE: "bolig",
            CONF_AVGIFTSSONE: "standard",
            CONF_HAR_NORGESPRIS: False,
            CONF_POWER_SENSOR: "sensor.power_1",  # allerede brukt av entry1
            CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
            CONF_ENERGILEDD_DAG: 0.4613,
            CONF_ENERGILEDD_NATT: 0.2329,
            CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
        }

        asyncio.run(flow.async_step_reconfigure(user_input))

        flow.async_update_reload_and_abort.assert_not_called()
        flow.async_show_form.assert_called_once()
        assert flow.async_show_form.call_args[1]["errors"][CONF_POWER_SENSOR] == "already_configured"


class TestTommeValgfrieFelt:
    """Et tømt valgfritt felt skal fjerne bindingen, i begge inngangene.

    Før gjeninnførte `{**current, **user_input}` den gamle verdien, og da kunne
    ingen fjerne en energisensor, en leverandørprissensor eller en eksportmåler
    de en gang hadde valgt (stromkalkulator-2zskcrd).
    """

    def test_options_fjerner_alle_tre_bindingene(self):
        entry = _full_entry()
        flow = _make_options_flow(entry)

        asyncio.run(flow.async_step_init(_skjema_uten_valgfrie()))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert CONF_ENERGY_SENSOR not in data
        assert CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR not in data
        assert CONF_EXPORT_POWER_SENSOR not in data

    def test_reconfigure_fjerner_alle_tre_bindingene(self):
        entry = _full_entry()
        flow = _make_reconfigure_flow(entry)

        asyncio.run(flow.async_step_reconfigure(_skjema_uten_valgfrie()))

        data = flow.async_update_reload_and_abort.call_args.kwargs["data"]
        assert CONF_ENERGY_SENSOR not in data
        assert CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR not in data
        assert CONF_EXPORT_POWER_SENSOR not in data

    def test_utfylt_felt_beholdes(self):
        """Negativ prøve: et felt som står igjen skal ikke bli fjernet."""
        entry = _full_entry()
        flow = _make_options_flow(entry)
        flow.hass.states.get = MagicMock(side_effect=_rolle_state)

        user_input = {**_skjema_uten_valgfrie(), CONF_ENERGY_SENSOR: "sensor.energy_1"}
        asyncio.run(flow.async_step_init(user_input))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert data[CONF_ENERGY_SENSOR] == "sensor.energy_1"
        assert CONF_EXPORT_POWER_SENSOR not in data

    def test_bytte_av_valgfri_sensor_gaar_gjennom(self):
        """En ny entitet i feltet skal erstatte den gamle, ikke bli ignorert."""
        entry = _full_entry()
        flow = _make_options_flow(entry)
        flow.hass.states.get = MagicMock(side_effect=_rolle_state)

        user_input = {**_skjema_uten_valgfrie(), CONF_ENERGY_SENSOR: "sensor.energy_2"}
        asyncio.run(flow.async_step_init(user_input))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert data[CONF_ENERGY_SENSOR] == "sensor.energy_2"

    def test_tomt_energiledd_gir_katalog_i_reconfigure(self):
        """Samme overstyringsregel i reconfigure som i options (kontrakt §6)."""
        entry = _full_entry()
        flow = _make_reconfigure_flow(entry)

        asyncio.run(flow.async_step_reconfigure(_skjema_uten_valgfrie()))

        data = flow.async_update_reload_and_abort.call_args.kwargs["data"]
        assert data[CONF_TARIFFMODUS] == "catalog"
        assert CONF_ENERGILEDD_DAG not in data
        assert CONF_ENERGILEDD_NATT not in data


# ===========================================================================
# 5. MaanedligNorgesprisKompensasjonSensor - native_value
# ===========================================================================


class TestMaanedligNorgesprisKompensasjonSensor:
    """Monthly Norgespris compensation sensor returns correct value."""

    def test_native_value_returns_compensation(self):
        coordinator = MagicMock()
        coordinator.data = {"monthly_norgespris_compensation_kr": -42.50}
        entry = _make_sensor_entry()

        sensor = MaanedligNorgesprisKompensasjonSensor(coordinator, entry)
        assert sensor.native_value == -42.50

    def test_native_value_returns_none_when_data_is_none(self):
        coordinator = MagicMock()
        coordinator.data = None
        entry = _make_sensor_entry()

        sensor = MaanedligNorgesprisKompensasjonSensor(coordinator, entry)
        assert sensor.native_value is None


# ===========================================================================
# 6. ForrigeMaanedNorgesprisKompensasjonSensor - native_value
# ===========================================================================


class TestForrigeMaanedNorgesprisKompensasjonSensor:
    """Previous month Norgespris compensation sensor returns correct value."""

    def test_native_value_returns_compensation(self):
        coordinator = MagicMock()
        coordinator.data = {"previous_month_norgespris_compensation_kr": 15.75}
        entry = _make_sensor_entry()

        sensor = ForrigeMaanedNorgesprisKompensasjonSensor(coordinator, entry)
        assert sensor.native_value == 15.75

    def test_native_value_returns_none_when_data_is_none(self):
        coordinator = MagicMock()
        coordinator.data = None
        entry = _make_sensor_entry()

        sensor = ForrigeMaanedNorgesprisKompensasjonSensor(coordinator, entry)
        assert sensor.native_value is None


# ===========================================================================
# 7. Both sensors return None when coordinator.data is None
# ===========================================================================


class TestNorgesprisKompensasjonSensorsNoneData:
    """Both compensation sensors return None when coordinator has no data."""

    @pytest.mark.parametrize(
        "sensor_class",
        [
            MaanedligNorgesprisKompensasjonSensor,
            ForrigeMaanedNorgesprisKompensasjonSensor,
        ],
    )
    def test_returns_none_without_data(self, sensor_class):
        coordinator = MagicMock()
        coordinator.data = None
        entry = _make_sensor_entry()

        sensor = sensor_class(coordinator, entry)
        assert sensor.native_value is None

    @pytest.mark.parametrize(
        "sensor_class,key",
        [
            (MaanedligNorgesprisKompensasjonSensor, "monthly_norgespris_compensation_kr"),
            (ForrigeMaanedNorgesprisKompensasjonSensor, "previous_month_norgespris_compensation_kr"),
        ],
    )
    def test_returns_none_when_key_missing(self, sensor_class, key):
        coordinator = MagicMock()
        coordinator.data = {}  # Data exists but key is absent
        entry = _make_sensor_entry()

        sensor = sensor_class(coordinator, entry)
        assert sensor.native_value is None


# ===========================================================================
# Egendefinert fastledd: trinntabellen i skjemaene (kontrakt §9)
# ===========================================================================


class TestTrinntabellISkjemaene:
    """Feltet finnes bare for Egendefinert, og valideres før det lagres.

    Trinnene er brukerens egne fordi Egendefinert ikke har noen prisliste vi
    kan lese. De kjente nettselskapene har trinn med kilde i dso.py, og et felt
    for dem ville invitert til å overstyre en verifisert prisliste med et minne.
    """

    def _skjema(self, **ekstra):
        return {**_skjema_uten_valgfrie(), CONF_DSO: "custom", **ekstra}

    def test_gyldig_tabell_lagres(self):
        entry = _make_entry(dso="custom")
        flow = _make_options_flow(entry)

        asyncio.run(flow.async_step_init(self._skjema(egendefinert_kapasitetstrinn="2:155,5:250")))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert data["egendefinert_kapasitetstrinn"] == "2:155,5:250"

    def test_ugyldig_tabell_avvises_med_feilnokkel(self):
        entry = _make_entry(dso="custom")
        flow = _make_options_flow(entry)

        asyncio.run(flow.async_step_init(self._skjema(egendefinert_kapasitetstrinn="2 kW koster 155")))

        flow.hass.config_entries.async_update_entry.assert_not_called()
        assert (
            flow.async_show_form.call_args[1]["errors"]["egendefinert_kapasitetstrinn"]
            == "trinntabell_ugyldig"
        )

    def test_tomt_felt_fjerner_tabellen(self):
        """Tomt betyr «jeg vet ikke», og da skal fastleddet bli ukjent igjen."""
        entry = _make_entry(dso="custom")
        entry.data["egendefinert_kapasitetstrinn"] = "2:155"
        flow = _make_options_flow(entry)

        asyncio.run(flow.async_step_init(self._skjema()))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert "egendefinert_kapasitetstrinn" not in data

    def test_bytte_til_kjent_nettselskap_fjerner_tabellen(self):
        """Trinnene hørte til ett nettselskap. Katalogen gjelder for det nye."""
        entry = _make_entry(dso="custom")
        entry.data["egendefinert_kapasitetstrinn"] = "2:155"
        flow = _make_options_flow(entry)

        asyncio.run(flow.async_step_init({**_skjema_uten_valgfrie(), CONF_DSO: "bkk"}))

        data = flow.hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert "egendefinert_kapasitetstrinn" not in data

    def test_feltet_vises_kun_for_egendefinert(self):
        cf_mod = _reload_config_flow()
        egendefinert = cf_mod._config_data_schema({CONF_DSO: "custom"})
        kjent = cf_mod._config_data_schema({CONF_DSO: "bkk"})
        assert "egendefinert_kapasitetstrinn" in egendefinert
        assert "egendefinert_kapasitetstrinn" not in kjent


class TestPricingStegetTarImotTrinn:
    """Førstegangsoppsettet skal kunne oppgi trinnene med en gang."""

    def _flow(self):
        cf_mod = _reload_config_flow()
        flow = cf_mod.NettleieConfigFlow()
        flow.hass = MagicMock()
        flow._data = {CONF_DSO: "custom", CONF_POWER_SENSOR: "sensor.power_1"}
        flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
        flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "pricing"})
        return flow

    def test_gyldig_tabell_blir_med_paa_entryet(self):
        flow = self._flow()
        asyncio.run(
            flow.async_step_pricing(
                {
                    CONF_AVGIFTSSONE: "standard",
                    CONF_ENERGILEDD_DAG: 0.24,
                    CONF_ENERGILEDD_NATT: 0.08,
                    "egendefinert_kapasitetstrinn": "2:155,5:250,10:415",
                }
            )
        )
        assert flow._data["egendefinert_kapasitetstrinn"] == "2:155,5:250,10:415"
        assert flow._data[CONF_TARIFFMODUS] == "manual"

    def test_tomt_felt_gir_ingen_noekkel(self):
        flow = self._flow()
        asyncio.run(
            flow.async_step_pricing(
                {
                    CONF_AVGIFTSSONE: "standard",
                    CONF_ENERGILEDD_DAG: 0.24,
                    CONF_ENERGILEDD_NATT: 0.08,
                }
            )
        )
        assert "egendefinert_kapasitetstrinn" not in flow._data
        flow.async_create_entry.assert_called_once()

    def test_ugyldig_tabell_stopper_oppsettet_med_feil(self):
        flow = self._flow()
        asyncio.run(
            flow.async_step_pricing(
                {
                    CONF_AVGIFTSSONE: "standard",
                    CONF_ENERGILEDD_DAG: 0.24,
                    CONF_ENERGILEDD_NATT: 0.08,
                    "egendefinert_kapasitetstrinn": "5:250,2:155",
                }
            )
        )
        flow.async_create_entry.assert_not_called()
        assert (
            flow.async_show_form.call_args[1]["errors"]["egendefinert_kapasitetstrinn"]
            == "trinntabell_ugyldig"
        )
