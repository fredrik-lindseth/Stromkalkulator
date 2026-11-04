"""Kontrakt for merkevarebildene Home Assistant leser fra integrasjonen.

Fra Home Assistant 2026.3 leser Brands-integrasjonen bilder fra
``custom_components/<domain>/brand/`` før den prøver den sentrale CDN-en.
Bildene der må være PNG med dimensjonene Brands API godtar.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

BRAND = Path(__file__).parent.parent / "custom_components" / "stromkalkulator" / "brand"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

FORVENTEDE_BILDER = {
    "icon.png": (256, 256),
    "icon@2x.png": (512, 512),
    "logo.png": (760, 256),
    "logo@2x.png": (1520, 512),
}


def _png_dimensjoner(sti: Path) -> tuple[int, int]:
    """Les dimensjonene fra PNG-ens faste IHDR-header uten bildebibliotek."""
    data = sti.read_bytes()
    assert data.startswith(PNG_SIGNATURE), f"{sti} er ikke en PNG-fil"
    assert data[12:16] == b"IHDR", f"{sti} mangler IHDR-header"
    return struct.unpack(">II", data[16:24])


@pytest.mark.parametrize(("filnavn", "dimensjoner"), FORVENTEDE_BILDER.items())
def test_brandbilder_er_png_med_riktige_dimensjoner(filnavn: str, dimensjoner: tuple[int, int]) -> None:
    bilde = BRAND / filnavn

    assert bilde.is_file(), f"{bilde} mangler"
    assert _png_dimensjoner(bilde) == dimensjoner


def test_brand_har_bare_de_forventede_bildene() -> None:
    assert {p.name for p in BRAND.iterdir()} == set(FORVENTEDE_BILDER)
