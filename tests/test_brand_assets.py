"""Kontrakt for lokale merkevarebilder i nyere Home Assistant.

Fra Home Assistant 2026.3 leser Brands-integrasjonen bilder fra
``custom_components/<domain>/brand/`` før den prøver den sentrale CDN-en.
Kopiene her må derfor følge de gamle fallback-bildene byte-for-byte, og ha
dimensjonene Brands API godtar.
"""

from __future__ import annotations

import struct
from pathlib import Path

import pytest

KOMPONENT = Path(__file__).parent.parent / "custom_components" / "stromkalkulator"
BRAND = KOMPONENT / "brand"
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
def test_lokale_brandbilder_er_gyldige_og_i_takt_med_fallback(
    filnavn: str, dimensjoner: tuple[int, int]
) -> None:
    """Ny HA bruker brand/, mens eldre HA fortsatt kan bruke rotfilene."""
    lokal = BRAND / filnavn
    fallback = KOMPONENT / filnavn

    assert lokal.is_file(), f"{lokal} mangler"
    assert _png_dimensjoner(lokal) == dimensjoner
    assert lokal.read_bytes() == fallback.read_bytes(), f"{filnavn} er ulik lokal fallback"
