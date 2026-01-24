"""Test offentlige avgifter (public fees) calculations.

Tests:
- Forbruksavgift (consumption tax)
- Enova-avgift
- MVA calculations
- Avgiftssoner (tax zones)
"""

from __future__ import annotations

# Constants (same as in const.py)
FORBRUKSAVGIFT_ALMINNELIG = 0.0713  # 7.13 øre/kWh eks. mva
FORBRUKSAVGIFT_REDUSERT = 0.0060   # 0.60 øre/kWh eks. mva
ENOVA_AVGIFT = 0.01                 # 1.0 øre/kWh eks. mva
MVA_SATS = 0.25                     # 25%

# Avgiftssoner
AVGIFTSSONE_STANDARD = "standard"
AVGIFTSSONE_NORD_NORGE = "nord_norge"
AVGIFTSSONE_TILTAKSSONE = "tiltakssone"


def get_forbruksavgift(avgiftssone: str, month: int = 1) -> float:
    """Get forbruksavgift based on avgiftssone.

    Fra 2026 er det flat sats hele året (ingen sesongvariasjon).

    Args:
        avgiftssone: 'standard', 'nord_norge', or 'tiltakssone'
        month: Month number (not used from 2026)

    Returns:
        Forbruksavgift in NOK/kWh (eks. mva)
    """
    if avgiftssone == AVGIFTSSONE_TILTAKSSONE:
        return 0.0
    return FORBRUKSAVGIFT_ALMINNELIG


def get_mva_sats(avgiftssone: str) -> float:
    """Get MVA rate based on avgiftssone.

    Args:
        avgiftssone: 'standard', 'nord_norge', or 'tiltakssone'

    Returns:
        MVA rate (0.0 or 0.25)
    """
    if avgiftssone in (AVGIFTSSONE_NORD_NORGE, AVGIFTSSONE_TILTAKSSONE):
        return 0.0
    return MVA_SATS


def calculate_offentlige_avgifter(avgiftssone: str) -> dict:
    """Calculate all public fees.

    Args:
        avgiftssone: Tax zone

    Returns:
        Dict with all fee components
    """
    mva_sats = get_mva_sats(avgiftssone)
    forbruksavgift_eks = get_forbruksavgift(avgiftssone)
    forbruksavgift_inkl = forbruksavgift_eks * (1 + mva_sats)
    enova_avgift_inkl = ENOVA_AVGIFT * (1 + mva_sats)
    total_eks = forbruksavgift_eks + ENOVA_AVGIFT
    total_inkl = forbruksavgift_inkl + enova_avgift_inkl

    return {
        "forbruksavgift_eks_mva": round(forbruksavgift_eks, 4),
        "forbruksavgift_inkl_mva": round(forbruksavgift_inkl, 4),
        "enova_avgift_eks_mva": round(ENOVA_AVGIFT, 4),
        "enova_avgift_inkl_mva": round(enova_avgift_inkl, 4),
        "total_eks_mva": round(total_eks, 4),
        "total_inkl_mva": round(total_inkl, 4),
        "mva_sats": mva_sats,
    }


class TestForbruksavgift:
    """Test forbruksavgift calculation."""

    def test_standard_zone(self):
        """Standard zone: 7.13 øre/kWh."""
        result = get_forbruksavgift(AVGIFTSSONE_STANDARD)
        assert result == 0.0713

    def test_nord_norge_zone(self):
        """Nord-Norge: Same as standard from 2026."""
        result = get_forbruksavgift(AVGIFTSSONE_NORD_NORGE)
        assert result == 0.0713

    def test_tiltakssone_exempt(self):
        """Tiltakssone: Exempt (0 øre/kWh)."""
        result = get_forbruksavgift(AVGIFTSSONE_TILTAKSSONE)
        assert result == 0.0

    def test_no_seasonal_variation_2026(self):
        """From 2026, no seasonal variation."""
        # All months should return same value
        for month in range(1, 13):
            result = get_forbruksavgift(AVGIFTSSONE_STANDARD, month)
            assert result == 0.0713


class TestEnovaAvgift:
    """Test Enova-avgift."""

    def test_enova_avgift_constant(self):
        """Enova-avgift is 1.0 øre/kWh for all zones."""
        assert ENOVA_AVGIFT == 0.01

    def test_enova_applies_to_all_zones(self):
        """Enova applies to all zones including tiltakssone."""
        for zone in [AVGIFTSSONE_STANDARD, AVGIFTSSONE_NORD_NORGE, AVGIFTSSONE_TILTAKSSONE]:
            result = calculate_offentlige_avgifter(zone)
            assert result["enova_avgift_eks_mva"] == 0.01


class TestMvaSats:
    """Test MVA rate by zone."""

    def test_standard_zone_25_percent(self):
        """Standard zone: 25% MVA."""
        assert get_mva_sats(AVGIFTSSONE_STANDARD) == 0.25

    def test_nord_norge_exempt(self):
        """Nord-Norge: MVA exempt."""
        assert get_mva_sats(AVGIFTSSONE_NORD_NORGE) == 0.0

    def test_tiltakssone_exempt(self):
        """Tiltakssone: MVA exempt."""
        assert get_mva_sats(AVGIFTSSONE_TILTAKSSONE) == 0.0


class TestOffentligeAvgifterTotal:
    """Test total offentlige avgifter calculation."""

    def test_standard_zone_total(self):
        """Standard zone total fees."""
        result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

        # Forbruksavgift: 7.13 øre eks → 8.9125 øre inkl
        assert result["forbruksavgift_eks_mva"] == 0.0713
        assert abs(result["forbruksavgift_inkl_mva"] - 0.0891) < 0.001

        # Enova: 1.0 øre eks → 1.25 øre inkl
        assert result["enova_avgift_eks_mva"] == 0.01
        assert result["enova_avgift_inkl_mva"] == 0.0125

        # Total: 8.13 øre eks → ~10.16 øre inkl
        assert result["total_eks_mva"] == 0.0813
        assert abs(result["total_inkl_mva"] - 0.1016) < 0.001

    def test_nord_norge_zone_total(self):
        """Nord-Norge zone (no MVA)."""
        result = calculate_offentlige_avgifter(AVGIFTSSONE_NORD_NORGE)

        # Same fees as standard but no MVA
        assert result["forbruksavgift_eks_mva"] == 0.0713
        assert result["forbruksavgift_inkl_mva"] == 0.0713  # No MVA

        assert result["enova_avgift_eks_mva"] == 0.01
        assert result["enova_avgift_inkl_mva"] == 0.01  # No MVA

        assert result["total_eks_mva"] == 0.0813
        assert result["total_inkl_mva"] == 0.0813  # No MVA

    def test_tiltakssone_total(self):
        """Tiltakssone (forbruksavgift exempt, no MVA)."""
        result = calculate_offentlige_avgifter(AVGIFTSSONE_TILTAKSSONE)

        # No forbruksavgift
        assert result["forbruksavgift_eks_mva"] == 0.0
        assert result["forbruksavgift_inkl_mva"] == 0.0

        # Enova still applies (no MVA)
        assert result["enova_avgift_eks_mva"] == 0.01
        assert result["enova_avgift_inkl_mva"] == 0.01

        # Total is just Enova
        assert result["total_eks_mva"] == 0.01
        assert result["total_inkl_mva"] == 0.01


class TestDocumentationExamples:
    """Test examples from beregninger.md."""

    def test_2026_satser(self):
        """Test 2026 rates from documentation."""
        result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

        # From docs: Forbruksavgift 7,13 øre/kWh eks. mva
        assert result["forbruksavgift_eks_mva"] == 0.0713

        # From docs: Enova-avgift 1,0 øre/kWh eks. mva
        assert result["enova_avgift_eks_mva"] == 0.01

        # From docs: Sum eks. mva: 8,13 øre/kWh
        assert result["total_eks_mva"] == 0.0813

        # From docs: Sum inkl. mva: ~10,16 øre/kWh
        assert abs(result["total_inkl_mva"] - 0.1016) < 0.001


class TestOreToNokConversion:
    """Test øre to NOK conversion consistency."""

    def test_forbruksavgift_ore_to_nok(self):
        """7.13 øre = 0.0713 NOK."""
        ore_value = 7.13
        nok_value = ore_value / 100
        assert nok_value == 0.0713
        assert nok_value == FORBRUKSAVGIFT_ALMINNELIG

    def test_enova_ore_to_nok(self):
        """1.0 øre = 0.01 NOK."""
        ore_value = 1.0
        nok_value = ore_value / 100
        assert nok_value == 0.01
        assert nok_value == ENOVA_AVGIFT

    def test_display_in_ore(self):
        """Values should be easy to convert back to øre for display."""
        result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

        # Convert back to øre
        forbruksavgift_ore = result["forbruksavgift_eks_mva"] * 100
        enova_ore = result["enova_avgift_eks_mva"] * 100

        assert abs(forbruksavgift_ore - 7.13) < 0.01
        assert abs(enova_ore - 1.0) < 0.01
