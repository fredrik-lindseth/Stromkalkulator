"""Tests for __init__.py: async_setup_entry and async_unload_entry.

Verifies that setup creates a coordinator, forwards platforms,
and that unload returns True. Also tests DSO migration triggering.
"""

from __future__ import annotations

import asyncio
import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.conftest import _make_entry


@pytest.fixture
def init_module():
    """Reload __init__ module and coordinator module."""
    import stromkalkulator.__init__ as init_mod
    import stromkalkulator.coordinator as coord

    importlib.reload(coord)
    importlib.reload(init_mod)

    # Patch Store in coordinator
    def make_store(hass, version, key):
        store = MagicMock()
        store.async_load = AsyncMock(return_value=None)
        store.async_save = AsyncMock()
        store.async_remove = AsyncMock()
        return store

    coord.Store = MagicMock(side_effect=make_store)
    return init_mod


def _make_hass():
    """HA-mock spesialtilpasset for setup/unload-tester (config_entries-API).

    Beholder denne lokalt fordi den trenger andre attributter enn den vanlige
    states.get-mockingen i conftest._make_hass.
    """
    hass = MagicMock()
    hass.config_entries.async_forward_entry_setups = AsyncMock()
    hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
    hass.config_entries.async_update_entry = MagicMock()
    hass.config.path = MagicMock(return_value="/tmp/.storage")
    return hass


class TestAsyncSetupEntry:
    """async_setup_entry creates coordinator and forwards platforms."""

    def test_returns_true(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        result = asyncio.run(init_module.async_setup_entry(hass, entry))
        assert result is True

    def test_sets_runtime_data(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_setup_entry(hass, entry))
        assert entry.runtime_data is not None

    def test_forwards_sensor_platform(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_setup_entry(hass, entry))
        hass.config_entries.async_forward_entry_setups.assert_called_once()
        # Verify SENSOR platform is in the list
        args = hass.config_entries.async_forward_entry_setups.call_args
        platforms = args[0][1]  # Second positional arg
        platform_values = [str(p) for p in platforms]
        assert any("sensor" in str(p).lower() for p in platform_values)


class TestAsyncUnloadEntry:
    """async_unload_entry returns True when unload succeeds."""

    def test_returns_true(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        result = asyncio.run(init_module.async_unload_entry(hass, entry))
        assert result is True

    def test_unloads_platforms(self, init_module):
        hass = _make_hass()
        entry = _make_entry()
        asyncio.run(init_module.async_unload_entry(hass, entry))
        hass.config_entries.async_unload_platforms.assert_called_once()


class TestDSOMigrationInSetup:
    """DSO migration triggers during setup for old DSO keys."""

    def test_migrated_dso_updates_config_entry(self, init_module):
        """Setup with old DSO key should update config entry to new key."""
        hass = _make_hass()
        entry = _make_entry(dso_id="skiakernett")

        with patch.object(init_module, "_migrate_storage_file", new_callable=AsyncMock):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        # Config entry should be updated with new DSO key
        hass.config_entries.async_update_entry.assert_called_once()
        # __init__.py kaller alltid async_update_entry(entry, data=new_data)
        new_data = hass.config_entries.async_update_entry.call_args.kwargs["data"]
        assert new_data["tso"] == "vevig"

    def test_current_dso_no_migration(self, init_module):
        """Setup with current DSO key should not trigger migration."""
        hass = _make_hass()
        entry = _make_entry(dso_id="bkk")

        asyncio.run(init_module.async_setup_entry(hass, entry))

        # async_update_entry should NOT be called
        hass.config_entries.async_update_entry.assert_not_called()

    def test_migrated_dso_creates_repair_issue(self, init_module):
        """DSO migration should create a repair issue."""
        hass = _make_hass()
        entry = _make_entry(dso_id="skiakernett")

        # Patch ir on the init_module (the module uses `ir.async_create_issue`)
        mock_ir = MagicMock()
        mock_ir.IssueSeverity.WARNING = "warning"

        with (
            patch.object(init_module, "ir", mock_ir),
            patch.object(init_module, "_migrate_storage_file", new_callable=AsyncMock),
        ):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        mock_ir.async_create_issue.assert_called_once()


class TestAvgiftssoneMigration:
    """Avgiftssone migration for NO3 DSOs (incident 003).

    NO3 was incorrectly mapped to nord_norge (mva-fritak).
    Most NO3 DSOs are in Trøndelag/Møre og Romsdal with 25% mva.
    Migration should change their avgiftssone to standard.
    """

    def test_no3_dso_migrated_to_standard(self, init_module):
        """NO3 DSO with nord_norge avgiftssone should be migrated to standard."""
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_tn")
        entry.data["avgiftssone"] = "nord_norge"

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_called_once()
        call_args = hass.config_entries.async_update_entry.call_args
        new_data = call_args[1].get("data") or call_args[0][1]
        assert new_data["avgiftssone"] == "standard"

    def test_no4_dso_not_migrated(self, init_module):
        """NO4 DSO with nord_norge should NOT be migrated."""
        hass = _make_hass()
        entry = _make_entry(dso_id="noranett")
        entry.data["avgiftssone"] = "nord_norge"

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_not_called()

    def test_bindal_not_migrated(self, init_module):
        """Bindal Kraftnett (NO3, Nordland) has explicit avgiftssone override, should NOT be migrated."""
        hass = _make_hass()
        entry = _make_entry(dso_id="bindal_kraftnett")
        entry.data["avgiftssone"] = "nord_norge"

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_not_called()

    def test_no3_standard_not_migrated(self, init_module):
        """NO3 DSO already on standard should not be touched."""
        hass = _make_hass()
        entry = _make_entry(dso_id="tensio_ts")
        entry.data["avgiftssone"] = "standard"

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_not_called()


class TestUniqueIdSetup:
    """async_setup_entry setter unique_id = entry_id for nye entries (v4-skjema).

    Nye entries opprettes av config-flowen uten unique_id (entry_id finnes ikke
    før entryet er laget). Migrerte entries har fått den via async_migrate_entry.
    bkk/standard er valgt fordi de ikke trigger DSO- eller avgiftssone-migrering,
    så det eneste async_update_entry-kallet kommer fra unique_id-logikken.
    """

    def test_new_entry_without_unique_id_gets_entry_id(self, init_module):
        """Ny entry (unique_id=None) skal få unique_id = entry_id ved oppstart."""
        hass = _make_hass()
        entry = _make_entry(dso_id="bkk")
        entry.unique_id = None

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_called_once_with(entry, unique_id=entry.entry_id)

    def test_entry_with_unique_id_not_touched(self, init_module):
        """Entry som allerede har unique_id (migrert v4) skal ikke oppdateres."""
        hass = _make_hass()
        entry = _make_entry(dso_id="bkk")
        entry.unique_id = entry.entry_id

        asyncio.run(init_module.async_setup_entry(hass, entry))

        hass.config_entries.async_update_entry.assert_not_called()


# ULID-formede entry-id-er: HA lager entry_id slik, og ryddingen kjenner igjen
# suffikset på formen. "test_entry" fra conftest gjør den ikke, med vilje.
LEVENDE_ENTRY = "01KFEFGNT6PZZFVPK0F0FSN40D"
SLETTET_ENTRY = "01KNMS11PBKD0SPDPND2ZFB0JZ"

# Entries opprettet før HA gikk over til ULID har 32 tegn heksadesimalt. De
# lever fortsatt i gamle installasjoner (22 av 66 i Fredriks HA), så den grenen
# i _ENTRY_ID_SUFFIX må ryddes like godt som ULID-grenen.
LEVENDE_HEX_ENTRY = "3f0a1c9b4d6e8f2a7b5c0d1e2f3a4b5c"
SLETTET_HEX_ENTRY = "a1b2c3d4e5f60718293a4b5c6d7e8f90"


def _mock_ir_med_issues(issues):
    """Lag en ir-mock der issue-registeret inneholder de gitte (domene, id)-parene."""
    mock_ir = MagicMock()
    mock_ir.IssueSeverity.WARNING = "warning"
    registry = MagicMock()
    registry.issues = dict.fromkeys(issues, MagicMock())
    mock_ir.async_get.return_value = registry
    return mock_ir


def _slettede(mock_ir):
    return [call.args[2] for call in mock_ir.async_delete_issue.call_args_list]


class TestRepairOpprydding:
    """Repair-issues suffikset med entry_id skal ikke overleve entryen sin.

    Fredriks HA hadde en spotpris_mva_check fra en entry som var slettet for
    lengst; den lå og maste om et anlegg som ikke fantes.
    """

    def test_remove_entry_sletter_issues_for_entryen(self, init_module):
        hass = _make_hass()
        entry = _make_entry(entry_id=SLETTET_ENTRY)
        mock_ir = _mock_ir_med_issues(
            [
                (init_module.DOMAIN, f"spotpris_mva_check_{SLETTET_ENTRY}"),
                (init_module.DOMAIN, f"dso_delt_{SLETTET_ENTRY}"),
                (init_module.DOMAIN, f"spotpris_mva_check_{LEVENDE_ENTRY}"),
                (init_module.DOMAIN, "satser_utdatert"),
                ("hacs", f"restart_required_{SLETTET_ENTRY}"),
            ],
        )

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_remove_entry(hass, entry))

        assert _slettede(mock_ir) == [
            f"spotpris_mva_check_{SLETTET_ENTRY}",
            f"dso_delt_{SLETTET_ENTRY}",
        ]
        assert all(call.args[1] == init_module.DOMAIN for call in mock_ir.async_delete_issue.call_args_list)

    def test_setup_sletter_foreldrelost_issue(self, init_module):
        hass = _make_hass()
        entry = _make_entry(entry_id=LEVENDE_ENTRY, dso_id="bkk")
        entry.unique_id = entry.entry_id
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        mock_ir = _mock_ir_med_issues(
            [
                (init_module.DOMAIN, f"spotpris_mva_check_{SLETTET_ENTRY}"),
                (init_module.DOMAIN, f"spotpris_mva_check_{LEVENDE_ENTRY}"),
            ],
        )

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        slettede = _slettede(mock_ir)
        assert f"spotpris_mva_check_{SLETTET_ENTRY}" in slettede
        assert f"spotpris_mva_check_{LEVENDE_ENTRY}" not in slettede

    def test_setup_rorer_ikke_domenevide_eller_andres_issues(self, init_module):
        hass = _make_hass()
        entry = _make_entry(entry_id=LEVENDE_ENTRY, dso_id="bkk")
        entry.unique_id = entry.entry_id
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        mock_ir = _mock_ir_med_issues(
            [
                (init_module.DOMAIN, "dso_migration_skiakernett_vevig"),
                (init_module.DOMAIN, "norgespris_utlopt"),
                ("hacs", f"spotpris_mva_check_{SLETTET_ENTRY}"),
            ],
        )

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        assert "dso_migration_skiakernett_vevig" not in _slettede(mock_ir)
        assert all(call.args[1] == init_module.DOMAIN for call in mock_ir.async_delete_issue.call_args_list)

    def test_setup_sletter_foreldrelost_issue_med_hex32_entry(self, init_module):
        """Entries fra før ULID-skiftet er 32 hex-tegn og skal ryddes likt."""
        hass = _make_hass()
        entry = _make_entry(entry_id=LEVENDE_HEX_ENTRY, dso_id="bkk")
        entry.unique_id = entry.entry_id
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        mock_ir = _mock_ir_med_issues(
            [
                (init_module.DOMAIN, f"spotpris_mva_check_{SLETTET_HEX_ENTRY}"),
                (init_module.DOMAIN, f"spotpris_mva_check_{LEVENDE_HEX_ENTRY}"),
                (init_module.DOMAIN, f"spotpris_mva_check_{SLETTET_ENTRY}"),
            ],
        )

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        slettede = _slettede(mock_ir)
        assert f"spotpris_mva_check_{SLETTET_HEX_ENTRY}" in slettede
        assert f"spotpris_mva_check_{SLETTET_ENTRY}" in slettede
        assert f"spotpris_mva_check_{LEVENDE_HEX_ENTRY}" not in slettede

    def test_remove_entry_sletter_issues_for_hex32_entry(self, init_module):
        hass = _make_hass()
        entry = _make_entry(entry_id=SLETTET_HEX_ENTRY)
        mock_ir = _mock_ir_med_issues(
            [
                (init_module.DOMAIN, f"spotpris_mva_check_{SLETTET_HEX_ENTRY}"),
                (init_module.DOMAIN, f"spotpris_mva_check_{LEVENDE_HEX_ENTRY}"),
                (init_module.DOMAIN, "satser_utdatert"),
            ],
        )

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_remove_entry(hass, entry))

        assert _slettede(mock_ir) == [f"spotpris_mva_check_{SLETTET_HEX_ENTRY}"]

    def test_hex32_med_versaler_er_ikke_et_entry_suffiks(self, init_module):
        """Mønsteret er hex i minuskler eller ULID i versaler, ikke noe midt imellom.

        En issue-id som slutter på 32 tegn i versaler er ingen av delene, og
        skal stå i fred framfor å bli tolket som en foreldreløs entry.
        """
        hass = _make_hass()
        entry = _make_entry(entry_id=LEVENDE_ENTRY, dso_id="bkk")
        entry.unique_id = entry.entry_id
        hass.config_entries.async_entries = MagicMock(return_value=[entry])
        versaler = SLETTET_HEX_ENTRY.upper()
        mock_ir = _mock_ir_med_issues([(init_module.DOMAIN, f"spotpris_mva_check_{versaler}")])

        with patch.object(init_module, "ir", mock_ir):
            asyncio.run(init_module.async_setup_entry(hass, entry))

        assert f"spotpris_mva_check_{versaler}" not in _slettede(mock_ir)
