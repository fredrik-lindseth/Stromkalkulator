#!/usr/bin/env python3
"""Hent release-noten for en versjon ut av CHANGELOG.md.

CHANGELOG-seksjonen ER release-noten. Release-workflowen kaller dette scriptet
og bruker utskriften som body, så teksten lever i repoet og ikke bare i en
GitHub-draft som kan forsvinne (stromkalkulator-1dk4).

To ting skiller utskriften fra rå CHANGELOG-tekst:

* Relative lenker skrives om til absolutte URL-er mot taggen som slippes.
  I repoet virker `](docs/incidents/006-...)`, men limt inn som release-body
  peker den på `/releases/tag/docs/...` og er død. Taggen brukes framfor
  `main` så lenken fortsatt viser innholdet slik det var ved releasen.
* Kategorien «Dette må du gjøre selv» løftes øverst, uansett hvor den står i
  seksjonen, så beskjeden ikke drukner under «Lagt til» og «Fikset».

Bruk:
    python3 scripts/release_notes.py 1.16.0
    python3 scripts/release_notes.py 1.16.0 --changelog /sti/til/CHANGELOG.md

Skriver seksjonen til stdout og avslutter med 0. Finnes ikke seksjonen, eller
peker en relativ lenke på en fil som ikke finnes i repoet, skrives en
feilmelding til stderr og exit-koden blir 1, slik at workflowen stopper i
stedet for å publisere en tom release eller en død lenke.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
REPO_URL = "https://github.com/fredrik-lindseth/Stromkalkulator"

# Overskriften for ting brukeren må gjøre aktivt etter oppgraderingen.
HANDLING = "Dette må du gjøre selv"

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
    return tekst if tekst.strip() else None


def kjente_versjoner(changelog: str) -> list[str]:
    """Alle versjonene som har en seksjon, i filens rekkefølge."""
    return [m.group("versjon") for linje in changelog.splitlines() if (m := SEKSJON.match(linje))]


class LenkeFeil(Exception):
    """En relativ lenke peker på noe som ikke finnes i repoet."""


# Markdown-lenker og bilder: `](mål)` med valgfri tittel etter målet.
LENKE = re.compile(r"\]\((?P<mal>[^)\s]+)(?P<tittel>\s+\"[^\"]*\")?\)")

# "https:", "mailto:" og "//example.com" er allerede absolutte.
ABSOLUTT = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]*:|//)")

# Kategorioverskrift, f.eks. "### Dette må du gjøre selv".
KATEGORI = re.compile(r"^### +(?P<navn>.+?)\s*$")

VERSJONSNUMMER = re.compile(r"^\d+(?:\.\d+)*$")


def tag_for(versjon: str) -> str:
    """Taggen lenkene skal peke på.

    Et versjonsnummer blir `v1.16.0`. «Ikke sluppet» har ingen tag ennå, så da
    faller vi til `main`: lenken kan råtne, men den virker når noen ser på
    seksjonen før release.
    """
    return f"v{versjon}" if VERSJONSNUMMER.match(versjon) else "main"


def _absolutt_url(mal: str, tag: str, repo_root: Path, repo_url: str, mangler: list[str]) -> str:
    """Gjør ett lenkemål absolutt. Ukjente filer samles i `mangler`."""
    if ABSOLUTT.match(mal):
        return mal

    if mal.startswith("#"):
        # Anker i CHANGELOG selv. På releasesiden finnes ikke resten av filen,
        # så pek på CHANGELOG.md i repoet med samme anker.
        return f"{repo_url}/blob/{tag}/CHANGELOG.md{mal}"

    sti, _, anker = mal.partition("#")
    sti = sti.removeprefix("./")

    if not sti:
        mangler.append(mal)
        return mal

    mal_sti = (repo_root / sti).resolve()
    try:
        relativ = mal_sti.relative_to(repo_root.resolve())
    except ValueError:
        mangler.append(mal)
        return mal

    if not mal_sti.exists():
        mangler.append(mal)
        return mal

    url = f"{repo_url}/blob/{tag}/{quote(relativ.as_posix())}"
    return f"{url}#{anker}" if anker else url


def skriv_om_lenker(
    tekst: str,
    versjon: str,
    *,
    repo_root: Path = REPO_ROOT,
    repo_url: str = REPO_URL,
) -> str:
    """Gjør relative lenker absolutte mot taggen som slippes.

    Absolutte lenker står urørt. Peker en relativ lenke på noe som ikke finnes
    i repoet, kastes LenkeFeil framfor å publisere en død lenke.
    """
    tag = tag_for(versjon)
    mangler: list[str] = []

    def bytt(treff: re.Match[str]) -> str:
        mal = _absolutt_url(treff.group("mal"), tag, repo_root, repo_url, mangler)
        return f"]({mal}{treff.group('tittel') or ''})"

    resultat = LENKE.sub(bytt, tekst)

    if mangler:
        raise LenkeFeil(", ".join(dict.fromkeys(mangler)))

    return resultat


def loft_handlingskategori(tekst: str, kategori: str = HANDLING) -> str:
    """Flytt «Dette må du gjøre selv» øverst i seksjonen.

    Rekkefølgen i CHANGELOG skal ikke avgjøre om brukeren ser beskjeden.
    Finnes ikke kategorien, står teksten som den er.
    """
    linjer = tekst.splitlines()
    start: int | None = None
    slutt = len(linjer)

    for nr, linje in enumerate(linjer):
        treff = KATEGORI.match(linje)
        if not treff:
            continue
        if start is None:
            if treff.group("navn").casefold() == kategori.casefold():
                start = nr
        else:
            slutt = nr
            break

    if start is None or start == 0:
        return tekst

    blokk = list(linjer[start:slutt])
    resten = linjer[:start] + linjer[slutt:]

    while blokk and not blokk[-1].strip():
        blokk.pop()
    while resten and not resten[0].strip():
        resten.pop(0)

    return "\n".join([*blokk, "", *resten]).strip("\n")


def bygg_body(
    changelog: str,
    versjon: str,
    *,
    repo_root: Path = REPO_ROOT,
    repo_url: str = REPO_URL,
) -> str | None:
    """Hele release-body-en: seksjonen, løftet kategori og absolutte lenker."""
    seksjon = finn_seksjon(changelog, versjon)
    if seksjon is None:
        return None
    return skriv_om_lenker(
        loft_handlingskategori(seksjon),
        versjon,
        repo_root=repo_root,
        repo_url=repo_url,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skriv ut CHANGELOG-seksjonen for en versjon.")
    parser.add_argument("versjon", help="versjonen uten v-prefiks, f.eks. 1.16.0")
    parser.add_argument("--changelog", type=Path, default=CHANGELOG, help="sti til CHANGELOG.md")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=REPO_ROOT,
        help="roten relative lenker sjekkes mot (default: dette repoet)",
    )
    args = parser.parse_args(argv)

    versjon = args.versjon.lstrip("v")

    try:
        changelog = args.changelog.read_text(encoding="utf-8")
    except OSError as err:
        print(f"Klarte ikke lese {args.changelog}: {err}", file=sys.stderr)
        return 1

    try:
        body = bygg_body(changelog, versjon, repo_root=args.repo_root)
    except LenkeFeil as err:
        print(
            f"Relativ lenke peker på noe som ikke finnes i {args.repo_root}: {err}\n"
            "Rett stien i CHANGELOG.md, eller bruk en absolutt URL. En død lenke i en\n"
            "publisert release kan ikke rettes uten å redigere releasen for hånd.",
            file=sys.stderr,
        )
        return 1

    if body is None:
        print(
            f"Fant ingen seksjon '## [{versjon}]' med innhold i {args.changelog}.\n"
            f"Seksjoner i filen: {', '.join(kjente_versjoner(changelog)) or '(ingen)'}\n"
            "Release-noten skal stå i CHANGELOG.md før versjonen slippes.",
            file=sys.stderr,
        )
        return 1

    print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
