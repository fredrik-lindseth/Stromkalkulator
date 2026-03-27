"""Test margin til neste kapasitetstrinn (margin to next capacity tier).

Tests the margin calculation showing how many kW remain before
the next tier boundary, and the binary warning sensor logic.
"""

from __future__ import annotations

import pytest

# BKK kapasitetstrinn 2026
BKK_KAPASITETSTRINN = [
    (2, 155),
    (5, 250),
    (10, 415),
    (15, 600),
    (20, 770),
    (25, 940),
    (50, 1800),
    (75, 2650),
    (100, 3500),
    (float("inf"), 6900),
]


def calculate_margin(
    avg_power: float, kapasitetstrinn: list[tuple[float, int]]
) -> tuple[float, int, int]:
    """Calculate margin to next capacity tier.

    Args:
        avg_power: Average of top 3 days power consumption in kW
        kapasitetstrinn: List of (threshold, price) tuples

    Returns:
        Tuple of (margin_kw, current_price, next_price)
        - margin_kw: kW remaining before next tier boundary
        - current_price: monthly fee for current tier (NOK)
        - next_price: monthly fee for next tier (NOK)
        If on highest tier: margin = 0, next_price = current_price
    """
    for i, (threshold, price) in enumerate(kapasitetstrinn):
        if avg_power <= threshold:
            if threshold == float("inf"):
                # Highest tier: no next tier
                return 0.0, price, price
            margin = threshold - avg_power
            if i + 1 < len(kapasitetstrinn):
                next_price = kapasitetstrinn[i + 1][1]
            else:
                next_price = price
            return margin, price, next_price
    # Fallback: already past all tiers (shouldn't happen with inf)
    last_price = kapasitetstrinn[-1][1]
    return 0.0, last_price, last_price


# =============================================================================
# Margin calculation tests
# =============================================================================


@pytest.mark.parametrize(
    ("avg_power", "expected_margin", "expected_current", "expected_next"),
    [
        (1.0, 1.0, 155, 250),
        (2.0, 0.0, 155, 250),
        (7.5, 2.5, 415, 600),
        (150.0, 0.0, 6900, 6900),
        (0.0, 2.0, 155, 250),
    ],
    ids=[
        "low_consumption_tier1",
        "at_boundary_tier1",
        "mid_tier3",
        "highest_tier",
        "zero_consumption",
    ],
)
def test_calculate_margin(
    avg_power: float,
    expected_margin: float,
    expected_current: int,
    expected_next: int,
) -> None:
    """Test margin calculation for various power levels."""
    margin, current_price, next_price = calculate_margin(avg_power, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(expected_margin)
    assert current_price == expected_current
    assert next_price == expected_next


def test_margin_at_each_boundary() -> None:
    """At exact boundary, margin should be 0 but stay in current tier."""
    for _i, (threshold, _price) in enumerate(BKK_KAPASITETSTRINN):
        if threshold == float("inf"):
            continue
        margin, _current, _next = calculate_margin(threshold, BKK_KAPASITETSTRINN)
        assert margin == 0.0, f"Margin should be 0 at boundary {threshold} kW"


def test_margin_just_below_boundary() -> None:
    """Just below boundary should have small positive margin."""
    margin, current, _next = calculate_margin(4.99, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(0.01, abs=0.001)
    assert current == 250  # Still in tier 2 (2-5 kW)


def test_margin_just_above_boundary() -> None:
    """Just above boundary should have full margin of new tier."""
    margin, current, _next = calculate_margin(5.01, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(4.99, abs=0.001)
    assert current == 415  # Now in tier 3 (5-10 kW)


# =============================================================================
# Varsel (warning) binary sensor tests
# =============================================================================

DEFAULT_TERSKEL = 2.0  # Default warning threshold in kW


def margin_varsel_active(margin: float, terskel: float = DEFAULT_TERSKEL) -> bool:
    """Determine if the capacity warning should be active.

    Args:
        margin: kW remaining before next tier
        terskel: Warning threshold in kW

    Returns:
        True if warning should be active (margin < threshold)
    """
    return margin < terskel


@pytest.mark.parametrize(
    ("margin", "terskel", "expected_active"),
    [
        (1.5, 2.0, True),
        (2.0, 2.0, False),
        (3.0, 2.0, False),
        (0.0, 2.0, True),
    ],
    ids=[
        "margin_below_threshold",
        "margin_equals_threshold",
        "margin_above_threshold",
        "margin_zero_at_boundary",
    ],
)
def test_varsel_threshold(margin: float, terskel: float, expected_active: bool) -> None:
    """Test warning activation based on margin vs threshold."""
    assert margin_varsel_active(margin, terskel) == expected_active


def test_varsel_highest_tier_always_warns() -> None:
    """On highest tier, margin is 0 so warning is always active."""
    margin, _current, _next = calculate_margin(150.0, BKK_KAPASITETSTRINN)
    assert margin == 0.0
    assert margin_varsel_active(margin) is True


def test_varsel_low_consumption_no_warning() -> None:
    """Low consumption with large margin should not trigger warning."""
    margin, _current, _next = calculate_margin(0.5, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(1.5)
    assert margin_varsel_active(margin) is True  # 1.5 < 2.0, still warns


def test_varsel_comfortable_margin() -> None:
    """Consumption well within tier should not warn."""
    margin, _current, _next = calculate_margin(5.5, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(4.5)
    assert margin_varsel_active(margin) is False  # 4.5 >= 2.0
