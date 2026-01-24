"""Test energiledd (energy component) and tariff calculations.

Tests:
- Day/night rate determination
- Holiday detection
- Weekend detection
- Energiledd selection
"""

from __future__ import annotations

from datetime import datetime

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


class TestDayNightHours:
    """Test day/night hour boundaries."""

    def test_day_hours_weekday(self):
        """Day rate: 06:00-21:59 on weekdays."""
        # Monday at different hours
        assert is_day_rate(datetime(2026, 1, 26, 6, 0)) is True   # 06:00
        assert is_day_rate(datetime(2026, 1, 26, 12, 0)) is True  # 12:00
        assert is_day_rate(datetime(2026, 1, 26, 21, 59)) is True # 21:59

    def test_night_hours_weekday(self):
        """Night rate: 22:00-05:59 on weekdays."""
        # Monday at night hours
        assert is_day_rate(datetime(2026, 1, 26, 22, 0)) is False  # 22:00
        assert is_day_rate(datetime(2026, 1, 26, 23, 0)) is False  # 23:00
        assert is_day_rate(datetime(2026, 1, 27, 0, 0)) is False   # 00:00 (next day)
        assert is_day_rate(datetime(2026, 1, 26, 5, 59)) is False  # 05:59

    def test_boundary_6_am(self):
        """Test boundary at 06:00."""
        # 05:59 is night, 06:00 is day
        assert is_day_rate(datetime(2026, 1, 26, 5, 59)) is False
        assert is_day_rate(datetime(2026, 1, 26, 6, 0)) is True

    def test_boundary_10_pm(self):
        """Test boundary at 22:00."""
        # 21:59 is day, 22:00 is night
        assert is_day_rate(datetime(2026, 1, 26, 21, 59)) is True
        assert is_day_rate(datetime(2026, 1, 26, 22, 0)) is False


class TestWeekends:
    """Test weekend detection."""

    def test_saturday_is_night_rate(self):
        """Saturday is always night rate."""
        # Saturday at various times
        assert is_day_rate(datetime(2026, 1, 24, 12, 0)) is False  # Saturday noon
        assert is_day_rate(datetime(2026, 1, 24, 6, 0)) is False   # Saturday morning
        assert is_day_rate(datetime(2026, 1, 24, 22, 0)) is False  # Saturday night

    def test_sunday_is_night_rate(self):
        """Sunday is always night rate."""
        # Sunday at various times
        assert is_day_rate(datetime(2026, 1, 25, 12, 0)) is False  # Sunday noon
        assert is_day_rate(datetime(2026, 1, 25, 6, 0)) is False   # Sunday morning

    def test_friday_to_monday_transition(self):
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


class TestFixedHolidays:
    """Test fixed holidays (same date every year)."""

    def test_new_years_day(self):
        """January 1st is night rate."""
        assert is_day_rate(datetime(2026, 1, 1, 12, 0)) is False
        assert is_day_rate(datetime(2027, 1, 1, 12, 0)) is False

    def test_labor_day(self):
        """May 1st is night rate."""
        assert is_day_rate(datetime(2026, 5, 1, 12, 0)) is False

    def test_constitution_day(self):
        """May 17th is night rate."""
        assert is_day_rate(datetime(2026, 5, 17, 12, 0)) is False

    def test_christmas(self):
        """December 25-26 are night rate."""
        assert is_day_rate(datetime(2026, 12, 25, 12, 0)) is False
        assert is_day_rate(datetime(2026, 12, 26, 12, 0)) is False

    def test_regular_weekday_not_holiday(self):
        """Regular weekday is day rate during day hours."""
        # January 2nd (if weekday)
        assert is_day_rate(datetime(2026, 1, 2, 12, 0)) is True


class TestMovingHolidays:
    """Test moving holidays (Easter, Pentecost, etc.)."""

    def test_easter_2026(self):
        """Easter 2026 dates are night rate."""
        # Skjærtorsdag
        assert is_day_rate(datetime(2026, 4, 2, 12, 0)) is False
        # Langfredag
        assert is_day_rate(datetime(2026, 4, 3, 12, 0)) is False
        # 1. påskedag
        assert is_day_rate(datetime(2026, 4, 5, 12, 0)) is False
        # 2. påskedag
        assert is_day_rate(datetime(2026, 4, 6, 12, 0)) is False

    def test_ascension_day_2026(self):
        """Kristi himmelfartsdag 2026 is night rate."""
        assert is_day_rate(datetime(2026, 5, 14, 12, 0)) is False

    def test_pentecost_2026(self):
        """Pentecost 2026 dates are night rate."""
        # 1. pinsedag
        assert is_day_rate(datetime(2026, 5, 24, 12, 0)) is False
        # 2. pinsedag
        assert is_day_rate(datetime(2026, 5, 25, 12, 0)) is False


class TestEnergyleddSelection:
    """Test energiledd selection based on tariff."""

    def test_day_rate_returns_dag_pris(self):
        """Day rate returns dag_pris."""
        dag_pris = 0.4613
        natt_pris = 0.2329
        # Monday noon
        result = get_energiledd(datetime(2026, 1, 26, 12, 0), dag_pris, natt_pris)
        assert result == dag_pris

    def test_night_rate_returns_natt_pris(self):
        """Night rate returns natt_pris."""
        dag_pris = 0.4613
        natt_pris = 0.2329
        # Monday night
        result = get_energiledd(datetime(2026, 1, 26, 23, 0), dag_pris, natt_pris)
        assert result == natt_pris
        # Weekend
        result = get_energiledd(datetime(2026, 1, 24, 12, 0), dag_pris, natt_pris)
        assert result == natt_pris

    def test_bkk_energiledd_values(self):
        """Test with actual BKK values."""
        dag_pris = 0.4613  # BKK 2026
        natt_pris = 0.2329  # BKK 2026

        # Weekday day
        assert get_energiledd(datetime(2026, 1, 26, 12, 0), dag_pris, natt_pris) == 0.4613
        # Weekday night
        assert get_energiledd(datetime(2026, 1, 26, 23, 0), dag_pris, natt_pris) == 0.2329
        # Weekend
        assert get_energiledd(datetime(2026, 1, 24, 12, 0), dag_pris, natt_pris) == 0.2329
        # Holiday
        assert get_energiledd(datetime(2026, 1, 1, 12, 0), dag_pris, natt_pris) == 0.2329


class TestTariffStrings:
    """Test tariff string representation."""

    def test_tariff_string_day(self):
        """Day tariff string."""
        dt = datetime(2026, 1, 26, 12, 0)
        tariff = "dag" if is_day_rate(dt) else "natt"
        assert tariff == "dag"

    def test_tariff_string_night(self):
        """Night tariff string."""
        dt = datetime(2026, 1, 26, 23, 0)
        tariff = "dag" if is_day_rate(dt) else "natt"
        assert tariff == "natt"

    def test_tariff_string_weekend(self):
        """Weekend should show natt."""
        dt = datetime(2026, 1, 24, 12, 0)  # Saturday
        tariff = "dag" if is_day_rate(dt) else "natt"
        assert tariff == "natt"
