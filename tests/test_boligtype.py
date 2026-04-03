"""Test boligtype constants and helper functions."""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_FRITIDSBOLIG,
    BOLIGTYPE_FRITIDSBOLIG_FAST,
    get_norgespris_max_kwh,
    get_stromstotte_max_kwh,
)


@pytest.mark.parametrize(
    ("boligtype", "expected"),
    [
        (BOLIGTYPE_BOLIG, 5000),
        (BOLIGTYPE_FRITIDSBOLIG, 1000),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000),
    ],
    ids=["bolig", "fritidsbolig", "fritidsbolig_fast"],
)
def test_get_norgespris_max_kwh(boligtype: str, expected: int) -> None:
    """Norgespris kWh cap: bolig/fast=5000, fritidsbolig=1000."""
    assert get_norgespris_max_kwh(boligtype) == expected


@pytest.mark.parametrize(
    ("boligtype", "expected"),
    [
        (BOLIGTYPE_BOLIG, 5000),
        (BOLIGTYPE_FRITIDSBOLIG, 0),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000),
    ],
    ids=["bolig", "fritidsbolig_ingen_rett", "fritidsbolig_fast"],
)
def test_get_stromstotte_max_kwh(boligtype: str, expected: int) -> None:
    """Stromstotte kWh cap: bolig/fast=5000, fritidsbolig=0 (ingen rett)."""
    assert get_stromstotte_max_kwh(boligtype) == expected
