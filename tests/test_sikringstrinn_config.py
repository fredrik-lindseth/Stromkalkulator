"""Tester for sikringsstørrelse-feltet i config-flowen.

Alut og Netera fakturerer fastleddet etter overbelastningsvernets størrelse.
Det er brukerdata: ingen sensor kan lese det, og et gjettet trinn ville gitt et
plausibelt men feil beløp, som er nøyaktig feilen incident 006 handler om.

Scaffoldingen speiler test_options_dso_bytte.py: voluptuous, selectors og
config_entries-baseklassene er stubbet slik at config_flow kan importeres uten
Home Assistant.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from unittest.mock import MagicMock

import pytest

if "voluptuous" not in sys.modules:
    _vol = MagicMock()
    _vol.Schema = MagicMock(side_effect=lambda x: x)
    _vol.Required = lambda name, **kw: name
    _vol.Optional = lambda name, **kw: name
    sys.modules["voluptuous"] = _vol


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
    CONF_SIKRINGSTRINN,
    CONF_SPOT_PRICE_SENSOR,
    DSO_LIST,
)
from stromkalkulator.dso import finn_sikringstrinn  # noqa: E402


def _reload_config_flow():
    _ce_mod.ConfigFlow = _FakeConfigFlow
    _ce_mod.OptionsFlow = _FakeOptionsFlow
    import stromkalkulator.config_flow as cf_mod

    importlib.reload(cf_mod)
    return cf_mod


def _state(value="1.2", unit="NOK/kWh"):
    state = MagicMock()
    state.state = str(value)
    state.attributes = {"unit_of_measurement": unit}
    return state


def _make_entry(dso="alut", sikringstrinn=None):
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {
        CONF_DSO: dso,
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: "standard",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: "sensor.power_1",
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_ENERGILEDD_DAG: DSO_LIST[dso]["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: DSO_LIST[dso]["energiledd_natt_eks_mva"],
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    if sikringstrinn is not None:
        entry.data[CONF_SIKRINGSTRINN] = sikringstrinn
    return entry


def _make_options_flow(entry):
    cf_mod = _reload_config_flow()
    flow = cf_mod.NettleieOptionsFlow()
    flow.config_entry = entry
    flow.hass = MagicMock()
    flow.hass.config_entries.async_entries.return_value = [entry]
    flow.hass.config_entries.async_update_entry = MagicMock()
    flow.hass.states.get = MagicMock(return_value=_state())
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow.async_show_form = MagicMock(return_value={"type": "form", "step_id": "init"})
    return cf_mod, flow


def _make_config_flow(dso="alut"):
    cf_mod = _reload_config_flow()
    flow = cf_mod.NettleieConfigFlow()
    flow.hass = MagicMock()
    flow.hass.states.get = MagicMock(return_value=_state())
    flow._async_current_entries = MagicMock(return_value=[])
    flow._data = {CONF_DSO: dso, CONF_BOLIGTYPE: "bolig", CONF_HAR_NORGESPRIS: False}
    flow.async_create_entry = MagicMock(return_value={"type": "create_entry"})
    flow.async_show_form = MagicMock(
        side_effect=lambda **kw: {"type": "form", **kw}
    )
    return cf_mod, flow


def _sensor_input():
    return {
        CONF_POWER_SENSOR: "sensor.power_1",
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
    }


def _submitted_data(flow):
    call = flow.hass.config_entries.async_update_entry.call_args
    return call.kwargs.get("data") or call[0][1]


def _base_options_input(dso, **overrides):
    """Skjema-submit for options. Feltene defaulter til lagrede verdier."""
    user_input = {
        CONF_DSO: dso,
        CONF_BOLIGTYPE: "bolig",
        CONF_AVGIFTSSONE: "standard",
        CONF_HAR_NORGESPRIS: False,
        CONF_POWER_SENSOR: "sensor.power_1",
        CONF_SPOT_PRICE_SENSOR: "sensor.spot_price",
        CONF_ENERGILEDD_DAG: DSO_LIST["bkk"]["energiledd_dag_eks_mva"],
        CONF_ENERGILEDD_NATT: DSO_LIST["bkk"]["energiledd_natt_eks_mva"],
        CONF_KAPASITET_VARSEL_TERSKEL: 2.0,
    }
    user_input.update(overrides)
    return user_input


class TestOppsettSpoerOmSikring:
    """Nye brukere skal aldri havne i "ikke valgt"-tilstanden."""

    @pytest.mark.parametrize("dso", ["alut", "netera"])
    def test_sensorsteget_leder_til_sikringssteget(self, dso):
        _cf, flow = _make_config_flow(dso)
        resultat = asyncio.run(flow.async_step_sensors(_sensor_input()))
        assert resultat["step_id"] == "sikring"
        flow.async_create_entry.assert_not_called()

    def test_vanlig_nettselskap_hopper_over_steget(self):
        _cf, flow = _make_config_flow("bkk")
        asyncio.run(flow.async_step_sensors(_sensor_input()))
        flow.async_create_entry.assert_called_once()

    def test_valget_lagres_paa_entryet(self):
        _cf, flow = _make_config_flow("alut")
        asyncio.run(flow.async_step_sensors(_sensor_input()))
        asyncio.run(flow.async_step_sikring({CONF_SIKRINGSTRINN: "over_3x125a"}))
        flow.async_create_entry.assert_called_once()
        assert flow._data[CONF_SIKRINGSTRINN] == "over_3x125a"

    def test_skjemaet_navngir_nettselskapet(self):
        _cf, flow = _make_config_flow("netera")
        asyncio.run(flow.async_step_sensors(_sensor_input()))
        resultat = asyncio.run(flow.async_step_sikring())
        assert resultat["description_placeholders"] == {"dso": "Netera"}


class TestOptionsSkjema:
    """Feltet vises bare der nettselskapet fakturerer etter sikringsstørrelse."""

    def test_feltet_er_med_for_sikringsbasert_nettselskap(self):
        cf_mod, _flow = _make_options_flow(_make_entry("alut", "inntil_3x125a"))
        skjema = cf_mod._config_data_schema(_make_entry("alut", "inntil_3x125a").data)
        assert CONF_SIKRINGSTRINN in skjema

    def test_feltet_er_borte_for_vanlig_nettselskap(self):
        cf_mod, _flow = _make_options_flow(_make_entry("bkk"))
        skjema = cf_mod._config_data_schema(_make_entry("bkk").data)
        assert CONF_SIKRINGSTRINN not in skjema

    def test_lagret_valg_bevares_ved_lagring(self):
        entry = _make_entry("alut", "over_3x125a")
        _cf, flow = _make_options_flow(entry)
        user_input = _base_options_input("alut", **{CONF_SIKRINGSTRINN: "over_3x125a"})
        asyncio.run(flow.async_step_init(user_input))
        assert _submitted_data(flow)[CONF_SIKRINGSTRINN] == "over_3x125a"


class TestDsoBytteToemmerValget:
    """En trinn-id hører til ett nettselskaps prisliste og skal ikke overleve et bytte."""

    def test_bytte_til_annet_sikringsbasert_nettselskap_toemmer(self):
        """Alut-id-en finnes ikke hos Netera, og skal ikke bli med."""
        entry = _make_entry("alut", "inntil_3x125a")
        _cf, flow = _make_options_flow(entry)
        user_input = _base_options_input("netera", **{CONF_SIKRINGSTRINN: "inntil_3x125a"})
        asyncio.run(flow.async_step_init(user_input))
        assert _submitted_data(flow)[CONF_SIKRINGSTRINN] is None

    def test_bytte_til_vanlig_nettselskap_toemmer(self):
        entry = _make_entry("alut", "inntil_3x125a")
        _cf, flow = _make_options_flow(entry)
        user_input = _base_options_input("bkk", **{CONF_SIKRINGSTRINN: "inntil_3x125a"})
        asyncio.run(flow.async_step_init(user_input))
        assert _submitted_data(flow)[CONF_SIKRINGSTRINN] is None

    def test_bytte_til_egendefinert_toemmer(self):
        """Egendefinert har ingen sikringstrinn, så en lagret id er død data."""
        entry = _make_entry("alut", "inntil_3x125a")
        _cf, flow = _make_options_flow(entry)
        user_input = _base_options_input("custom", **{CONF_SIKRINGSTRINN: "inntil_3x125a"})
        asyncio.run(flow.async_step_init(user_input))
        assert _submitted_data(flow)[CONF_SIKRINGSTRINN] is None

    def test_uten_bytte_beholdes_valget(self):
        entry = _make_entry("netera", "400v_40_80")
        _cf, flow = _make_options_flow(entry)
        user_input = _base_options_input("netera", **{CONF_SIKRINGSTRINN: "400v_40_80"})
        asyncio.run(flow.async_step_init(user_input))
        assert _submitted_data(flow)[CONF_SIKRINGSTRINN] == "400v_40_80"


class TestFinnSikringstrinn:
    """Oppslaget skal skille "ikke valgt" fra "ugyldig", men behandle dem likt."""

    def test_finner_riktig_rad_med_nummer(self):
        nummer, trinn = finn_sikringstrinn(DSO_LIST["netera"], "230v_63_125")
        assert nummer == 3
        assert trinn["kr_mnd"] == 667

    @pytest.mark.parametrize("valg", [None, "", "finnes_ikke"])
    def test_manglende_eller_ukjent_id_gir_none(self, valg):
        assert finn_sikringstrinn(DSO_LIST["netera"], valg) is None

    def test_nettselskap_uten_sikringstrinn_gir_none(self):
        assert finn_sikringstrinn(DSO_LIST["bkk"], "230v_0_10") is None
