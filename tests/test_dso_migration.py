"""Tests for DSO migration data structures."""

from __future__ import annotations

from stromkalkulator.dso import DSO_LIST, DSO_MIGRATIONS


def test_dso_migrations_targets_exist_in_dso_list():
    """Every migration target must exist in DSO_LIST."""
    for migration in DSO_MIGRATIONS:
        assert migration.ny in DSO_LIST, (
            f"Migration target '{migration.ny}' not found in DSO_LIST"
        )


def test_dso_migrations_sources_not_in_dso_list():
    """Migrated DSO keys should be removed from DSO_LIST."""
    for migration in DSO_MIGRATIONS:
        assert migration.gammel not in DSO_LIST, (
            f"Migrated key '{migration.gammel}' should be removed from DSO_LIST"
        )


def test_migrate_dso_returns_new_key():
    """_check_dso_migration returns DSOFusjon when migration exists."""
    from stromkalkulator.__init__ import _check_dso_migration

    result = _check_dso_migration("skiakernett")
    assert result is not None
    assert result.ny == "vevig"


def test_migrate_dso_returns_none_for_current():
    """_check_dso_migration returns None when no migration needed."""
    from stromkalkulator.__init__ import _check_dso_migration

    result = _check_dso_migration("bkk")
    assert result is None


def test_migrate_storage_file_renames(tmp_path):
    """Storage file is renamed from old to new DSO key."""
    from stromkalkulator.__init__ import _migrate_storage_file_sync as _migrate_storage_file

    # Create a fake old storage file
    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "test"}')

    _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    new_file = storage_dir / "stromkalkulator_glitre"
    assert new_file.exists()
    assert not old_file.exists()
    assert new_file.read_text() == '{"data": "test"}'


def test_migrate_storage_file_no_old_file(tmp_path):
    """No error when old storage file doesn't exist."""
    from stromkalkulator.__init__ import _migrate_storage_file_sync as _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()

    # Should not raise
    _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")


def test_migrate_storage_file_target_exists(tmp_path):
    """Don't overwrite if target storage file already exists."""
    from stromkalkulator.__init__ import _migrate_storage_file_sync as _migrate_storage_file

    storage_dir = tmp_path / ".storage"
    storage_dir.mkdir()
    old_file = storage_dir / "stromkalkulator_norgesnett"
    old_file.write_text('{"data": "old"}')
    new_file = storage_dir / "stromkalkulator_glitre"
    new_file.write_text('{"data": "existing"}')

    _migrate_storage_file(str(storage_dir), "norgesnett", "glitre")

    # Existing file should not be overwritten
    assert new_file.read_text() == '{"data": "existing"}'
