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
    CONF_TARIFFMODUS,
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
    state.last_updated = None
    return state


def _rolle_state(entity_id):
    """State med en enhet som passer rollen entity-id-en antyder.

    Config-flowen validerer nå alle fem rollene gjennom inputadapteren. En mock
    som ga alle sensorer samme enhet ville felt effektfeltet på at det så en
    pris der det skulle sett watt.
    """
    if "power" in entity_id or "export" in entity_id:
        return _state(5000, "W")
    if "energy" in entity_id:
        state = _state(1000, "kWh")
        state.attributes["state_class"] = "total_increasing"
        return state
    return _state(1.2, "NOK/kWh")


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

    def hent(entity_id):
        if spot_state is not None and "spot" in entity_id:
            return spot_state
        return _rolle_state(entity_id)

    flow.hass.states.get = MagicMock(side_effect=hent)

    flow.async_create_entry = MagicMock(return_value={"type": "create_entry", "title": "", "data": {}})
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
    def test_dso_change_dropper_arvet_energiledd(self):
        """Bytte BKK -> Elvia skal kvitte seg med de arvede BKK-energileddene.

        Før ble de skrevet om til Elvias katalogverdier. Nå fjernes de helt og
        entryet settes i `catalog`, som er det samme tallet og i tillegg følger
        prislisten videre. Hadde de blitt stående, ville brukeren fått BKKs sats
        med Elvias kapasitetstrinn.
        """
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry)

        # Skjemaet sender BKK-energiledd (arvede defaults) med ny DSO Elvia.
        user_input = _base_input("elvia")
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_DSO] == "elvia"
        assert data[CONF_TARIFFMODUS] == "catalog"
        assert CONF_ENERGILEDD_DAG not in data
        assert CONF_ENERGILEDD_NATT not in data

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
        entry = _make_entry(dso="bkk", energiledd_dag=0.5000, energiledd_natt=0.4000)
        flow = _make_options_flow(entry)

        user_input = _base_input(
            "bkk",
            **{CONF_ENERGILEDD_DAG: 0.5000, CONF_ENERGILEDD_NATT: 0.4000},
        )
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_ENERGILEDD_DAG] == 0.5000
        assert data[CONF_ENERGILEDD_NATT] == 0.4000
        assert data[CONF_TARIFFMODUS] == "manual"

    def test_tomt_energiledd_gir_katalog(self):
        """Lagring med tomt overstyringsfelt betyr «følg katalogen» (kontrakt §6)."""
        entry = _make_entry(dso="bkk", energiledd_dag=0.5000, energiledd_natt=0.4000)
        entry.data[CONF_TARIFFMODUS] = "legacy_unconfirmed"
        flow = _make_options_flow(entry)

        user_input = _base_input("bkk")
        user_input.pop(CONF_ENERGILEDD_DAG)
        user_input.pop(CONF_ENERGILEDD_NATT)
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_TARIFFMODUS] == "catalog"
        assert CONF_ENERGILEDD_DAG not in data
        assert CONF_ENERGILEDD_NATT not in data

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
        assert data[CONF_TARIFFMODUS] == "manual"

    def test_switch_to_custom_arver_satsen_anlegget_laa_paa(self):
        """Tomt energiledd-felt ved bytte til Egendefinert skal ikke gi ingenting.

        Skjemaet ble tegnet for BKK, der feltet er en overstyring og står tomt
        når katalogen gjelder. Egendefinert har ingen katalog, så tallet må
        komme et sted fra, og da er det der anlegget faktisk lå.
        """
        entry = _make_entry(dso="bkk")
        del entry.data[CONF_ENERGILEDD_DAG]
        del entry.data[CONF_ENERGILEDD_NATT]
        flow = _make_options_flow(entry)

        user_input = _base_input("custom")
        user_input.pop(CONF_ENERGILEDD_DAG)
        user_input.pop(CONF_ENERGILEDD_NATT)
        asyncio.run(flow.async_step_init(user_input))

        data = _submitted_data(flow)
        assert data[CONF_TARIFFMODUS] == "manual"
        assert data[CONF_ENERGILEDD_DAG] == BKK["energiledd_dag_eks_mva"]
        assert data[CONF_ENERGILEDD_NATT] == BKK["energiledd_natt_eks_mva"]


# ===========================================================================
# Bug 3hnc: øre/kWh ble avvist der den kunne vært regnet om
# ===========================================================================


class TestSpotSensorEnhetValidering:
    """Enhetene valideres nå av inputadapteren, i alle fire inngangene.

    Retningen er snudd: øre/kWh godtas og regnes om, mens EUR avvises. Vi har
    ingen valutakurs, og å lese euro som kroner er verre enn å si nei.
    """

    def _feil(self, state):
        cf_mod = _reload_config_flow()
        hass = MagicMock()
        hass.states.get = MagicMock(return_value=state)
        return cf_mod._valider_sensorfelt(
            hass, {CONF_SPOT_PRICE_SENSOR: "sensor.spot_price"}, paakrevd=set()
        ).get(CONF_SPOT_PRICE_SENSOR)

    def test_ore_per_kwh_godtas(self):
        assert self._feil(_state("50", "øre/kWh")) is None

    def test_ore_ascii_godtas(self):
        assert self._feil(_state("50", "ore/kWh")) is None

    def test_nok_per_kwh_still_accepted(self):
        assert self._feil(_state("1.2", "NOK/kWh")) is None

    def test_eur_per_mwh_avvises(self):
        assert self._feil(_state("45", "EUR/MWh")) == "enhet_feil_valuta"

    def test_options_flow_avviser_eur_spot_sensor(self):
        """Ende-til-ende: en EUR-sensor i options skal gi feil, ikke lagres."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry, spot_state=_state("45", "EUR/MWh"))

        user_input = _base_input("bkk")
        asyncio.run(flow.async_step_init(user_input))

        flow.hass.config_entries.async_update_entry.assert_not_called()
        flow.async_create_entry.assert_not_called()
        flow.async_show_form.assert_called_once()
        errors = flow.async_show_form.call_args[1]["errors"]
        assert errors[CONF_SPOT_PRICE_SENSOR] == "enhet_feil_valuta"

    def test_options_flow_lagrer_ore_sensor(self):
        """Motsatt retning: øre/kWh skal ikke stoppe lagringen lenger."""
        entry = _make_entry(dso="bkk")
        flow = _make_options_flow(entry, spot_state=_state("50", "øre/kWh"))

        asyncio.run(flow.async_step_init(_base_input("bkk")))

        flow.hass.config_entries.async_update_entry.assert_called_once()
