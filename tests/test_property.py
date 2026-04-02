"""Property-based tests using Hypothesis — overkill edition.

Three tiers of testing:
1. Property tests (Hypothesis) — random inputs, verify invariants
2. Exhaustive tests — brute-force every hour of the year, every DSO
3. Differential tests — two independent implementations must agree

Inspired by SQLite's approach of redundant verification across
multiple strategies to catch bugs that any single approach would miss.
"""

from __future__ import annotations

import calendar
from datetime import datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.stromkalkulator.const import (
    AVGIFTSSONE_NORD_NORGE,
    AVGIFTSSONE_STANDARD,
    AVGIFTSSONE_TILTAKSSONE,
    FORBRUKSAVGIFT_ALMINNELIG,
    HELLIGDAGER_BEVEGELIGE,
    HELLIGDAGER_FASTE,
    MVA_SATS,
    NORGESPRIS_INKL_MVA_NORD,
    NORGESPRIS_INKL_MVA_STANDARD,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    get_forbruksavgift,
    get_mva_sats,
    get_norgespris_inkl_mva,
)
from custom_components.stromkalkulator.dso import DSO_LIST
from tests.test_energiledd import is_day_rate
from tests.test_kapasitetstrinn import (
    BKK_KAPASITETSTRINN,
    calculate_avg_top_3,
    get_kapasitetsledd,
)


def calculate_stromstotte(spot_price: float) -> float:
    """Calculate strømstøtte."""
    if spot_price > STROMSTOTTE_LEVEL:
        return round((spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
    return 0.0


# =============================================================================
# TIER 1: Property tests (Hypothesis) — 10,000 random inputs per test
# =============================================================================

HEAVY = settings(max_examples=10_000, deadline=None)


# -- Kapasitetstrinn ----------------------------------------------------------


@given(power=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
@HEAVY
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
@HEAVY
def test_kapasitetstrinn_monotonic(a: float, b: float) -> None:
    """Higher power must never give a lower price (monotonicity)."""
    price_a, _, _ = get_kapasitetsledd(a, BKK_KAPASITETSTRINN)
    price_b, _, _ = get_kapasitetsledd(b, BKK_KAPASITETSTRINN)
    if a <= b:
        assert price_a <= price_b
    else:
        assert price_a >= price_b


@given(power=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
@HEAVY
def test_kapasitetstrinn_tier_matches_range_string(power: float) -> None:
    """The range string must describe the tier the power falls into."""
    _price, tier, range_str = get_kapasitetsledd(power, BKK_KAPASITETSTRINN)
    # Range string should contain "kW"
    assert "kW" in range_str
    # If it starts with ">", it's the last tier
    if range_str.startswith(">"):
        assert tier == len(BKK_KAPASITETSTRINN)
    else:
        # Should contain a dash separator
        assert "-" in range_str


@given(
    power=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    offset=st.floats(min_value=0.001, max_value=100, allow_nan=False, allow_infinity=False),
)
@HEAVY
def test_kapasitetstrinn_adding_power_never_decreases_price(power: float, offset: float) -> None:
    """Adding any positive amount of power must never decrease the price."""
    price_before, _, _ = get_kapasitetsledd(power, BKK_KAPASITETSTRINN)
    price_after, _, _ = get_kapasitetsledd(power + offset, BKK_KAPASITETSTRINN)
    assert price_after >= price_before


# -- Top-3 average ------------------------------------------------------------


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=31,
    )
)
@HEAVY
def test_avg_top3_bounded_by_max(values: list[float]) -> None:
    """Average of top 3 can never exceed the maximum value."""
    daily_max = {f"2026-01-{i + 1:02d}": v for i, v in enumerate(values)}
    avg = calculate_avg_top_3(daily_max)
    assert avg <= max(values) + 1e-10
    assert avg >= 0


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=31,
    )
)
@HEAVY
def test_avg_top3_between_min_and_max_of_top3(values: list[float]) -> None:
    """Average must lie between the min and max of the top 3 values."""
    daily_max = {f"2026-01-{i + 1:02d}": v for i, v in enumerate(values)}
    avg = calculate_avg_top_3(daily_max)
    top3 = sorted(values, reverse=True)[:3]
    assert avg >= min(top3) - 1e-10
    assert avg <= max(top3) + 1e-10


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=31,
    )
)
@HEAVY
def test_avg_top3_ignores_low_values(values: list[float]) -> None:
    """Adding a value below the min of top 3 must not change the average."""
    daily_max = {f"2026-01-{i + 1:02d}": v for i, v in enumerate(values)}
    avg_before = calculate_avg_top_3(daily_max)
    top3 = sorted(values, reverse=True)[:3]
    if min(top3) > 0:
        daily_max["2026-02-01"] = 0.0
        avg_after = calculate_avg_top_3(daily_max)
        assert abs(avg_after - avg_before) < 1e-10


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=3,
        max_size=31,
    ),
    extra=st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
)
@HEAVY
def test_avg_top3_adding_value_never_decreases_when_3_plus(values: list[float], extra: float) -> None:
    """With 3+ existing values, adding a new one can never decrease the top-3 average.

    Note: With <3 values, adding a low value CAN decrease the average since
    the denominator grows. This invariant only holds once we have 3+ values.
    """
    daily_max = {f"2026-01-{i + 1:02d}": v for i, v in enumerate(values)}
    avg_before = calculate_avg_top_3(daily_max)
    daily_max["2026-02-01"] = extra
    avg_after = calculate_avg_top_3(daily_max)
    assert avg_after >= avg_before - 1e-10


# -- Day/night tariff ---------------------------------------------------------


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@HEAVY
def test_weekends_always_night(dt: datetime) -> None:
    """Weekends must always be night rate."""
    if dt.weekday() >= 5:
        assert is_day_rate(dt) is False


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@HEAVY
def test_night_hours_always_night(dt: datetime) -> None:
    """Hours outside 06-22 must always be night rate."""
    if dt.hour < 6 or dt.hour >= 22:
        assert is_day_rate(dt) is False


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2026, 12, 31)))
@HEAVY
def test_day_rate_implies_weekday_and_day_hours(dt: datetime) -> None:
    """If is_day_rate returns True, it must be a weekday during 06-22 and not a holiday."""
    if is_day_rate(dt):
        assert dt.weekday() < 5, f"Day rate on weekend: {dt}"
        assert 6 <= dt.hour < 22, f"Day rate during night hours: {dt}"
        mm_dd = dt.strftime("%m-%d")
        yyyy_mm_dd = dt.strftime("%Y-%m-%d")
        assert mm_dd not in HELLIGDAGER_FASTE, f"Day rate on fixed holiday: {dt}"
        assert yyyy_mm_dd not in HELLIGDAGER_BEVEGELIGE, f"Day rate on moving holiday: {dt}"


# -- Strømstøtte --------------------------------------------------------------


@given(price=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False))
@HEAVY
def test_stromstotte_never_negative(price: float) -> None:
    """Strømstøtte must never be negative."""
    assert calculate_stromstotte(price) >= 0


@given(price=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False))
@HEAVY
def test_stromstotte_never_exceeds_price_above_threshold(price: float) -> None:
    """Strømstøtte must never exceed the amount above threshold."""
    stotte = calculate_stromstotte(price)
    if price > STROMSTOTTE_LEVEL:
        assert stotte <= (price - STROMSTOTTE_LEVEL) + 1e-4
    else:
        assert stotte == 0.0


@given(
    a=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False),
    b=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False),
)
@HEAVY
def test_stromstotte_monotonic(a: float, b: float) -> None:
    """Higher spot price must never give lower strømstøtte."""
    if a <= b:
        assert calculate_stromstotte(a) <= calculate_stromstotte(b) + 1e-4
    else:
        assert calculate_stromstotte(a) >= calculate_stromstotte(b) - 1e-4


@given(price=st.floats(min_value=-10, max_value=100, allow_nan=False, allow_infinity=False))
@HEAVY
def test_stromstotte_effective_price_never_below_threshold(price: float) -> None:
    """Spot price minus strømstøtte must never go below the threshold."""
    stotte = calculate_stromstotte(price)
    effective = price - stotte
    if price > STROMSTOTTE_LEVEL:
        # Should pay approximately threshold + 10% of excess
        expected = STROMSTOTTE_LEVEL + (price - STROMSTOTTE_LEVEL) * (1 - STROMSTOTTE_RATE)
        assert abs(effective - expected) < 1e-3
    else:
        assert effective == price  # no change


# -- Avgifter ------------------------------------------------------------------


@given(month=st.integers(min_value=1, max_value=12))
def test_tiltakssone_always_zero_forbruksavgift(month: int) -> None:
    """Tiltakssone has 0 forbruksavgift for every month."""
    assert get_forbruksavgift(AVGIFTSSONE_TILTAKSSONE, month) == 0.0


# -- Total price consistency ---------------------------------------------------


# =============================================================================
# TIER 2: Exhaustive tests — brute-force verification
# =============================================================================


def test_exhaustive_every_hour_of_2026() -> None:
    """Brute-force test is_day_rate for all 8,760 hours of 2026.

    Verifies against an independent implementation that uses a completely
    different approach (set lookups instead of string formatting).
    """
    # Build holiday set using a different method than the production code
    holidays: set[tuple[int, int]] = set()
    # Fixed holidays as (month, day) tuples
    for mm_dd in HELLIGDAGER_FASTE:
        m, d = map(int, mm_dd.split("-"))
        holidays.add((m, d))
    # Moving holidays for 2026
    for yyyy_mm_dd in HELLIGDAGER_BEVEGELIGE:
        if yyyy_mm_dd.startswith("2026"):
            _, m, d = map(int, yyyy_mm_dd.split("-"))
            holidays.add((m, d))

    dt = datetime(2026, 1, 1, 0, 0)
    end = datetime(2027, 1, 1, 0, 0)
    day_count = 0
    night_count = 0

    while dt < end:
        result = is_day_rate(dt)

        # Independent oracle: compute expected result from scratch
        is_weekend = dt.weekday() >= 5
        is_night_hour = dt.hour < 6 or dt.hour >= 22
        is_holiday = (dt.month, dt.day) in holidays
        expected = not (is_weekend or is_night_hour or is_holiday)

        assert result == expected, (
            f"Mismatch at {dt}: got {result}, expected {expected} "
            f"(weekend={is_weekend}, night={is_night_hour}, holiday={is_holiday})"
        )

        if result:
            day_count += 1
        else:
            night_count += 1

        dt += timedelta(hours=1)

    total_hours = day_count + night_count
    assert total_hours == 8760, f"Expected 8760 hours, got {total_hours}"
    # Sanity: day hours should be roughly 30-40% of total
    day_pct = day_count / total_hours
    assert 0.25 < day_pct < 0.50, f"Day percentage {day_pct:.1%} seems wrong"


def test_exhaustive_every_boundary_of_every_kapasitetstrinn() -> None:
    """Test every exact boundary and boundary+/-epsilon for all DSOs."""
    for dso_id, dso in DSO_LIST.items():
        if not dso["supported"]:
            continue
        trinn = dso["kapasitetstrinn"]
        # Skip dict-format kapasitetstrinn
        if trinn and isinstance(trinn[0], dict):
            continue

        for i, (threshold, expected_price) in enumerate(trinn):
            if threshold == float("inf"):
                continue

            # At boundary: should be this tier
            price_at, _, _ = get_kapasitetsledd(threshold, trinn)
            assert price_at == expected_price, (
                f"{dso_id}: at {threshold} kW expected {expected_price}, got {price_at}"
            )

            # Just above: should be next tier
            if i + 1 < len(trinn):
                next_price = trinn[i + 1][1]
                price_above, _, _ = get_kapasitetsledd(threshold + 0.001, trinn)
                assert price_above == next_price, (
                    f"{dso_id}: at {threshold}+e expected {next_price}, got {price_above}"
                )


def test_exhaustive_all_dso_kapasitetstrinn_monotonic() -> None:
    """Every DSO's kapasitetstrinn must be monotonically non-decreasing."""
    for dso_id, dso in DSO_LIST.items():
        if not dso["supported"]:
            continue
        trinn = dso["kapasitetstrinn"]
        if trinn and isinstance(trinn[0], dict):
            continue

        prev_price = 0
        for threshold, price in trinn:
            assert price >= prev_price, (
                f"{dso_id}: price decreased from {prev_price} to {price} at {threshold} kW"
            )
            prev_price = price


def test_exhaustive_all_dso_have_catch_all_tier() -> None:
    """Every DSO must have a final tier with inf threshold (catch-all)."""
    for dso_id, dso in DSO_LIST.items():
        if not dso["supported"]:
            continue
        trinn = dso["kapasitetstrinn"]
        if trinn and isinstance(trinn[0], dict):
            continue
        last_threshold = trinn[-1][0]
        assert last_threshold == float("inf"), (
            f"{dso_id}: last tier threshold is {last_threshold}, not inf"
        )


def test_exhaustive_all_dso_energiledd_dag_gte_natt() -> None:
    """Day rate must be >= night rate for all supported DSOs."""
    for dso_id, dso in DSO_LIST.items():
        if not dso["supported"]:
            continue
        assert dso["energiledd_dag"] >= dso["energiledd_natt"], (
            f"{dso_id}: dag ({dso['energiledd_dag']}) < natt ({dso['energiledd_natt']})"
        )


def test_exhaustive_forbruksavgift_all_months_all_soner() -> None:
    """Verify forbruksavgift for all 12 months x 3 avgiftssoner."""
    for month in range(1, 13):
        std = get_forbruksavgift(AVGIFTSSONE_STANDARD, month)
        nord = get_forbruksavgift(AVGIFTSSONE_NORD_NORGE, month)
        tiltak = get_forbruksavgift(AVGIFTSSONE_TILTAKSSONE, month)

        assert std == FORBRUKSAVGIFT_ALMINNELIG, f"month {month}: standard wrong"
        assert nord == FORBRUKSAVGIFT_ALMINNELIG, f"month {month}: nord wrong"
        assert tiltak == 0.0, f"month {month}: tiltakssone should be 0"


def test_exhaustive_mva_all_soner() -> None:
    """MVA rates must be consistent across avgiftssoner."""
    assert get_mva_sats(AVGIFTSSONE_STANDARD) == MVA_SATS
    assert get_mva_sats(AVGIFTSSONE_NORD_NORGE) == 0.0
    assert get_mva_sats(AVGIFTSSONE_TILTAKSSONE) == 0.0


def test_exhaustive_norgespris_all_soner() -> None:
    """Norgespris must be consistent across avgiftssoner."""
    assert get_norgespris_inkl_mva(AVGIFTSSONE_STANDARD) == NORGESPRIS_INKL_MVA_STANDARD
    assert get_norgespris_inkl_mva(AVGIFTSSONE_NORD_NORGE) == NORGESPRIS_INKL_MVA_NORD
    assert get_norgespris_inkl_mva(AVGIFTSSONE_TILTAKSSONE) == NORGESPRIS_INKL_MVA_NORD
    # Nord-Norge pays less than standard
    assert NORGESPRIS_INKL_MVA_NORD <= NORGESPRIS_INKL_MVA_STANDARD


# =============================================================================
# TIER 3: Differential tests — two independent implementations must agree
# =============================================================================


def _alt_stromstotte(spot: float) -> float:
    """Alternative strømstøtte implementation using max() instead of if."""
    return round(max(0.0, (spot - STROMSTOTTE_LEVEL)) * STROMSTOTTE_RATE, 4)


@given(price=st.floats(min_value=-100, max_value=100, allow_nan=False, allow_infinity=False))
@HEAVY
def test_differential_stromstotte_two_implementations(price: float) -> None:
    """Two independent strømstøtte implementations must agree."""
    impl1 = calculate_stromstotte(price)
    impl2 = _alt_stromstotte(price)
    assert abs(impl1 - impl2) < 1e-10, (
        f"Implementations disagree at price={price}: {impl1} vs {impl2}"
    )


def _alt_is_day_rate(dt: datetime) -> bool:
    """Alternative day rate implementation using weekday set and range check."""
    weekdays = {0, 1, 2, 3, 4}  # Mon-Fri
    day_hours = range(6, 22)

    if dt.weekday() not in weekdays:
        return False
    if dt.hour not in day_hours:
        return False

    # Check holidays — completely different approach: parse into tuples
    fixed = {(int(h[:2]), int(h[3:])) for h in HELLIGDAGER_FASTE}
    if (dt.month, dt.day) in fixed:
        return False

    moving = set()
    for h in HELLIGDAGER_BEVEGELIGE:
        parts = h.split("-")
        if int(parts[0]) == dt.year:
            moving.add((int(parts[1]), int(parts[2])))
    return (dt.month, dt.day) not in moving


@given(dt=st.datetimes(min_value=datetime(2026, 1, 1), max_value=datetime(2027, 12, 31)))
@HEAVY
def test_differential_day_rate_two_implementations(dt: datetime) -> None:
    """Two independent is_day_rate implementations must agree."""
    impl1 = is_day_rate(dt)
    impl2 = _alt_is_day_rate(dt)
    assert impl1 == impl2, f"Implementations disagree at {dt}: {impl1} vs {impl2}"


def _alt_kapasitetsledd(avg_power: float, trinn: list) -> int:
    """Alternative kapasitetsledd: linear scan with explicit boundary check."""
    for threshold, price in trinn:
        if avg_power <= threshold:
            return price
    return trinn[-1][1]


@given(power=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False))
@HEAVY
def test_differential_kapasitetsledd_two_implementations(power: float) -> None:
    """Two independent kapasitetsledd implementations must agree on price."""
    price1, _, _ = get_kapasitetsledd(power, BKK_KAPASITETSTRINN)
    price2 = _alt_kapasitetsledd(power, BKK_KAPASITETSTRINN)
    assert price1 == price2, f"At {power} kW: {price1} vs {price2}"


def _alt_avg_top3(daily_max: dict[str, float]) -> float:
    """Alternative top-3 average: use heapq instead of sort."""
    import heapq

    if not daily_max:
        return 0.0
    values = list(daily_max.values())
    top3 = heapq.nlargest(min(3, len(values)), values)
    return sum(top3) / len(top3)


@given(
    values=st.lists(
        st.floats(min_value=0, max_value=100, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=31,
    )
)
@HEAVY
def test_differential_avg_top3_two_implementations(values: list[float]) -> None:
    """Two independent top-3 average implementations must agree."""
    daily_max = {f"2026-01-{i + 1:02d}": v for i, v in enumerate(values)}
    result1 = calculate_avg_top_3(daily_max)
    result2 = _alt_avg_top3(daily_max)
    assert abs(result1 - result2) < 1e-10, (
        f"Implementations disagree: {result1} vs {result2} for {values}"
    )


# =============================================================================
# TIER 2 bonus: Exhaustive cross-component tests
# =============================================================================


def test_exhaustive_fastledd_per_kwh_all_months_all_tiers() -> None:
    """Verify fastledd per kWh for all months x all tiers gives sane values."""
    for month in range(1, 13):
        days = calendar.monthrange(2026, month)[1]
        for _threshold, price in BKK_KAPASITETSTRINN:
            fastledd_per_kwh = (price / days) / 24
            # Should be a small positive number (< 10 NOK/kWh even for highest tier)
            assert 0 < fastledd_per_kwh < 15, (
                f"month {month}, price {price}: fastledd_per_kwh={fastledd_per_kwh}"
            )
            # Longer months should give lower per-kWh cost
            if month in (1, 3, 5, 7, 8, 10, 12):  # 31-day months
                fastledd_31 = (price / 31) / 24
                fastledd_28 = (price / 28) / 24
                assert fastledd_31 < fastledd_28


@pytest.mark.parametrize("dso_id", [k for k, v in DSO_LIST.items() if v["supported"]])
def test_exhaustive_total_price_sane_for_each_dso(dso_id: str) -> None:
    """For each DSO, compute total price at various spot prices and verify sanity."""
    dso = DSO_LIST[dso_id]
    trinn = dso["kapasitetstrinn"]
    if trinn and isinstance(trinn[0], dict):
        pytest.skip(f"{dso_id} uses dict-format kapasitetstrinn")

    energiledd_dag = dso["energiledd_dag"]
    # Use lowest kapasitetstrinn for baseline
    kapasitetsledd = trinn[0][1]

    for spot in [0.0, 0.5, STROMSTOTTE_LEVEL, 1.0, 2.0, 5.0]:
        stotte = calculate_stromstotte(spot)
        fastledd = (kapasitetsledd / 30) / 24
        total = (spot - stotte) + energiledd_dag + fastledd
        # Total should never be negative for non-negative spot
        assert total >= -1e-10, f"{dso_id}: negative total {total} at spot={spot}"
        # Total without støtte should always be >= total with støtte
        total_uten = spot + energiledd_dag + fastledd
        assert total_uten >= total - 1e-10
