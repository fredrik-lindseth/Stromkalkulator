"""Test strømpris per kWh calculations (uten kapasitetsledd).

Tests the two new coordinator values:
- strompris_per_kwh = spotpris + energiledd (before subsidy)
- strompris_per_kwh_etter_stotte = (spotpris - strømstøtte) + energiledd (after subsidy)
- For Norgespris: both = norgespris + energiledd

These values represent the variable electricity cost per kWh, excluding
the capacity component (kapasitetsledd) which is a fixed monthly fee.
"""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    NORGESPRIS_INKL_MVA_STANDARD,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
)

# =============================================================================
# Local helper functions (mirrors coordinator logic)
# =============================================================================


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


def strompris_per_kwh(spot_price: float, energiledd: float) -> float:
    """Calculate strømpris per kWh before subsidy.

    strompris_per_kwh = spotpris + energiledd

    Args:
        spot_price: Spot price in NOK/kWh
        energiledd: Energy component in NOK/kWh

    Returns:
        Price per kWh in NOK (rounded to 4 decimals)
    """
    return round(spot_price + energiledd, 4)


def strompris_per_kwh_etter_stotte(spot_price: float, energiledd: float) -> float:
    """Calculate strømpris per kWh after subsidy.

    strompris_per_kwh_etter_stotte = (spotpris - strømstøtte) + energiledd

    Args:
        spot_price: Spot price in NOK/kWh
        energiledd: Energy component in NOK/kWh

    Returns:
        Price per kWh in NOK (rounded to 4 decimals)
    """
    stromstotte = calculate_stromstotte(spot_price)
    return round(spot_price - stromstotte + energiledd, 4)


def strompris_per_kwh_norgespris(norgespris: float, energiledd: float) -> float:
    """Calculate strømpris per kWh for Norgespris users.

    Both before and after subsidy are identical for Norgespris.

    Args:
        norgespris: Norgespris in NOK/kWh (inkl. mva)
        energiledd: Energy component in NOK/kWh

    Returns:
        Price per kWh in NOK (rounded to 4 decimals)
    """
    return round(norgespris + energiledd, 4)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bkk_energiledd() -> tuple[float, float]:
    """BKK energiledd prices 2026 (dag, natt)."""
    return (0.4613, 0.2329)


# =============================================================================
# Standard spotpris (before subsidy)
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd", "expected"),
    [
        (0.50, 0.4613, 0.9613),  # Low spot + day rate
        (0.50, 0.2329, 0.7329),  # Low spot + night rate
        (1.20, 0.4613, 1.6613),  # Moderate spot + day rate
        (1.20, 0.2329, 1.4329),  # Moderate spot + night rate
        (2.50, 0.4613, 2.9613),  # High spot + day rate
        (0.00, 0.4613, 0.4613),  # Zero spot (energiledd only)
    ],
    ids=[
        "low_spot_day",
        "low_spot_night",
        "moderate_spot_day",
        "moderate_spot_night",
        "high_spot_day",
        "zero_spot_day",
    ],
)
def test_strompris_per_kwh_before_subsidy(
    spot_price: float, energiledd: float, expected: float
) -> None:
    """strompris_per_kwh = spotpris + energiledd."""
    result = strompris_per_kwh(spot_price, energiledd)
    assert result == expected


def test_strompris_per_kwh_is_sum_of_components(
    bkk_energiledd: tuple[float, float],
) -> None:
    """Verify strompris_per_kwh is simply spot + energiledd."""
    dag, natt = bkk_energiledd
    spot = 1.50
    assert strompris_per_kwh(spot, dag) == round(spot + dag, 4)
    assert strompris_per_kwh(spot, natt) == round(spot + natt, 4)


# =============================================================================
# After subsidy (strompris_per_kwh_etter_stotte)
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd"),
    [
        (1.20, 0.4613),  # Above threshold + day rate
        (1.50, 0.4613),  # Well above threshold + day rate
        (2.00, 0.2329),  # High spot + night rate
        (5.00, 0.4613),  # Extreme spot + day rate
    ],
    ids=["moderate_day", "high_day", "high_night", "extreme_day"],
)
def test_strompris_etter_stotte_above_threshold(
    spot_price: float, energiledd: float
) -> None:
    """When spot > threshold, after-subsidy price is reduced."""
    before = strompris_per_kwh(spot_price, energiledd)
    after = strompris_per_kwh_etter_stotte(spot_price, energiledd)
    assert after < before


@pytest.mark.parametrize(
    ("spot_price", "energiledd"),
    [
        (1.20, 0.4613),
        (2.00, 0.2329),
        (5.00, 0.4613),
    ],
    ids=["moderate", "high", "extreme"],
)
def test_strompris_etter_stotte_formula(
    spot_price: float, energiledd: float
) -> None:
    """Verify formula: (spotpris - strømstøtte) + energiledd."""
    stromstotte = calculate_stromstotte(spot_price)
    expected = round(spot_price - stromstotte + energiledd, 4)
    assert strompris_per_kwh_etter_stotte(spot_price, energiledd) == expected


# =============================================================================
# Under threshold (before and after should be equal)
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd"),
    [
        (0.50, 0.4613),  # Well below threshold
        (0.70, 0.2329),  # Below threshold
        (0.90, 0.4613),  # Just below threshold
        (STROMSTOTTE_LEVEL, 0.4613),  # Exactly at threshold
        (0.00, 0.2329),  # Zero spot
    ],
    ids=["well_below", "below", "just_below", "at_threshold", "zero"],
)
def test_under_threshold_before_and_after_equal(
    spot_price: float, energiledd: float
) -> None:
    """When spot <= threshold, no subsidy applies — before and after are equal."""
    before = strompris_per_kwh(spot_price, energiledd)
    after = strompris_per_kwh_etter_stotte(spot_price, energiledd)
    assert before == after


# =============================================================================
# Negative spot price
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd"),
    [
        (-0.10, 0.4613),  # Slightly negative + day rate
        (-0.50, 0.2329),  # Moderately negative + night rate
        (-1.00, 0.4613),  # Very negative + day rate
    ],
    ids=["slightly_negative", "moderately_negative", "very_negative"],
)
def test_negative_spot_price(spot_price: float, energiledd: float) -> None:
    """Negative spot prices should still calculate correctly."""
    before = strompris_per_kwh(spot_price, energiledd)
    after = strompris_per_kwh_etter_stotte(spot_price, energiledd)
    expected = round(spot_price + energiledd, 4)
    # Negative spot is below threshold, so no subsidy
    assert before == expected
    assert before == after


def test_negative_spot_can_give_negative_total() -> None:
    """If |spot| > energiledd, strompris_per_kwh can be negative."""
    result = strompris_per_kwh(-0.50, 0.2329)
    assert result < 0


# =============================================================================
# Norgespris (both values identical)
# =============================================================================


def test_norgespris_both_values_identical(
    bkk_energiledd: tuple[float, float],
) -> None:
    """For Norgespris users, before and after subsidy are the same."""
    dag, natt = bkk_energiledd
    norgespris = NORGESPRIS_INKL_MVA_STANDARD

    before_dag = strompris_per_kwh_norgespris(norgespris, dag)
    after_dag = strompris_per_kwh_norgespris(norgespris, dag)
    assert before_dag == after_dag

    before_natt = strompris_per_kwh_norgespris(norgespris, natt)
    after_natt = strompris_per_kwh_norgespris(norgespris, natt)
    assert before_natt == after_natt


def test_norgespris_uses_fixed_price(
    bkk_energiledd: tuple[float, float],
) -> None:
    """Norgespris ignores spot price — always uses the fixed Norgespris."""
    dag, _ = bkk_energiledd
    norgespris = NORGESPRIS_INKL_MVA_STANDARD
    expected = round(norgespris + dag, 4)
    assert strompris_per_kwh_norgespris(norgespris, dag) == expected


def test_norgespris_day_vs_night(
    bkk_energiledd: tuple[float, float],
) -> None:
    """Norgespris still varies by day/night due to energiledd."""
    dag, natt = bkk_energiledd
    norgespris = NORGESPRIS_INKL_MVA_STANDARD
    day_price = strompris_per_kwh_norgespris(norgespris, dag)
    night_price = strompris_per_kwh_norgespris(norgespris, natt)
    assert day_price > night_price


# =============================================================================
# Comparison with total price (strompris < total, since total includes
# kapasitetsledd per kWh)
# =============================================================================


@pytest.mark.parametrize(
    ("spot_price", "energiledd", "kapasitetsledd_per_kwh"),
    [
        (1.20, 0.4613, 0.05),  # Typical values
        (0.50, 0.2329, 0.10),  # Low spot, higher capacity
        (2.00, 0.4613, 0.01),  # High spot, low capacity
    ],
    ids=["typical", "low_spot_high_cap", "high_spot_low_cap"],
)
def test_strompris_less_than_total_price(
    spot_price: float, energiledd: float, kapasitetsledd_per_kwh: float
) -> None:
    """strompris_per_kwh should always be less than total_price.

    total_price = spotpris - strømstøtte + energiledd + kapasitetsledd_per_kwh
    strompris_per_kwh_etter_stotte = spotpris - strømstøtte + energiledd

    The difference is kapasitetsledd_per_kwh, which is always > 0.
    """
    stromstotte = calculate_stromstotte(spot_price)
    strompris = strompris_per_kwh_etter_stotte(spot_price, energiledd)
    total = round(spot_price - stromstotte + energiledd + kapasitetsledd_per_kwh, 4)
    assert strompris < total


def test_strompris_differs_from_total_by_kapasitetsledd() -> None:
    """The difference between total_price and strompris_per_kwh is kapasitetsledd."""
    spot_price = 1.50
    energiledd = 0.4613
    kapasitetsledd_per_kwh = 0.0532

    stromstotte = calculate_stromstotte(spot_price)
    strompris = strompris_per_kwh_etter_stotte(spot_price, energiledd)
    total = round(spot_price - stromstotte + energiledd + kapasitetsledd_per_kwh, 4)

    diff = round(total - strompris, 4)
    assert diff == kapasitetsledd_per_kwh
