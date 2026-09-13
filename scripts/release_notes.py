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

`--kort` gir en annen utskrift av den samme teksten: alt under «Dette må du
gjøre selv», punktene som er merket med `<!--kort-->`, og en lenke til hele
endringsloggen. Den er release-body-en, altså det HACS viser i
oppdateringspanelet inne i Home Assistant, en smal rute folk scroller gjennom
før de trykker oppdater. En seksjon på førti punkter blir ikke lest der. Begge
utskriftene kommer fra CHANGELOG.md, så det finnes fortsatt bare én tekst å
skrive og én å holde vedlike.

Bruk:
    python3 scripts/release_notes.py 1.16.0
    python3 scripts/release_notes.py 1.16.0 --kort
    python3 scripts/release_notes.py 1.16.0 --changelog /sti/til/CHANGELOG.md

Skriver seksjonen til stdout og avslutter med 0. Finnes ikke seksjonen, peker
en relativ lenke på en fil som ikke finnes i repoet, eller står
handlingskategorien tom, skrives en feilmelding til stderr og exit-koden blir
1, slik at workflowen stopper i stedet for å publisere en tom release, en død
lenke eller en naken overskrift. Med `--kort` feller det også at seksjonen som
er under arbeid ikke har et eneste merket punkt, siden en tom kort versjon er
verre enn ingen.
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

# Merket som sier at et punkt skal med i den korte release-noten. En
# HTML-kommentar er usynlig når CHANGELOG.md leses som markdown på GitHub. Den
# står til slutt: først i et punkt kan GitHub vise resten som råtekst. Skriv:
#
#     - **Månedskostnaden faller 64 til 145 kroner.** ... <!--kort-->
MERKE_TEKST = "<!--kort-->"
MERKE = re.compile(r"<!--\s*kort\s*-->[ \t]*")

# Overskriften de merkede punktene samles under i den korte noten.
KORT_OVERSKRIFT = "Det viktigste"

# Et punkt i en liste. Stjerne-varianten er ikke i bruk i filen, men koster
# ingenting å ta med.
PUNKT = re.compile(r"^[-*] +\S")

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


class TomKategoriFeil(Exception):
    """En kategorioverskrift står uten punkter under seg."""

    def __init__(self, versjon: str, overskrift: str) -> None:
        super().__init__(f"seksjonen for {versjon} har kategorien '{overskrift}' uten innhold")
        self.versjon = versjon
        self.overskrift = overskrift


# Markdown-lenker og bilder: `](mål)` med valgfri tittel etter målet. Målet kan
# stå i vinkelparenteser, som er den eneste måten å skrive en sti med mellomrom.
LENKE = re.compile(r"\]\((?:<(?P<vinkel>[^<>\n]*)>|(?P<mal>[^)\s]+))(?P<tittel>\s+\"[^\"]*\")?\)")

# Referansedefinisjon: `[ref]: mål "tittel"` på egen linje. Lenken selv står som
# `[tekst][ref]` et annet sted og har ikke målet i seg, så det er her det bor.
REFERANSE = re.compile(
    r"^(?P<pre>\s{0,3}\[[^\]\n]+\]:[ \t]*)"
    r"(?:<(?P<vinkel>[^<>\n]*)>|(?P<mal>\S+))"
    r"(?P<tittel>[ \t]+(?:\"[^\"\n]*\"|\'[^\'\n]*\'|\([^)\n]*\)))?[ \t]*$",
    re.MULTILINE,
)

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

    Dekker vanlige lenker og bilder, mål i vinkelparenteser (`](<sti med
    mellomrom>)`) og referansedefinisjoner (`[ref]: sti`). Autolenker
    (`<https://...>`) må ha et skjema for å være lenker i det hele tatt, så de
    er alltid absolutte og står urørt.

    Absolutte lenker står urørt. Peker en relativ lenke på noe som ikke finnes
    i repoet, kastes LenkeFeil framfor å publisere en død lenke.
    """
    tag = tag_for(versjon)
    mangler: list[str] = []

    def nytt_mal(treff: re.Match[str]) -> str:
        """Målet slik det skal stå etter omskriving, vinkelparenteser og alt.

        Et mål i vinkelparenteser som blir absolutt, kommer ut som en URL uten
        mellomrom og trenger dem ikke lenger. Står det urørt, beholder vi dem.
        """
        vinkel = treff.group("vinkel")
        if vinkel is None:
            return _absolutt_url(treff.group("mal"), tag, repo_root, repo_url, mangler)
        mal = _absolutt_url(vinkel, tag, repo_root, repo_url, mangler)
        return f"<{mal}>" if mal == vinkel else mal

    def bytt_lenke(treff: re.Match[str]) -> str:
        return f"]({nytt_mal(treff)}{treff.group('tittel') or ''})"

    def bytt_referanse(treff: re.Match[str]) -> str:
        return f"{treff.group('pre')}{nytt_mal(treff)}{treff.group('tittel') or ''}"

    resultat = REFERANSE.sub(bytt_referanse, tekst)
    resultat = LENKE.sub(bytt_lenke, resultat)

    if mangler:
        raise LenkeFeil(", ".join(dict.fromkeys(mangler)))

    return resultat


def loft_handlingskategori(tekst: str, versjon: str, kategori: str = HANDLING) -> str:
    """Flytt «Dette må du gjøre selv» øverst i seksjonen.

    Rekkefølgen i CHANGELOG skal ikke avgjøre om brukeren ser beskjeden.
    Finnes ikke kategorien, står teksten som den er.

    Står overskriften uten punkter under seg, kastes TomKategoriFeil. En naken
    overskrift øverst i en publisert release ser ødelagt ut og uroer brukerne
    uten grunn, og den som får feilen retter den i sin egen CHANGELOG-seksjon.
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

    if start is None:
        return tekst

    # Blanke linjer teller ikke som innhold, på linje med en tom seksjon.
    if not any(linje.strip() for linje in linjer[start + 1 : slutt]):
        raise TomKategoriFeil(versjon, linjer[start].strip())

    if start == 0:
        return tekst

    blokk = list(linjer[start:slutt])
    resten = linjer[:start] + linjer[slutt:]

    while blokk and not blokk[-1].strip():
        blokk.pop()
    while resten and not resten[0].strip():
        resten.pop(0)

    return "\n".join([*blokk, "", *resten]).strip("\n")


class UmerketFeil(Exception):
    """En seksjon har ikke ett eneste punkt merket for den korte noten."""

    def __init__(self, versjon: str) -> None:
        super().__init__(f"seksjonen for {versjon} har ingen punkter merket med {MERKE_TEKST}")
        self.versjon = versjon


def del_i_kategorier(tekst: str) -> list[tuple[str | None, list[str]]]:
    """Del en seksjon i (kategorinavn, punkter), i filens rekkefølge.

    Første element har navn None og holder det som står før den første
    `###`-overskriften. Et punkt er linjen som starter med `-` eller `*`, pluss
    linjene under den til neste punkt, neste overskrift eller en blank linje, så
    et punkt som går over flere linjer holder sammen.
    """
    kategorier: list[tuple[str | None, list[str]]] = []
    navn: str | None = None
    punkter: list[str] = []
    apent: list[str] | None = None

    def lukk() -> None:
        nonlocal apent
        if apent is not None:
            punkter.append("\n".join(apent).rstrip())
            apent = None

    for linje in tekst.splitlines():
        treff = KATEGORI.match(linje)
        if treff:
            lukk()
            kategorier.append((navn, punkter))
            navn, punkter = treff.group("navn"), []
            continue
        if PUNKT.match(linje):
            lukk()
            apent = [linje]
            continue
        if apent is not None:
            if linje.strip():
                apent.append(linje)
            else:
                lukk()

    lukk()
    kategorier.append((navn, punkter))
    return kategorier


def _er_handling(navn: str | None, kategori: str = HANDLING) -> bool:
    return navn is not None and navn.casefold() == kategori.casefold()


def uten_merker(tekst: str) -> str:
    """Fjern `<!--kort-->` fra teksten som skal publiseres."""
    return MERKE.sub("", tekst)


def merkede_punkter(seksjon: str, kategori: str = HANDLING) -> list[str]:
    """Punktene som er merket for den korte noten, utenom handlingskategorien.

    Handlingskategorien blir med i sin helhet uansett, så et merke der ville
    bare vært støy.
    """
    return [
        punkt
        for navn, punkter in del_i_kategorier(seksjon)
        if not _er_handling(navn, kategori)
        for punkt in punkter
        if MERKE.search(punkt)
    ]


def bygg_kort(
    seksjon: str,
    versjon: str,
    *,
    kategori: str = HANDLING,
    changelog_lenke: str = "CHANGELOG.md",
) -> str:
    """Den korte noten: handlingskategorien, de merkede punktene og en lenke.

    Kaster UmerketFeil hvis ingen punkter er merket. Den som får feilen merker
    punktene i sin egen CHANGELOG-seksjon; alternativet er en release-note som
    bare sier «se endringsloggen», og det er verre enn ingen kort versjon.
    """
    kategorier = del_i_kategorier(seksjon)

    handling_navn = next((navn for navn, _ in kategorier if _er_handling(navn, kategori)), None)
    handling = [punkt for navn, punkter in kategorier if _er_handling(navn, kategori) for punkt in punkter]
    merket = merkede_punkter(seksjon, kategori)
    if not merket:
        raise UmerketFeil(versjon)

    deler: list[str] = []
    if handling_navn is not None and handling:
        deler += [f"### {handling_navn}", "", *handling, ""]
    deler += [f"### {KORT_OVERSKRIFT}", "", *merket, ""]
    deler.append(f"[Alt som er endret i denne versjonen]({changelog_lenke})")

    return uten_merker("\n".join(deler))


def er_under_arbeid(changelog: str, versjon: str) -> bool:
    """Er dette den øverste seksjonen i filen, altså den som skrives nå?

    Alt under den er sluppet og er historikk. Historikken merkes ikke i
    ettertid, så vakten for merkede punkter gjelder bare toppen.
    """
    versjoner = kjente_versjoner(changelog)
    return bool(versjoner) and versjoner[0] == versjon


def bygg_kort_body(
    changelog: str,
    versjon: str,
    *,
    repo_root: Path = REPO_ROOT,
    repo_url: str = REPO_URL,
    streng: bool = True,
) -> str | None:
    """Den korte release-body-en, med absolutte lenker.

    `streng=False` gir hele seksjonen i stedet for å kaste UmerketFeil når
    ingenting er merket. Det er svaret for en sluppet versjon: den ble skrevet
    før merkene fantes, og en gammel note skal kunne hentes fram igjen uten at
    verktøyet krasjer.
    """
    seksjon = finn_seksjon(changelog, versjon)
    if seksjon is None:
        return None
    loftet = loft_handlingskategori(seksjon, versjon)
    try:
        kort = bygg_kort(loftet, versjon)
    except UmerketFeil:
        if streng:
            raise
        kort = uten_merker(loftet)
    return skriv_om_lenker(kort, versjon, repo_root=repo_root, repo_url=repo_url)


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
        uten_merker(loft_handlingskategori(seksjon, versjon)),
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
    parser.add_argument(
        "--kort",
        action="store_true",
        help="bare handlingskategorien og de merkede punktene, pluss lenke til hele loggen",
    )
    args = parser.parse_args(argv)

    versjon = args.versjon.lstrip("v")

    try:
        changelog = args.changelog.read_text(encoding="utf-8")
    except OSError as err:
        print(f"Klarte ikke lese {args.changelog}: {err}", file=sys.stderr)
        return 1

    # Historikken merkes ikke i ettertid, så vakten gjelder seksjonen som er
    # under arbeid. Hentes en gammel note fram med --kort, får du hele den.
    streng = er_under_arbeid(changelog, versjon)

    try:
        if args.kort:
            body = bygg_kort_body(changelog, versjon, repo_root=args.repo_root, streng=streng)
            if (
                body is not None
                and not streng
                and not merkede_punkter(finn_seksjon(changelog, versjon) or "")
            ):
                print(
                    f"Seksjonen for {versjon} er sluppet og har ingen merkede punkter. "
                    "Skriver hele seksjonen.",
                    file=sys.stderr,
                )
        else:
            body = bygg_body(changelog, versjon, repo_root=args.repo_root)
    except UmerketFeil as err:
        print(
            f"Seksjonen '## [{err.versjon}]' i {args.changelog} har ingen punkter merket\n"
            f"med {MERKE_TEKST}, så den korte release-noten ville blitt tom.\n"
            "Sett merket rett etter streken på de punktene en bruker faktisk merker:\n"
            f"  - {MERKE_TEKST} **Månedskostnaden faller 64 til 145 kroner.** ...\n"
            "Merket er en HTML-kommentar og er usynlig når CHANGELOG.md leses som markdown.",
            file=sys.stderr,
        )
        return 1
    except LenkeFeil as err:
        print(
            f"Relativ lenke peker på noe som ikke finnes i {args.repo_root}: {err}\n"
            "Rett stien i CHANGELOG.md, eller bruk en absolutt URL. En død lenke i en\n"
            "publisert release kan ikke rettes uten å redigere releasen for hånd.",
            file=sys.stderr,
        )
        return 1
    except TomKategoriFeil as err:
        print(
            f"Seksjonen '## [{err.versjon}]' i {args.changelog} har kategorien\n"
            f"'{err.overskrift}' uten punkter under seg.\n"
            "Skriv punktene, eller slett overskriften. Kategorien løftes øverst i\n"
            "release-noten, så tom blir den til en naken overskrift hos alle brukerne.",
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
