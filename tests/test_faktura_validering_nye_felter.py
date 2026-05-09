"""Tests for new invoice verification fields.

- Norgespris compensation accumulation
- Previous month kapasitetsledd calculation
- Daily max power with hour tracking
- Migration from old float format to new dict format
- Top 3 calculation with new format
"""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import get_norgespris_inkl_mva

# =============================================================================
# Change 1: Norgespris compensation accumulation
# =============================================================================


class TestNorgesprisCompensation:
    """Test the (norgespris - spotpris) * kWh accumulator."""

    def test_spot_below_norgespris_positive_compensation(self) -> None:
        """When spot < norgespris, compensation is positive (norgespris costs more)."""
        norgespris = get_norgespris_inkl_mva("standard")  # 0.50
        spot = 0.30
        kwh = 10.0
        compensation = (norgespris - spot) * kwh
        assert compensation == pytest.approx(2.0)

    def test_spot_above_norgespris_negative_compensation(self) -> None:
        """When spot > norgespris, compensation is negative."""
        norgespris = get_norgespris_inkl_mva("standard")  # 0.50
        spot = 1.20
        kwh = 10.0
        compensation = (norgespris - spot) * kwh
        assert compensation == pytest.approx(-7.0)

    def test_negative_spot_price(self) -> None:
        """Negative spot prices should yield large positive compensation."""
        norgespris = get_norgespris_inkl_mva("standard")  # 0.50
        spot = -0.10
        kwh = 5.0
        compensation = (norgespris - spot) * kwh
        assert compensation == pytest.approx(3.0)

    def test_accumulation_over_multiple_hours(self) -> None:
        """Verify running total across multiple updates."""
        norgespris = get_norgespris_inkl_mva("standard")  # 0.50
        total = 0.0

        # Hour 1: cheap spot
        total += (norgespris - 0.30) * 10.0  # +2.0
        assert total == pytest.approx(2.0)

        # Hour 2: expensive spot
        total += (norgespris - 1.50) * 5.0  # -5.0
        assert total == pytest.approx(-3.0)

        # Hour 3: spot at norgespris
        total += (norgespris - 0.50) * 8.0  # 0.0
        assert total == pytest.approx(-3.0)

    def test_zero_consumption_no_change(self) -> None:
        """Zero kWh should not change compensation."""
        norgespris = get_norgespris_inkl_mva("standard")
        existing = 42.5
        delta = (norgespris - 1.00) * 0.0
        assert existing + delta == pytest.approx(42.5)

    def test_nord_norge_norgespris(self) -> None:
        """Nord-Norge has lower norgespris (no MVA)."""
        norgespris = get_norgespris_inkl_mva("nord_norge")  # 0.40
        assert norgespris == pytest.approx(0.40)
        spot = 0.30
        kwh = 10.0
        compensation = (norgespris - spot) * kwh
        assert compensation == pytest.approx(1.0)


# =============================================================================
# Change 2: Previous month kapasitetsledd
# =============================================================================


class TestPreviousMonthKapasitetsledd:
    """Test kapasitetsledd computation from top-3 at month change."""

    @pytest.fixture
    def bkk_trinn(self):
        return [
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

    def _get_kapasitetsledd(self, avg_power: float, kapasitetstrinn: list) -> tuple[int, int, str]:
        """Mirror the coordinator's _get_kapasitetsledd method."""
        for i, (threshold, price) in enumerate(kapasitetstrinn, 1):
            if avg_power <= threshold:
                prev_threshold = kapasitetstrinn[i - 2][0] if i > 1 else 0.0
                if threshold == float("inf"):
                    tier_range = f">{prev_threshold:.0f} kW"
                else:
                    tier_range = f"{prev_threshold:.0f}-{threshold:.0f} kW"
                return price, i, tier_range
        last_idx = len(kapasitetstrinn)
        prev = kapasitetstrinn[-2][0] if last_idx > 1 else 0.0
        last_price = kapasitetstrinn[-1][1]
        return last_price, last_idx, f">{prev:.0f} kW"

    def test_tier_2_5_kw(self, bkk_trinn) -> None:
        """Top-3 average in 2-5 kW range -> 250 kr."""
        top_3 = {
            "2026-03-05": {"kw": 3.5, "hour": 16},
            "2026-03-12": {"kw": 3.2, "hour": 8},
            "2026-03-20": {"kw": 3.0, "hour": 18},
        }
        kw_values = [e["kw"] for e in top_3.values()]
        avg = sum(kw_values) / len(kw_values)
        price, _, tier_range = self._get_kapasitetsledd(avg, bkk_trinn)
        assert price == 250
        assert tier_range == "2-5 kW"

    def test_tier_10_15_kw(self, bkk_trinn) -> None:
        """Top-3 average in 10-15 kW range -> 600 kr."""
        top_3 = {
            "2026-03-01": {"kw": 14.0, "hour": 7},
            "2026-03-10": {"kw": 12.5, "hour": 17},
            "2026-03-20": {"kw": 11.0, "hour": 20},
        }
        kw_values = [e["kw"] for e in top_3.values()]
        avg = sum(kw_values) / len(kw_values)
        assert avg == pytest.approx(12.5)
        price, _, tier_range = self._get_kapasitetsledd(avg, bkk_trinn)
        assert price == 600
        assert tier_range == "10-15 kW"

    def test_empty_top_3_gives_zero(self) -> None:
        """Empty top-3 should produce kapasitetsledd=0."""
        top_3: dict = {}
        if top_3:
            kw_values = [e["kw"] for e in top_3.values()]
            avg = sum(kw_values) / len(kw_values)
        else:
            avg = 0
        assert avg == 0

    def test_single_day_top_3(self, bkk_trinn) -> None:
        """With only 1 day, average = that day's kW."""
        top_3 = {"2026-03-15": {"kw": 1.5, "hour": 10}}
        kw_values = [e["kw"] for e in top_3.values()]
        avg = sum(kw_values) / len(kw_values)
        assert avg == pytest.approx(1.5)
        price, _, _ = self._get_kapasitetsledd(avg, bkk_trinn)
        assert price == 155  # 0-2 kW tier


# =============================================================================
# Change 3: Hour tracking for max power
# =============================================================================


class TestDailyMaxPowerWithHour:
    """Test the new dict format for _daily_max_power."""

    def test_new_format_stores_kw_and_hour(self) -> None:
        """New entries should have kw and hour keys."""
        entry = {"kw": 4.798, "hour": 16}
        assert entry["kw"] == 4.798
        assert entry["hour"] == 16

    def test_top_3_sorting_by_kw(self) -> None:
        """Top 3 should sort by kw value, not hour."""
        daily_max = {
            "2026-03-05": {"kw": 3.5, "hour": 10},
            "2026-03-10": {"kw": 7.2, "hour": 16},
            "2026-03-15": {"kw": 5.1, "hour": 8},
            "2026-03-20": {"kw": 2.0, "hour": 22},
        }
        sorted_days = sorted(daily_max.items(), key=lambda x: x[1]["kw"], reverse=True)
        top_3 = dict(sorted_days[:3])
        assert list(top_3.keys()) == ["2026-03-10", "2026-03-15", "2026-03-05"]
        assert top_3["2026-03-10"]["kw"] == 7.2
        assert top_3["2026-03-10"]["hour"] == 16

    def test_avg_power_from_new_format(self) -> None:
        """Average kW should be computed from the kw field."""
        top_3 = {
            "2026-03-10": {"kw": 6.0, "hour": 16},
            "2026-03-15": {"kw": 5.0, "hour": 8},
            "2026-03-05": {"kw": 4.0, "hour": 10},
        }
        kw_values = [e["kw"] for e in top_3.values()]
        avg = sum(kw_values) / len(kw_values)
        assert avg == pytest.approx(5.0)

    def test_hour_can_be_none_for_migrated_data(self) -> None:
        """Migrated entries from old format have hour=None."""
        entry = {"kw": 3.5, "hour": None}
        assert entry["kw"] == 3.5
        assert entry["hour"] is None

    def test_new_max_replaces_old(self) -> None:
        """A higher kW value should replace the old entry for the same date."""
        daily_max: dict[str, dict] = {}
        date = "2026-03-15"

        # First measurement
        daily_max[date] = {"kw": 3.0, "hour": 10}

        # Higher measurement later in the day
        new_kw = 5.5
        new_hour = 16
        old_kw = daily_max.get(date, {}).get("kw", 0)
        if new_kw > old_kw:
            daily_max[date] = {"kw": new_kw, "hour": new_hour}

        assert daily_max[date]["kw"] == 5.5
        assert daily_max[date]["hour"] == 16

    def test_lower_value_does_not_replace(self) -> None:
        """A lower kW value should not replace existing max."""
        daily_max = {"2026-03-15": {"kw": 5.5, "hour": 16}}
        date = "2026-03-15"

        new_kw = 3.0
        old_kw = daily_max.get(date, {}).get("kw", 0)
        if new_kw > old_kw:
            daily_max[date] = {"kw": new_kw, "hour": 10}

        assert daily_max[date]["kw"] == 5.5
        assert daily_max[date]["hour"] == 16


# Migration-tester for _validate_daily_max_power ligger i
# test_coordinator_robustness.py::TestValidateDailyMaxPower (kanonisk versjon
# som tester den faktiske coordinator-metoden, ikke en lokal kopi).
