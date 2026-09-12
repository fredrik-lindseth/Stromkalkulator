#!/usr/bin/env python3
"""En liten GitHub-etterligning, brukt som `gh` av tests/test_release_publish.py.

Den er ikke en mock som returnerer ferdige svar. Den holder tilstand (tagger,
releaser, assets, attestasjoner) i en JSON-fil, så en test kan kjøre flyten,
avbryte den midt i, og kjøre den om igjen mot den tilstanden avbruddet
etterlot. Det er hele poenget: gjenopptak kan ikke testes mot noe som ikke
husker forrige forsøk.

Feil sprøytes inn med `GH_FEIL`, en kommaliste:

    upload_etter_lagring   filen tas imot, så ryker svaret (den klassiske)
    upload_korrupt         filen tas imot, men det lagres noe annet
    publish                PATCH til draft=false feiler
    attest                 attestasjonsverifisering feiler

Hvert kall logges i `kall`, så testene kan slå fast at et gjenopptak *ikke*
lastet opp på nytt.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

TILSTAND = Path(os.environ["GH_TILSTAND"])


def les() -> dict:
    return json.loads(TILSTAND.read_text())


def skriv(tilstand: dict) -> None:
    TILSTAND.write_text(json.dumps(tilstand, indent=1))


def feil_aktiv(navn: str) -> bool:
    return navn in os.environ.get("GH_FEIL", "").split(",")


def svar(data) -> None:
    print(json.dumps(data))
    sys.exit(0)


def http_feil(kode: int, melding: str) -> None:
    print(f"gh: {melding} (HTTP {kode})", file=sys.stderr)
    sys.exit(1)


def parse_api(argv: list[str]) -> tuple[str, str, str | None, list[str]]:
    """(metode, sti, --input-verdi, accept-headere)."""
    metode, sti, inn, headere = "GET", None, None, []
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--method":
            metode, i = argv[i + 1], i + 2
        elif arg == "--input":
            inn, i = argv[i + 1], i + 2
        elif arg in {"-H", "--header"}:
            headere.append(argv[i + 1])
            i += 2
        elif arg == "--paginate":
            i += 1
        else:
            sti, i = arg, i + 1
    assert sti is not None, f"fant ingen sti i {argv}"
    return metode, sti, inn, headere


def kropp(inn: str | None) -> dict:
    if inn == "-":
        return json.loads(sys.stdin.buffer.read())
    return {}


def api(argv: list[str]) -> None:
    metode, sti, inn, headere = parse_api(argv)
    tilstand = les()
    tilstand["kall"].append(f"{metode} {sti}")
    skriv(tilstand)
    biter = sti.split("?")[0].rstrip("/").split("/")

    # GET repos/R/releases/assets/<id> med octet-stream: innholdet, rått.
    if any("octet-stream" in h for h in headere):
        innhold = tilstand["assets"].get(biter[-1])
        if innhold is None:
            http_feil(404, "Not Found")
        sys.stdout.buffer.write(bytes.fromhex(innhold))
        sys.exit(0)

    if sti.startswith("https://uploads.github.com/"):
        release = finn_release_id(tilstand, biter[biter.index("releases") + 1])
        navn = sti.split("name=")[1]
        data = Path(inn).read_bytes() if inn else b""
        if feil_aktiv("upload_korrupt"):
            data = b"noe helt annet"
        asset_id = str(tilstand["neste_id"])
        tilstand["neste_id"] += 1
        tilstand["assets"][asset_id] = data.hex()
        release["assets"].append({"id": asset_id, "name": navn})
        skriv(tilstand)
        if feil_aktiv("upload_etter_lagring"):
            http_feil(502, "Bad Gateway")
        svar({"id": asset_id, "name": navn})

    if biter[-2:] == ["git", "refs"] and metode == "POST":
        data = kropp(inn)
        tag = data["ref"].removeprefix("refs/tags/")
        if tag in tilstand["tags"]:
            http_feil(422, "Reference already exists")
        tilstand["tags"][tag] = {"type": "commit", "sha": data["sha"]}
        skriv(tilstand)
        svar({"ref": data["ref"], "object": tilstand["tags"][tag]})

    if "git" in biter and "ref" in biter and "tags" in biter:
        tag = biter[-1]
        if tag not in tilstand["tags"]:
            http_feil(404, "Not Found")
        svar({"ref": f"refs/tags/{tag}", "object": tilstand["tags"][tag]})

    if biter[-3:-1] == ["git", "tags"] or (len(biter) > 2 and biter[-2] == "tags" and "git" in biter):
        pekt = tilstand["annoterte"].get(biter[-1])
        if pekt is None:
            http_feil(404, "Not Found")
        svar({"object": {"type": "commit", "sha": pekt}})

    if biter[-1] == "releases" and metode == "GET":
        svar(tilstand["releaser"])

    if biter[-1] == "latest":
        publiserte = [r for r in tilstand["releaser"] if not r["draft"]]
        if not publiserte:
            http_feil(404, "Not Found")
        svar(publiserte[-1])

    if biter[-1] == "releases" and metode == "POST":
        data = kropp(inn)
        ny = {
            "id": str(tilstand["neste_id"]),
            "tag_name": data["tag_name"],
            "target_commitish": data.get("target_commitish"),
            "name": data.get("name"),
            "body": data.get("body", ""),
            "draft": bool(data.get("draft")),
            "assets": [],
        }
        tilstand["neste_id"] += 1
        tilstand["releaser"].append(ny)
        skriv(tilstand)
        svar(ny)

    if len(biter) >= 2 and biter[-2] == "releases":
        release = finn_release_id(tilstand, biter[-1])
        if metode == "GET":
            svar(release)
        if metode == "PATCH":
            if feil_aktiv("publish"):
                http_feil(500, "Internal Server Error")
            release.update(kropp(inn))
            skriv(tilstand)
            svar(release)

    http_feil(404, f"falsk gh kjenner ikke {metode} {sti}")


def finn_release_id(tilstand: dict, release_id: str) -> dict:
    for release in tilstand["releaser"]:
        if release["id"] == release_id:
            return release
    http_feil(404, "Not Found")
    raise AssertionError  # uoppnåelig, http_feil avslutter


def attestation(argv: list[str]) -> None:
    tilstand = les()
    tilstand["kall"].append("attestation verify")
    skriv(tilstand)
    if feil_aktiv("attest"):
        print("Error: verification failed", file=sys.stderr)
        sys.exit(1)

    fil = Path(argv[1])
    flagg = {argv[i]: argv[i + 1] for i in range(len(argv)) if argv[i].startswith("--") and i + 1 < len(argv)}
    digest = hashlib.sha256(fil.read_bytes()).hexdigest()

    treff = [
        a for a in tilstand["attestasjoner"] if a["digest"] == digest and a["repo"] == flagg.get("--repo")
    ]
    if not treff:
        print(f"Error: no attestations found for {digest}", file=sys.stderr)
        sys.exit(1)
    kilde = flagg.get("--source-digest")
    if kilde and treff[0]["sha"] != kilde:
        print(
            f"Error: expected SourceRepositoryDigest to be {kilde}, got {treff[0]['sha']}",
            file=sys.stderr,
        )
        sys.exit(1)
    signer = flagg.get("--signer-workflow")
    if signer and treff[0]["workflow"] != signer:
        print(f"Error: expected signer workflow {signer}", file=sys.stderr)
        sys.exit(1)
    svar(
        [
            {
                "verificationResult": {
                    "statement": {"subject": [{"name": fil.name, "digest": {"sha256": digest}}]},
                    "signature": {"certificate": {"sourceRepositoryDigest": treff[0]["sha"]}},
                }
            }
        ]
    )


if __name__ == "__main__":
    if sys.argv[1] == "api":
        api(sys.argv[2:])
    elif sys.argv[1] == "attestation":
        attestation(sys.argv[2:])
    else:
        print(f"falsk gh kjenner ikke {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
