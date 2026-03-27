"""Test akkumulert Norgespris-besparelse.

Tests the accumulated monthly comparison between spot price and Norgespris:
- Spot users see savings/loss compared to Norgespris
- Norgespris users see savings/loss compared to spot+stotte
- Positive value = saving with current plan
- Accumulates over each hour's consumption
"""

from __future__ import annotations

import pytest


def accumulate_norgespris_diff(
    har_norgespris: bool,
    spot_total: float,
    norgespris_total: float,
    forbruk_kwh: float,
    existing_diff: float,
) -> float:
    """Calculate accumulated price difference between spot and Norgespris.

    Args:
        har_norgespris: True if user has Norgespris, False if spot.
        spot_total: Total spot cost per kWh (inkl. mva, stotte, nettleie).
        norgespris_total: Total Norgespris cost per kWh (inkl. mva, nettleie).
        forbruk_kwh: Consumption in kWh for the period.
        existing_diff: Previously accumulated difference in kr.

    Returns:
        New accumulated difference in kr. Positive = saving with current plan.
    """
    if har_norgespris:
        diff_per_kwh = spot_total - norgespris_total  # positive when spot > norgespris = saving
    else:
        diff_per_kwh = norgespris_total - spot_total  # positive when norgespris > spot = saving
    return existing_diff + diff_per_kwh * forbruk_kwh


# =============================================================================
# Spot user tests
# =============================================================================


def test_spot_user_saves_vs_norgespris() -> None:
    """Spot user saves when spot is cheaper than Norgespris.

    spot=0.30, norgespris=0.50, 10 kWh:
    diff_per_kwh = 0.50 - 0.30 = 0.20 (norgespris is more expensive)
    result = 0 + 0.20 * 10 = 2.0 kr saving
    """
    result = accumulate_norgespris_diff(
        har_norgespris=False,
        spot_total=0.30,
        norgespris_total=0.50,
        forbruk_kwh=10.0,
        existing_diff=0.0,
    )
    assert result == pytest.approx(2.0)


def test_spot_user_loses_vs_norgespris() -> None:
    """Spot user loses when spot is more expensive than Norgespris.

    spot=0.80, norgespris=0.50, 10 kWh:
    diff_per_kwh = 0.50 - 0.80 = -0.30 (spot is more expensive)
    result = 0 + (-0.30) * 10 = -3.0 kr loss
    """
    result = accumulate_norgespris_diff(
        har_norgespris=False,
        spot_total=0.80,
        norgespris_total=0.50,
        forbruk_kwh=10.0,
        existing_diff=0.0,
    )
    assert result == pytest.approx(-3.0)


# =============================================================================
# Norgespris user tests
# =============================================================================


def test_norgespris_user_saves_vs_spot() -> None:
    """Norgespris user saves when spot is more expensive.

    norgespris=0.50, spot=0.80, 10 kWh:
    diff_per_kwh = 0.80 - 0.50 = 0.30 (spot is more expensive = saving)
    result = 0 + 0.30 * 10 = 3.0 kr saving
    """
    result = accumulate_norgespris_diff(
        har_norgespris=True,
        spot_total=0.80,
        norgespris_total=0.50,
        forbruk_kwh=10.0,
        existing_diff=0.0,
    )
    assert result == pytest.approx(3.0)


# =============================================================================
# Accumulation tests
# =============================================================================


def test_accumulation_over_time() -> None:
    """Verify running total accumulates across two updates.

    Update 1: spot=0.30, norgespris=0.50, 10 kWh → +2.0 kr
    Update 2: spot=0.80, norgespris=0.50, 5 kWh → -1.5 kr
    Total: 2.0 + (-1.5) = 0.5 kr
    """
    # First hour: cheap spot
    diff = accumulate_norgespris_diff(
        har_norgespris=False,
        spot_total=0.30,
        norgespris_total=0.50,
        forbruk_kwh=10.0,
        existing_diff=0.0,
    )
    assert diff == pytest.approx(2.0)

    # Second hour: expensive spot
    diff = accumulate_norgespris_diff(
        har_norgespris=False,
        spot_total=0.80,
        norgespris_total=0.50,
        forbruk_kwh=5.0,
        existing_diff=diff,
    )
    assert diff == pytest.approx(0.5)


def test_zero_consumption_no_change() -> None:
    """Zero consumption should not change accumulated diff."""
    result = accumulate_norgespris_diff(
        har_norgespris=False,
        spot_total=0.80,
        norgespris_total=0.50,
        forbruk_kwh=0.0,
        existing_diff=5.0,
    )
    assert result == pytest.approx(5.0)
