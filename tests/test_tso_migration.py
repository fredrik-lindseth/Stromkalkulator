"""Tests for TSO migration data structures."""

from __future__ import annotations

import pytest

from stromkalkulator.tso import TSO_LIST, TSO_MIGRATIONS, TSOFusjon


def test_tso_fusjon_dataclass():
    """TSOFusjon has gammel and ny fields."""
    fusjon = TSOFusjon(gammel="old_tso", ny="new_tso")
    assert fusjon.gammel == "old_tso"
    assert fusjon.ny == "new_tso"


def test_tso_fusjon_is_frozen():
    """TSOFusjon is immutable."""
    fusjon = TSOFusjon(gammel="old_tso", ny="new_tso")
    with pytest.raises(AttributeError):
        fusjon.gammel = "other"  # type: ignore[misc]


def test_tso_migrations_exist():
    """TSO_MIGRATIONS contains known mergers."""
    gammel_keys = [m.gammel for m in TSO_MIGRATIONS]
    assert "skiakernett" in gammel_keys
    assert "norgesnett" in gammel_keys


def test_tso_migrations_targets_exist_in_tso_list():
    """Every migration target must exist in TSO_LIST."""
    for migration in TSO_MIGRATIONS:
        assert migration.ny in TSO_LIST, (
            f"Migration target '{migration.ny}' not found in TSO_LIST"
        )


@pytest.mark.skip(reason="norgesnett removed in Task 5")
def test_tso_migrations_sources_not_in_tso_list():
    """Migrated TSO keys should be removed from TSO_LIST."""
    for migration in TSO_MIGRATIONS:
        assert migration.gammel not in TSO_LIST, (
            f"Migrated key '{migration.gammel}' should be removed from TSO_LIST"
        )


def test_build_migration_index():
    """_build_migration_index returns dict mapping gammel → TSOFusjon."""
    from stromkalkulator.__init__ import _build_migration_index

    index = _build_migration_index()
    assert isinstance(index, dict)
    assert "skiakernett" in index
    assert index["skiakernett"].ny == "vevig"
    assert "norgesnett" in index
    assert index["norgesnett"].ny == "glitre"


def test_migrate_tso_returns_new_key():
    """_check_tso_migration returns TSOFusjon when migration exists."""
    from stromkalkulator.__init__ import _check_tso_migration

    result = _check_tso_migration("skiakernett")
    assert result is not None
    assert result.ny == "vevig"


def test_migrate_tso_returns_none_for_current():
    """_check_tso_migration returns None when no migration needed."""
    from stromkalkulator.__init__ import _check_tso_migration

    result = _check_tso_migration("bkk")
    assert result is None


@pytest.mark.asyncio
async def test_migrate_storage_file_renames(tmp_path):
    """Storage file is renamed from old to new TSO key."""
    from stromkalkulator.__init__ import _migrate_storage_file

    # Create a fake old storage file
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "test"}')

    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    new_file = storage_dir / "stromkalkulator_glitre"
    assert new_file.exists()
    assert not old_file.exists()
    assert new_file.read_text() == '{"data": "test"}'


@pytest.mark.asyncio
async def test_migrate_storage_file_no_old_file(tmp_path):
    """No error when old storage file doesn't exist."""
    from stromkalkulator.__init__ import _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()

    # Should not raise
    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")


@pytest.mark.asyncio
async def test_migrate_storage_file_target_exists(tmp_path):
    """Don't overwrite if target storage file already exists."""
    from stromkalkulator.__init__ import _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "old"}')
    new_file = storage_dir / "stromkalkulator_glitre"
    new_file.write_text('{"data": "existing"}')

    await _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    # Existing file should not be overwritten
    assert new_file.read_text() == '{"data": "existing"}'
