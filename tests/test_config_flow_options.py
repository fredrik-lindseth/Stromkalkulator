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

# ---- HA module mocks (same pattern as other test files) ----
_sensor_mod = sys.modules["homeassistant.components.sensor"]
_sensor_mod.SensorDeviceClass = type("SensorDeviceClass", (), {
    "MONETARY": "monetary",
    "POWER": "power",
    "ENERGY": "energy",
})
_sensor_mod.SensorEntity = type("SensorEntity", (), {})
_sensor_mod.SensorStateClass = type("SensorStateClass", (), {
    "MEASUREMENT": "measurement",
    "TOTAL": "total",
    "TOTAL_INCREASING": "total_increasing",
})

_const_mod = sys.modules["homeassistant.const"]
_const_mod.EntityCategory = type("EntityCategory", (), {
    "DIAGNOSTIC": "diagnostic",
    "CONFIG": "config",
})

_entity_mod = sys.modules["homeassistant.helpers.entity"]
_entity_mod.EntityCategory = _const_mod.EntityCategory

_coord_mod = sys.modules["homeassistant.helpers.update_coordinator"]


class FakeCoordinatorEntity:
    """Minimal CoordinatorEntity stub."""

    def __init__(self, coordinator):
        self.coordinator = coordinator


_coord_mod.CoordinatorEntity = FakeCoordinatorEntity


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
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
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

    # States: both sensors exist
    def get_state(entity_id):
        state = MagicMock()
        state.state = "100"
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

    @pytest.mark.parametrize("sensor_class", [
        MaanedligNorgesprisKompensasjonSensor,
        ForrigeMaanedNorgesprisKompensasjonSensor,
    ])
    def test_returns_none_without_data(self, sensor_class):
        coordinator = MagicMock()
        coordinator.data = None
        entry = _make_sensor_entry()

        sensor = sensor_class(coordinator, entry)
        assert sensor.native_value is None

    @pytest.mark.parametrize("sensor_class,key", [
        (MaanedligNorgesprisKompensasjonSensor, "monthly_norgespris_compensation_kr"),
        (ForrigeMaanedNorgesprisKompensasjonSensor, "previous_month_norgespris_compensation_kr"),
    ])
    def test_returns_none_when_key_missing(self, sensor_class, key):
        coordinator = MagicMock()
        coordinator.data = {}  # Data exists but key is absent
        entry = _make_sensor_entry()

        sensor = sensor_class(coordinator, entry)
        assert sensor.native_value is None
