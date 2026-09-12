#!/usr/bin/env python3
"""Hent release-noten for en versjon ut av CHANGELOG.md.

CHANGELOG-seksjonen ER release-noten. Release-workflowen kaller dette scriptet
og bruker utskriften som body, så teksten lever i repoet og ikke bare i en
GitHub-draft som kan forsvinne (stromkalkulator-1dk4).

Bruk:
    python3 scripts/release_notes.py 1.16.0
    python3 scripts/release_notes.py 1.16.0 --changelog /sti/til/CHANGELOG.md

Skriver seksjonen til stdout og avslutter med 0. Finnes ikke seksjonen,
skrives en feilmelding til stderr og exit-koden blir 1, slik at workflowen
stopper i stedet for å publisere en tom release.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# "## [1.16.0]" og "## [0.31.0] - 2026-01-30" er begge i bruk i filen.
SEKSJON = re.compile(r"^## \[(?P<versjon>[^\]]+)\]\s*(?:-\s*\S+)?\s*$")


def finn_seksjon(changelog: str, versjon: str) -> str | None:
    """Returner teksten under `## [versjon]`, uten selve overskriften.

    Returnerer None hvis versjonen ikke har en egen seksjon. Tom seksjon (bare
    overskrift) regnes også som manglende: en release uten tekst er ikke bedre
    enn ingen seksjon.
    """
    linjer = changelog.splitlines()
    start: int | None = None
    slutt = len(linjer)

    for nr, linje in enumerate(linjer):
        treff = SEKSJON.match(linje)
        if not treff:
            continue
        if start is None:
            if treff.group("versjon") == versjon:
                start = nr + 1
        else:
            slutt = nr
            break

    if start is None:
        return None

    tekst = "\n".join(linjer[start:slutt]).strip("\n")
    return tekst or None


def kjente_versjoner(changelog: str) -> list[str]:
    """Alle versjonene som har en seksjon, i filens rekkefølge."""
    return [m.group("versjon") for linje in changelog.splitlines() if (m := SEKSJON.match(linje))]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skriv ut CHANGELOG-seksjonen for en versjon.")
    parser.add_argument("versjon", help="versjonen uten v-prefiks, f.eks. 1.16.0")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG, help="sti til CHANGELOG.md")
    args = parser.parse_args(argv)

    versjon = args.versjon.lstrip("v")

    try:
        changelog = args.changelog.read_text(encoding="utf-8")
    except OSError as err:
        print(f"Klarte ikke lese {args.changelog}: {err}", file=sys.stderr)
        return 1

    seksjon = finn_seksjon(changelog, versjon)
    if seksjon is None:
        print(
            f"Fant ingen seksjon '## [{versjon}]' med innhold i {args.changelog}.\n"
            f"Seksjoner i filen: {', '.join(kjente_versjoner(changelog)) or '(ingen)'}\n"
            "Release-noten skal stå i CHANGELOG.md før versjonen slippes.",
            file=sys.stderr,
        )
        return 1

    print(seksjon)
    return 0


if __name__ == "__main__":
    sys.exit(main())
