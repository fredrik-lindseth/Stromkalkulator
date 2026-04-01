"""Test strømstøtte 5000 kWh-tak (monthly consumption cap).

Tests the electricity subsidy calculation with the 5000 kWh/month cap:
- 90% of spot price above 96.25 øre/kWh (inkl. mva)
- Zero support when monthly consumption exceeds 5000 kWh
- Zero support for Norgespris users (alternative scheme)
"""

from __future__ import annotations

import pytest

# Constants matching const.py
STROMSTOTTE_LEVEL = 0.9625  # 96.25 øre/kWh inkl. mva (terskel 2026)
STROMSTOTTE_RATE = 0.90  # 90% kompensasjon over terskel
STROMSTOTTE_MAX_KWH = 5000  # Maks 5000 kWh/mnd per målepunkt


def calculate_stromstotte(
    spot_price: float,
    har_norgespris: bool,
    monthly_consumption_kwh: float,
) -> float:
    """Calculate strømstøtte per kWh.

    Args:
        spot_price: Current spot price in NOK/kWh (inkl. mva)
        har_norgespris: Whether user has Norgespris (alternative to strømstøtte)
        monthly_consumption_kwh: Total monthly consumption so far in kWh

    Returns:
        Strømstøtte in NOK/kWh (positive = support amount, 0 = no support)
    """
    # Norgespris users don't get strømstøtte
    if har_norgespris:
        return 0.0

    # Over monthly cap: no support
    if monthly_consumption_kwh >= STROMSTOTTE_MAX_KWH:
        return 0.0

    # Below threshold: no support
    if spot_price <= STROMSTOTTE_LEVEL:
        return 0.0

    # Support = 90% of amount above threshold (positive, matching coordinator convention)
    return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE


def stromstotte_gjenstaaende(monthly_consumption_kwh: float) -> float:
    """Calculate remaining kWh before the 5000 kWh cap is reached.

    Args:
        monthly_consumption_kwh: Total monthly consumption so far in kWh

    Returns:
        Remaining kWh before cap (0 if already exceeded)
    """
    return max(0.0, STROMSTOTTE_MAX_KWH - monthly_consumption_kwh)


# =============================================================================
# Strømstøtte calculation tests
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "har_norgespris", "monthly_kwh", "expected"),
    [
        # Under cap: normal strømstøtte (positive = support amount)
        (1.50, False, 2000, (1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (1.20, False, 0, (1.20 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        (2.00, False, 4999, (2.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE),
        # At 5000 kWh: strømstøtte = 0
        (1.50, False, 5000, 0.0),
        # Over 5000 kWh: strømstøtte = 0
        (1.50, False, 6000, 0.0),
        (2.00, False, 10000, 0.0),
        # Norgespris user: always 0
        (1.50, True, 2000, 0.0),
        (2.00, True, 0, 0.0),
        (1.50, True, 6000, 0.0),
        # Spot under threshold: no support regardless of cap
        (0.50, False, 1000, 0.0),
        (STROMSTOTTE_LEVEL, False, 1000, 0.0),
        (0.80, False, 0, 0.0),
    ],
    ids=[
        "under_cap_high_spot",
        "zero_consumption_high_spot",
        "just_under_cap",
        "at_cap",
        "over_cap",
        "far_over_cap",
        "norgespris_under_cap",
        "norgespris_zero_consumption",
        "norgespris_over_cap",
        "spot_under_threshold",
        "spot_at_threshold",
        "spot_below_threshold_zero_consumption",
    ],
)
def test_calculate_stromstotte(
    spot_price: float,
    har_norgespris: bool,
    monthly_kwh: float,
    expected: float,
) -> None:
    """Test strømstøtte calculation with 5000 kWh cap."""
    result = calculate_stromstotte(spot_price, har_norgespris, monthly_kwh)
    assert result == pytest.approx(expected)


def test_stromstotte_is_positive_when_applicable() -> None:
    """Strømstøtte should be positive (matching coordinator convention) when applicable."""
    result = calculate_stromstotte(1.50, False, 1000)
    assert result > 0.0


def test_stromstotte_magnitude() -> None:
    """Verify exact strømstøtte amount for a known spot price.

    Spot 1.50 NOK/kWh: (1.50 - 0.9625) * 0.90 = 0.48375 NOK/kWh
    """
    result = calculate_stromstotte(1.50, False, 1000)
    assert result == pytest.approx(0.48375)


# =============================================================================
# Gjenstående kWh tests
# =============================================================================


@pytest.mark.parametrize(
    ("monthly_kwh", "expected_remaining"),
    [
        (0, 5000.0),
        (3000, 2000.0),
        (5000, 0.0),
        (6000, 0.0),
    ],
    ids=[
        "zero_consumption",
        "partial_consumption",
        "at_cap",
        "over_cap",
    ],
)
def test_stromstotte_gjenstaaende(
    monthly_kwh: float,
    expected_remaining: float,
) -> None:
    """Test remaining kWh before 5000 kWh cap."""
    result = stromstotte_gjenstaaende(monthly_kwh)
    assert result == pytest.approx(expected_remaining)


def test_gjenstaaende_never_negative() -> None:
    """Remaining kWh should never be negative, even with extreme consumption."""
    assert stromstotte_gjenstaaende(99999) == 0.0
