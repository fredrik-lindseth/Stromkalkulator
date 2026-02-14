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
