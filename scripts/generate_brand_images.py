#!/usr/bin/env python3
"""Lag merkevarebildene Home Assistant leser fra integrasjonens brand/-mappe.

Bruk:
    uv run --with pillow python scripts/generate_brand_images.py [--output DIR]

Kildene er images/icon.png (kvadratisk) og images/logo-light.png (liggende).
Uten --output skrives bildene til custom_components/stromkalkulator/brand/.
Skriv til en annen mappe først og sammenlign hvis du bare vil se resultatet.

Utdata:
    - icon.png (256x256)
    - icon@2x.png (512x512)
    - logo.png (korteste side 256px)
    - logo@2x.png (nøyaktig dobbel logo.png)
"""

import argparse
from pathlib import Path

from PIL import Image

PROSJEKTROT = Path(__file__).parent.parent
KILDER = PROSJEKTROT / "images"
BRAND = PROSJEKTROT / "custom_components" / "stromkalkulator" / "brand"


def korteste_side(img: Image.Image, mål: int) -> tuple[int, int]:
    """Dimensjoner der korteste side er `mål` og sideforholdet beholdes."""
    bredde, høyde = img.size
    if bredde < høyde:
        return mål, round(høyde * mål / bredde)
    return round(bredde * mål / høyde), mål


def lagre(img: Image.Image, størrelse: tuple[int, int], sti: Path) -> None:
    img.resize(størrelse, Image.Resampling.LANCZOS).save(sti, "PNG", optimize=True)
    print(f"  {sti.name}: {størrelse[0]}x{størrelse[1]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=BRAND, help="mappe å skrive til")
    utdata: Path = parser.parse_args().output
    utdata.mkdir(parents=True, exist_ok=True)

    ikon = Image.open(KILDER / "icon.png")
    logo = Image.open(KILDER / "logo-light.png")

    lagre(ikon, (256, 256), utdata / "icon.png")
    lagre(ikon, (512, 512), utdata / "icon@2x.png")

    # @2x er dobbel 1x heller enn egen avrunding, så de to logoene har
    # nøyaktig samme sideforhold (760x256 og 1520x512 fra en 1080x364-kilde).
    bredde, høyde = korteste_side(logo, 256)
    lagre(logo, (bredde, høyde), utdata / "logo.png")
    lagre(logo, (bredde * 2, høyde * 2), utdata / "logo@2x.png")


if __name__ == "__main__":
    main()
