#!/usr/bin/env python3
"""Generate brand images for home-assistant/brands repo.

Usage:
    .venv/bin/python3 scripts/generate_brand_images.py

This script generates properly sized images from the source files in images/
for submission to the home-assistant/brands repository.

Requirements:
    - Pillow (pip install pillow)

Output:
    - custom_components/stromkalkulator/icon.png (256x256)
    - custom_components/stromkalkulator/icon@2x.png (512x512)
    - custom_components/stromkalkulator/logo.png (korteste side 256px)
    - custom_components/stromkalkulator/logo@2x.png (korteste side 512px)
"""

from pathlib import Path

from PIL import Image


def resize_to_shortest_side(img: Image.Image, target_shortest: int) -> Image.Image:
    """Resize image so shortest side matches target, maintaining aspect ratio."""
    width, height = img.size
    if width < height:
        # Width is shortest
        new_width = target_shortest
        new_height = int(height * (target_shortest / width))
    else:
        # Height is shortest
        new_height = target_shortest
        new_width = int(width * (target_shortest / height))

    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def resize_square(img: Image.Image, size: int) -> Image.Image:
    """Resize image to square dimensions."""
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    """Generate all brand images."""
    # Paths
    project_root = Path(__file__).parent.parent
    source_dir = project_root / "images"
    output_dir = project_root / "custom_components" / "stromkalkulator"

    # Source files
    logo_source = source_dir / "logo.png"
    icon_source = source_dir / "icon.png"

    print(f"Source logo: {logo_source}")
    print(f"Source icon: {icon_source}")
    print(f"Output dir: {output_dir}")
    print()

    # Load source images
    logo_img = Image.open(logo_source)
    icon_img = Image.open(icon_source)

    print(f"Logo source size: {logo_img.size}")
    print(f"Icon source size: {icon_img.size}")
    print()

    # Generate icons (square, from icon source)
    print("Generating icons...")

    icon_256 = resize_square(icon_img, 256)
    icon_256.save(output_dir / "icon.png", "PNG", optimize=True)
    print(f"  icon.png: {icon_256.size}")

    icon_512 = resize_square(icon_img, 512)
    icon_512.save(output_dir / "icon@2x.png", "PNG", optimize=True)
    print(f"  icon@2x.png: {icon_512.size}")

    # Generate logos (landscape, shortest side requirement)
    # Normal: shortest side 128-256px (we use 256 for max quality)
    # hDPI: shortest side 256-512px (we use 512 for max quality)
    print("Generating logos...")

    logo_normal = resize_to_shortest_side(logo_img, 256)
    logo_normal.save(output_dir / "logo.png", "PNG", optimize=True)
    print(f"  logo.png: {logo_normal.size}")

    logo_hdpi = resize_to_shortest_side(logo_img, 512)
    logo_hdpi.save(output_dir / "logo@2x.png", "PNG", optimize=True)
    print(f"  logo@2x.png: {logo_hdpi.size}")

    print()
    print("Done! Generated images in:", output_dir)
    print()
    print("For brands repo submission, copy to:")
    print("  custom_integrations/stromkalkulator/")


if __name__ == "__main__":
    main()
