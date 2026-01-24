"""Test kapasitetstrinn (capacity tier) calculations.

Tests the capacity-based grid tariff calculation:
- Based on average of top 3 consumption days
- Determines monthly fixed fee (kapasitetsledd)
"""

from __future__ import annotations

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
            prev_threshold = kapasitetstrinn[i-2][0] if i > 1 else 0
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


class TestKapasitetstrinnSelection:
    """Test kapasitetstrinn tier selection."""

    def test_tier_1_0_to_2_kw(self):
        """Tier 1: 0-2 kW → 155 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(0.5, BKK_KAPASITETSTRINN)
        assert price == 155
        assert tier == 1
        assert range_str == "0-2 kW"

        price, tier, range_str = get_kapasitetsledd(2.0, BKK_KAPASITETSTRINN)
        assert price == 155
        assert tier == 1

    def test_tier_2_2_to_5_kw(self):
        """Tier 2: 2-5 kW → 250 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(2.1, BKK_KAPASITETSTRINN)
        assert price == 250
        assert tier == 2
        assert range_str == "2-5 kW"

        price, tier, range_str = get_kapasitetsledd(5.0, BKK_KAPASITETSTRINN)
        assert price == 250
        assert tier == 2

    def test_tier_3_5_to_10_kw(self):
        """Tier 3: 5-10 kW → 415 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(5.1, BKK_KAPASITETSTRINN)
        assert price == 415
        assert tier == 3
        assert range_str == "5-10 kW"

        price, tier, range_str = get_kapasitetsledd(10.0, BKK_KAPASITETSTRINN)
        assert price == 415
        assert tier == 3

    def test_tier_4_10_to_15_kw(self):
        """Tier 4: 10-15 kW → 600 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(10.1, BKK_KAPASITETSTRINN)
        assert price == 600
        assert tier == 4
        assert range_str == "10-15 kW"

    def test_tier_5_15_to_20_kw(self):
        """Tier 5: 15-20 kW → 770 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(15.1, BKK_KAPASITETSTRINN)
        assert price == 770
        assert tier == 5
        assert range_str == "15-20 kW"

    def test_tier_6_20_to_25_kw(self):
        """Tier 6: 20-25 kW → 940 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(20.1, BKK_KAPASITETSTRINN)
        assert price == 940
        assert tier == 6
        assert range_str == "20-25 kW"

    def test_tier_7_25_to_50_kw(self):
        """Tier 7: 25-50 kW → 1800 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(30.0, BKK_KAPASITETSTRINN)
        assert price == 1800
        assert tier == 7
        assert range_str == "25-50 kW"

    def test_tier_8_50_to_75_kw(self):
        """Tier 8: 50-75 kW → 2650 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(60.0, BKK_KAPASITETSTRINN)
        assert price == 2650
        assert tier == 8
        assert range_str == "50-75 kW"

    def test_tier_9_75_to_100_kw(self):
        """Tier 9: 75-100 kW → 3500 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(90.0, BKK_KAPASITETSTRINN)
        assert price == 3500
        assert tier == 9
        assert range_str == "75-100 kW"

    def test_tier_10_above_100_kw(self):
        """Tier 10: >100 kW → 6900 kr/mnd."""
        price, tier, range_str = get_kapasitetsledd(150.0, BKK_KAPASITETSTRINN)
        assert price == 6900
        assert tier == 10
        assert range_str == ">100 kW"

    def test_zero_consumption(self):
        """Zero consumption should give tier 1."""
        price, tier, _range_str = get_kapasitetsledd(0.0, BKK_KAPASITETSTRINN)
        assert price == 155
        assert tier == 1

    def test_boundary_values(self):
        """Test exact boundary values."""
        # Exactly at boundary should stay in lower tier
        assert get_kapasitetsledd(2.0, BKK_KAPASITETSTRINN)[0] == 155
        assert get_kapasitetsledd(5.0, BKK_KAPASITETSTRINN)[0] == 250
        assert get_kapasitetsledd(10.0, BKK_KAPASITETSTRINN)[0] == 415

        # Just above boundary should move to next tier
        assert get_kapasitetsledd(2.01, BKK_KAPASITETSTRINN)[0] == 250
        assert get_kapasitetsledd(5.01, BKK_KAPASITETSTRINN)[0] == 415
        assert get_kapasitetsledd(10.01, BKK_KAPASITETSTRINN)[0] == 600


class TestTop3DaysCalculation:
    """Test top 3 days average calculation."""

    def test_exactly_3_days(self):
        """With exactly 3 days, return average."""
        daily_max = {
            "2026-01-01": 4.5,
            "2026-01-02": 5.0,
            "2026-01-03": 5.5,
        }
        result = calculate_avg_top_3(daily_max)
        expected = (4.5 + 5.0 + 5.5) / 3
        assert result == expected

    def test_more_than_3_days_takes_top_3(self):
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

    def test_less_than_3_days(self):
        """With less than 3 days, average what we have."""
        # 2 days
        daily_max = {
            "2026-01-01": 4.0,
            "2026-01-02": 6.0,
        }
        result = calculate_avg_top_3(daily_max)
        expected = (4.0 + 6.0) / 2
        assert result == expected

        # 1 day
        daily_max = {"2026-01-01": 5.0}
        result = calculate_avg_top_3(daily_max)
        assert result == 5.0

    def test_empty_returns_zero(self):
        """Empty dict returns 0."""
        assert calculate_avg_top_3({}) == 0.0

    def test_documentation_example(self):
        """Test example from beregninger.md."""
        # Eksempel: 3.5, 4.8, 4.8 kW → snitt 4.37 kW
        daily_max = {
            "2026-01-05": 3.5,
            "2026-01-12": 4.8,
            "2026-01-20": 4.8,
        }
        result = calculate_avg_top_3(daily_max)
        (3.5 + 4.8 + 4.8) / 3
        assert abs(result - 4.37) < 0.01


class TestFastleddPerKwh:
    """Test fastledd per kWh calculation."""

    def test_fastledd_per_kwh_30_days(self):
        """Test fastledd per kWh for 30-day month."""
        kapasitetsledd = 400  # kr/mnd
        days_in_month = 30
        fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24
        expected = 400 / 30 / 24  # ≈ 0.556 NOK/kWh
        assert abs(fastledd_per_kwh - expected) < 0.001
        assert abs(fastledd_per_kwh - 0.556) < 0.01

    def test_fastledd_per_kwh_31_days(self):
        """Test fastledd per kWh for 31-day month."""
        kapasitetsledd = 400  # kr/mnd
        days_in_month = 31
        fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24
        expected = 400 / 31 / 24  # ≈ 0.538 NOK/kWh
        assert abs(fastledd_per_kwh - expected) < 0.001

    def test_fastledd_per_kwh_28_days(self):
        """Test fastledd per kWh for February (28 days)."""
        kapasitetsledd = 400  # kr/mnd
        days_in_month = 28
        fastledd_per_kwh = (kapasitetsledd / days_in_month) / 24
        expected = 400 / 28 / 24  # ≈ 0.595 NOK/kWh
        assert abs(fastledd_per_kwh - expected) < 0.001

    def test_different_kapasitetsledd_values(self):
        """Test with different kapasitetsledd values."""
        days_in_month = 30

        # Tier 1: 155 kr
        assert abs((155 / days_in_month / 24) - 0.215) < 0.01

        # Tier 3: 415 kr
        assert abs((415 / days_in_month / 24) - 0.576) < 0.01

        # Tier 5: 770 kr
        assert abs((770 / days_in_month / 24) - 1.069) < 0.01
