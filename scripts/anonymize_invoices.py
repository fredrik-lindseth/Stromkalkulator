#!/usr/bin/env python3
"""Anonymiser personlig data før commit.

To kjøremoduser:

1. **Invoice-mode (default):** Tar .txt-fakturaer fra Fakturaer/ og skriver
   anonymiserte versjoner til docs/fakturaer/. Originalt mønster.

2. **Inplace-mode (--inplace):** Anonymiserer filer direkte (i samme path).
   Brukes for docs/, fixtures/, og Måleverdier/README.md som ikke har en
   "input/output"-separasjon. Filer listet i `anonymize_inplace_globs` i
   .anonymize_config.json.

Begge moduser leser replacements fra .anonymize_config.json (gitignored).

Bruk:

    # Default: anonymiser fakturaer fra Fakturaer/ til docs/fakturaer/
    python3 scripts/anonymize_invoices.py

    # Inplace: anonymiser alle filer i anonymize_inplace_globs
    python3 scripts/anonymize_invoices.py --inplace

    # Sjekk uten å endre filer (vis hva som ville blitt endret)
    python3 scripts/anonymize_invoices.py --inplace --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def load_config() -> dict:
    """Last anonymiseringskonfig fra .anonymize_config.json."""
    config_path = Path(__file__).parent.parent / ".anonymize_config.json"

    if not config_path.exists():
        print("FEIL: .anonymize_config.json finnes ikke!", file=sys.stderr)
        print("Opprett den med dine reelle data og mappings til generiske.", file=sys.stderr)
        sys.exit(1)

    return json.loads(config_path.read_text(encoding="utf-8"))


def anonymize_content(content: str, replacements: dict[str, str]) -> str:
    """Anvend alle replacements på innholdet.

    Iterer i lengde-rekkefølge slik at lengre matches erstattes først (unngår
    at en kortere match spiser en del av en lengre).
    """
    sorted_keys = sorted(replacements.keys(), key=len, reverse=True)
    for original in sorted_keys:
        replacement = replacements[original]
        content = content.replace(original, replacement)
    return content


def run_invoice_mode(config: dict) -> None:
    """Anonymiser .txt-fakturaer fra Fakturaer/ til docs/fakturaer/."""
    replacements = config.get("replacements", {})
    filename_mappings = config.get("filename_mappings", {})

    root = Path(__file__).parent.parent
    fakturaer_dir = root / "Fakturaer"
    output_dir = root / "docs" / "fakturaer"
    output_dir.mkdir(parents=True, exist_ok=True)

    txt_files = list(fakturaer_dir.glob("*.txt"))
    if not txt_files:
        print("Ingen .txt-filer i Fakturaer/")
        return

    for txt_file in txt_files:
        print(f"Anonymiserer {txt_file.name}...")
        anonymized = anonymize_content(txt_file.read_text(encoding="utf-8"), replacements)

        output_name = txt_file.name
        for old_pattern, new_pattern in filename_mappings.items():
            output_name = output_name.replace(old_pattern, new_pattern)

        output_path = output_dir / output_name
        output_path.write_text(anonymized, encoding="utf-8")
        print(f"  -> {output_path}")

    ref_file = fakturaer_dir / "referanse.md"
    if ref_file.exists():
        ref_content = anonymize_content(ref_file.read_text(encoding="utf-8"), replacements)
        output_ref = output_dir / "referanse.md"
        output_ref.write_text(ref_content, encoding="utf-8")
        print(f"  -> {output_ref}")

    print("\nFerdig. Sjekk filene i docs/fakturaer/ før commit.")


def run_inplace_mode(config: dict, dry_run: bool) -> None:
    """Anonymiser filer som er listet i config.anonymize_inplace_globs."""
    replacements = config.get("replacements", {})
    globs = config.get("anonymize_inplace_globs", [])

    if not globs:
        print("Ingen filer i anonymize_inplace_globs.")
        return

    root = Path(__file__).parent.parent
    total_changes = 0

    for glob_pattern in globs:
        matched = list(root.glob(glob_pattern))
        if not matched:
            print(f"  (glob '{glob_pattern}' matcher ingen filer)")
            continue

        for path in matched:
            original = path.read_text(encoding="utf-8")
            anonymized = anonymize_content(original, replacements)

            if original == anonymized:
                continue

            changes = sum(
                original.count(k)
                for k, v in replacements.items()
                if k != v and k in original
            )
            total_changes += changes
            rel = path.relative_to(root)

            if dry_run:
                print(f"  [dry-run] {rel}: {changes} treff ville blitt erstattet")
            else:
                path.write_text(anonymized, encoding="utf-8")
                print(f"  {rel}: {changes} erstatninger")

    if dry_run:
        print(f"\nDry-run: ingen filer endret. Totalt {total_changes} mulige treff.")
    else:
        print(f"\nFerdig. {total_changes} erstatninger gjort.")
        print("Sjekk endringer med `git diff` før commit.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--inplace", action="store_true", help="Anonymiser filer fra anonymize_inplace_globs direkte (overwrite).")
    p.add_argument("--dry-run", action="store_true", help="Med --inplace: vis hva som ville blitt endret, men skriv ikke.")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    config = load_config()

    if args.inplace:
        run_inplace_mode(config, args.dry_run)
    else:
        if args.dry_run:
            print("FEIL: --dry-run krever --inplace.", file=sys.stderr)
            sys.exit(1)
        run_invoice_mode(config)


if __name__ == "__main__":
    main()
