"""Tests for persistent storage: load, save, migration, and month-change reset.

Verifies _load_stored_data, _save_stored_data, migration from DSO-based
storage to entry-based storage, and correct data reset on stored month mismatch.
"""

from __future__ import annotations

import asyncio
import importlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest

from tests.conftest import _make_entry

OSLO = ZoneInfo("Europe/Oslo")


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


class TestEnergiBaselinePersistens:
    """Baselinen på Store-skjema v2, bundet til kilden sin.

    Vi akkumulerer kWh som delta av energisensoren. Persisteres ikke baselinen,
    blir første delta etter en omstart enten 0 (verdien tapt) eller gigantisk
    (alt forbruk siden restart). Uten kildebinding blir et målerbytte til
    falskt forbruk.

    Aldersgrensen er borte med vilje (kontrakt §5). En hytte som sto avslått i
    en uke skal få forbruket sitt fordelt, ikke slettet; vernet mot det
    gigantiske spranget er MAX_ENERGY_DELTA_KWH, som viser brukeren tallet.
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

    @staticmethod
    def _baseline(coord_modul, kwh=1234.567, *, kilde="maaler-1", entity_id="sensor.tpi"):
        from stromkalkulator.inputadapter import Baseline

        return Baseline(kilde, entity_id, kwh, datetime(2026, 6, 15, 11, 59))

    def test_baselinen_persisteres(self):
        """Roundtrip: verdien, kilden og observasjonstiden overlever omstarten."""
        coord = _reload_coord()

        saved_data: dict = {}
        coord.Store = MagicMock(side_effect=self._make_store_factory(None, saved_data))

        hass = MagicMock()
        entry = _make_entry(energy_sensor="sensor.tpi")
        coordinator = coord.NettleieCoordinator(hass, entry)
        coordinator._last_update = coord.dt_util.now() - timedelta(minutes=1)
        coordinator._baseline = self._baseline(coord)

        asyncio.run(coordinator._save_stored_data())

        lagret = saved_data["energi_baseline"]
        assert lagret["value_kwh"] == 1234.567
        assert lagret["source_identity"] == "maaler-1"
        assert lagret["schema_version"] == 2

        coord.Store = MagicMock(side_effect=self._make_store_factory(saved_data))
        coordinator2 = coord.NettleieCoordinator(hass, entry)
        assert coordinator2._baseline is None
        asyncio.run(coordinator2._load_stored_data())

        assert coordinator2._baseline.value_kwh == 1234.567
        assert coordinator2._baseline.source_identity == "maaler-1"

    def test_gammel_baseline_uten_kilde_forkastes(self):
        """Alt som ligger lagret fra før er en rå verdi uten kilde og uten enhet.

        Den forkastes én gang. Månedsdata beholdes, og neste avlesning setter ny
        baseline med delta 0. Det koster inntil ett pollintervall med forbruk,
        og alternativet, å stole på en verdi vi ikke vet hvilken måler kom fra,
        er verre.
        """
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 120.0, "natt": 80.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "last_tpi_kwh": 1234.567,
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None
        assert coordinator._baseline_forkastet is True
        assert coordinator._monthly_consumption.dag == 120.0
        assert coordinator._monthly_consumption.natt == 80.0

    def test_gammel_baseline_uansett_alder_forkastes_likt(self):
        """Aldersgrensen er ikke det som avgjør lenger, kildeidentiteten er."""
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

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None

    def test_v2_baseline_gjenopptas_uansett_alder(self):
        """Hytta som sto avslått i en uke skal ikke miste baselinen sin."""
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(days=7)).isoformat(),
            "energi_baseline": {
                "schema_version": 2,
                "source_identity": "maaler-1",
                "entity_id": "sensor.tpi",
                "value_kwh": 1234.567,
                "observed_at": "2026-06-08T10:00:00+00:00",
            },
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline.value_kwh == 1234.567
        assert coordinator._baseline_forkastet is False

    def test_baseline_mangler_i_storage_gir_none(self):
        """Bakoverkompat: en fil uten noen baseline i det hele tatt."""
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None
        assert coordinator._baseline_forkastet is False, "ingenting ble forkastet, det sto ingenting der"

    def test_skrevet_null_baseline_er_ikke_en_forkastet_baseline(self):
        """`_save_stored_data` skriver `energi_baseline: None` ved hver lagring.

        Nøkkelen finnes da i filen hos alle, også hos den som aldri har hatt en
        baseline. Et `nøkkel in data` gjorde derfor at hver eneste nye bruker
        fikk forkastet-flagget i diagnostikken og en INFO-linje om en baseline
        som aldri fantes, ved hver omstart. Falske positiver er grunnen til at
        vaktholdet i dette repoet ble avvist to ganger.
        """
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "energi_baseline": None,
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None
        assert coordinator._baseline_forkastet is False
        assert coordinator._baseline_rapport() is None

    def test_lesbar_baseline_uten_energisensor_er_ikke_forkastet(self):
        """Baselinen droppes fordi sensoren er fjernet, ikke fordi den var ulesbar.

        Teksten i loggen og flagget i diagnostikken sier «manglet
        kildeidentitet», og det ville vært feil her: den hadde kilde, den har
        bare ingen sensor å høre til lenger.
        """
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "energi_baseline": {
                "schema_version": 2,
                "source_identity": "maaler-1",
                "entity_id": "sensor.tpi",
                "value_kwh": 1234.567,
                "observed_at": "2026-06-08T10:00:00+00:00",
            },
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry())
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None
        assert coordinator._baseline_forkastet is False

    @pytest.mark.parametrize(
        "ugyldig",
        [
            {"schema_version": 2, "value_kwh": "tull", "entity_id": "sensor.tpi", "observed_at": "x"},
            {"schema_version": 1, "value_kwh": 1.0, "entity_id": "sensor.tpi", "observed_at": "x"},
            {"schema_version": 2, "value_kwh": -100.0, "entity_id": "sensor.tpi", "observed_at": "x"},
            {"schema_version": 2, "value_kwh": 0.0, "entity_id": "sensor.tpi", "observed_at": "x"},
            {"schema_version": 2, "value_kwh": float("nan"), "entity_id": "s", "observed_at": "x"},
            {"schema_version": 2, "value_kwh": float("inf"), "entity_id": "s", "observed_at": "x"},
            {"schema_version": 2, "value_kwh": 1.0, "observed_at": "2026-06-15T10:00:00+00:00"},
            {"schema_version": 2, "value_kwh": 1.0, "entity_id": "sensor.tpi"},
            "ikke en dict",
        ],
    )
    def test_korrupt_baseline_forkastes_uten_krasj(self, ugyldig):
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "energi_baseline": ugyldig,
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None

    def test_baseline_droppes_naar_energisensoren_er_fjernet(self):
        """Settes sensoren inn igjen senere, er det per definisjon en ny kilde."""
        coord = _reload_coord()
        now = coord.dt_util.now()
        stored = {
            "daily_max_power": {},
            "monthly_consumption": {"dag": 0.0, "natt": 0.0},
            "current_month": now.strftime("%Y-%m"),
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "energi_baseline": {
                "schema_version": 2,
                "source_identity": "maaler-1",
                "entity_id": "sensor.tpi",
                "value_kwh": 1234.567,
                "observed_at": "2026-06-15T10:00:00+00:00",
            },
        }
        coord.Store = MagicMock(side_effect=self._make_store_factory(stored))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor=None))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None


class TestLastEnergyIncreasePersistens:
    """`last_energy_increase` er additiv: nye filer har den, gamle klarer seg uten.

    Tidsstempelet er det frossen-deteksjonen måler fra. Uten persistens ville
    hver omstart nullstille klokken, og et flere døgn langt utfall ville aldri
    rekke over terskelen.
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

    def test_roundtrip(self):
        """Tidsstempelet overlever en kort omstart, altså en med baseline i behold."""
        coord = _reload_coord()
        saved: dict = {}
        coord.Store = MagicMock(side_effect=self._make_store_factory(None, saved))

        hass = MagicMock()
        entry = _make_entry(energy_sensor="sensor.tpi")
        coordinator = coord.NettleieCoordinator(hass, entry)
        coordinator._last_energy_increase = datetime(2026, 6, 15, 10, 58)
        coordinator._baseline = TestEnergiBaselinePersistens._baseline(coord, 133282.18)
        # Samme klokkeslett som dt_util.now() i testene, altså en omstart uten
        # nedetid. Nedetid skyver klokken fram, og det er en annen test.
        coordinator._last_update = datetime(2026, 6, 15, 12, 0)

        asyncio.run(coordinator._save_stored_data())
        assert saved["last_energy_increase"] == "2026-06-15T10:58:00"

        coord.Store = MagicMock(side_effect=self._make_store_factory(saved))
        gjenopptatt = coord.NettleieCoordinator(hass, entry)
        asyncio.run(gjenopptatt._load_stored_data())
        assert gjenopptatt._last_energy_increase == datetime(2026, 6, 15, 10, 58)

    def test_lang_nedetid_nullstiller_klokken(self):
        """O1: baseline droppet som foreldet skal ta frossen-klokken med seg.

        Hytta som slås på etter en uke har en gammel last_energy_increase i
        lagringsfilen, men ingen tpi-baseline å måle fra. Å ha vært avslått er
        ikke en frossen måler, så klokken skal starte ved første poll.
        """
        coord = _reload_coord()
        coord.Store = MagicMock(
            side_effect=self._make_store_factory(
                {
                    "last_energy_increase": "2026-06-08T12:00:00",
                    "last_update": "2026-06-08T12:00:00",
                    "last_tpi_kwh": 133282.18,  # v1-form uten kilde: forkastes
                }
            )
        )
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._baseline is None, "v1-baselinen har ingen kilde og skal forkastes"
        assert coordinator._last_energy_increase is None

    def test_nedetiden_teller_ikke_paa_klokken(self):
        """Fem timer nede: timen vi så beholdes, de blinde fem gjør ikke.

        Baselinen er i behold, så klokken overlever omstarten, men den skyves
        fram med nedetiden. Ingen kunne se telleren øke mens HA var av, og et
        strømbrudd på en natt skal ikke bli et frossen-varsel ved første poll.
        """
        coord = _reload_coord()
        coord.Store = MagicMock(
            side_effect=self._make_store_factory(
                {
                    "last_energy_increase": "2026-06-15T06:00:00",
                    "last_update": "2026-06-15T07:00:00",
                    "energi_baseline": {
                        "schema_version": 2,
                        "source_identity": "maaler-1",
                        "entity_id": "sensor.tpi",
                        "value_kwh": 133282.18,
                        "observed_at": "2026-06-15T05:00:00+00:00",
                    },
                }
            )
        )
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        # dt_util.now() er 12:00: en time var observert før avstengningen 07:00,
        # så klokken står på 11:00 og har to timer igjen til terskelen.
        assert coordinator._baseline.value_kwh == 133282.18
        assert coordinator._last_energy_increase == datetime(2026, 6, 15, 11, 0)

    def test_tidsstempel_lagres_i_utc(self):
        """Tidssonebevisst tidsstempel skal lagres som UTC, ikke lokal sone.

        Kommer det tilbake med samme ZoneInfo-objekt som dt_util.now(), hopper
        Python over utcoffset i subtraksjonen og vaktholdet måler veggklokke.
        """
        from zoneinfo import ZoneInfo

        coord = _reload_coord()
        saved: dict = {}
        coord.Store = MagicMock(side_effect=self._make_store_factory(None, saved))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        coordinator._last_energy_increase = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("Europe/Oslo"))

        asyncio.run(coordinator._save_stored_data())
        assert saved["last_energy_increase"] == "2026-06-15T10:00:00+00:00"

    def test_gammel_lagringsfil_uten_nokkelen(self):
        """Fil skrevet før v1.17.0: ingen nøkkel, ingen krasj, står på None."""
        coord = _reload_coord()
        coord.Store = MagicMock(
            side_effect=self._make_store_factory({"daily_max_power": {}, "monthly_consumption": {}})
        )
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())
        assert coordinator._last_energy_increase is None

    def test_ulesbart_tidsstempel_droppes(self):
        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._make_store_factory({"last_energy_increase": "i går"}))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())
        assert coordinator._last_energy_increase is None


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
        assert coordinator._monthly_consumption == coord.ConsumptionData(dag=100.0, natt=50.0)

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
            # Kostnadskjernen (L3b): splitten av energileddet, strømstøtten i
            # kroner, og åpningsbalansen for et energiledd fra før splitten.
            "monthly_stromstotte",
            "monthly_energiledd_dag",
            "monthly_energiledd_natt",
            "monthly_avgifter",
            "monthly_energiledd_apning",
            "previous_month_export_kwh",
            "previous_month_export_revenue",
            "previous_month_cost",
            "last_update",
            "skjema_versjon",
            "energi_baseline",
            "weekly_max_power",
            "last_energy_increase",
            # Avregningsboken (kontrakt D). Den skriver `skjema_versjon` over,
            # og den er én teller for hele filen: K1 satte den til 2, boken
            # løfter den til 3.
            "aktiv_maned",
            "ufullstendig",
            "avvist_kwh",
            "sist_observert",
            "pris",
            "intervaller",
            "arkiv",
        }
        assert expected_keys == set(saved_data.keys())
        assert saved_data["skjema_versjon"] == 3

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


class TestAvregningsbokPersistens:
    """Store v3: boken skrives, leses og migreres fra v2 (avregningskontrakten D).

    Kollisjonen dette forebygger: `skjema_versjon` er én teller for hele
    Store-filen. K1 satte den til 2 for baselinen sin, og boken løfter den til
    3. To skrivere av samme nøkkel med hvert sitt tall ville gjort filen
    ulesbar for begge.
    """

    @staticmethod
    def _store(stored_data, saved_holder=None):
        def make_store(hass, version, key):
            store = MagicMock()
            store.async_load = AsyncMock(return_value=stored_data)

            async def save(data):
                if saved_holder is not None:
                    saved_holder.clear()
                    saved_holder.update(data)

            store.async_save = AsyncMock(side_effect=save)
            store.async_remove = AsyncMock()
            return store

        return make_store

    @staticmethod
    def _v2_fil(coord, *, maned="2026-06"):
        """En lagringsfil slik 1.16-serien etterlater den (K1, skjema 2)."""
        now = coord.dt_util.now()
        return {
            "skjema_versjon": 2,
            "daily_max_power": {"2026-06-14": {"kw": 7.5, "hour": 17}},
            "weekly_max_power": {},
            "monthly_consumption": {"dag": 410.0, "natt": 260.0},
            "current_month": maned,
            "previous_month_consumption": {"dag": 0.0, "natt": 0.0},
            "monthly_norgespris_compensation": -123.45,
            "last_update": (now - timedelta(minutes=1)).isoformat(),
            "energi_baseline": {
                "schema_version": 2,
                "source_identity": "maaler-1",
                "entity_id": "sensor.tpi",
                "value_kwh": 5000.0,
                "observed_at": (now - timedelta(minutes=1)).astimezone(UTC).isoformat(),
            },
        }

    def test_v2_fil_beholder_maanedsdata_og_baseline(self):
        """Brukeren på 1.16.0 skal komme uskadd gjennom."""
        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._store(self._v2_fil(coord)))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._monthly_consumption == coord.ConsumptionData(dag=410.0, natt=260.0)
        assert coordinator._monthly_norgespris_compensation == -123.45
        assert coordinator._baseline is not None
        assert coordinator._baseline.value_kwh == 5000.0
        # Baselinen er bokens også: uten den ville første avlesning etter
        # oppgraderingen blitt ny baseline, og en times forbruk forsvunnet.
        assert coordinator._bok.sist_observert is not None
        assert coordinator._bok.sist_observert.value_kwh == 5000.0

    def test_v2_fil_merker_maaneden_ufullstendig(self):
        """Månedssummene fra v2 kan ikke gjøres om til intervallhistorikk."""
        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._store(self._v2_fil(coord)))

        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())

        assert coordinator._bok.ufullstendig is True
        assert coordinator._bok.intervaller() == []
        # Månedssummen fra v2 ligger som åpningsbalanse utenfor boken.
        assert coordinator._aapningsbalanse() == coord.ConsumptionData(dag=410.0, natt=260.0)

    def test_ufullstendig_forsvinner_ved_forste_maanedsskifte(self):
        """Flagget gjelder overgangsmåneden, ikke for alltid (kontrakt D)."""
        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._store(self._v2_fil(coord)))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())
        assert coordinator._bok.ufullstendig is True

        from stromkalkulator.avregning import Avlesning

        naa = coord.dt_util.now().replace(tzinfo=OSLO)
        coordinator._bok.bokfor(
            Avlesning("maaler-1", 5001.0, naa.replace(month=6, day=30, hour=23, minute=30))
        )
        coordinator._bok.bokfor(Avlesning("maaler-1", 5003.0, naa.replace(month=7, day=1, hour=0, minute=30)))

        assert coordinator._bok.ufullstendig is False

    def test_v3_fil_skriver_en_skjemaversjon_for_hele_filen(self):
        """`skjema_versjon` er 3 på toppnivå, og v2-feltene står ved siden av."""
        coord = _reload_coord()
        lagret: dict = {}
        coord.Store = MagicMock(side_effect=self._store(self._v2_fil(coord), lagret))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(coordinator._load_stored_data())
        asyncio.run(coordinator._save_stored_data())

        assert lagret["skjema_versjon"] == 3
        # v2-feltene skrives uendret, så en nedgradering ikke mister måneden.
        assert lagret["energi_baseline"]["schema_version"] == 2
        assert lagret["monthly_consumption"] == {"dag": 410.0, "natt": 260.0}
        # Og bokens egne nøkler ligger på toppnivå, ikke nestet.
        assert lagret["aktiv_maned"] is None
        assert lagret["ufullstendig"] is True

    def test_apent_intervall_og_prisruter_overlever_omstart(self):
        """C5: en omstart midt i timen skal ikke gjøre komplett til delvis."""
        coord = _reload_coord()
        lagret: dict = {}
        coord.Store = MagicMock(side_effect=self._store(None, lagret))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))

        from stromkalkulator.avregning import Avlesning

        start = datetime(2026, 6, 15, 10, 0, tzinfo=OSLO)
        for kvarter in range(4):
            coordinator._bok.registrer_prisprove(
                start + timedelta(minutes=15 * kvarter, seconds=120), 1.0 + kvarter * 0.1
            )
        coordinator._bok.bokfor(Avlesning("maaler-1", 100.0, start))
        coordinator._bok.bokfor(Avlesning("maaler-1", 103.0, start + timedelta(minutes=59)))
        coordinator._last_update = coord.dt_util.now()
        asyncio.run(coordinator._save_stored_data())

        coord.Store = MagicMock(side_effect=self._store(lagret))
        gjenopptatt = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        asyncio.run(gjenopptatt._load_stored_data())

        intervall = gjenopptatt._bok.intervall(start.astimezone(UTC))
        assert intervall is not None
        assert intervall.kwh == pytest.approx(3.0)
        assert intervall.pris is not None
        assert intervall.pris.pris_prover == 4
        assert intervall.nok_per_kwh_eks_mva == pytest.approx(1.15)

    def test_lagringen_tar_bare_med_vinduet_som_kan_endre_seg(self):
        """En hel måned med prisruter er hundrevis av kilobyte per poll.

        Lagringen skal bære det åpne intervallet og timene rett før, ikke hele
        måneden. Det som faller utenfor er ferdig avregnet, og summen av det
        ligger i månedsfeltene.
        """
        coord = _reload_coord()
        lagret: dict = {}
        coord.Store = MagicMock(side_effect=self._store(None, lagret))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))

        from stromkalkulator.avregning import Avlesning

        start = datetime(2026, 6, 1, 0, 0, tzinfo=OSLO)
        teller = 100.0
        for time in range(48):
            coordinator._bok.registrer_prisprove(start + timedelta(hours=time, minutes=2), 1.0)
            teller += 2.0
            coordinator._bok.bokfor(Avlesning("maaler-1", teller, start + timedelta(hours=time + 1)))
        coord.dt_util.now.return_value = start + timedelta(hours=48)
        asyncio.run(coordinator._save_stored_data())

        assert len(coordinator._bok.intervaller()) >= 40
        assert len(lagret["intervaller"]) <= 4
        assert len(lagret["pris"]["ruter"]) <= 4

    def test_debugloggen_bærer_ikke_kildeidentiteten(self, caplog):
        """§10.1: `source_identity` er målepunkt-ID hos AMS-integrasjoner.

        Home Assistant har en knapp som slår på DEBUG og laster ned loggen for
        innliming i et offentlig issue. Entity-id-en skal stå, for uten den vet
        ikke brukeren hvilken sensor linjen gjelder.
        """
        import logging

        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._store(None))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))
        coordinator._baseline = TestEnergiBaselinePersistens._baseline(coord, kilde="707057500012345678")

        with caplog.at_level(logging.DEBUG, logger="stromkalkulator.coordinator"):
            asyncio.run(coordinator._save_stored_data())

        assert "707057500012345678" not in caplog.text
        assert "sensor.tpi" in caplog.text
        assert "<redigert>" in caplog.text

    def test_uten_debuglogging_bygges_ingen_kopi(self, caplog):
        """Motsatt retning: redigeringen skal ikke koste noe når DEBUG er av."""
        import logging

        coord = _reload_coord()
        coord.Store = MagicMock(side_effect=self._store(None))
        coordinator = coord.NettleieCoordinator(MagicMock(), _make_entry(energy_sensor="sensor.tpi"))

        with caplog.at_level(logging.INFO, logger="stromkalkulator.coordinator"):
            asyncio.run(coordinator._save_stored_data())

        assert "Lagret" not in caplog.text
