"""Tester for options-flow ved DSO-bytte og øre/kWh-validering.

Dekker to bugs:
- stromkalkulator-16hk: bytte av DSO i options må re-resolve energiledd og
  avgiftssone, ellers arver du forrige DSOs satser med ny DSOs kapasitetstrinn.
- stromkalkulator-3hnc: _validate_spot_sensor må avvise øre/kWh-sensorer, ellers
  tolker coordinator verdien som NOK/kWh og hele kjeden blir 100x for lav.

Scaffoldingen speiler test_config_flow_options.py: voluptuous, selectors og
config_entries-baseklassene er stubbet slik at config_flow kan importeres uten
Home Assistant.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import MagicMock

# ---- Mock voluptuous før config_flow importeres ----
if "voluptuous" not in sys.modules:
    _vol = MagicMock()
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    _vol.Required = lambda name, **kw: name
    _vol.Optional = lambda name, **kw: name
    sys.modules["voluptuous"] = _vol


# ---- Ekte baseklasser for ConfigFlow / OptionsFlow ----
class _FakeConfigFlow:
    def __init_subclass__(cls, domain=None, **kwargs):
        pass

    def __init__(self):
        self._data = {}


class _FakeOptionsFlow:
    pass


class _FakeConfigEntry:
    pass


_ce_mod = sys.modules["homeassistant.config_entries"]
_ce_mod.ConfigFlow = _FakeConfigFlow
_ce_mod.OptionsFlow = _FakeOptionsFlow
_ce_mod.ConfigEntry = _FakeConfigEntry
sys.modules["homeassistant"].config_entries = _ce_mod

sys.modules["homeassistant.core"].callback = lambda f: f

# ---- selector-stubs: SelectOptionDict må være et ekte, sorterbart dict ----
_selector_mod = sys.modules["homeassistant.helpers.selector"]
_selector_mod.SelectOptionDict = lambda **kw: kw
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
    DSO_LIST,
    resolve_avgiftssone,
)

# Faste satser hentet fra DSO_LIST slik at testene følger med hvis kildene endres.
BKK = DSO_LIST["bkk"]
ELVIA = DSO_LIST["elvia"]
ARVA = DSO_LIST["arva"]


def _reload_config_flow():
    """Last config_flow med baseklasse-stubbene på plass."""
    _ce_mod.ConfigFlow = _FakeConfigFlow
    _ce_mod.OptionsFlow = _FakeOptionsFlow
    import stromkalkulator.config_flow as cf_mod

    importlib.reload(cf_mod)
    return cf_mod


def _state(value, unit=None):
    """Mock HA-state med ekte attributes-dict (så .get fungerer normalt)."""
    state = MagicMock()
    state.state = str(value)
    state.attributes = {"unit_of_measurement": unit} if unit is not None else {}
    return state


def _make_entry(
    entry_id: str = "entry1",
    dso: str = "bkk",
    power_sensor: str = "sensor.power_1",
    energiledd_dag: float | None = None,
    energiledd_natt: float | None = None,
    avgiftssone: str = "standard",
) -> MagicMock:
    """Config entry med satsene til `dso` med mindre annet er oppgitt."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.unique_id = f"{DOMAIN}_{power_sensor}"
    entry.data = {
        CONF_DSO: dso,
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: avgiftssone,
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: power_sensor,
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_ENERGILEDD_DAG: energiledd_dag
        if energiledd_dag is not None
        else DSO_LIST[dso]["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: energiledd_natt
        if energiledd_natt is not None
        else DSO_LIST[dso]["energiledd_natt_eks_mva"],
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    return entry


def _make_options_flow(entry: MagicMock, spot_state: MagicMock | None = None):
    """Options-flow med mocket hass; spot-sensor validerer OK som default."""
    cf_mod = _reload_config_flow()

    flow = cf_mod.NettleieOptionsFlow()
    flow.config_entry = entry
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries.return_value = [entry]
    flow.hass.config_entries.async_update_entry = MagicMock()

    default_spot = spot_state if spot_state is not None else _state("1.2", "NOK/kWh")
    flow.hass.states.get = MagicMock(return_value=default_spot)

    flow.async_create_entry = MagicMock(
        return_value={"type": "create_entry", "title": "", "data": {}}
    )
    flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "init"})
    return flow


def _submitted_data(flow: MagicMock) -> dict:
    """Hent data-argumentet fra async_update_entry-kallet."""
    call = flow.hass.config_entries.async_update_entry.call_args
    return call.kwargs.get("data") or call[0][1]


def _base_input(dso: str, **overrides) -> dict:
    """Simuler skjema-submit. Energiledd/avgiftssone defaulter til BKK-verdier,
    slik skjemaet faktisk gjør (defaults fra lagret, forrige DSO)."""
    user_input = {
        CONF_DSO: dso,
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: "standard",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: "sensor.power_1",
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_ENERGILEDD_DAG: BKK["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: BKK["energiledd_natt_eks_mva"],
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    user_input.update(overrides)
    return user_input


# ===========================================================================
# Bug 16hk: DSO-bytte re-resolver energiledd og avgiftssone
# ===========================================================================


class TestDsoBytteReResolverSatser:
    def test_dso_change_reresolves_energiledd(self):
        """Bytte BKK -> Elvia skal overskrive de arvede BKK-energileddene."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry)

        # Skjemaet sender BKK-energiledd (arvede defaults) med ny DSO Elvia.
        user_input = _base_input("elvia")
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_DSO] == "elvia"
        assert data[CONF_ENERGILEDD_DAG] == ELVIA["energiledd_dag_eks_mva"]
        assert data[CONF_ENERGILEDD_NATT] == ELVIA["energiledd_natt_eks_mva"]

    def test_dso_change_reresolves_avgiftssone(self):
        """Bytte BKK (NO5, standard) -> Arva (NO4, nord_norge) skal re-resolve sonen."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry)

        # Skjemaet sender fortsatt standard-sonen (arvet default).
        user_input = _base_input("arva", **{CONF_AVGIFTSSONE: "standard"})
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_DSO] == "arva"
        assert data[CONF_AVGIFTSSONE] == resolve_avgiftssone(ARVA)
        assert data[CONF_AVGIFTSSONE] != "standard"

    def test_no_dso_change_preserves_energiledd_override(self):
        """Uten DSO-bytte skal brukerens energiledd-overstyring bevares."""
        entry = _make_entry(
            dso="bkk", energiledd_dag=0.5000, energiledd_natt=0.4000
        )
        flow = _make_options_flow(entry)

        user_input = _base_input(
            "bkk",
            **{CONF_ENERGILEDD_DAG: 0.5000, CONF_ENERGILEDD_NATT: 0.4000},
        )
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_ENERGILEDD_DAG] == 0.5000
        assert data[CONF_ENERGILEDD_NATT] == 0.4000

    def test_switch_to_custom_keeps_user_energiledd(self):
        """Bytte til Egendefinert skal beholde brukerens egne energiledd og sone."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry)

        user_input = _base_input(
            "custom",
            **{
                CONF_ENERGILEDD_DAG: 0.3333,
                CONF_ENERGILEDD_NATT: 0.2222,
                CONF_AVGIFTSSONE: "nord_norge",
            },
        )
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_DSO] == "custom"
        assert data[CONF_ENERGILEDD_DAG] == 0.3333
        assert data[CONF_ENERGILEDD_NATT] == 0.2222
        assert data[CONF_AVGIFTSSONE] == "nord_norge"


# ===========================================================================
# Bug 3hnc: _validate_spot_sensor avviser øre/kWh
# ===========================================================================


class TestSpotSensorOereValidering:
    def test_ore_per_kwh_unit_rejected(self):
        cf_mod = _reload_config_flow()
        assert cf_mod._validate_spot_sensor(_state("50", "øre/kWh")) == "spot_unit_invalid"

    def test_ore_ascii_unit_rejected(self):
        cf_mod = _reload_config_flow()
        assert cf_mod._validate_spot_sensor(_state("50", "ore/kWh")) == "spot_unit_invalid"

    def test_nok_per_kwh_still_accepted(self):
        cf_mod = _reload_config_flow()
        assert cf_mod._validate_spot_sensor(_state("1.2", "NOK/kWh")) is None

    def test_eur_per_mwh_still_accepted(self):
        cf_mod = _reload_config_flow()
        assert cf_mod._validate_spot_sensor(_state("45", "EUR/MWh")) is None

    def test_options_flow_rejects_ore_spot_sensor(self):
        """Ende-til-ende: en øre/kWh spot-sensor i options skal gi feil, ikke lagres."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry, spot_state=_state("50", "øre/kWh"))

        user_input = _base_input("bkk")
        asyncio.run(flow.async_step_init(user_input))

        flow.hass.config_entries.async_update_entry.assert_not_called()
        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()
        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors[CONF_SPOT_PRICE_SENSOR] == "spot_unit_invalid"
