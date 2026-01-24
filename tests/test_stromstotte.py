"""Test strømstøtte calculations.

Tests the electricity subsidy (strømstøtte) calculation:
- 90% coverage of spot price above threshold (inkl. mva)

Historikk terskelverdi (eks. mva → inkl. 25% mva):
- 2024: 73 øre → 91,25 øre inkl. mva
- 2025: 75 øre → 93,75 øre inkl. mva
- 2026+: Ikke fastsatt, antar samme som 2025

Kilde: https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
"""

from __future__ import annotations

import pytest

# Import from const.py to ensure consistency
from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL, STROMSTOTTE_RATE


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


class TestStromstotteCalculation:
    """Test strømstøtte calculation logic."""

    def test_price_below_threshold_returns_zero(self):
        """When spot price is below threshold, strømstøtte should be 0."""
        assert calculate_stromstotte(0.50) == 0.0
        assert calculate_stromstotte(0.70) == 0.0
        assert calculate_stromstotte(0.90) == 0.0

    def test_price_at_threshold_returns_zero(self):
        """When spot price equals threshold, strømstøtte should be 0."""
        assert calculate_stromstotte(STROMSTOTTE_LEVEL) == 0.0

    def test_price_just_above_threshold(self):
        """When spot price is just above threshold."""
        result = calculate_stromstotte(1.00)
        expected = round((1.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_price_medium_above_threshold(self):
        """Test with medium price above threshold."""
        result = calculate_stromstotte(1.20)
        expected = round((1.20 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_price_high_above_threshold(self):
        """Test with high price above threshold."""
        result = calculate_stromstotte(1.50)
        expected = round((1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_price_very_high(self):
        """Test with very high price."""
        result = calculate_stromstotte(2.00)
        expected = round((2.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_price_extreme(self):
        """Test with extreme price."""
        result = calculate_stromstotte(5.00)
        expected = round((5.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_negative_price_returns_zero(self):
        """Negative spot price should return 0 strømstøtte."""
        assert calculate_stromstotte(-0.10) == 0.0
        assert calculate_stromstotte(-1.00) == 0.0

    def test_zero_price_returns_zero(self):
        """Zero spot price should return 0 strømstøtte."""
        assert calculate_stromstotte(0.0) == 0.0


class TestSpotprisEtterStotte:
    """Test spotpris after strømstøtte deduction."""

    def test_spotpris_etter_stotte_low_price(self):
        """Low price remains unchanged."""
        spot_price = 0.50
        stromstotte = calculate_stromstotte(spot_price)
        result = spot_price - stromstotte
        assert result == 0.50

    def test_spotpris_etter_stotte_high_price(self):
        """High price is reduced by strømstøtte."""
        spot_price = 2.00
        stromstotte = calculate_stromstotte(spot_price)
        result = round(spot_price - stromstotte, 4)
        expected = round(spot_price - (spot_price - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_spotpris_etter_stotte_never_below_threshold(self):
        """Spotpris etter støtte should approach but never go below minimum for high prices."""
        # For very high prices, spotpris etter støtte approaches:
        # spotpris - (spotpris - terskel) * 0.9 = spotpris * 0.1 + terskel * 0.9
        for price in [1.5, 2.0, 3.0, 5.0, 10.0]:
            stromstotte = calculate_stromstotte(price)
            etter_stotte = price - stromstotte
            # Should always be positive
            assert etter_stotte > 0


class TestStromstotteDocumentationExamples:
    """Test examples with current threshold value."""

    def test_example_spotpris_below_threshold(self):
        """Price below threshold → 0 NOK strømstøtte."""
        assert calculate_stromstotte(0.50) == 0.0
        assert calculate_stromstotte(0.90) == 0.0

    def test_example_spotpris_at_threshold(self):
        """Price at threshold → 0 NOK strømstøtte."""
        assert calculate_stromstotte(STROMSTOTTE_LEVEL) == 0.0

    def test_example_spotpris_100(self):
        """1.00 NOK/kWh → small strømstøtte."""
        result = calculate_stromstotte(1.00)
        expected = round((1.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected
        assert result > 0  # Should be positive since 1.00 > threshold

    def test_example_spotpris_150(self):
        """1.50 NOK/kWh → medium strømstøtte."""
        result = calculate_stromstotte(1.50)
        expected = round((1.50 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected

    def test_example_spotpris_200(self):
        """2.00 NOK/kWh → high strømstøtte."""
        result = calculate_stromstotte(2.00)
        expected = round((2.00 - STROMSTOTTE_LEVEL) * STROMSTOTTE_RATE, 4)
        assert result == expected


class TestStromstotteThresholdValues:
    """Test that threshold values are correct."""

    def test_threshold_is_2025_value(self):
        """Verify threshold is set to 2025 value (75 øre eks. mva × 1.25)."""
        # 75 øre/kWh eks. mva × 1.25 = 93.75 øre/kWh inkl. mva = 0.9375 NOK/kWh
        assert STROMSTOTTE_LEVEL == 0.9375

    def test_rate_is_90_percent(self):
        """Verify rate is 90%."""
        assert STROMSTOTTE_RATE == 0.9
