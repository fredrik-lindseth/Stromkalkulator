"""Test boligtype constants and helper functions."""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_FRITIDSBOLIG,
    BOLIGTYPE_FRITIDSBOLIG_FAST,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_MAX_KWH,
    STROMSTOTTE_RATE,
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


# =============================================================================
# Threshold and rate validation (satsvakt, flyttet fra test_stromstotte_tak.py)
# =============================================================================


def test_threshold_is_2026_value() -> None:
    """Verify threshold is set to 2026 value (77 øre eks. mva * 1.25)."""
    assert STROMSTOTTE_LEVEL == 0.9625


def test_rate_is_90_percent() -> None:
    """Verify rate is 90%."""
    assert STROMSTOTTE_RATE == 0.9


def test_cap_is_5000_kwh() -> None:
    """Verify monthly cap is 5000 kWh."""
    assert STROMSTOTTE_MAX_KWH == 5000
