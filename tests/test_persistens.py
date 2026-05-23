"""Tests for persistent storage: load, save, migration, and month-change reset.

Verifies _load_stored_data, _save_stored_data, migration from DSO-based
storage to entry-based storage, and correct data reset on stored month mismatch.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from tests.conftest import _make_entry


def _reload_coord():
    """Reload coordinator module fresh."""
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    return coord


class TestSaveLoadCycle:
    """Data should survive a save -> load cycle."""

    def test_round_trip(self):
        """Saved data is faithfully restored on load."""
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)

        # Set some state
        coordinator._daily_max_power = {
            "2026-04-01": coord.DailyMaxEntry(kw=8.5, hour=10),
            "2026-04-02": coord.DailyMaxEntry(kw=12.0, hour=16),
        }
        coordinator._monthly_consumption = coord.ConsumptionData(dag=200.0, natt=100.0)
        coordinator._monthly_norgespris_diff = 15.5
        coordinator._previous_month_consumption = coord.ConsumptionData(dag=300.0, natt=150.0)
        coordinator._previous_month_top_3 = {
            "2026-03-01": coord.DailyMaxEntry(kw=10.0, hour=8),
            "2026-03-10": coord.DailyMaxEntry(kw=9.0, hour=18),
        }
        coordinator._previous_month_name = "mars 2026"

        asyncio.run(coordinator._save_stored_data())

        # Verify save was called with correct data
        assert saved_data["daily_max_power"] == {
            "2026-04-01": {"kw": 8.5, "hour": 10},
            "2026-04-02": {"kw": 12.0, "hour": 16},
        }
        assert saved_data["monthly_consumption"] == {"dag": 200.0, "natt": 100.0}
        assert saved_data["monthly_norgespris_diff"] == 15.5
        assert saved_data["previous_month_consumption"] == {"dag": 300.0, "natt": 150.0}
        assert saved_data["previous_month_top_3"] == {
            "2026-03-01": {"kw": 10.0, "hour": 8},
            "2026-03-10": {"kw": 9.0, "hour": 18},
        }
        assert saved_data["previous_month_name"] == "mars 2026"

        # Now create a new coordinator and load the saved data
        def make_store_with_data(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=saved_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store_with_data)

        coordinator2 = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._daily_max_power == {
            "2026-04-01": coord.DailyMaxEntry(kw=8.5, hour=10),
            "2026-04-02": coord.DailyMaxEntry(kw=12.0, hour=16),
        }
        assert coordinator2._monthly_consumption == coord.ConsumptionData(dag=200.0, natt=100.0)
        assert coordinator2._monthly_norgespris_diff == 15.5
        assert coordinator2._previous_month_consumption == coord.ConsumptionData(dag=300.0, natt=150.0)
        assert coordinator2._previous_month_top_3 == {
            "2026-03-01": coord.DailyMaxEntry(kw=10.0, hour=8),
            "2026-03-10": coord.DailyMaxEntry(kw=9.0, hour=18),
        }
        assert coordinator2._previous_month_name == "mars 2026"

    def test_load_empty_store_uses_defaults(self):
        """Loading from empty store should keep default values."""
        coord = _reload_coord()

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._daily_max_power == {}
        assert coordinator._monthly_consumption == coord.ConsumptionData()
        assert coordinator._previous_month_top_3 == {}


class TestLastUpdatePersistens:
    """_last_update skal lagres og lastes for å unngå tap av forbruk ved restart.

    Bug: ved HA-restart settes _last_update = None i __init__, og første poll
    får elapsed_hours = 0 -> energien for restart-perioden ignoreres. Hvis
    spot-sensor ikke er klar enda kastes UpdateFailed slik at _last_update
    forblir None gjennom hele oppstarten. Når første vellykkede poll endelig
    kjører cappes elapsed til MAX_ELAPSED_HOURS (6 min). April 2026 hadde
    12 release-restarter -- gapet forklarer en del av 36 %-Norgespris-bugen.
    """

    def test_last_update_persisteres(self):
        """_last_update lagres som isoformat og restored hvis innenfor vindu."""
        coord = _reload_coord()

        saved_data: dict = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)

        # dt_util.now() er 2026-06-15 12:00:00 (conftest). MAX_ELAPSED_HOURS = 0.1.
        # Sett _last_update til 1 minutt tilbake -- godt innenfor 6-minutters-vinduet.
        now = coord.dt_util.now()
        last_update = now - timedelta(minutes=1)
        coordinator._last_update = last_update

        asyncio.run(coordinator._save_stored_data())

        assert saved_data["last_update"] == last_update.isoformat()

        # Last data i en ny coordinator
        def make_store_with_data(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=saved_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store_with_data)

        coordinator2 = coord.NettleieCoordinator(hass, entry)
        assert coordinator2._last_update is None  # __init__ default
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._last_update == last_update

    def test_last_update_ignoreres_hvis_for_gammelt(self):
        """Lagret last_update eldre enn MAX_ELAPSED_HOURS skal ignoreres.

        Vi vil ikke at "siste oppdatering var 3 timer siden" skal gi
        3 h * current_power i akkumulert energi -- det ville være feil.
        Bedre å starte friskt (None) og miste én poll-syklus.
        """
        coord = _reload_coord()

        # Storage med last_update fra 3 timer siden (langt utenfor 6-min-vinduet)
        now = coord.dt_util.now()
        gammelt = (now - timedelta(hours=3)).isoformat()
        stored_data = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": gammelt,
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_update is None

    def test_last_update_mangler_i_storage_gir_none(self):
        """Bakoverkompatibilitet: storage uten last_update -> _last_update er None."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored_data = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            # last_update mangler bevisst
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_update is None

    def test_last_update_korrupt_isoformat_ignoreres(self):
        """Ugyldig isoformat-string skal logges som warning og ignoreres."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored_data = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": "ikke-en-gyldig-dato",
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_update is None


class TestLastTpiKwhPersistens:
    """Tester for persistens og restore av _last_tpi_kwh (fix B).

    Fix B akkumulerer kWh som delta av tpi-sensoren. Hvis _last_tpi_kwh
    ikke persisteres ved restart, blir første delta enten 0 (verdi tapt)
    eller gigantisk (alt forbruk siden restart). Begge er feil.
    Restore krever fersk last_update for å unngå at en uker gammel tpi
    bruker som baseline ved første poll.
    """

    @staticmethod
    def _make_store_factory(stored_data, saved_holder=None):
        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            if saved_holder is not None:
                async def save(data):
                    saved_holder.update(data)
                store.async_save = AsyncMock(side_effect=save)
            else:
                store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store
        return make_store

    def test_last_tpi_kwh_persisteres(self):
        """Roundtrip: save lagrer float, load gjenoppretter eksakt verdi."""
        coord = _reload_coord()

        saved_data: dict = {}
        coord.Store = MagicMock(side_effect=self._make_store_factory(None, saved_data))

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)

        # Sett fersk last_update slik at tpi restores ved load
        now = coord.dt_util.now()
        coordinator._last_update = now - timedelta(minutes=1)
        coordinator._last_tpi_kwh = 1234.567

        asyncio.run(coordinator._save_stored_data())

        assert saved_data["last_tpi_kwh"] == 1234.567

        coord.Store = MagicMock(side_effect=self._make_store_factory(saved_data))
        coordinator2 = coord.NettleieCoordinator(hass, entry)
        assert coordinator2._last_tpi_kwh is None
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._last_tpi_kwh == 1234.567

    def test_last_tpi_kwh_ignoreres_hvis_last_update_stale(self):
        """last_update > TPI_STALE_HOURS (24t) gammelt: tpi droppes."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(hours=25)).isoformat(),
            "last_tpi_kwh": 1234.567,
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        hass = MagicMock()
        coordinator = coord.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_tpi_kwh is None

    def test_last_tpi_kwh_ignoreres_hvis_last_update_mangler(self):
        """Uten last_update kan vi ikke bedømme alder: drop tpi."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_tpi_kwh": 1234.567,
            # last_update mangler bevisst
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        hass = MagicMock()
        coordinator = coord.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_tpi_kwh is None

    def test_last_tpi_kwh_mangler_i_storage_gir_none(self):
        """Bakoverkompat: storage uten last_tpi_kwh-nøkkel."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            # last_tpi_kwh mangler
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        hass = MagicMock()
        coordinator = coord.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._last_tpi_kwh is None

    def test_last_tpi_kwh_korrupt_verdi_ignoreres(self):
        """Ikke-numerisk verdi: load skal ikke kaste, tpi forblir None."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "last_tpi_kwh": "not_a_number",
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        hass = MagicMock()
        coordinator = coord.NettleieCoordinator(hass, _make_entry())
        asyncio.run(coordinator._load_stored_data())  # skal ikke kaste

        assert coordinator._last_tpi_kwh is None

    def test_last_tpi_kwh_negativ_eller_null_ignoreres(self):
        """Negativ eller null tpi er ugyldig; tpi-tellere er monotont stigende."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        for ugyldig in (-100.0, 0.0):
            stored = {
                "daily_max_power": {},
                "monthly_consumption": {"dag": 0.0, "natt": 0.0},
                "current_month": now.strftime("%Y-%m"),
                "last_update": (now - timedelta(minutes=1)).isoformat(),
                "last_tpi_kwh": ugyldig,
            }
            coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

            hass = MagicMock()
            coordinator = coord.NettleieCoordinator(hass, _make_entry())
            asyncio.run(coordinator._load_stored_data())

            assert coordinator._last_tpi_kwh is None, f"verdi {ugyldig} burde gi None"

    def test_last_tpi_kwh_nan_inf_ignoreres(self):
        """NaN/Inf: defensiv filtrering via math.isfinite."""
        coord = _reload_coord()

        now = coord.dt_util.now()
        for ugyldig in (float("nan"), float("inf"), float("-inf")):
            stored = {
                "daily_max_power": {},
                "monthly_consumption": {"dag": 0.0, "natt": 0.0},
                "current_month": now.strftime("%Y-%m"),
                "last_update": (now - timedelta(minutes=1)).isoformat(),
                "last_tpi_kwh": ugyldig,
            }
            coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

            hass = MagicMock()
            coordinator = coord.NettleieCoordinator(hass, _make_entry())
            asyncio.run(coordinator._load_stored_data())

            assert coordinator._last_tpi_kwh is None, f"verdi {ugyldig} burde gi None"

    def test_round_trip_inkluderer_last_tpi_med_verdi(self):
        """Variant av test_round_trip som faktisk verifiserer at last_tpi_kwh
        round-tripper med verdi, ikke bare at nøkkelen finnes."""
        coord = _reload_coord()

        saved_data: dict = {}
        coord.Store = MagicMock(side_effect=self._make_store_factory(None, saved_data))

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)

        now = coord.dt_util.now()
        coordinator._last_update = now - timedelta(minutes=2)
        coordinator._last_tpi_kwh = 9876.5

        asyncio.run(coordinator._save_stored_data())
        assert saved_data["last_tpi_kwh"] == 9876.5

        coord.Store = MagicMock(side_effect=self._make_store_factory(saved_data))
        coordinator2 = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._last_tpi_kwh == 9876.5


class TestMigrationFromDSOStorage:
    """Migration from old DSO-based storage to entry-based storage."""

    def test_migrates_from_dso_key_to_entry_key(self):
        """When entry store is empty, data from DSO store is loaded and migrated."""
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 5.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        stores = {}

        def make_store(hass, version, key):
            store = MagicMock()
            stores[key] = store
            if key == "stromkalkulator_bkk":
                store.async_load = AsyncMock(return_value=stored_data)
                store.async_remove = AsyncMock()
            else:
                store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry("entry_new", dso_id="bkk")
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # Data should be loaded from old store (migrated from float to dict format)
        assert coordinator._daily_max_power == {"2026-04-01": coord.DailyMaxEntry(kw=5.0)}

        # New store should be saved to
        entry_store = stores["stromkalkulator_entry_new"]
        entry_store.async_save.assert_called_once()

        # Old store should be removed
        old_store = stores["stromkalkulator_bkk"]
        old_store.async_remove.assert_called_once()

    def test_no_migration_when_entry_store_has_data(self):
        """When entry store has data, DSO store is never checked."""
        coord = _reload_coord()

        now = datetime.now()
        entry_data = {
            "daily_max_power": {"2026-04-01": 9.0},
            "monthly_consumption": {"dag": 200.0, "natt": 100.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        old_store_accessed = False

        def make_store(hass, version, key):
            nonlocal old_store_accessed
            store = MagicMock()
            if key == "stromkalkulator_entry_test":
                store.async_load = AsyncMock(return_value=entry_data)
            else:
                old_store_accessed = True
                store.async_load = AsyncMock(return_value=None)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry("entry_test", dso_id="bkk")
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # Should have loaded from entry store, not DSO store (migrated format)
        assert coordinator._daily_max_power == {"2026-04-01": coord.DailyMaxEntry(kw=9.0)}
        assert not old_store_accessed


class TestMonthMismatchReset:
    """Loading stored data from a different month should reset current-month data."""

    def test_stored_month_differs_sets_stored_month(self):
        """If stored month != current month, _current_month is set to stored value
        so that the normal month-transition in _async_update_data fires."""
        coord = _reload_coord()

        now = datetime.now()
        current_month_str = now.strftime("%Y-%m")
        # Use a different month string
        old_month_str = "2025-12"
        assert old_month_str != current_month_str

        stored_data = {
            "daily_max_power": {"old-date": 15.0},
            "monthly_consumption": {"dag": 500.0, "natt": 300.0},
            "current_month": old_month_str,
            "monthly_norgespris_diff": 99.9,
            "previous_month_consumption": {"dag": 250.0, "natt": 150.0},
            "previous_month_top_3": {"2025-11-01": 8.0},
            "previous_month_name": "november 2025",
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # _current_month should be set to stored value (triggers transition in _async_update_data)
        assert coordinator._current_month == old_month_str
        # Data is loaded as-is (migrated from float to dict); transition happens in _async_update_data
        assert coordinator._daily_max_power == {"old-date": coord.DailyMaxEntry(kw=15.0)}

        # Previous month data should be preserved (migrated format)
        assert coordinator._previous_month_consumption == coord.ConsumptionData(dag=250.0, natt=150.0)
        assert coordinator._previous_month_top_3 == {"2025-11-01": coord.DailyMaxEntry(kw=8.0)}
        assert coordinator._previous_month_name == "november 2025"

    def test_stored_month_matches_preserves_data(self):
        """If stored month == current month, data is preserved."""
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 7.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.strftime("%Y-%m"),
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "previous_month_top_3": {},
            "previous_month_name": None,
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._daily_max_power == {"2026-04-01": coord.DailyMaxEntry(kw=7.0)}
        assert coordinator._monthly_consumption == coord.ConsumptionData(dag=100.0, natt=50.0)


class TestSaveDataStructure:
    """Verify the structure of saved data."""

    def test_save_includes_all_fields(self):
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._save_stored_data())

        expected_keys = {
            "daily_max_power",
            "monthly_consumption",
            "current_month",
            "previous_month_consumption",
            "previous_month_top_3",
            "previous_month_name",
            "monthly_norgespris_diff",
            "previous_month_norgespris_diff",
            "monthly_norgespris_compensation",
            "previous_month_norgespris_compensation",
            "previous_month_kapasitetsledd",
            "previous_month_kapasitetstrinn",
            "previous_month_energiledd_dag",
            "previous_month_energiledd_natt",
            "daily_cost",
            "current_date",
            "current_hour_energy",
            "current_hour",
            "monthly_export_kwh",
            "monthly_export_revenue",
            "monthly_cost",
            "monthly_accumulated_cost",
            "monthly_accumulated_cost_strom",
            "monthly_accumulated_cost_energiledd",
            "monthly_accumulated_cost_kapasitetsledd",
            "previous_month_export_kwh",
            "previous_month_export_revenue",
            "previous_month_cost",
            "last_update",
            "last_tpi_kwh",
        }
        assert expected_keys == set(saved_data.keys())

    def test_save_stores_current_month_as_string(self):
        coord = _reload_coord()

        saved_data = {}

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=None)

            async def save(data):
                saved_data.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._save_stored_data())

        # Coordinator init uses dt_util.now() which conftest sets to 2026-06-15
        assert saved_data["current_month"] == "2026-06"


class TestLoadMissingFields:
    """Loading data with missing optional fields should use defaults."""

    def test_missing_norgespris_diff_defaults_to_zero(self):
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {"2026-04-01": 5.0},
            "monthly_consumption": {"dag": 100.0, "natt": 50.0},
            "current_month": now.month,
            # missing: monthly_norgespris_diff
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._monthly_norgespris_diff == 0.0

    def test_missing_previous_month_defaults(self):
        coord = _reload_coord()

        now = datetime.now()
        stored_data = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.month,
            # missing: previous_month_*, monthly_norgespris_diff
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._previous_month_consumption == coord.ConsumptionData()
        assert coordinator._previous_month_top_3 == {}
        assert coordinator._previous_month_name is None


# =============================================================================
# Storage-korrupsjon (validator-tester ligger i test_coordinator_robustness.py)
# =============================================================================


class TestCorruptStorageData:
    """Test _load_stored_data with corrupt data."""

    def test_corrupt_kapasitetsledd_string_defaults_to_zero(self):
        """Non-numeric kapasitetsledd in storage should default to 0."""
        coord = _reload_coord()

        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": "2026-06",
            "previous_month_kapasitetsledd": "not_a_number",
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._previous_month_kapasitetsledd == 0

    def test_totally_corrupt_storage_uses_defaults(self):
        """Storage data that raises on access should fall back to defaults."""
        coord = _reload_coord()

        # A list instead of dict will cause AttributeError on .get()
        stored = [1, 2, 3]

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        # Should have defaults, not crash
        assert coordinator._daily_max_power == {}
        assert coordinator._monthly_consumption == coord.ConsumptionData()

    def test_wrong_typed_values_per_key_use_defaults(self):
        """Dict with wrong-typed values per key should fall back to defaults."""
        coord = _reload_coord()

        stored = {
            "daily_max_power": "not_a_dict",  # Should be dict
            "monthly_consumption": 42,  # Should be dict
            "current_month": ["wrong"],  # Should be str or int
        }

        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored)
            store.async_save = AsyncMock()
            store.async_remove = AsyncMock()
            return store

        coord.Store = MagicMock(side_effect=make_store)

        hass = MagicMock()
        entry = _make_entry()
        coordinator = coord.NettleieCoordinator(hass, entry)
        asyncio.run(coordinator._load_stored_data())

        assert isinstance(coordinator._daily_max_power, dict)
        assert isinstance(coordinator._monthly_consumption, coord.ConsumptionData)
