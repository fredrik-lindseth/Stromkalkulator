#!/usr/bin/env python3
"""Tilstandsmaskinen som slipper en versjon, og som tåler å bli kjørt om igjen.

Problemet den løser: tagg, ZIP og attestasjon var tre løse ledd. Taggen ble
opprettet av release-API-et uten `target_commitish`, ZIP-en ble bygget fra
checkouten, og attestasjonen ble laget av et tredje steg. En release kunne
tagge én commit, bygge en annen og attestere en tredje, og releasen var
offentlig lenge før ZIP-en lå der. Det er ikke teori: v1.16.0 sin tagg peker på
9dad0dd, mens attestasjonen for `stromkalkulator.zip` sier at filen ble bygget
fra c7e7c70. Innholdet var heldigvis likt den gangen.

Her er kandidaten én ting: **repo + full commit-SHA + manifestversjon**. Alle
tre leddene bindes til den, og bindingen er etterprøvbar i ettertid:

* ZIP-en bygges fra git-objektene på akkurat den SHA-en, ikke fra arbeidstreet,
  så innholdet *er* det taggen peker på. Bygget er deterministisk, så hvem som
  helst kan bygge det samme og få samme sha256.
* Taggen opprettes eksplisitt på den SHA-en. Finnes den fra før, derefereres
  den (annotert eller lettvekts) og sammenlignes. Den flyttes aldri.
* Attestasjonen verifiseres mot repo, kilde-SHA, signer-workflow og sha256-en
  til ZIP-en *før* noe publiseres.
* Kandidaten må ligge på hovedgrenen. En kjøring fra en annen gren stopper, så
  det som går ut til brukerne ikke kan komme et sted fra som aldri har vært på
  main. Unntaket er prøveslipp av versjon 0.0.0, se krev_hovedgren.

Rekkefølgen gjør flyten atomisk der det betyr noe: alt skjer i en draft, og
`draft=false` er siste kall. Feiler noe før det, finnes det ingen offentlig
release å rydde. Hvert steg er idempotent, så et nytt forsøk på samme SHA
plukker opp der det stoppet: taggen er allerede riktig, draften gjenbrukes,
et asset som alt er lastet opp leses tilbake og sammenlignes framfor å byttes.

Er ZIP-en på plass, men med feil sha256, stopper vi. Da vet vi ikke hva som
ligger der, og HACS laster ned nettopp den filen. Automatisk overskriving
ville gjort en uklar tilstand til en ny uklar tilstand.

Underkommandoer:

    plan      les tilstanden og si hva som ville skjedd (leser bare)
    build     bygg deterministisk ZIP fra en SHA, skriv sha256 til stdout
    publish   kjør tilstandsmaskinen (`--dry-run` gjør den til en ren lesing)
    verify    etterprøv en publisert release mot taggen sin, og felle på avvik

Bruk lokalt:

    just release-zip     bygg ZIP-en og se sha256-en
    just release-plan    les tilstanden på GitHub uten å skrive noe
    just release-verify  etterprøv en release som alt er ute
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
KOMPONENT = "custom_components/stromkalkulator"
ASSET_NAVN = "stromkalkulator.zip"

# Workflowen som har lov til å ha signert attestasjonen. Verifiseringen er
# verdiløs uten dette leddet: uten det godtar vi en attestasjon laget av hvilken
# som helst workflow i repoet.
SIGNER_WORKFLOW = ".github/workflows/release.yml"

# Faste ZIP-metadata. Tidsstempelet er ZIP-formatets nullpunkt (1980-01-01), og
# rettighetene settes fra git-modusen, ikke fra filsystemet. Uten dette får to
# bygg av samme innhold ulik sha256 fordi de kjørte til ulik tid.
ZIP_TID = (1980, 1, 1, 0, 0, 0)
ZIP_RETTIGHETER = {"100644": 0o644, "100755": 0o755}

SHA_RE = re.compile(r"^[0-9a-f]{40}$")
VERSJON_RE = re.compile(r"^\d+\.\d+\.\d+$")

# Versjonen en prøvekjøring må ha. Unntaksveien rundt hovedgren-vakten er
# bundet til dette tallet, se krev_hovedgren.
PROVEVERSJON = "0.0.0"

EXIT_OK = 0
EXIT_FEIL = 1
EXIT_STOPP = 2


class Feil(Exception):
    """Noe er galt med oppsettet eller kallet. Exit 1."""


class Stopp(Exception):
    """Tilstanden er uklar eller i konflikt. Exit 2, og ingen skriving."""


# --------------------------------------------------------------------------
# git
# --------------------------------------------------------------------------


class Git:
    """Tynt lag over `git`. Alt leses fra objektdatabasen, ikke fra arbeidstreet."""

    def __init__(self, rot: Path) -> None:
        self.rot = rot

    def _kjor(self, argv: list[str]) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            ["git", "-C", str(self.rot), *argv],
            capture_output=True,
            check=False,
        )

    def tekst(self, *argv: str) -> str:
        res = self._kjor(list(argv))
        if res.returncode != 0:
            raise Feil(f"git {' '.join(argv)} feilet: {res.stderr.decode(errors='replace').strip()}")
        return res.stdout.decode().strip()

    def bytes(self, *argv: str) -> bytes:
        res = self._kjor(list(argv))
        if res.returncode != 0:
            raise Feil(f"git {' '.join(argv)} feilet: {res.stderr.decode(errors='replace').strip()}")
        return res.stdout

    def finnes(self, *argv: str) -> bool:
        return self._kjor(list(argv)).returncode == 0


def full_sha(git: Git, ref: str) -> str:
    """Gjør en ref om til en full commit-SHA, og krev at commiten finnes lokalt.

    `^{commit}` derefererer en annotert tagg. Mangler objektet, er checkouten
    for grunn (`fetch-depth: 0` og tagger må til) og da skal vi si det framfor
    å bygge noe annet enn det vi tror.
    """
    sha = git.tekst("rev-parse", "--verify", f"{ref}^{{commit}}")
    if not SHA_RE.match(sha):
        raise Feil(f"git ga ikke en full SHA for {ref!r}: {sha!r}")
    return sha


def les_versjon(git: Git, sha: str) -> str:
    """Manifestversjonen slik den står *på den SHA-en*, ikke i arbeidstreet."""
    raa = git.bytes("show", f"{sha}:{KOMPONENT}/manifest.json")
    try:
        manifest = json.loads(raa)
    except json.JSONDecodeError as err:
        raise Feil(f"manifest.json på {sha} er ikke gyldig JSON: {err}") from err
    versjon = manifest.get("version")
    if not isinstance(versjon, str) or not VERSJON_RE.match(versjon):
        raise Feil(f"manifest.json på {sha} har ugyldig versjon: {versjon!r}")
    return versjon


def komponentfiler(git: Git, sha: str) -> list[tuple[str, str, str]]:
    """(modus, blob-sha, navn i ZIP-en) for hver sporet fil i komponenten.

    Navnet er stien relativt til komponentkatalogen, fordi HACS pakker ut
    ZIP-en rett i `custom_components/stromkalkulator/` uten å strippe et
    prefiks. Rekkefølgen er sortert, som er det `git ls-tree` gir uansett, men
    vi sorterer eksplisitt så determinismen ikke hviler på git sin.
    """
    raa = git.tekst("ls-tree", "-r", "-z", sha, "--", KOMPONENT)
    filer: list[tuple[str, str, str]] = []
    for post in raa.split("\0"):
        if not post:
            continue
        meta, _, sti = post.partition("\t")
        modus, objekttype, blob = meta.split()
        if objekttype != "blob":
            raise Feil(
                f"{sti} på {sha} er {objekttype}, ikke en vanlig fil. "
                "Symlenker og undermoduler hører ikke hjemme i en HACS-ZIP."
            )
        if modus not in ZIP_RETTIGHETER:
            raise Feil(f"{sti} har git-modus {modus}, som ikke kan pakkes deterministisk")
        filer.append((modus, blob, sti[len(KOMPONENT) + 1 :]))
    if not filer:
        raise Feil(f"{KOMPONENT} har ingen sporede filer på {sha}")
    return sorted(filer, key=lambda rad: rad[2])


def bygg_zip(git: Git, sha: str, mal: Path) -> str:
    """Bygg ZIP-en for en SHA og returner sha256-en.

    Determinismen er hele poenget: samme SHA gir byte-lik fil, uansett maskin,
    klokke, umask eller rekkefølgen filene tilfeldigvis lå i. Da kan hvem som
    helst bygge om artefakten og sammenligne med den HACS lastet ned.
    """
    filer = komponentfiler(git, sha)
    mal.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(mal, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zipfil:
        for modus, blob, navn in filer:
            info = zipfile.ZipInfo(navn, ZIP_TID)
            info.compress_type = zipfile.ZIP_DEFLATED
            # 3 = Unix. Rettighetene ligger i de øvre 16 bitene.
            info.create_system = 3
            info.external_attr = ZIP_RETTIGHETER[modus] << 16
            zipfil.writestr(info, git.bytes("cat-file", "blob", blob))
    return sha256_av(mal)


def sha256_av(sti: Path) -> str:
    with sti.open("rb") as fil:
        return hashlib.file_digest(fil, "sha256").hexdigest()


# --------------------------------------------------------------------------
# gh
# --------------------------------------------------------------------------


class Gh:
    """Tynt lag over `gh`, med en tørrkjøringsbryter som stopper all skriving."""

    def __init__(self, repo: str, *, dry_run: bool = False) -> None:
        self.repo = repo
        self.dry_run = dry_run

    def _kjor(self, argv: list[str], *, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(["gh", *argv], input=stdin, capture_output=True, check=False)

    def api(
        self,
        sti: str,
        *,
        metode: str = "GET",
        data: dict[str, Any] | None = None,
        fil: Path | None = None,
        aksept: str | None = None,
        paginate: bool = False,
        tillat_404: bool = False,
    ) -> Any:
        """Ett API-kall. Returnerer parset JSON, eller None ved tillatt 404."""
        if metode != "GET" and self.dry_run:
            raise Feil(f"tørrkjøring forsøkte å skrive: {metode} {sti}")
        argv = ["api", "--method", metode]
        if paginate:
            argv.append("--paginate")
        if aksept:
            argv += ["-H", f"Accept: {aksept}"]
        stdin: bytes | None = None
        if data is not None:
            argv += ["--input", "-"]
            stdin = json.dumps(data).encode()
        if fil is not None:
            argv += ["--input", str(fil), "-H", "Content-Type: application/zip"]
        argv.append(sti)

        res = self._kjor(argv, stdin=stdin)
        if res.returncode != 0:
            feilmelding = res.stderr.decode(errors="replace").strip()
            if tillat_404 and "HTTP 404" in feilmelding:
                return None
            raise Feil(f"gh api {metode} {sti} feilet: {feilmelding}")
        if not res.stdout.strip():
            return None
        return json.loads(res.stdout)

    def raa(self, sti: str, *, aksept: str) -> bytes:
        res = self._kjor(["api", "-H", f"Accept: {aksept}", sti])
        if res.returncode != 0:
            raise Feil(f"gh api {sti} feilet: {res.stderr.decode(errors='replace').strip()}")
        return res.stdout

    def attestasjon(self, argv: list[str]) -> Any:
        res = self._kjor(["attestation", *argv])
        if res.returncode != 0:
            raise Stopp("gh attestation verify feilet:\n" + res.stderr.decode(errors="replace").strip())
        return json.loads(res.stdout)


# --------------------------------------------------------------------------
# Kandidat og tilstand
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Kandidat:
    """De tre leddene som til sammen utgjør «denne releasen»."""

    repo: str
    sha: str
    versjon: str

    @property
    def tag(self) -> str:
        return f"v{self.versjon}"

    def __str__(self) -> str:
        return f"{self.repo}@{self.sha[:12]} som {self.tag}"


def les_kandidat(git: Git, repo: str, ref: str) -> Kandidat:
    sha = full_sha(git, ref)
    return Kandidat(repo=repo, sha=sha, versjon=les_versjon(git, sha))


def tag_sha(gh: Gh, kandidat: Kandidat) -> str | None:
    """SHA-en taggen peker på, eller None om den ikke finnes.

    En annotert tagg peker på et tag-objekt, ikke på commiten, så den må
    derefereres. Uten det ville en annotert tagg på riktig commit sett ut som
    en tagg på feil commit, og flyten ville stoppet uten grunn.
    """
    ref = gh.api(f"repos/{kandidat.repo}/git/ref/tags/{kandidat.tag}", tillat_404=True)
    if ref is None:
        return None
    objekt = ref["object"]
    if objekt["type"] == "commit":
        return str(objekt["sha"])
    if objekt["type"] == "tag":
        tagobjekt = gh.api(f"repos/{kandidat.repo}/git/tags/{objekt['sha']}")
        return str(tagobjekt["object"]["sha"])
    raise Stopp(f"{kandidat.tag} peker på et {objekt['type']}-objekt, som ikke er en commit")


def finn_release(gh: Gh, kandidat: Kandidat) -> dict[str, Any] | None:
    """Releasen for taggen, draft eller ikke.

    Oppslag på tagg (`releases/tags/...`) finner ikke drafter, og en draft er
    nettopp tilstanden vi må kunne gjenoppta. Derfor listes alle releaser.
    """
    releaser = gh.api(f"repos/{kandidat.repo}/releases", paginate=True) or []
    treff = [rel for rel in releaser if rel.get("tag_name") == kandidat.tag]
    if len(treff) > 1:
        raise Stopp(
            f"{len(treff)} releaser har taggen {kandidat.tag}. Rydd for hånd; "
            "flyten vet ikke hvilken som er den rette."
        )
    return treff[0] if treff else None


# --------------------------------------------------------------------------
# Hovedgren-vakten
# --------------------------------------------------------------------------


def krev_hovedgren(gh: Gh, kandidat: Kandidat, *, proveslipp: bool) -> None:
    """Kandidaten skal være på hovedgrenen. Ellers slipper vi ingenting.

    `workflow_dispatch` kan kjøres fra hvilken som helst gren, og uten denne
    vakten kunne en gren som aldri har vært på main bli en offentlig release.
    Sjekken går mot GitHub og ikke mot lokale refs: det er GitHubs hovedgren som
    er fasiten, og en lokal `origin/main` kan være hva som helst.

    Unntaksveien finnes, for prøvekjøringen mot en engangstagg trenger en ekte
    workflow-kjøring for å få en attestasjon. Den er bundet til versjon 0.0.0,
    så en dispatch på feil gren kan aldri slippe en ekte versjon selv om noen
    huker av feil rute.
    """
    if proveslipp:
        if kandidat.versjon != PROVEVERSJON:
            raise Stopp(
                f"prøveslipp gjelder bare versjon {PROVEVERSJON}, men kandidaten er "
                f"{kandidat.versjon}. Ekte versjoner slippes fra hovedgrenen."
            )
        print(f"! Prøveslipp: {kandidat.tag} slippes uten krav om hovedgren.")
        return

    hovedgren = str((gh.api(f"repos/{kandidat.repo}") or {}).get("default_branch") or "main")
    svar = gh.api(f"repos/{kandidat.repo}/compare/{hovedgren}...{kandidat.sha}", tillat_404=True)
    if svar is None:
        raise Stopp(
            f"GitHub kjenner ikke {kandidat.sha[:12]}. Er commiten ikke pushet til {hovedgren}, "
            "finnes det ingenting å slippe."
        )
    # `status` beskriver head mot base: «identical» er hovedgrenens egen spiss,
    # «behind» er en eldre commit på den. «ahead» og «diverged» betyr at det
    # ligger noe her som hovedgrenen ikke har.
    status = str(svar.get("status") or "ukjent")
    if status not in {"identical", "behind"}:
        raise Stopp(
            f"{kandidat.sha[:12]} er ikke på {hovedgren} (status: {status}).\n"
            "Det som går ut til brukerne skal komme fra hovedgrenen. Merge inn først, "
            f"eller kjør en prøveslipp med manifestversjon {PROVEVERSJON}."
        )
    print(f"✓ Kandidaten er på {hovedgren} ({status}).")


# --------------------------------------------------------------------------
# Verifisering
# --------------------------------------------------------------------------


def verifiser_attestasjon(gh: Gh, kandidat: Kandidat, zipfil: Path, digest: str) -> None:
    """Krev at attestasjonen gjelder denne filen, bygget fra denne SHA-en, her.

    `gh` gjør den kryptografiske jobben. Flaggene binder den til repo,
    kilde-SHA og signer-workflow, og vi leser i tillegg subject-digesten ut av
    svaret. Det siste er ikke overflødig: flaggene sier hvem som signerte, ikke
    at det var *denne* ZIP-en de signerte.
    """
    svar = gh.attestasjon(
        [
            "verify",
            str(zipfil),
            "--repo",
            kandidat.repo,
            "--source-digest",
            kandidat.sha,
            "--signer-workflow",
            f"{kandidat.repo}/{SIGNER_WORKFLOW}",
            "--deny-self-hosted-runners",
            "--format",
            "json",
        ]
    )
    if not isinstance(svar, list) or not svar:
        raise Stopp("gh attestation verify ga ingen attestasjoner for ZIP-en")

    digester = {
        emne.get("digest", {}).get("sha256")
        for post in svar
        for emne in post.get("verificationResult", {}).get("statement", {}).get("subject", [])
    }
    if digest not in digester:
        raise Stopp(
            f"attestasjonen gjelder {sorted(d for d in digester if d)}, ikke ZIP-en vi bygget "
            f"({digest}). Tagg, ZIP og attestasjon er da ikke samme artefakt."
        )


def last_ned_asset(gh: Gh, kandidat: Kandidat, asset: dict[str, Any], mal: Path) -> str:
    """Les asset-et tilbake fra GitHub og returner sha256-en av det som ligger der.

    Vi stoler ikke på at opplastingen rapporterte sant. `size` i API-svaret er
    GitHubs eget tall; en avkortet eller byttet fil er bare synlig om vi laster
    ned igjen og regner ut digesten selv.
    """
    innhold = gh.raa(
        f"repos/{kandidat.repo}/releases/assets/{asset['id']}",
        aksept="application/octet-stream",
    )
    mal.write_bytes(innhold)
    return sha256_av(mal)


# --------------------------------------------------------------------------
# Release-body
# --------------------------------------------------------------------------


def hent_release_note(versjon: str, repo_root: Path) -> str:
    """Den korte CHANGELOG-noten, gjennom scripts/release_notes.py.

    Importeres framfor å kjøres som subprosess, så feilene kommer ut som
    unntak med tekst vi kan videreformidle.

    Den korte varianten er det brukerne faktisk leser: HACS viser release-body-en
    i en smal rute inne i Home Assistant, og en seksjon på førti punkter blir
    scrollet forbi. Hele seksjonen står i CHANGELOG.md, som noten lenker til.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import release_notes

    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    try:
        body = release_notes.bygg_kort_body(
            changelog,
            versjon,
            repo_root=repo_root,
            # Historikken merkes ikke i ettertid. Slippes en gammel seksjon om
            # igjen, får den hele teksten sin framfor å stoppe flyten.
            streng=release_notes.er_under_arbeid(changelog, versjon),
        )
    except (
        release_notes.LenkeFeil,
        release_notes.TomKategoriFeil,
        release_notes.UmerketFeil,
    ) as err:
        raise Feil(f"release-noten for {versjon} er ikke klar: {err}") from err
    if body is None:
        raise Feil(
            f"CHANGELOG.md har ingen seksjon '## [{versjon}]' med innhold. "
            "Release-noten skal stå i repoet før versjonen slippes."
        )
    return body


def commits_siden_forrige(git: Git, kandidat: Kandidat) -> str:
    tagger = [t for t in git.tekst("tag", "--sort=-version:refname").splitlines() if t != kandidat.tag]
    spenn = f"{tagger[0]}..{kandidat.sha}" if tagger else kandidat.sha
    logg = git.tekst("log", spenn, "--pretty=format:- %s", "--no-merges")
    return logg or "- Første release"


def bygg_body(git: Git, kandidat: Kandidat, digest: str, repo_root: Path) -> str:
    """Release-body-en: noten fra CHANGELOG, pluss beviset for hva som ligger i ZIP-en.

    Både SHA-en og sha256-en står i teksten, så bindingen mellom tagg, ZIP og
    attestasjon kan leses av et menneske på releasesiden, ikke bare av `gh`.
    """
    url = f"https://github.com/{kandidat.repo}"
    return "\n".join(
        [
            hent_release_note(kandidat.versjon, repo_root),
            "",
            "## Verifisering",
            "",
            f"Bygget fra commit [`{kandidat.sha[:12]}`]({url}/commit/{kandidat.sha}), "
            f"som er commiten taggen `{kandidat.tag}` peker på.",
            "",
            f"**SHA256:** `{digest}` ([hvordan verifisere]({url}/blob/{kandidat.tag}/SECURITY.md))",
            "",
            "<details>",
            "<summary>Alle commits</summary>",
            "",
            commits_siden_forrige(git, kandidat),
            "",
            "</details>",
        ]
    )


def _versjonstall(versjon: str) -> tuple[int, ...]:
    return tuple(int(del_) for del_ in versjon.split("."))


def skal_vaere_latest(gh: Gh, kandidat: Kandidat) -> bool:
    """Eksplisitt make_latest: bare når versjonen er høyere enn den som er latest.

    GitHub sin default er «nyeste publiserte», som gjør en patch på en gammel
    gren til «latest» og sender HACS-brukere bakover. Her er valget et tall vi
    kan lese. Prøveversjonen er aldri latest, uansett hva som ellers ligger ute.
    """
    if kandidat.versjon == PROVEVERSJON:
        return False
    latest = gh.api(f"repos/{kandidat.repo}/releases/latest", tillat_404=True)
    if latest is None:
        return True
    nuvaerende = str(latest.get("tag_name", "")).lstrip("v")
    if not VERSJON_RE.match(nuvaerende):
        return True
    return _versjonstall(kandidat.versjon) > _versjonstall(nuvaerende)


# --------------------------------------------------------------------------
# Tilstandsmaskinen
# --------------------------------------------------------------------------


def sikre_tagg(gh: Gh, kandidat: Kandidat) -> str:
    """Taggen skal peke på kandidat-SHA-en. Den opprettes, eller den stemmer.

    Den flyttes aldri. En tagg som flytter seg, gjør alt som er sagt om eldre
    releaser usant i ettertid, og det er nettopp det denne flyten skal hindre.
    """
    finnes = tag_sha(gh, kandidat)
    if finnes == kandidat.sha:
        return "uendret"
    if finnes is not None:
        raise Stopp(
            f"{kandidat.tag} peker allerede på {finnes}, mens kandidaten er {kandidat.sha}.\n"
            "Taggen flyttes ikke automatisk. Enten er versjonen sluppet fra en annen commit, "
            "eller så skal denne endringen ut som en ny versjon."
        )
    if gh.dry_run:
        return "ville opprettet"
    gh.api(
        f"repos/{kandidat.repo}/git/refs",
        metode="POST",
        data={"ref": f"refs/tags/{kandidat.tag}", "sha": kandidat.sha},
    )
    return "opprettet"


def krev_draft_pa_kandidaten(kandidat: Kandidat, release: dict[str, Any]) -> None:
    """En draft hører til én commit, og den gjenbrukes ikke på en annen.

    Sti: taggen ble dyttet på commit A, publiseringen feilet, et menneske
    slettet taggen men lot draften stå. En ny kjøring på B med samme versjon
    ville da tagget B, gjenbrukt draften fra A, og publisert en body som sier
    «bygget fra commit A, som er commiten taggen peker på». Teksten er det
    eneste brukeren ser, og den ville vært usann.

    Sjekken kjøres før taggen opprettes, så et stopp ikke etterlater nye
    skriverier å rydde. En draft laget for hånd i nettleseren peker på en gren
    og ikke en commit; den har heller ingen body fra oss å lyve med, så den
    slippes gjennom.
    """
    mal = str(release.get("target_commitish") or "")
    if SHA_RE.match(mal) and mal != kandidat.sha:
        raise Stopp(
            f"draften for {kandidat.tag} ble laget for {mal[:12]}, mens kandidaten er "
            f"{kandidat.sha[:12]}.\n"
            "Den gjenbrukes ikke på en annen commit: body-en ville beskrevet noe annet enn "
            "det som ligger i ZIP-en. Slett draften, eller slipp dette som en ny versjon."
        )
    if mal and not SHA_RE.match(mal):
        print(
            f"! Draften peker på «{mal}» og ikke en commit, så den er ikke laget av denne "
            "flyten. Den gjenbrukes som den er.",
            file=sys.stderr,
        )


def sikre_draft(
    gh: Gh, kandidat: Kandidat, release: dict[str, Any] | None, body: str
) -> tuple[dict[str, Any] | None, str]:
    """Draften finnes etterpå, og en som finnes fra før skrives ikke om.

    En draft fra et tidligere forsøk kan være redigert for hånd. Å overskrive
    body-en ville kastet den redigeringen uten at noen ba om det. At draften
    hører til kandidaten, er allerede avgjort av krev_draft_pa_kandidaten.
    """
    if release is not None:
        if release.get("body", "") != body:
            print(
                "! Draften har en annen body enn CHANGELOG gir nå. Den beholdes som den er.",
                file=sys.stderr,
            )
        return release, "gjenbrukt"
    if gh.dry_run:
        return None, "ville opprettet"
    ny = gh.api(
        f"repos/{kandidat.repo}/releases",
        metode="POST",
        data={
            "tag_name": kandidat.tag,
            "target_commitish": kandidat.sha,
            "name": kandidat.tag,
            "body": body,
            "draft": True,
            # En prøvekjøring skal aldri se ut som en versjon noen kan installere.
            "prerelease": kandidat.versjon == PROVEVERSJON,
        },
    )
    return ny, "opprettet"


def sikre_asset(
    gh: Gh, kandidat: Kandidat, release: dict[str, Any], zipfil: Path, digest: str, arbeidsmappe: Path
) -> str:
    """ZIP-en ligger på releasen med riktig sha256 etterpå, eller vi stopper.

    Opplasting som feiler etter at GitHub har tatt imot filen, er den vanlige
    halvveisen: nettverket ryker på svaret, jobben feiler, og neste kjøring ser
    et asset den ikke vet noe om. Derfor leses det alltid tilbake og regnes ut
    på nytt før vi konkluderer.
    """
    eksisterende = [a for a in release.get("assets", []) if a.get("name") == ASSET_NAVN]
    if eksisterende:
        lastet = last_ned_asset(gh, kandidat, eksisterende[0], arbeidsmappe / "readback.zip")
        if lastet == digest:
            return "alt på plass, digest stemmer"
        raise Stopp(
            f"{ASSET_NAVN} på {kandidat.tag} har sha256 {lastet}, men bygget gir {digest}.\n"
            "Filen byttes ikke automatisk: HACS installerer nøyaktig den, og vi vet ikke hva "
            "den inneholder. Slett asset-et bevisst, eller slipp en ny versjon."
        )

    if gh.dry_run:
        return "ville lastet opp"

    url = (
        f"https://uploads.github.com/repos/{kandidat.repo}/releases/{release['id']}/assets?name={ASSET_NAVN}"
    )
    try:
        gh.api(url, metode="POST", fil=zipfil)
    except Feil as err:
        # Kan ha kommet fram likevel. Les tilbake framfor å gjette.
        print(f"! Opplastingen feilet ({err}). Leser tilbake for å se om den kom fram.", file=sys.stderr)

    oppdatert = gh.api(f"repos/{kandidat.repo}/releases/{release['id']}")
    etterpaa = [a for a in oppdatert.get("assets", []) if a.get("name") == ASSET_NAVN]
    if not etterpaa:
        raise Feil(f"{ASSET_NAVN} ble ikke lastet opp til {kandidat.tag}")
    lastet = last_ned_asset(gh, kandidat, etterpaa[0], arbeidsmappe / "readback.zip")
    if lastet != digest:
        raise Stopp(
            f"{ASSET_NAVN} ble lastet opp, men leser tilbake som {lastet} og ikke {digest}. "
            "Ikke publiser dette."
        )
    return "lastet opp og lest tilbake"


@dataclass(frozen=True)
class Sjekk:
    """Ett ledd i beviset for at en publisert release henger sammen."""

    navn: str
    ok: bool
    melding: str
    blokkerende: bool = False

    def __str__(self) -> str:
        return f"{'✓' if self.ok else '!'} {self.navn}: {self.melding}"


def _pakk_ut(sti: Path) -> dict[str, bytes]:
    """Filnavn til innhold. Katalogoppføringer hoppes over.

    `zip -r` legger inn egne oppføringer for hver katalog. Vi gjør ikke det,
    fordi de ikke er innhold. Uten dette ville hver eldre release sett ut som om
    den inneholdt noe annet enn taggen.
    """
    with zipfile.ZipFile(sti) as zipfil:
        return {
            info.filename: zipfil.read(info)
            for info in sorted(zipfil.infolist(), key=lambda i: i.filename)
            if not info.is_dir()
        }


def sjekk_publisert(
    gh: Gh, git: Git, kandidat: Kandidat, release: dict[str, Any], arbeidsmappe: Path
) -> list[Sjekk]:
    """Bevis en publisert versjon mot sin egen tagg, ikke mot ny main.

    Etter en release fortsetter main å bevege seg med uendret manifestversjon,
    så denne flyten kjører igjen på en annen SHA. Det er ingen konflikt, men det
    er heller ingen grunn til å hoppe over uten å se etter. Vi bygger ZIP-en på
    nytt fra taggens egen commit og sammenligner.

    Innholdssjekken er den blokkerende: stemmer ikke filene i ZIP-en med treet
    taggen peker på, installerer brukerne kode som ikke står i taggen, og det er
    en alarm. De to andre er rapport. En release som alt er ute, blir ikke bedre
    av at hver eneste push til main etterpå går rød, og releaser laget før denne
    flyten kan ikke være byte-like: de ble pakket med `zip -r` fra arbeidstreet,
    så tidsstempler og rettigheter kom fra runneren.
    """
    sha = tag_sha(gh, kandidat)
    if sha is None:
        return [
            Sjekk("tagg", False, f"{kandidat.tag} finnes ikke, så releasen kan ikke bevises mot en commit")
        ]
    sjekker = [Sjekk("tagg", True, f"{kandidat.tag} peker på {sha[:12]}")]

    eksisterende = [a for a in release.get("assets", []) if a.get("name") == ASSET_NAVN]
    if not eksisterende:
        sjekker.append(
            Sjekk(
                "innhold",
                False,
                f"releasen mangler {ASSET_NAVN}, så HACS har ingenting å hente. "
                "Reparer bevisst, eller slipp en ny versjon.",
                blokkerende=True,
            )
        )
        return sjekker

    fra_tagg = arbeidsmappe / "fra-tagg.zip"
    lest = arbeidsmappe / "publisert.zip"
    forventet_digest = bygg_zip(git, sha, fra_tagg)
    faktisk_digest = last_ned_asset(gh, kandidat, eksisterende[0], lest)

    if faktisk_digest == forventet_digest:
        sjekker.append(Sjekk("innhold", True, f"byte-lik et nytt bygg av {sha[:12]} ({faktisk_digest})"))
    else:
        fasit, publisert = _pakk_ut(fra_tagg), _pakk_ut(lest)
        if fasit == publisert:
            sjekker.append(
                Sjekk(
                    "innhold",
                    True,
                    f"filene er de samme som i {sha[:12]}, men ZIP-en er ikke byte-lik "
                    "(pakket før flyten ble deterministisk)",
                )
            )
        else:
            avvik = sorted(set(fasit) ^ set(publisert)) or [
                navn for navn in fasit if fasit[navn] != publisert.get(navn)
            ]
            sjekker.append(
                Sjekk(
                    "innhold",
                    False,
                    f"ZIP-en er ikke koden taggen peker på. Avvik: {', '.join(avvik[:5])}",
                    blokkerende=True,
                )
            )
            return sjekker

    taggens = Kandidat(repo=kandidat.repo, sha=sha, versjon=kandidat.versjon)
    try:
        verifiser_attestasjon(gh, taggens, lest, faktisk_digest)
    except Stopp as err:
        sjekker.append(Sjekk("attestasjon", False, str(err).replace("\n", " ")))
    else:
        sjekker.append(Sjekk("attestasjon", True, f"dekker ZIP-en og kildecommit {sha[:12]}"))
    return sjekker


def kjor(
    *,
    git: Git,
    gh: Gh,
    kandidat: Kandidat,
    arbeidsmappe: Path,
    repo_root: Path,
    zipfil: Path | None,
    bare_plan: bool,
    krev_attestasjon: bool,
    streng: bool = False,
    proveslipp: bool = False,
) -> int:
    """Selve tilstandsmaskinen. Publisering er siste kall, alltid."""
    print(f"Kandidat: {kandidat}")
    release = finn_release(gh, kandidat)

    if streng and (release is None or release.get("draft", False)):
        raise Stopp(
            f"{kandidat.tag} er ikke publisert ({'ligger som draft' if release else 'finnes ikke'}), "
            "så det er ingenting å etterprøve."
        )

    if release is not None and not release.get("draft", False):
        print(f"{kandidat.tag} er allerede publisert. Beviser den mot sin egen tagg.")
        sjekker = sjekk_publisert(gh, git, kandidat, release, arbeidsmappe)
        for sjekk in sjekker:
            print(f"  {sjekk}")
        verre = [s for s in sjekker if not s.ok and (s.blokkerende or streng)]
        if verre:
            raise Stopp(
                f"{kandidat.tag} er publisert, men henger ikke sammen:\n  "
                + "\n  ".join(s.melding for s in verre)
            )
        if any(not s.ok for s in sjekker):
            print(f"! {kandidat.tag} er ute som den er. Kjør `verify` for hele bildet.")
        print(f"Ingenting å gjøre for {kandidat.versjon}.")
        skriv_utfall(utfall="noop", versjon=kandidat.versjon, tag=kandidat.tag, sha=kandidat.sha)
        return EXIT_OK

    # Vakten står her og ikke lenger opp med vilje: en versjon som alt er ute,
    # bevises mot sin egen tagg, og den commiten trenger ikke ligge på
    # hovedgrenen i dag (v1.16.0 gjør ikke det). Det er bare veien til en *ny*
    # release som er sperret.
    krev_hovedgren(gh, kandidat, proveslipp=proveslipp)
    if release is not None:
        krev_draft_pa_kandidaten(kandidat, release)

    skriv_utfall(utfall="klar", versjon=kandidat.versjon, tag=kandidat.tag, sha=kandidat.sha)

    if zipfil is None:
        zipfil = arbeidsmappe / ASSET_NAVN
        digest = bygg_zip(git, kandidat.sha, zipfil)
    else:
        digest = sha256_av(zipfil)
        forventet = bygg_zip(git, kandidat.sha, arbeidsmappe / "kontroll.zip")
        if digest != forventet:
            raise Stopp(
                f"ZIP-en som ble gitt har sha256 {digest}, men en ny bygging av {kandidat.sha[:12]} "
                f"gir {forventet}. Da er ikke filen bygget fra kandidaten."
            )
    print(f"ZIP: {digest}")

    if krev_attestasjon:
        verifiser_attestasjon(gh, kandidat, zipfil, digest)
        print("✓ Attestasjonen dekker denne ZIP-en, bygget fra kandidat-SHA-en av release.yml")
    else:
        print("- Hopper over attestasjonssjekken: `plan` kjøres før ZIP-en er attestert.")

    body = bygg_body(git, kandidat, digest, repo_root)
    latest = skal_vaere_latest(gh, kandidat)

    if bare_plan:
        print(f"Tagg: {sikre_tagg(gh, kandidat)}")
        print(f"Draft: {'gjenbrukes' if release else 'opprettes'}")
        assets = [a.get("name") for a in (release or {}).get("assets", [])]
        print(f"Asset: {'ligger alt der' if ASSET_NAVN in assets else 'lastes opp'}")
        print(f"make_latest: {str(latest).lower()}")
        print("Tørrkjøring: ingenting ble skrevet.")
        return EXIT_OK

    print(f"Tagg {kandidat.tag} på {kandidat.sha[:12]}: {sikre_tagg(gh, kandidat)}")
    release, hva = sikre_draft(gh, kandidat, release, body)
    print(f"Draft: {hva}")
    assert release is not None
    print(f"Asset: {sikre_asset(gh, kandidat, release, zipfil, digest, arbeidsmappe)}")

    gh.api(
        f"repos/{kandidat.repo}/releases/{release['id']}",
        metode="PATCH",
        data={"draft": False, "make_latest": str(latest).lower()},
    )
    print(f"✓ Publisert {kandidat.tag} (make_latest={str(latest).lower()})")
    return EXIT_OK


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def skriv_utfall(**felt: str) -> None:
    """Legg utfallet i $GITHUB_OUTPUT når vi kjører i Actions.

    Workflowen må vite forskjell på «publisert fra før» og «klar til å slippes»
    uten å lese loggteksten, ellers ender vi med en grep mot norsk prosa som
    styrer om en release går ut.
    """
    sti = os.environ.get("GITHUB_OUTPUT")
    if not sti:
        return
    with open(sti, "a", encoding="utf-8") as ut:
        for navn, verdi in felt.items():
            ut.write(f"{navn}={verdi}\n")


def standard_repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY", "fredrik-lindseth/Stromkalkulator")


def lag_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT, help="git-roten (default: dette repoet)")
    under = parser.add_subparsers(dest="kommando", required=True)

    bygg = under.add_parser("build", help="bygg deterministisk ZIP fra en SHA")
    bygg.add_argument("--sha", default="HEAD", help="commit ZIP-en bygges fra (default: HEAD)")
    bygg.add_argument("--output", type=Path, default=Path("dist") / ASSET_NAVN)

    for navn, hjelp in (
        ("plan", "les tilstanden, skriv ingenting"),
        ("verify", "etterprøv en publisert release mot taggen sin"),
        ("publish", "kjør flyten"),
    ):
        sub = under.add_parser(navn, help=hjelp)
        sub.add_argument("--sha", default="HEAD")
        sub.add_argument("--repo", default=standard_repo())
        sub.add_argument("--zip", type=Path, default=None, help="ferdigbygget ZIP (kontrolleres mot SHA)")
        sub.add_argument("--arbeidsmappe", type=Path, default=None)
        if navn in {"plan", "publish"}:
            sub.add_argument(
                "--proveslipp",
                action="store_true",
                help=f"prøvekjøring utenfor hovedgrenen, krever manifestversjon {PROVEVERSJON}",
            )
        if navn == "publish":
            sub.add_argument("--dry-run", action="store_true", help="som plan: leser, skriver ikke")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = lag_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    git = Git(repo_root)

    try:
        if args.kommando == "build":
            digest = bygg_zip(git, full_sha(git, args.sha), args.output)
            print(digest)
            return EXIT_OK

        bare_plan = args.kommando in {"plan", "verify"} or getattr(args, "dry_run", False)
        # `plan` kjøres før attestasjonen finnes (lokalt, eller før byggesteget).
        # `publish --dry-run` kjøres der den skal finnes, og skal felle om den ikke gjør det.
        krev_attestasjon = args.kommando != "plan"
        arbeidsmappe = args.arbeidsmappe or repo_root / "dist"
        arbeidsmappe.mkdir(parents=True, exist_ok=True)
        return kjor(
            git=git,
            gh=Gh(args.repo, dry_run=bare_plan),
            kandidat=les_kandidat(git, args.repo, args.sha),
            arbeidsmappe=arbeidsmappe,
            repo_root=repo_root,
            zipfil=args.zip,
            bare_plan=bare_plan,
            krev_attestasjon=krev_attestasjon,
            streng=args.kommando == "verify",
            proveslipp=getattr(args, "proveslipp", False),
        )
    except Stopp as err:
        print(f"STOPP: {err}", file=sys.stderr)
        return EXIT_STOPP
    except Feil as err:
        print(f"FEIL: {err}", file=sys.stderr)
        return EXIT_FEIL


if __name__ == "__main__":
    sys.exit(main())
