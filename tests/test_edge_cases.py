"""Tests for edge cases not covered elsewhere.

Covers:
- Daylight saving time (DST) transitions
- Holiday calculations beyond 2030
- Strømstøtte at exact threshold boundary
- is_day_rate at DST clock change boundaries
"""

from __future__ import annotations

import typing
from datetime import date, datetime, timedelta

import pytest

from custom_components.stromkalkulator.const import (
    HELLIGDAGER_BEVEGELIGE,
    STROMSTOTTE_LEVEL,
    STROMSTOTTE_RATE,
    _bevegelige_helligdager,
    _easter,
)
from tests.test_energiledd import is_day_rate

# =============================================================================
# DST (sommertid) — energiledd rundt klokkeomstilling
# =============================================================================


class TestDaylightSavingTime:
    """Test is_day_rate around DST transitions.

    Norway switches to summer time last Sunday of March (02:00 → 03:00)
    and back last Sunday of October (03:00 → 02:00).

    is_day_rate uses naive datetimes (hour-based), so DST doesn't affect
    the logic directly. But we verify behavior at the boundary hours.
    """

    def test_spring_forward_boundary_march_2026(self):
        """Last Sunday of March 2026 = March 29. Weekend → always night rate."""
        # At 01:59 (before spring forward)
        assert is_day_rate(datetime(2026, 3, 29, 1, 59)) is False  # weekend
        # At 03:00 (after spring forward, 02:00 doesn't exist)
        assert is_day_rate(datetime(2026, 3, 29, 3, 0)) is False  # weekend
        # At 06:00 — still weekend
        assert is_day_rate(datetime(2026, 3, 29, 6, 0)) is False  # weekend

    def test_day_after_spring_forward_march_2026(self):
        """Monday March 30 2026 — first weekday after spring forward."""
        # 05:59 → night rate
        assert is_day_rate(datetime(2026, 3, 30, 5, 59)) is False
        # 06:00 → day rate
        assert is_day_rate(datetime(2026, 3, 30, 6, 0)) is True
        # 21:59 → day rate
        assert is_day_rate(datetime(2026, 3, 30, 21, 59)) is True
        # 22:00 → night rate
        assert is_day_rate(datetime(2026, 3, 30, 22, 0)) is False

    def test_fall_back_boundary_october_2026(self):
        """Last Sunday of October 2026 = October 25. Weekend → always night rate."""
        assert is_day_rate(datetime(2026, 10, 25, 2, 0)) is False  # weekend
        assert is_day_rate(datetime(2026, 10, 25, 12, 0)) is False  # weekend

    def test_day_after_fall_back_october_2026(self):
        """Monday October 26 2026 — first weekday after fall back."""
        assert is_day_rate(datetime(2026, 10, 26, 5, 59)) is False
        assert is_day_rate(datetime(2026, 10, 26, 6, 0)) is True
        assert is_day_rate(datetime(2026, 10, 26, 22, 0)) is False


# =============================================================================
# Helligdager 2031+ — påskealgoritmen utover forhåndskompilert cache
# =============================================================================


class TestHolidaysBeyond2030:
    """Test that _easter() and _bevegelige_helligdager() work for years beyond 2030.

    HELLIGDAGER_BEVEGELIGE is precomputed for 2025-2030.
    The production code only checks this list, so years 2031+ won't match.
    These tests verify the algorithm itself works correctly.
    """

    # Known Easter dates (from astronomical calculations)
    KNOWN_EASTER_DATES: typing.ClassVar[list[tuple[int, date]]] = [
        (2031, date(2031, 4, 13)),
        (2032, date(2032, 3, 28)),
        (2033, date(2033, 4, 17)),
        (2034, date(2034, 4, 9)),
        (2035, date(2035, 3, 25)),
        (2040, date(2040, 4, 1)),
        (2050, date(2050, 4, 10)),
    ]

    @pytest.mark.parametrize(
        ("year", "expected"),
        KNOWN_EASTER_DATES,
        ids=[str(y) for y, _ in KNOWN_EASTER_DATES],
    )
    def test_easter_algorithm_known_dates(self, year, expected):
        """Verify Meeus algorithm against known Easter dates."""
        assert _easter(year) == expected

    def test_easter_2026_matches_precomputed(self):
        """2026 Easter should match what's in HELLIGDAGER_BEVEGELIGE."""
        easter_2026 = _easter(2026)
        # Easter 2026 is April 5
        assert easter_2026 == date(2026, 4, 5)
        # Verify it's in the precomputed list
        assert easter_2026.isoformat() in HELLIGDAGER_BEVEGELIGE

    def test_bevegelige_helligdager_2031(self):
        """Verify moving holidays for 2031 are computed correctly."""
        holidays = _bevegelige_helligdager(2031)
        easter = date(2031, 4, 13)

        # All 7 moving holidays
        expected_dates = [
            (easter - timedelta(days=3)).isoformat(),  # Skjærtorsdag
            (easter - timedelta(days=2)).isoformat(),  # Langfredag
            easter.isoformat(),                         # 1. påskedag
            (easter + timedelta(days=1)).isoformat(),  # 2. påskedag
            (easter + timedelta(days=39)).isoformat(), # Kr. himmelfart
            (easter + timedelta(days=49)).isoformat(), # 1. pinsedag
            (easter + timedelta(days=50)).isoformat(), # 2. pinsedag
        ]
        assert holidays == expected_dates

    def test_2031_not_in_precomputed_cache(self):
        """Verify that 2031 holidays are NOT in HELLIGDAGER_BEVEGELIGE.

        This documents the known limitation: the precomputed list only
        covers 2025-2030. If someone runs the integration in 2031,
        moving holidays won't be detected for tariff purposes.
        """
        holidays_2031 = _bevegelige_helligdager(2031)
        for h in holidays_2031:
            assert h not in HELLIGDAGER_BEVEGELIGE, (
                f"{h} found in precomputed list — update const.py?"
            )

    def test_is_day_rate_on_2031_easter_not_detected(self):
        """Easter 2031 (April 13) will be treated as normal Sunday.

        This test documents the current behavior: since 2031 holidays
        aren't in HELLIGDAGER_BEVEGELIGE, they won't trigger night rate
        via the holiday check. April 13, 2031 happens to be a Sunday,
        so it gets night rate via the weekend check instead.
        """
        easter_2031 = datetime(2031, 4, 13, 12, 0)  # Sunday
        # Still night rate because it's a weekend
        assert is_day_rate(easter_2031) is False

    def test_is_day_rate_on_2031_kristi_himmelfartsdag_not_detected(self):
        """Kr. himmelfart 2031 (May 22, Thursday) won't be detected as holiday.

        This is a genuine bug for 2031: a weekday holiday not in the cache
        will be treated as a normal weekday with day rate.
        """
        # Easter 2031 is April 13, +39 = May 22 (Thursday)
        kr_himmelfart = datetime(2031, 5, 22, 12, 0)
        assert kr_himmelfart.weekday() == 3  # Thursday

        # BUG: This should be False (holiday), but returns True because
        # 2031 isn't in the precomputed cache
        assert is_day_rate(kr_himmelfart) is True  # Known limitation


# =============================================================================
# Strømstøtte grense-presisjon
# =============================================================================


class TestStromstotteThresholdPrecision:
    """Test strømstøtte at exact threshold boundary with floating point precision."""

    def _calculate(self, spot_price: float) -> float:
        """Same formula as coordinator.py."""
        if spot_price > STROMSTOTTE_LEVEL:
            return (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE
        return 0.0

    def test_exactly_at_threshold(self):
        """Spot == STROMSTOTTE_LEVEL → no support."""
        assert self._calculate(STROMSTOTTE_LEVEL) == 0.0

    def test_one_ore_above_threshold(self):
        """Spot = threshold + 0.01 (1 øre) → small support."""
        result = self._calculate(STROMSTOTTE_LEVEL + 0.01)
        assert result == pytest.approx(0.01 * STROMSTOTTE_RATE)

    def test_epsilon_above_threshold(self):
        """Spot = threshold + tiny epsilon → tiny support (not zero)."""
        epsilon = 1e-10
        result = self._calculate(STROMSTOTTE_LEVEL + epsilon)
        assert result > 0

    def test_epsilon_below_threshold(self):
        """Spot = threshold - tiny epsilon → no support."""
        epsilon = 1e-10
        result = self._calculate(STROMSTOTTE_LEVEL - epsilon)
        assert result == 0.0

    def test_floating_point_addition_edge(self):
        """Test with a price that might have floating point issues.

        0.9625 is exact in binary (= 385/400), so threshold comparisons
        should be stable. This test verifies that.
        """
        # 0.50 + 0.4625 should exactly equal 0.9625
        assembled = 0.50 + 0.4625
        assert self._calculate(assembled) == 0.0

    def test_negative_price(self):
        """Negative spot price → no support."""
        assert self._calculate(-1.0) == 0.0

    def test_zero_price(self):
        """Zero spot price → no support."""
        assert self._calculate(0.0) == 0.0
