"""Tests for akkumulert kostnadssensor (Energy Dashboard stat_cost).

Tester akkumulering av strompris, energiledd og kapasitetsledd,
kapasitetsledd-linearitet over en hel maned, manedsskifte-reset,
Norgespris vs. spot, og lagringspersistens.
"""

from __future__ import annotations

import asyncio
import importlib
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

_real_datetime = datetime


@pytest.fixture(autouse=True)
def _patch_update_coordinator():
    """Replace mocked DataUpdateCoordinator with a real base class."""

    class FakeDataUpdateCoordinator:
        def __init_subclass__(cls, **kwargs):
            pass

        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval):
            self.hass = hass

    mod = sys.modules["homeassistant.helpers.update_coordinator"]
    original = getattr(mod, "DataUpdateCoordinator", None)
    mod.DataUpdateCoordinator = FakeDataUpdateCoordinator
    yield
    mod.DataUpdateCoordinator = original


@pytest.fixture
def coord_module():
    """Reload coordinator module and patch Store + dt_util."""
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)

    coord.dt_util = MagicMock()
    coord.dt_util.now.return_value = _real_datetime(2026, 6, 15, 12, 0)

    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return coord


def _make_state(value):
    """Create a mock HA state object."""
    state = MagicMock()
    state.state = str(value)
    return state


def _make_entry(
    entry_id="test_entry",
    dso_id="bkk",
    har_norgespris=False,
    avgiftssone="standard",
):
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {
        "tso": dso_id,
        "power_sensor": "sensor.power",
        "spot_price_sensor": "sensor.spot_price",
        "har_norgespris": har_norgespris,
        "avgiftssone": avgiftssone,
    }
    return entry


def _make_hass(power_w=5000, spot_price=1.20):
    """Create a mock HA instance with sensor states."""
    hass = MagicMock()

    def get_state(entity_id):
        if entity_id == "sensor.power":
            return _make_state(power_w)
        if entity_id == "sensor.spot_price":
            return _make_state(spot_price)
        return None

    hass.states.get = MagicMock(side_effect=get_state)
    return hass


def _run_update(coord_module, coordinator, now=None):
    """Run _async_update_data with optional time override."""
    if now is not None:
        coord_module.dt_util.now.return_value = now
    return asyncio.run(coordinator._async_update_data())


class TestBasicAccumulation:
    """Strompris + energiledd + kapasitetsledd akkumuleres korrekt."""

    def test_first_update_no_accumulation(self, coord_module):
        """Forste oppdatering har ingen akkumulering (ingen _last_update)."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)
        _run_update(coord_module, c, _real_datetime(2026, 6, 15, 12, 0))

        assert c._monthly_accumulated_cost == 0.0
        assert c._monthly_accumulated_cost_strom == 0.0
        assert c._monthly_accumulated_cost_energiledd == 0.0
        assert c._monthly_accumulated_cost_kapasitetsledd == 0.0

    def test_second_update_accumulates(self, coord_module):
        """Andre oppdatering akkumulerer alle tre komponenter."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)

        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        # 5 kW * (60/3600) h = 5/60 kWh
        energy_kwh = 5.0 * (60 / 3600)

        # Strompris: spotpris - stromstotte
        from stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE
        stromstotte = (1.20 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        strom_pris = 1.20 - stromstotte

        # Sjekk intern state (unrounded)
        assert c._monthly_accumulated_cost_strom == pytest.approx(
            energy_kwh * strom_pris, abs=1e-10
        )

        # Energiledd (dagtariff for BKK)
        energiledd_dag = c.energiledd_dag
        assert c._monthly_accumulated_cost_energiledd == pytest.approx(
            energy_kwh * energiledd_dag, abs=1e-10
        )

        # Kapasitetsledd (tidsbasert, 60 sekunder)
        kapasitetsledd = c.kapasitetstrinn[0][1]  # trinn 1 (ingen topp enna)
        days_in_month = 30  # juni
        seconds_in_month = days_in_month * 24 * 3600
        expected_kap = 60 * (kapasitetsledd / seconds_in_month)
        assert c._monthly_accumulated_cost_kapasitetsledd == pytest.approx(
            expected_kap, abs=1e-10
        )

        # Total er summen
        expected_total = (energy_kwh * strom_pris) + (energy_kwh * energiledd_dag) + expected_kap
        assert c._monthly_accumulated_cost == pytest.approx(
            expected_total, abs=1e-10
        )


class TestKapasitetsleddLinear:
    """Kapasitetsledd akkumuleres lineaert, uavhengig av forbruk."""

    def test_zero_consumption_still_accumulates_kapasitetsledd(self, coord_module):
        """Kapasitetsledd oker selv uten stromforbruk."""
        hass = _make_hass(power_w=0, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)

        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        assert c._monthly_accumulated_cost_strom == 0.0
        assert c._monthly_accumulated_cost_energiledd == 0.0
        assert c._monthly_accumulated_cost_kapasitetsledd > 0

    def test_full_month_sums_to_kapasitetsledd(self, coord_module):
        """Over en hel maned summerer kapasitetsledd til noyaktig kapasitetsledd_kr."""
        hass = _make_hass(power_w=0, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)

        # Juni 2026 har 30 dager. Bruk 1-minutts intervaller.
        # 30 * 24 * 60 = 43200 oppdateringer er for mange, bruk 5-minutts intervaller.
        days_in_month = 30
        interval_minutes = 5
        total_updates = (days_in_month * 24 * 60) // interval_minutes

        t = _real_datetime(2026, 6, 1, 0, 0)
        _run_update(coord_module, c, t)

        # Kapasitetsledd for laveste trinn (0 kW forbruk)
        kapasitetsledd = c.kapasitetstrinn[0][1]  # BKK trinn 1: 155 kr

        for i in range(1, total_updates + 1):
            t_next = _real_datetime(2026, 6, 1, 0, 0) + timedelta(minutes=i * interval_minutes)
            # Siste oppdatering skal vaere 2026-06-30 23:55, fremdeles i juni
            if t_next.month != 6:
                break
            _run_update(coord_module, c, t_next)

        assert c._monthly_accumulated_cost_kapasitetsledd == pytest.approx(
            kapasitetsledd, abs=0.1
        )


class TestMonthReset:
    """Manedsskifte nullstiller alle akkumulatorer."""

    def test_month_change_resets_accumulators(self, coord_module):
        """Alle akkumulatorer nullstilles ved manedsskifte."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)

        # Bygg opp akkumulering i juni
        t0 = _real_datetime(2026, 6, 30, 23, 58)
        _run_update(coord_module, c, t0)
        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        assert c._monthly_accumulated_cost > 0
        assert c._monthly_accumulated_cost_strom > 0
        assert c._monthly_accumulated_cost_kapasitetsledd > 0

        # Kryss manedsskiftet til juli
        t2 = _real_datetime(2026, 7, 1, 0, 1)
        _run_update(coord_module, c, t2)

        # Manedsskiftet nullstiller. Deretter akkumuleres for elapsed fra t1 til t2.
        # t1=23:59, t2=00:01 -> 2 min = 120 sekunder (under 360s clamp).
        days_in_july = 31
        seconds_in_july = days_in_july * 24 * 3600
        elapsed = 120  # 2 minutter
        kapasitetsledd = c.kapasitetstrinn[0][1]
        expected_kap = elapsed * (kapasitetsledd / seconds_in_july)

        # Akkumulatorene inneholder kun den ene oppdateringen etter reset
        assert c._monthly_accumulated_cost_kapasitetsledd == pytest.approx(expected_kap, abs=1e-6)
        # Strom og energiledd inneholder bare den ene oppdateringen (ikke forrige maned)
        assert c._monthly_accumulated_cost_strom < 0.5


class TestNorgespricing:
    """Norgespris-kunder bruker norgespris i stedet for spot - stromstotte."""

    def test_norgespris_uses_fixed_price(self, coord_module):
        """Med Norgespris brukes fast pris, ikke spot - stromstotte."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry(har_norgespris=True)
        c = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)

        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        from stromkalkulator.const import get_norgespris_inkl_mva

        norgespris = get_norgespris_inkl_mva("standard")
        energy_kwh = 5.0 * (60 / 3600)

        assert c._monthly_accumulated_cost_strom == pytest.approx(
            energy_kwh * norgespris, abs=1e-10
        )

    def test_spot_pricing_with_subsidy(self, coord_module):
        """Uten Norgespris brukes spot - stromstotte."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry(har_norgespris=False)
        c = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)

        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        from stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE

        stromstotte = (1.20 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        strom_pris = 1.20 - stromstotte
        energy_kwh = 5.0 * (60 / 3600)

        assert c._monthly_accumulated_cost_strom == pytest.approx(
            energy_kwh * strom_pris, abs=1e-10
        )

    def test_norgespris_over_tak_uses_spot(self, coord_module):
        """Over Norgespris kWh-tak brukes spotpris uten stromstotte."""
        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry(har_norgespris=True)
        c = coord_module.NettleieCoordinator(hass, entry)

        # Sett forbruk over Norgespris-taket (5000 kWh for bolig)
        c._monthly_consumption = {"dag": 4000.0, "natt": 1001.0}

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)

        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        # Over tak: bruker spot - stromstotte (ikke norgespris)
        # Men stromstotte er 0 fordi monthly_total_kwh > stromstotte_max
        energy_kwh = 5.0 * (60 / 3600)
        strom_pris = 1.20 - 0  # stromstotte = 0 over tak

        assert c._monthly_accumulated_cost_strom == pytest.approx(
            energy_kwh * strom_pris, abs=1e-10
        )


class TestStoragePersistence:
    """Akkumulert kostnad overlever restart via lagring."""

    def test_save_and_load(self, coord_module):
        """Akkumulert kostnad lagres og lastes korrekt."""
        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store)

        hass = _make_hass(power_w=5000, spot_price=1.20)
        entry = _make_entry()
        c = coord_module.NettleieCoordinator(hass, entry)

        t0 = _real_datetime(2026, 6, 15, 12, 0)
        _run_update(coord_module, c, t0)
        t1 = t0 + timedelta(minutes=1)
        _run_update(coord_module, c, t1)

        # Verdier er lagret
        assert "monthly_accumulated_cost" in saved_data
        assert "monthly_accumulated_cost_strom" in saved_data
        assert "monthly_accumulated_cost_energiledd" in saved_data
        assert "monthly_accumulated_cost_kapasitetsledd" in saved_data
        assert saved_data["monthly_accumulated_cost"] > 0

        # Lag ny coordinator som laster fra lagret data
        def make_store_with_data(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=dict(saved_data))
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord_module.Store = MagicMock(side_effect=make_store_with_data)

        c2 = coord_module.NettleieCoordinator(hass, entry)
        asyncio.run(c2._load_stored_data())

        assert c2._monthly_accumulated_cost == pytest.approx(
            saved_data["monthly_accumulated_cost"], abs=1e-10
        )
        assert c2._monthly_accumulated_cost_strom == pytest.approx(
            saved_data["monthly_accumulated_cost_strom"], abs=1e-10
        )
        assert c2._monthly_accumulated_cost_energiledd == pytest.approx(
            saved_data["monthly_accumulated_cost_energiledd"], abs=1e-10
        )
        assert c2._monthly_accumulated_cost_kapasitetsledd == pytest.approx(
            saved_data["monthly_accumulated_cost_kapasitetsledd"], abs=1e-10
        )


class TestSensorClass:
    """Tester AkkumulertKostnadSensor-klassen."""

    def _make_sensor(self):
        """Sett opp sensor med mock coordinator og entry."""
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
            def __init__(self, coordinator):
                self.coordinator = coordinator

        _coord_mod.CoordinatorEntity = FakeCoordinatorEntity

        import stromkalkulator.sensor as sensor_mod
        importlib.reload(sensor_mod)

        coord = MagicMock()
        coord.data = {
            "monthly_accumulated_cost_kr": 123.4567,
            "monthly_accumulated_cost_strom_kr": 80.1234,
            "monthly_accumulated_cost_energiledd_kr": 30.5678,
            "monthly_accumulated_cost_kapasitetsledd_kr": 12.7655,
            "monthly_consumption_total_kwh": 200.5,
        }

        entry = MagicMock()
        entry.entry_id = "test"
        entry.data = {"tso": "bkk"}

        s = sensor_mod.AkkumulertKostnadSensor(coord, entry)
        return s

    def test_native_value(self):
        s = self._make_sensor()
        assert s.native_value == 123.4567

    def test_extra_attributes(self):
        s = self._make_sensor()
        attrs = s.extra_state_attributes
        assert attrs["strompris_kr"] == 80.1234
        assert attrs["energiledd_kr"] == 30.5678
        assert attrs["kapasitetsledd_kr"] == 12.7655
        assert attrs["total_kwh"] == 200.5
        assert "bruk" in attrs

    def test_disabled_by_default(self):
        s = self._make_sensor()
        assert s._attr_entity_registry_enabled_default is False

    def test_state_class_total(self):
        s = self._make_sensor()
        assert s._attr_state_class == "total"

    def test_none_when_no_data(self):
        s = self._make_sensor()
        s.coordinator.data = None
        assert s.native_value is None
        assert s.extra_state_attributes is None
