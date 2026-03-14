"""Property-based tests using Hypothesis.

Tests invariants that should hold for ALL possible inputs, not just
hand-picked examples. Complements the parametrized unit tests.
"""

from __future__ import annotations

from datetime import datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.test_energiledd import is_day_rate
from tests.test_kapasitetstrinn import (
    BKK_KAPASITETSTRINN,
    calculate_avg_top_3,
    get_kapasitetsledd,
)

from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE


def calculate_stromstotte(spot_price: float) -> float:
    """Calculate strømstøtte."""
    if spot_price > STROMSTOTTE_LEVEL:
        return round((spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    return 0.0


# =============================================================================
# Kapasitetstrinn invariants
# =============================================================================


@given(power=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
def test_kapasitetstrinn_always_returns_valid_tier(power: float) -> None:
    """Any non-negative power value must map to a valid tier."""
    price, tier, range_str = get_kapasitetsledd(power, BKK_KAPASITETSTRINN)
    assert price > 0
    assert 1 <= tier <= len(BKK_KAPASITETSTRINN)
    assert "kW" in range_str


@given(
    a=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
)
def test_kapasitetstrinn_monotonic(a: float, b: float) -> None:
    """Higher power must never give a lower price (monotonicity)."""
    price_a, _, _ = get_kapasitetsledd(a, BKK_KAPASITETSTRINN)
    price_b, _, _ = get_kapasitetsledd(b, BKK_KAPASITETSTRINN)
    if a <= b:
        assert price_a <= price_b
    else:
        assert price_a >= price_b


# =============================================================================
# Top-3 average invariants
# =============================================================================


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=31,
    )
)
def test_avg_top3_bounded_by_max(values: list[float]) -> None:
    """Average of top 3 can never exceed the maximum value."""
    daily_max = {f"2026-01-{i+1:02d}": v for i, v in enumerate(values)}
    avg = calculate_avg_top_3(daily_max)
    assert avg <= max(values) + 1e-10  # floating point tolerance
    assert avg >= 0


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=31,
    )
)
def test_avg_top3_ignores_low_values(values: list[float]) -> None:
    """Adding a value lower than all top 3 must not change the average."""
    daily_max = {f"2026-01-{i+1:02d}": v for i, v in enumerate(values)}
    avg_before = calculate_avg_top_3(daily_max)

    # Add a value that's guaranteed to be lower than all existing
    daily_max["2026-01-00"] = -1.0  # below any valid power
    # Recalculate with min_value=0 in original, but we used -1 which is below
    # Actually let's use 0 and only test when min of top3 > 0
    sorted_vals = sorted(values, reverse=True)[:3]
    if min(sorted_vals) > 0:
        daily_max_extended = {**daily_max, "2026-02-01": 0.0}
        avg_after = calculate_avg_top_3(daily_max_extended)
        assert abs(avg_after - avg_before) < 1e-10


# =============================================================================
# Day/night tariff invariants
# =============================================================================


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@settings(max_examples=500)
def test_tariff_always_boolean(dt: datetime) -> None:
    """is_day_rate must return True or False for any datetime in 2026."""
    result = is_day_rate(dt)
    assert result is True or result is False


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@settings(max_examples=500)
def test_weekends_always_night(dt: datetime) -> None:
    """Weekends must always be night rate."""
    if dt.weekday() >= 5:
        assert is_day_rate(dt) is False


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@settings(max_examples=500)
def test_night_hours_always_night(dt: datetime) -> None:
    """Hours outside 06-22 must always be night rate."""
    if dt.hour < 6 or dt.hour >= 22:
        assert is_day_rate(dt) is False


# =============================================================================
# Strømstøtte invariants
# =============================================================================


@given(price=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False))
def test_stromstotte_never_negative(price: float) -> None:
    """Strømstøtte must never be negative."""
    assert calculate_stromstotte(price) >= 0


@given(price=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False))
def test_stromstotte_never_exceeds_price_above_threshold(price: float) -> None:
    """Strømstøtte must never exceed the amount above threshold."""
    stotte = calculate_stromstotte(price)
    if price > STROMSTOTTE_LEVEL:
        assert stotte <= (price - STROMSTOTTE_LEVEL) + 1e-10
    else:
        assert stotte == 0.0
