"""Test energiledd (energy component) and tariff calculations.

Tests:
- Day/night rate determination
- Holiday detection
- Weekend detection
- Energiledd selection
"""

from __future__ import annotations

from datetime import datetime

import pytest

# Faste helligdager (MM-DD format)
HELLIGDAGER_FASTE = [
    "01-01",  # Nyttårsdag
    "05-01",  # Arbeidernes dag
    "05-17",  # Grunnlovsdag
    "12-25",  # 1. juledag
    "12-26",  # 2. juledag
]

# Bevegelige helligdager (YYYY-MM-DD format) - 2024-2027
HELLIGDAGER_BEVEGELIGE = [
    # 2025
    "2025-04-17",  # Skjærtorsdag
    "2025-04-18",  # Langfredag
    "2025-04-20",  # 1. påskedag
    "2025-04-21",  # 2. påskedag
    "2025-05-29",  # Kristi himmelfartsdag
    "2025-06-08",  # 1. pinsedag
    "2025-06-09",  # 2. pinsedag
    # 2026
    "2026-04-02",  # Skjærtorsdag
    "2026-04-03",  # Langfredag
    "2026-04-05",  # 1. påskedag
    "2026-04-06",  # 2. påskedag
    "2026-05-14",  # Kristi himmelfartsdag
    "2026-05-24",  # 1. pinsedag
    "2026-05-25",  # 2. pinsedag
]


def is_day_rate(dt: datetime) -> bool:
    """Check if current time is day rate.

    Day rate: Weekdays 06:00-22:00 (not holidays)
    Night rate: 22:00-06:00, weekends, and holidays

    Args:
        dt: datetime to check

    Returns:
        True if day rate, False if night rate
    """
    date_mm_dd = dt.strftime("%m-%d")
    date_yyyy_mm_dd = dt.strftime("%Y-%m-%d")

    is_fixed_holiday = date_mm_dd in HELLIGDAGER_FASTE
    is_moving_holiday = date_yyyy_mm_dd in HELLIGDAGER_BEVEGELIGE
    is_weekend = dt.weekday() >= 5  # 5=Saturday, 6=Sunday
    is_night = dt.hour < 6 or dt.hour >= 22

    return not (is_fixed_holiday or is_moving_holiday or is_weekend or is_night)


def get_energiledd(dt: datetime, dag_pris: float, natt_pris: float) -> float:
    """Get energiledd based on time.

    Args:
        dt: datetime to check
        dag_pris: Day rate in NOK/kWh
        natt_pris: Night rate in NOK/kWh

    Returns:
        Energiledd in NOK/kWh
    """
    if is_day_rate(dt):
        return dag_pris
    return natt_pris


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def bkk_prices() -> tuple[float, float]:
    """BKK energiledd prices 2026."""
    return (0.4613, 0.2329)  # (dag, natt)


# =============================================================================
# Day/Night hour boundary tests
# =============================================================================


@pytest.mark.parametrize(
    ("hour", "expected"),
    [
        (6, True),  # 06:00 - day starts
        (12, True),  # 12:00 - midday
        (21, True),  # 21:00 - still day
        (22, False),  # 22:00 - night starts
        (23, False),  # 23:00 - night
        (0, False),  # 00:00 - night
        (5, False),  # 05:00 - still night
    ],
    ids=["6am_day", "noon_day", "9pm_day", "10pm_night", "11pm_night", "midnight_night", "5am_night"],
)
def test_hour_boundaries_weekday(hour: int, expected: bool) -> None:
    """Test hour boundaries on a regular weekday (Monday)."""
    dt = datetime(2026, 1, 26, hour, 0)  # Monday
    assert is_day_rate(dt) is expected


def test_boundary_exactly_6am() -> None:
    """05:59 is night, 06:00 is day."""
    assert is_day_rate(datetime(2026, 1, 26, 5, 59)) is False
    assert is_day_rate(datetime(2026, 1, 26, 6, 0)) is True


def test_boundary_exactly_10pm() -> None:
    """21:59 is day, 22:00 is night."""
    assert is_day_rate(datetime(2026, 1, 26, 21, 59)) is True
    assert is_day_rate(datetime(2026, 1, 26, 22, 0)) is False


# =============================================================================
# Weekend tests
# =============================================================================


@pytest.mark.parametrize(
    "hour",
    [6, 12, 22],
    ids=["morning", "noon", "evening"],
)
def test_saturday_always_night_rate(hour: int) -> None:
    """Saturday is always night rate regardless of time."""
    assert is_day_rate(datetime(2026, 1, 24, hour, 0)) is False  # Saturday


@pytest.mark.parametrize(
    "hour",
    [6, 12, 22],
    ids=["morning", "noon", "evening"],
)
def test_sunday_always_night_rate(hour: int) -> None:
    """Sunday is always night rate regardless of time."""
    assert is_day_rate(datetime(2026, 1, 25, hour, 0)) is False  # Sunday


def test_friday_to_monday_transition() -> None:
    """Test transition from Friday to Monday."""
    # Friday 21:59 - day rate
    assert is_day_rate(datetime(2026, 1, 23, 21, 59)) is True
    # Friday 22:00 - night rate
    assert is_day_rate(datetime(2026, 1, 23, 22, 0)) is False
    # Saturday - night rate
    assert is_day_rate(datetime(2026, 1, 24, 12, 0)) is False
    # Sunday - night rate
    assert is_day_rate(datetime(2026, 1, 25, 12, 0)) is False
    # Monday 06:00 - day rate
    assert is_day_rate(datetime(2026, 1, 26, 6, 0)) is True


# =============================================================================
# Fixed holiday tests
# =============================================================================


@pytest.mark.parametrize(
    ("month", "day", "name"),
    [
        (1, 1, "nyttarsdag"),
        (5, 1, "arbeidernes_dag"),
        (5, 17, "grunnlovsdag"),
        (12, 25, "juledag_1"),
        (12, 26, "juledag_2"),
    ],
    ids=["nyttarsdag", "arbeidernes_dag", "grunnlovsdag", "juledag_1", "juledag_2"],
)
def test_fixed_holidays_are_night_rate(month: int, day: int, name: str) -> None:
    """Fixed holidays should always be night rate."""
    assert is_day_rate(datetime(2026, month, day, 12, 0)) is False


def test_regular_weekday_not_holiday() -> None:
    """Regular weekday is day rate during day hours."""
    # January 2nd 2026 is a Friday (weekday, not holiday)
    assert is_day_rate(datetime(2026, 1, 2, 12, 0)) is True


# =============================================================================
# Moving holiday tests (Easter, Pentecost, etc.)
# =============================================================================


@pytest.mark.parametrize(
    ("date", "name"),
    [
        ("2026-04-02", "skjaertorsdag"),
        ("2026-04-03", "langfredag"),
        ("2026-04-05", "1_paskedag"),
        ("2026-04-06", "2_paskedag"),
        ("2026-05-14", "kristi_himmelfartsdag"),
        ("2026-05-24", "1_pinsedag"),
        ("2026-05-25", "2_pinsedag"),
    ],
    ids=[
        "skjaertorsdag",
        "langfredag",
        "1_paskedag",
        "2_paskedag",
        "kristi_himmelfartsdag",
        "1_pinsedag",
        "2_pinsedag",
    ],
)
def test_moving_holidays_2026_are_night_rate(date: str, name: str) -> None:
    """Moving holidays in 2026 should be night rate."""
    year, month, day = map(int, date.split("-"))
    assert is_day_rate(datetime(year, month, day, 12, 0)) is False


# =============================================================================
# Energiledd selection tests
# =============================================================================


def test_day_rate_returns_dag_pris(bkk_prices: tuple[float, float]) -> None:
    """Day rate returns dag_pris."""
    dag_pris, natt_pris = bkk_prices
    result = get_energiledd(datetime(2026, 1, 26, 12, 0), dag_pris, natt_pris)  # Monday noon
    assert result == dag_pris


def test_night_rate_returns_natt_pris(bkk_prices: tuple[float, float]) -> None:
    """Night rate returns natt_pris."""
    dag_pris, natt_pris = bkk_prices
    # Night hours
    assert get_energiledd(datetime(2026, 1, 26, 23, 0), dag_pris, natt_pris) == natt_pris
    # Weekend
    assert get_energiledd(datetime(2026, 1, 24, 12, 0), dag_pris, natt_pris) == natt_pris


@pytest.mark.parametrize(
    ("dt", "expected_rate"),
    [
        (datetime(2026, 1, 26, 12, 0), "dag"),  # Weekday day
        (datetime(2026, 1, 26, 23, 0), "natt"),  # Weekday night
        (datetime(2026, 1, 24, 12, 0), "natt"),  # Weekend
        (datetime(2026, 1, 1, 12, 0), "natt"),  # Holiday
    ],
    ids=["weekday_day", "weekday_night", "weekend", "holiday"],
)
def test_bkk_energiledd_selection(dt: datetime, expected_rate: str, bkk_prices: tuple[float, float]) -> None:
    """Test with actual BKK values."""
    dag_pris, natt_pris = bkk_prices
    expected = dag_pris if expected_rate == "dag" else natt_pris
    assert get_energiledd(dt, dag_pris, natt_pris) == expected


# =============================================================================
# Tariff string tests
# =============================================================================


@pytest.mark.parametrize(
    ("dt", "expected_tariff"),
    [
        (datetime(2026, 1, 26, 12, 0), "dag"),
        (datetime(2026, 1, 26, 23, 0), "natt"),
        (datetime(2026, 1, 24, 12, 0), "natt"),  # Saturday
    ],
    ids=["weekday_day", "weekday_night", "weekend"],
)
def test_tariff_string(dt: datetime, expected_tariff: str) -> None:
    """Test tariff string representation."""
    tariff = "dag" if is_day_rate(dt) else "natt"
    assert tariff == expected_tariff
