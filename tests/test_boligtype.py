"""Test boligtype constants and helper functions."""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_FRITIDSBOLIG,
    BOLIGTYPE_FRITIDSBOLIG_FAST,
    STROMSTOTTE_LEVEL,
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


def calculate_stromstotte_with_boligtype(
    spot_price: float,
    monthly_consumption_kwh: float,
    boligtype: str,
) -> float:
    """Calculate strømstøtte with boligtype-aware cap."""
    max_kwh = get_stromstotte_max_kwh(boligtype)
    if max_kwh == 0 or monthly_consumption_kwh >= max_kwh:
        return 0.0
    if spot_price <= STROMSTOTTE_LEVEL:
        return 0.0
    return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE


def calculate_norgespris_over_cap(
    monthly_consumption_kwh: float,
    boligtype: str,
) -> bool:
    """Return True if Norgespris cap is exceeded."""
    max_kwh = get_norgespris_max_kwh(boligtype)
    return monthly_consumption_kwh >= max_kwh


@pytest.mark.parametrize(
    ("boligtype", "spot", "kwh", "expected"),
    [
        (BOLIGTYPE_BOLIG, 1.50, 2000, (1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (BOLIGTYPE_BOLIG, 1.50, 5000, 0.0),
        (BOLIGTYPE_FRITIDSBOLIG, 1.50, 0, 0.0),
        (BOLIGTYPE_FRITIDSBOLIG, 2.00, 500, 0.0),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 1.50, 2000, (1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 1.50, 5000, 0.0),
    ],
    ids=[
        "bolig_under_cap",
        "bolig_at_cap",
        "fritid_zero_consumption",
        "fritid_high_spot",
        "fast_under_cap",
        "fast_at_cap",
    ],
)
def test_stromstotte_with_boligtype(
    boligtype: str, spot: float, kwh: float, expected: float,
) -> None:
    """Strømstøtte respects boligtype."""
    assert calculate_stromstotte_with_boligtype(spot, kwh, boligtype) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("boligtype", "kwh", "over_cap"),
    [
        (BOLIGTYPE_BOLIG, 4999, False),
        (BOLIGTYPE_BOLIG, 5000, True),
        (BOLIGTYPE_FRITIDSBOLIG, 999, False),
        (BOLIGTYPE_FRITIDSBOLIG, 1000, True),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 4999, False),
        (BOLIGTYPE_FRITIDSBOLIG_FAST, 5000, True),
    ],
    ids=[
        "bolig_under",
        "bolig_at",
        "fritid_under",
        "fritid_at",
        "fast_under",
        "fast_at",
    ],
)
def test_norgespris_cap_with_boligtype(
    boligtype: str, kwh: float, over_cap: bool,
) -> None:
    """Norgespris cap: bolig/fast=5000, fritidsbolig=1000."""
    assert calculate_norgespris_over_cap(kwh, boligtype) == over_cap
