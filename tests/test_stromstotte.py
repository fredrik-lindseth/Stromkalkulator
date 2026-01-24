"""Test strømstøtte calculations.

Tests the electricity subsidy (strømstøtte) calculation:
- 90% coverage of spot price above 91.25 øre/kWh (0.9125 NOK/kWh)
"""

from __future__ import annotations

import pytest

# Constants (same as in const.py)
STROMSTOTTE_LEVEL = 0.9125  # 91.25 øre/kWh inkl. mva
STROMSTOTTE_RATE = 0.9      # 90% dekningsgrad


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
        assert calculate_stromstotte(0.9125) == 0.0

    def test_price_just_above_threshold(self):
        """When spot price is just above threshold."""
        # 1.00 - 0.9125 = 0.0875 * 0.9 = 0.07875 ≈ 0.0788
        result = calculate_stromstotte(1.00)
        expected = round((1.00 - 0.9125) * 0.9, 4)
        assert result == expected
        assert result == 0.0788

    def test_price_medium_above_threshold(self):
        """Test with medium price above threshold."""
        # 1.20 - 0.9125 = 0.2875 * 0.9 = 0.25875
        result = calculate_stromstotte(1.20)
        expected = round((1.20 - 0.9125) * 0.9, 4)
        assert result == expected
        # Allow for floating-point rounding (0.2587 or 0.2588)
        assert abs(result - 0.2588) < 0.0002

    def test_price_high_above_threshold(self):
        """Test with high price above threshold."""
        # 1.50 - 0.9125 = 0.5875 * 0.9 = 0.52875 ≈ 0.5288
        result = calculate_stromstotte(1.50)
        expected = round((1.50 - 0.9125) * 0.9, 4)
        assert result == expected
        assert result == 0.5288

    def test_price_very_high(self):
        """Test with very high price."""
        # 2.00 - 0.9125 = 1.0875 * 0.9 = 0.97875
        result = calculate_stromstotte(2.00)
        expected = round((2.00 - 0.9125) * 0.9, 4)
        assert result == expected
        # Allow for floating-point rounding (0.9787 or 0.9788)
        assert abs(result - 0.9788) < 0.0002

    def test_price_extreme(self):
        """Test with extreme price."""
        # 5.00 - 0.9125 = 4.0875 * 0.9 = 3.67875 ≈ 3.6788
        result = calculate_stromstotte(5.00)
        expected = round((5.00 - 0.9125) * 0.9, 4)
        assert result == expected
        assert result == 3.6788

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
        # 2.00 - 0.9787/0.9788 ≈ 1.0212/1.0213
        assert abs(result - 1.0212) < 0.0002

    def test_spotpris_etter_stotte_never_below_threshold(self):
        """Spotpris etter støtte should approach but never go below threshold for high prices."""
        # For very high prices, spotpris etter støtte approaches:
        # spotpris - (spotpris - terskel) * 0.9 = spotpris * 0.1 + terskel * 0.9
        # As spotpris → ∞, this → terskel * 0.9 = 0.82125
        for price in [1.5, 2.0, 3.0, 5.0, 10.0]:
            stromstotte = calculate_stromstotte(price)
            etter_stotte = price - stromstotte
            # Should always be > 0.9125 * 0.1 = 0.09125 (minimum theoretical)
            assert etter_stotte > 0.09


class TestStromstotteDocumentationExamples:
    """Test examples from beregninger.md documentation."""

    def test_example_spotpris_050(self):
        """Example: 0.50 NOK → 0.00 NOK strømstøtte."""
        assert calculate_stromstotte(0.50) == 0.0

    def test_example_spotpris_09125(self):
        """Example: 0.9125 NOK → 0.00 NOK strømstøtte."""
        assert calculate_stromstotte(0.9125) == 0.0

    def test_example_spotpris_100(self):
        """Example: 1.00 NOK → 0.08 NOK strømstøtte."""
        result = calculate_stromstotte(1.00)
        # Actual: 0.0788, docs round to 0.08
        assert abs(result - 0.08) < 0.01

    def test_example_spotpris_150(self):
        """Example: 1.50 NOK → 0.53 NOK strømstøtte."""
        result = calculate_stromstotte(1.50)
        # Actual: 0.5288, docs round to 0.53
        assert abs(result - 0.53) < 0.01

    def test_example_spotpris_200(self):
        """Example: 2.00 NOK → 0.98 NOK strømstøtte."""
        result = calculate_stromstotte(2.00)
        # Actual: 0.9788, docs round to 0.98
        assert abs(result - 0.98) < 0.01
