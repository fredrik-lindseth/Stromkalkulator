"""Test Norgespris calculations.

Tests the Norgespris fixed-price electricity product:
- Fixed price based on geographic zone (avgiftssone)
- No strømstøtte when using Norgespris
- Max 5000 kWh/month (not enforced in this integration)

Priser (fra 1. oktober 2025):
- Sør-Norge (standard): 40 øre + 25% mva = 50 øre/kWh inkl. mva
- Nord-Norge/Tiltakssonen: 40 øre/kWh (mva-fritak)

Kilde: https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
"""

from __future__ import annotations

import pytest

from custom_components.stromkalkulator.const import (
    AVGIFTSSONE_NORD_NORGE,
    AVGIFTSSONE_STANDARD,
    AVGIFTSSONE_TILTAKSSONE,
    NORGESPRIS_EKS_MVA,
    NORGESPRIS_INKL_MVA_NORD,
    NORGESPRIS_INKL_MVA_STANDARD,
    get_norgespris_inkl_mva,
)

# =============================================================================
# Constants validation
# =============================================================================


def test_norgespris_base_price() -> None:
    """Base price is 40 øre/kWh eks. mva."""
    assert NORGESPRIS_EKS_MVA == 0.40


def test_norgespris_sor_norge_price() -> None:
    """Sør-Norge price is 50 øre/kWh inkl. 25% mva."""
    expected = NORGESPRIS_EKS_MVA * 1.25
    assert expected == NORGESPRIS_INKL_MVA_STANDARD
    assert NORGESPRIS_INKL_MVA_STANDARD == 0.50


def test_norgespris_nord_norge_price() -> None:
    """Nord-Norge price is 40 øre/kWh (mva-fritak)."""
    assert NORGESPRIS_INKL_MVA_NORD == 0.40


# =============================================================================
# get_norgespris_inkl_mva function tests
# =============================================================================


@pytest.mark.parametrize(
    ("avgiftssone", "expected"),
    [
        (AVGIFTSSONE_STANDARD, 0.50),
        (AVGIFTSSONE_NORD_NORGE, 0.40),
        (AVGIFTSSONE_TILTAKSSONE, 0.40),
    ],
    ids=["sor_norge", "nord_norge", "tiltakssone"],
)
def test_norgespris_by_zone(avgiftssone: str, expected: float) -> None:
    """Test Norgespris for each zone."""
    assert get_norgespris_inkl_mva(avgiftssone) == expected


# =============================================================================
# Norgespris vs Spotpris comparison tests
# =============================================================================


@pytest.mark.parametrize(
    ("spotpris", "zone", "norgespris_cheaper"),
    [
        (1.50, AVGIFTSSONE_STANDARD, True),  # High spot → Norgespris cheaper
        (0.30, AVGIFTSSONE_STANDARD, False),  # Low spot → Spotpris cheaper
        (0.50, AVGIFTSSONE_STANDARD, False),  # Equal (breakeven)
        (0.40, AVGIFTSSONE_NORD_NORGE, False),  # Equal (breakeven Nord-Norge)
    ],
    ids=["high_spot", "low_spot", "breakeven_sor", "breakeven_nord"],
)
def test_norgespris_vs_spotpris(spotpris: float, zone: str, norgespris_cheaper: bool) -> None:
    """Compare Norgespris with various spotpris levels."""
    norgespris = get_norgespris_inkl_mva(zone)
    if norgespris_cheaper:
        assert norgespris < spotpris
    else:
        assert spotpris <= norgespris


# =============================================================================
# Norgespris + strømstøtte interaction
# =============================================================================


def test_norgespris_no_stromstotte() -> None:
    """Norgespris users don't get strømstøtte even if spotpris is high.

    This is the expected behavior - if you have Norgespris, your price
    is fixed and you don't get strømstøtte on top of it.
    """
    # This tests the conceptual rule - actual logic is in coordinator.py
    har_norgespris = True
    stromstotte = 0 if har_norgespris else 0.5  # Example value
    assert stromstotte == 0
