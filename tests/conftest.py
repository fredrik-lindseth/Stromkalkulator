"""Pytest configuration, shared helpers og fixtures for Strømkalkulator-tester."""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add custom_components to path so we can import without Home Assistant
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

# Mock Home Assistant modules before importing our code
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.data_entry_flow"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.issue_registry"] = MagicMock()
sys.modules["homeassistant.helpers.storage"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.helpers.selector"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()
_ha_util_mock = MagicMock()
_dt_util_mock = MagicMock()
# Fast tidspunkt for å unngå flakiness ved midnatt/månedsskifte
_dt_util_mock.now.return_value = datetime(2026, 6, 15, 12, 0, 0)
_ha_util_mock.dt = _dt_util_mock
sys.modules["homeassistant.util"] = _ha_util_mock
sys.modules["homeassistant.util.dt"] = _dt_util_mock


# ---------------------------------------------------------------------------
# Delte test-helpers (importeres av testfiler som module-level callables)
# ---------------------------------------------------------------------------


def _make_state(value):
    """Lag et mock HA state-objekt med .state = str(value)."""
    state = MagicMock()
    state.state = str(value)
    return state


def _make_entry(
    entry_id="test_entry",
    dso_id="bkk",
    har_norgespris=False,
    avgiftssone="standard",
    spotpris_inkl_mva=True,
    power_sensor="sensor.power",
    spot_price_sensor="sensor.spot_price",
    electricity_company_price_sensor=None,
    export_power_sensor=None,
    energy_sensor=None,
    extra_data=None,
):
    """Lag et mock config entry med felles defaults og valgfrie utvidelser.

    Tester som trenger andre felter, kan enten passere extra_data eller
    sette entry.data[...] direkte etter at entryet er laget.
    """
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": power_sensor,
        "spot_price_sensor": spot_price_sensor,
        "spotpris_inkl_mva": spotpris_inkl_mva,
        "har_norgespris": har_norgespris,
        "avgiftssone": avgiftssone,
    }
    if electricity_company_price_sensor:
        entry.data["electricity_provider_price_sensor"] = electricity_company_price_sensor
    if export_power_sensor:
        entry.data["export_power_sensor"] = export_power_sensor
    if energy_sensor:
        entry.data["energy_sensor"] = energy_sensor
    if extra_data:
        entry.data.update(extra_data)
    entry.runtime_data = None
    return entry


def _make_hass(
    power_w=5000,
    spot_price=1.20,
    electricity_company_price=None,
    export_power_w=None,
):
    """Lag en mock HA-instans som returnerer states for vanlige sensorer.

    sensor.power -> power_w
    sensor.spot_price -> spot_price
    sensor.elco_price -> electricity_company_price (kun hvis satt)
    sensor.export_power -> export_power_w (kun hvis satt)
    """
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        if entity_id == "sensor.elco_price" and electricity_company_price is not None:
            return _make_state(electricity_company_price)
        if entity_id == "sensor.export_power" and export_power_w is not None:
            return _make_state(export_power_w)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _run_update(coord_module, coordinator, now=None):
    """Kjør _async_update_data, eventuelt med override av dt_util.now."""
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


# ---------------------------------------------------------------------------
# Globale fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_update_coordinator():
    """Erstatt mocked DataUpdateCoordinator med en ekte baseklasse.

    conftest mocker homeassistant.helpers.update_coordinator som MagicMock,
    men subklassing av en MagicMock påvirker ikke __init__. Tester som
    instansierer NettleieCoordinator trenger en reell base. Sikrer også at
    UpdateFailed er en ekte exception-klasse og at
    async_config_entry_first_refresh finnes (brukt av __init__.py).
    """

    class FakeDataUpdateCoordinator:
        def __init_subclass__(cls, **kwargs):
            pass

        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval):
            self.hass = hass

        async def async_config_entry_first_refresh(self):
            pass

    mod = sys.modules["homeassistant.helpers.update_coordinator"]
    original = getattr(mod, "DataUpdateCoordinator", None)
    mod.DataUpdateCoordinator = FakeDataUpdateCoordinator

    original_uf = getattr(mod, "UpdateFailed", None)
    if not isinstance(original_uf, type) or not issubclass(original_uf, BaseException):
        class UpdateFailed(Exception):
            pass

        mod.UpdateFailed = UpdateFailed
    yield
    mod.DataUpdateCoordinator = original


@pytest.fixture
def coord_module():
    """Last coordinator-modulen på nytt og patch Store + dt_util.

    dt_util.now defaulter til 2026-06-15 12:00. Tester som trenger andre
    tidspunkt kan enten sette coord_module.dt_util.now.return_value direkte
    eller bruke _run_update(now=...).
    """
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)

    coord.dt_util = MagicMock()
    coord.dt_util.now.return_value = datetime(2026, 6, 15, 12, 0)

    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return coord


# ---------------------------------------------------------------------------
# Domene-fixtures (eksisterende)
# ---------------------------------------------------------------------------


@pytest.fixture
def bkk_kapasitetstrinn():
    """BKK kapasitetstrinn 2026."""
    return [
        (2, 155),
        (5, 250),
        (10, 415),
        (15, 600),
        (20, 770),
        (25, 940),
        (50, 1800),
        (75, 2650),
        (100, 3500),
        (float("inf"), 6900),
    ]


@pytest.fixture
def sample_spot_prices():
    """Sample spot prices for testing.

    Terskel 2026: 77 øre eks. mva * 1.25 = 96.25 øre inkl. mva = 0.9625 NOK/kWh
    """
    from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL

    return {
        "low": 0.50,
        "threshold": STROMSTOTTE_LEVEL,
        "medium": 1.20,
        "high": 2.00,
        "extreme": 5.00,
    }
