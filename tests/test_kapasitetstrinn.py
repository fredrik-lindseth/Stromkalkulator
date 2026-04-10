"""Test kapasitetstrinn (capacity tier) calculations.

Tests the capacity-based grid tariff calculation:
- Based on average of top 3 consumption days
- Determines monthly fixed fee (kapasitetsledd)
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


def get_kapasitetsledd(avg_power: float, kapasitetstrinn: list[tuple[float, int]]) -> tuple[int, int, str]:
    """Get kapasitetsledd based on average power.

    Args:
        avg_power: Average of top 3 days power consumption in kW
        kapasitetstrinn: List of (threshold, price) tuples

    Returns:
        Tuple of (price, tier_number, tier_range_string)
    """
    for i, (threshold, price) in enumerate(kapasitetstrinn, 1):
        if avg_power <= threshold:
            prev_threshold = kapasitetstrinn[i - 2][0] if i > 1 else 0
            if threshold == float("inf"):
                tier_range = f">{prev_threshold} kW"
            else:
                tier_range = f"{prev_threshold}-{threshold} kW"
            return price, i, tier_range
    # Fallback to last tier
    last_idx = len(kapasitetstrinn)
    prev = kapasitetstrinn[-2][0] if last_idx > 1 else 0
    return kapasitetstrinn[-1][1], last_idx, f">{prev} kW"


def calculate_avg_top_3(daily_max_power: dict[str, float]) -> float:
    """Calculate average of top 3 days.

    Args:
        daily_max_power: Dict of {date_str: max_power_kw}

    Returns:
        Average power in kW
    """
    if not daily_max_power:
        return 0.0
    sorted_days = sorted(daily_max_power.values(), reverse=True)
    top_3 = sorted_days[:3]
    if len(top_3) >= 3:
        return sum(top_3) / 3
    return sum(top_3) / max(len(top_3), 1)


# =============================================================================
# Kapasitetstrinn tier selection tests
# =============================================================================


@pytest.mark.parametrize(
    ("avg_power", "expected_price", "expected_tier", "expected_range"),
    [
        (0.0, 155, 1, "0-2 kW"),
        (0.5, 155, 1, "0-2 kW"),
        (2.0, 155, 1, "0-2 kW"),
        (2.1, 250, 2, "2-5 kW"),
        (5.0, 250, 2, "2-5 kW"),
        (5.1, 415, 3, "5-10 kW"),
        (10.0, 415, 3, "5-10 kW"),
        (10.1, 600, 4, "10-15 kW"),
        (15.1, 770, 5, "15-20 kW"),
        (20.1, 940, 6, "20-25 kW"),
        (30.0, 1800, 7, "25-50 kW"),
        (60.0, 2650, 8, "50-75 kW"),
        (90.0, 3500, 9, "75-100 kW"),
        (150.0, 6900, 10, ">100 kW"),
    ],
    ids=[
        "zero",
        "tier1_low",
        "tier1_boundary",
        "tier2_low",
        "tier2_boundary",
        "tier3_low",
        "tier3_boundary",
        "tier4_low",
        "tier5",
        "tier6",
        "tier7",
        "tier8",
        "tier9",
        "tier10",
    ],
)
def test_kapasitetstrinn_selection(
    avg_power: float,
    expected_price: int,
    expected_tier: int,
    expected_range: str,
) -> None:
    """Test kapasitetstrinn tier selection for various power levels."""
    price, tier, range_str = get_kapasitetsledd(avg_power, BKK_KAPASITETSTRINN)
    assert price == expected_price
    assert tier == expected_tier
    assert range_str == expected_range


@pytest.mark.parametrize(
    ("boundary", "expected_lower", "expected_higher"),
    [
        (2.0, 155, 250),
        (5.0, 250, 415),
        (10.0, 415, 600),
    ],
    ids=["2kw", "5kw", "10kw"],
)
def test_boundary_values(boundary: float, expected_lower: int, expected_higher: int) -> None:
    """Exactly at boundary stays in lower tier, just above moves to next."""
    assert get_kapasitetsledd(boundary, BKK_KAPASITETSTRINN)[0] == expected_lower
    assert get_kapasitetsledd(boundary + 0.01, BKK_KAPASITETSTRINN)[0] == expected_higher


# =============================================================================
# Top 3 days calculation tests
# =============================================================================


def test_exactly_3_days() -> None:
    """With exactly 3 days, return average."""
    daily_max = {
        "2026-01-01": 4.5,
        "2026-01-02": 5.0,
        "2026-01-03": 5.5,
    }
    result = calculate_avg_top_3(daily_max)
    expected = (4.5 + 5.0 + 5.5) / 3
    assert result == expected


def test_more_than_3_days_takes_top_3() -> None:
    """With more than 3 days, take top 3."""
    daily_max = {
        "2026-01-01": 3.0,  # Not in top 3
        "2026-01-02": 4.0,  # Not in top 3
        "2026-01-03": 5.0,  # 3rd
        "2026-01-04": 6.0,  # 2nd
        "2026-01-05": 7.0,  # 1st
    }
    result = calculate_avg_top_3(daily_max)
    expected = (5.0 + 6.0 + 7.0) / 3
    assert result == expected


@pytest.mark.parametrize(
    ("daily_max", "expected"),
    [
        ({"2026-01-01": 4.0, "2026-01-02": 6.0}, (4.0 + 6.0) / 2),
        ({"2026-01-01": 5.0}, 5.0),
        ({}, 0.0),
    ],
    ids=["two_days", "one_day", "empty"],
)
def test_less_than_3_days(daily_max: dict[str, float], expected: float) -> None:
    """With less than 3 days, average what we have."""
    assert calculate_avg_top_3(daily_max) == expected


def test_documentation_example() -> None:
    """Test example from beregninger.md: 3.5, 4.8, 4.8 kW → snitt 4.37 kW."""
    daily_max = {
        "2026-01-05": 3.5,
        "2026-01-12": 4.8,
        "2026-01-20": 4.8,
    }
    result = calculate_avg_top_3(daily_max)
    assert result == pytest.approx(4.37, abs=0.01)


# =============================================================================
# Fastledd per kWh tests
# =============================================================================


@pytest.mark.parametrize(
    ("kapasitetsledd", "days_in_month", "expected_approx"),
    [
        (400, 30, 0.556),
        (400, 31, 0.538),
        (400, 28, 0.595),
        (155, 30, 0.215),  # Tier 1
        (415, 30, 0.576),  # Tier 3
        (770, 30, 1.069),  # Tier 5
    ],
    ids=["30_days", "31_days", "28_days", "tier1", "tier3", "tier5"],
)
def test_fastledd_per_kwh(kapasitetsledd: int, days_in_month: int, expected_approx: float) -> None:
    """Test fastledd per kWh calculation."""
    fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24
    assert fastledd_per_kwh == pytest.approx(expected_approx, abs=0.01)


# =============================================================================
# Margin til neste kapasitetstrinn
# =============================================================================


def calculate_margin(
    avg_power: float, kapasitetstrinn: list[tuple[float, int]]
) -> tuple[float, int, int]:
    """Calculate margin to next capacity tier.

    Returns:
        Tuple of (margin_kw, current_price, next_price)
        If on highest tier: margin = 0, next_price = current_price
    """
    for i, (threshold, price) in enumerate(kapasitetstrinn):
        if avg_power <= threshold:
            if threshold == float("inf"):
                return 0.0, price, price
            margin = threshold - avg_power
            if i + 1 < len(kapasitetstrinn):
                next_price = kapasitetstrinn[i + 1][1]
            else:
                next_price = price
            return margin, price, next_price
    last_price = kapasitetstrinn[-1][1]
    return 0.0, last_price, last_price


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
    for threshold, _price in BKK_KAPASITETSTRINN:
        if threshold == float("inf"):
            continue
        margin, _current, _next = calculate_margin(threshold, BKK_KAPASITETSTRINN)
        assert margin == 0.0, f"Margin should be 0 at boundary {threshold} kW"


def test_margin_just_below_boundary() -> None:
    """Just below boundary should have small positive margin."""
    margin, current, _next = calculate_margin(4.99, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(0.01, abs=0.001)
    assert current == 250

def test_margin_just_above_boundary() -> None:
    """Just above boundary should have full margin of new tier."""
    margin, current, _next = calculate_margin(5.01, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(4.99, abs=0.001)
    assert current == 415


# =============================================================================
# Kapasitetsvarsel (warning)
# =============================================================================

DEFAULT_TERSKEL = 2.0


def margin_varsel_active(margin: float, terskel: float = DEFAULT_TERSKEL) -> bool:
    """True if warning should be active (margin < threshold)."""
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


def test_varsel_comfortable_margin() -> None:
    """Consumption well within tier should not warn."""
    margin, _current, _next = calculate_margin(5.5, BKK_KAPASITETSTRINN)
    assert margin == pytest.approx(4.5)
    assert margin_varsel_active(margin) is False
