"""Test offentlige avgifter (public fees) calculations.

Tests:
- Forbruksavgift (consumption tax)
- Enova-avgift
- MVA calculations
- Avgiftssoner (tax zones)
"""

from __future__ import annotations

import pytest

# Constants (same as in const.py)
FORBRUKSAVGIFT_ALMINNELIG = 0.0713  # 7.13 øre/kWh eks. mva
FORBRUKSAVGIFT_REDUSERT = 0.0060  # 0.60 øre/kWh eks. mva
ENOVA_AVGIFT = 0.01  # 1.0 øre/kWh eks. mva
MVA_SATS = 0.25  # 25%

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


# =============================================================================
# Forbruksavgift tests
# =============================================================================


@pytest.mark.parametrize(
    ("avgiftssone", "expected"),
    [
        (AVGIFTSSONE_STANDARD, 0.0713),
        (AVGIFTSSONE_NORD_NORGE, 0.0713),  # Same as standard from 2026
        (AVGIFTSSONE_TILTAKSSONE, 0.0),  # Exempt
    ],
    ids=["standard", "nord_norge", "tiltakssone"],
)
def test_forbruksavgift_by_zone(avgiftssone: str, expected: float) -> None:
    """Test forbruksavgift for each zone."""
    assert get_forbruksavgift(avgiftssone) == expected


@pytest.mark.parametrize("month", range(1, 13))
def test_forbruksavgift_no_seasonal_variation(month: int) -> None:
    """From 2026, no seasonal variation - all months same value."""
    result = get_forbruksavgift(AVGIFTSSONE_STANDARD, month)
    assert result == 0.0713


# =============================================================================
# Enova-avgift tests
# =============================================================================


def test_enova_avgift_constant() -> None:
    """Enova-avgift is 1.0 øre/kWh for all zones."""
    assert ENOVA_AVGIFT == 0.01


@pytest.mark.parametrize(
    "zone",
    [AVGIFTSSONE_STANDARD, AVGIFTSSONE_NORD_NORGE, AVGIFTSSONE_TILTAKSSONE],
)
def test_enova_applies_to_all_zones(zone: str) -> None:
    """Enova applies to all zones including tiltakssone."""
    result = calculate_offentlige_avgifter(zone)
    assert result["enova_avgift_eks_mva"] == 0.01


# =============================================================================
# MVA tests
# =============================================================================


@pytest.mark.parametrize(
    ("avgiftssone", "expected"),
    [
        (AVGIFTSSONE_STANDARD, 0.25),
        (AVGIFTSSONE_NORD_NORGE, 0.0),
        (AVGIFTSSONE_TILTAKSSONE, 0.0),
    ],
    ids=["standard_25pct", "nord_norge_exempt", "tiltakssone_exempt"],
)
def test_mva_sats_by_zone(avgiftssone: str, expected: float) -> None:
    """Test MVA rate for each zone."""
    assert get_mva_sats(avgiftssone) == expected


# =============================================================================
# Total offentlige avgifter tests
# =============================================================================


def test_standard_zone_total() -> None:
    """Standard zone total fees."""
    result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

    # Forbruksavgift: 7.13 øre eks → 8.9125 øre inkl
    assert result["forbruksavgift_eks_mva"] == 0.0713
    assert result["forbruksavgift_inkl_mva"] == pytest.approx(0.0891, abs=0.001)

    # Enova: 1.0 øre eks → 1.25 øre inkl
    assert result["enova_avgift_eks_mva"] == 0.01
    assert result["enova_avgift_inkl_mva"] == 0.0125

    # Total: 8.13 øre eks → ~10.16 øre inkl
    assert result["total_eks_mva"] == 0.0813
    assert result["total_inkl_mva"] == pytest.approx(0.1016, abs=0.001)


def test_nord_norge_zone_total() -> None:
    """Nord-Norge zone (no MVA)."""
    result = calculate_offentlige_avgifter(AVGIFTSSONE_NORD_NORGE)

    # Same fees as standard but no MVA
    assert result["forbruksavgift_eks_mva"] == 0.0713
    assert result["forbruksavgift_inkl_mva"] == 0.0713  # No MVA

    assert result["enova_avgift_eks_mva"] == 0.01
    assert result["enova_avgift_inkl_mva"] == 0.01  # No MVA

    assert result["total_eks_mva"] == 0.0813
    assert result["total_inkl_mva"] == 0.0813  # No MVA


def test_tiltakssone_total() -> None:
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


# =============================================================================
# Documentation examples
# =============================================================================


def test_2026_satser_from_docs() -> None:
    """Test 2026 rates from documentation."""
    result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

    # From docs: Forbruksavgift 7,13 øre/kWh eks. mva
    assert result["forbruksavgift_eks_mva"] == 0.0713

    # From docs: Enova-avgift 1,0 øre/kWh eks. mva
    assert result["enova_avgift_eks_mva"] == 0.01

    # From docs: Sum eks. mva: 8,13 øre/kWh
    assert result["total_eks_mva"] == 0.0813

    # From docs: Sum inkl. mva: ~10,16 øre/kWh
    assert result["total_inkl_mva"] == pytest.approx(0.1016, abs=0.001)


# =============================================================================
# Øre to NOK conversion
# =============================================================================


@pytest.mark.parametrize(
    ("ore_value", "nok_expected", "constant"),
    [
        (7.13, 0.0713, FORBRUKSAVGIFT_ALMINNELIG),
        (1.0, 0.01, ENOVA_AVGIFT),
    ],
    ids=["forbruksavgift", "enova"],
)
def test_ore_to_nok_conversion(ore_value: float, nok_expected: float, constant: float) -> None:
    """Test øre to NOK conversion."""
    nok_value = ore_value / 100
    assert nok_value == nok_expected
    assert nok_value == constant


def test_display_values_in_ore() -> None:
    """Values should be easy to convert back to øre for display."""
    result = calculate_offentlige_avgifter(AVGIFTSSONE_STANDARD)

    forbruksavgift_ore = result["forbruksavgift_eks_mva"] * 100
    enova_ore = result["enova_avgift_eks_mva"] * 100

    assert forbruksavgift_ore == pytest.approx(7.13, abs=0.01)
    assert enova_ore == pytest.approx(1.0, abs=0.01)
