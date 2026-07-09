"""Tests for edge cases not covered elsewhere.

Covers:
- Holiday calculations beyond 2030

DST-overganger (is_day_rate rundt klokkeomstilling) dekkes av
tests/test_dst_overgang.py mot den ekte coordinator._is_day_rate.
"""

from __future__ import annotations

import typing
from datetime import date, timedelta

import pytest

from custom_components.stromkalkulator.const import (
    HELLIGDAGER_BEVEGELIGE,
    _bevegelige_helligdager,
    _easter,
)

# =============================================================================
# Helligdager 2031+, påskealgoritmen utover forhåndskompilert cache
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
                f"{h} found in precomputed list, update const.py?"
            )
