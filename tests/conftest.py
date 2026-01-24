"""Pytest configuration and fixtures for Strømkalkulator tests."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Add custom_components to path so we can import without Home Assistant
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

# Mock Home Assistant modules before importing our code
sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.const"] = MagicMock()
sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.config_entries"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.storage"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()


@pytest.fixture
def bkk_kapasitetstrinn():
    """BKK kapasitetstrinn 2026."""
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


@pytest.fixture
def sample_spot_prices():
    """Sample spot prices for testing.
    
    Terskel 2025: 75 øre eks. mva × 1.25 = 93.75 øre inkl. mva = 0.9375 NOK/kWh
    """
    from custom_components.stromkalkulator.const import STROMSTOTTE_LEVEL
    return {
        "low": 0.50,      # Under terskel
        "threshold": STROMSTOTTE_LEVEL,  # Akkurat på terskel
        "medium": 1.20,   # Over terskel
        "high": 2.00,     # Høy pris
        "extreme": 5.00,  # Ekstrem pris
    }
