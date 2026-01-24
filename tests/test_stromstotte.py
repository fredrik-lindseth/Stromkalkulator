"""Test strømstøtte calculations.

Tests the electricity subsidy (strømstøtte) calculation:
- 90% coverage of spot price above threshold (inkl. mva)
- Max 5000 kWh/month (not enforced in this integration)

Historikk terskelverdi (eks. mva → inkl. 25% mva):
- 2024: 73 øre → 91,25 øre inkl. mva
- 2025: 75 øre → 93,75 øre inkl. mva
- 2026: 77 øre → 96,25 øre inkl. mva

Kilde: https://lovdata.no/dokument/SF/forskrift/2025-09-08-1791
"""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE


def calculate_stromstotte(spot_price: float) -> float:
    """Calculate strømstøtte based on spot price.

    Args:
        spot_price: Spot price in NOK/kWh

    Returns:
        Strømstøtte in NOK/kWh
    """
    if spot_price > STROMSTOTTE_LEVEL:
        return round((spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    return 0.0


# =============================================================================
# Strømstøtte calculation tests
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "expected"),
    [
        (0.50, 0.0),  # Below threshold
        (0.70, 0.0),  # Below threshold
        (0.90, 0.0),  # Below threshold
        (STROMSTOTTE_LEVEL, 0.0),  # At threshold
        (-0.10, 0.0),  # Negative price
        (-1.00, 0.0),  # Negative price
        (0.0, 0.0),  # Zero price
    ],
    ids=[
        "low_price_50",
        "low_price_70",
        "low_price_90",
        "at_threshold",
        "negative_10",
        "negative_100",
        "zero_price",
    ],
)
def test_stromstotte_no_support(spot_price: float, expected: float) -> None:
    """When spot price is at or below threshold, strømstøtte should be 0."""
    assert calculate_stromstotte(spot_price) == expected


@pytest.mark.parametrize(
    "spot_price",
    [1.00, 1.20, 1.50, 2.00, 5.00],
    ids=["100_ore", "120_ore", "150_ore", "200_ore", "500_ore"],
)
def test_stromstotte_above_threshold(spot_price: float) -> None:
    """When spot price is above threshold, strømstøtte is calculated."""
    result = calculate_stromstotte(spot_price)
    expected = round((spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    assert result == expected
    assert result > 0


# =============================================================================
# Spotpris etter støtte tests
# =============================================================================


def test_spotpris_etter_stotte_low_price() -> None:
    """Low price remains unchanged."""
    spot_price = 0.50
    stromstotte = calculate_stromstotte(spot_price)
    result = spot_price - stromstotte
    assert result == 0.50


def test_spotpris_etter_stotte_high_price() -> None:
    """High price is reduced by strømstøtte."""
    spot_price = 2.00
    stromstotte = calculate_stromstotte(spot_price)
    result = round(spot_price - stromstotte, 4)
    expected = round(spot_price - (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    assert result == expected


@pytest.mark.parametrize("price", [1.5, 2.0, 3.0, 5.0, 10.0])
def test_spotpris_etter_stotte_always_positive(price: float) -> None:
    """Spotpris etter støtte should always be positive."""
    stromstotte = calculate_stromstotte(price)
    etter_stotte = price - stromstotte
    assert etter_stotte > 0


# =============================================================================
# Threshold and rate validation
# =============================================================================


def test_threshold_is_2026_value() -> None:
    """Verify threshold is set to 2026 value (77 øre eks. mva * 1.25)."""
    # 77 øre/kWh eks. mva * 1.25 = 96.25 øre/kWh inkl. mva = 0.9625 NOK/kWh
    assert STROMSTOTTE_LEVEL == 0.9625


def test_rate_is_90_percent() -> None:
    """Verify rate is 90%."""
    assert STROMSTOTTE_RATE == 0.9
