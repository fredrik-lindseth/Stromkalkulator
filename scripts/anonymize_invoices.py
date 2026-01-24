#!/usr/bin/env python3
"""Anonymize invoice text files for public sharing.

Replaces personal information with realistic fake data.
Reads replacement mappings from .anonymize_config.json (gitignored).
"""

import json
from pathlib import Path


def load_config() -> dict:
    """Load anonymization config from .anonymize_config.json."""
    config_path = Path(__file__).parent.parent / ".anonymize_config.json"

    if not config_path.exists():
        print("ERROR: .anonymize_config.json not found!")
        print("Create it from .anonymize_config.example.json:")
        print("  cp .anonymize_config.example.json .anonymize_config.json")
        print("Then edit it with your real data.")
        raise SystemExit(1)

    return json.loads(config_path.read_text(encoding="utf-8"))


def anonymize_file(filepath: Path, replacements: dict[str, str]) -> str:
    """Anonymize a single file and return the anonymized content."""
    content = filepath.read_text(encoding="utf-8")

    for original, replacement in replacements.items():
        content = content.replace(original, replacement)

    return content


def main() -> None:
    """Anonymize all invoice text files."""
    config = load_config()
    replacements = config.get("replacements", {})
    filename_mappings = config.get("filename_mappings", {})

    fakturaer_dir = Path(__file__).parent.parent / "Fakturaer"
    output_dir = Path(__file__).parent.parent / "docs" / "fakturaer"

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_files = list(fakturaer_dir.glob("*.txt"))

    if not txt_files:
        print("No .txt files found in Fakturaer/")
        return

    for txt_file in txt_files:
        print(f"Anonymizing {txt_file.name}...")
        anonymized = anonymize_file(txt_file, replacements)

        # Create anonymized filename using mappings
        output_name = txt_file.name
        for old_pattern, new_pattern in filename_mappings.items():
            output_name = output_name.replace(old_pattern, new_pattern)

        output_path = output_dir / output_name
        output_path.write_text(anonymized, encoding="utf-8")
        print(f"  -> {output_path}")

    # Also copy REFERANSE.md if it exists
    ref_file = fakturaer_dir / "REFERANSE.md"
    if ref_file.exists():
        ref_content = ref_file.read_text(encoding="utf-8")
        # Anonymize invoice numbers in reference
        for old_pattern, new_pattern in filename_mappings.items():
            ref_content = ref_content.replace(old_pattern, new_pattern)

        output_ref = output_dir / "REFERANSE.md"
        output_ref.write_text(ref_content, encoding="utf-8")
        print(f"  -> {output_ref}")

    print("\nDone! Anonymized files in docs/fakturaer/")
    print("Review the files before committing to ensure all personal data is removed.")


if __name__ == "__main__":
    main()
