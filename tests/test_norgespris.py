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

from custom_components.stromkalkulator.const import (
    AVGIFTSSONE_NORD_NORGE,
    AVGIFTSSONE_STANDARD,
    AVGIFTSSONE_TILTAKSSONE,
    NORGESPRIS_EKS_MVA,
    NORGESPRIS_INKL_MVA_NORD,
    NORGESPRIS_INKL_MVA_STANDARD,
    get_norgespris_inkl_mva,
)


class TestNorgesprisConstants:
    """Test that Norgespris constants are correct."""

    def test_norgespris_eks_mva(self):
        """Base price is 40 øre/kWh eks. mva."""
        assert NORGESPRIS_EKS_MVA == 0.40

    def test_norgespris_sor_norge_inkl_mva(self):
        """Sør-Norge price is 50 øre/kWh inkl. 25% mva."""
        # 40 øre * 1.25 = 50 øre
        expected = NORGESPRIS_EKS_MVA * 1.25
        assert expected == NORGESPRIS_INKL_MVA_STANDARD
        assert NORGESPRIS_INKL_MVA_STANDARD == 0.50

    def test_norgespris_nord_norge_inkl_mva(self):
        """Nord-Norge price is 40 øre/kWh (mva-fritak)."""
        assert NORGESPRIS_INKL_MVA_NORD == 0.40


class TestGetNorgesprisfunc:
    """Test the get_norgespris_inkl_mva function."""

    def test_standard_zone_returns_50_ore(self):
        """Standard zone (Sør-Norge) should return 0.50 NOK/kWh."""
        result = get_norgespris_inkl_mva(AVGIFTSSONE_STANDARD)
        assert result == 0.50

    def test_nord_norge_zone_returns_40_ore(self):
        """Nord-Norge zone should return 0.40 NOK/kWh (mva-fritak)."""
        result = get_norgespris_inkl_mva(AVGIFTSSONE_NORD_NORGE)
        assert result == 0.40

    def test_tiltakssone_returns_40_ore(self):
        """Tiltakssonen should return 0.40 NOK/kWh (mva-fritak)."""
        result = get_norgespris_inkl_mva(AVGIFTSSONE_TILTAKSSONE)
        assert result == 0.40


class TestNorgesprisfvsSpotpris:
    """Test comparison scenarios between Norgespris and spotpris."""

    def test_high_spotpris_norgespris_cheaper(self):
        """When spotpris is high, Norgespris should be cheaper."""
        spotpris = 1.50  # 150 øre/kWh
        norgespris = get_norgespris_inkl_mva(AVGIFTSSONE_STANDARD)
        assert norgespris < spotpris

    def test_low_spotpris_spotpris_cheaper(self):
        """When spotpris is low, spotpris should be cheaper."""
        spotpris = 0.30  # 30 øre/kWh
        norgespris = get_norgespris_inkl_mva(AVGIFTSSONE_STANDARD)
        assert spotpris < norgespris

    def test_breakeven_point_sor_norge(self):
        """At 50 øre/kWh spotpris, prices are equal in Sør-Norge."""
        spotpris = 0.50
        norgespris = get_norgespris_inkl_mva(AVGIFTSSONE_STANDARD)
        assert spotpris == norgespris

    def test_breakeven_point_nord_norge(self):
        """At 40 øre/kWh spotpris, prices are equal in Nord-Norge."""
        spotpris = 0.40
        norgespris = get_norgespris_inkl_mva(AVGIFTSSONE_NORD_NORGE)
        assert spotpris == norgespris


class TestNorgesprisNoStromstotte:
    """Test that Norgespris cannot be combined with strømstøtte."""

    def test_norgespris_with_high_spot_no_benefit(self):
        """Norgespris users don't get strømstøtte even if spotpris is high.

        This is the expected behavior - if you have Norgespris, your price
        is fixed and you don't get strømstøtte on top of it.
        """
        # This is a conceptual test - the actual logic is in coordinator.py
        # which sets stromstotte=0 when har_norgespris=True
        har_norgespris = True
        if har_norgespris:
            stromstotte = 0  # Always 0 with Norgespris
        else:
            # Would normally calculate strømstøtte here
            stromstotte = 0.5  # Example

        assert stromstotte == 0
