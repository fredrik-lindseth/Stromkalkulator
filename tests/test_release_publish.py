"""Releaseflyten: at tagg, ZIP og attestasjon er samme artefakt, og at et
avbrutt forsøk kan kjøres om igjen uten å etterlate en halv release.

Oppsettet er med vilje ikke en mock-karusell. `gh` byttes ut med
`tests/falsk_gh.py`, en liten GitHub-etterligning som *husker* tilstand mellom
kall, så et avbrudd kan etterlate nøyaktig den halvferdige tilstanden neste
kjøring må rydde opp i. `git` er derimot ekte, og kjører mot et ferskt repo i
tmp_path: det er selve git-objektene ZIP-en bygges fra, og en stub av dem ville
bevist at stubben er deterministisk, ikke at bygget er det.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import release_publish  # noqa: E402

REPONAVN = "eier/Stromkalkulator"
VERSJON = "9.9.9"
TAG = f"v{VERSJON}"

CHANGELOG = f"""# Endringer

## [{VERSJON}]

### Fikset

- En ting, med [en lenke](docs/noe.md)
"""

KOMPONENT = "custom_components/stromkalkulator"


# --------------------------------------------------------------------------
# Fixturer
# --------------------------------------------------------------------------


def _git(rot: Path, *argv: str) -> str:
    miljo = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.invalid",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.invalid",
        "GIT_CONFIG_GLOBAL": str(rot / ".gitconfig-tom"),
        "GIT_CONFIG_SYSTEM": str(rot / ".gitconfig-tom"),
    }
    res = subprocess.run(
        ["git", "-C", str(rot), *argv], capture_output=True, text=True, check=True, env=miljo
    )
    return res.stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Et ekte lite git-repo med komponent, CHANGELOG og den lenkede filen."""
    rot = tmp_path / "repo"
    (rot / KOMPONENT / "translations").mkdir(parents=True)
    (rot / "docs").mkdir()
    (rot / KOMPONENT / "manifest.json").write_text(
        json.dumps({"domain": "stromkalkulator", "version": VERSJON}) + "\n"
    )
    (rot / KOMPONENT / "__init__.py").write_text("# integrasjonen\n")
    (rot / KOMPONENT / "sensor.py").write_text("SENSOR = 1\n")
    (rot / KOMPONENT / "translations" / "nb.json").write_text('{"title": "Strømkalkulator"}\n')
    (rot / "docs" / "noe.md").write_text("# Noe\n")
    (rot / "CHANGELOG.md").write_text(CHANGELOG)
    (rot / "README.md").write_text("ikke med i zipen\n")
    _git(rot, "init", "-q", "-b", "main")
    _git(rot, "add", "-A")
    _git(rot, "commit", "-q", "-m", "alt")
    return rot


@pytest.fixture
def sha(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


class FalskGitHub:
    """Tilstanden den falske GitHub-en holder, sett fra testen."""

    def __init__(self, sti: Path) -> None:
        self.sti = sti

    def les(self) -> dict:
        return json.loads(self.sti.read_text())

    def skriv(self, tilstand: dict) -> None:
        self.sti.write_text(json.dumps(tilstand, indent=1))

    @property
    def releaser(self) -> list[dict]:
        return self.les()["releaser"]

    def release(self, tag: str = TAG) -> dict | None:
        return next((r for r in self.releaser if r["tag_name"] == tag), None)

    def asset_innhold(self, tag: str = TAG) -> bytes:
        release = self.release(tag)
        assert release is not None
        (asset,) = release["assets"]
        return bytes.fromhex(self.les()["assets"][asset["id"]])

    def tagg(self, tag: str = TAG) -> dict | None:
        return self.les()["tags"].get(tag)

    def sett_tagg(self, tag: str, sha: str) -> None:
        tilstand = self.les()
        tilstand["tags"][tag] = {"type": "commit", "sha": sha}
        self.skriv(tilstand)

    def attester(self, digest: str, sha: str, workflow: str | None = None) -> None:
        tilstand = self.les()
        tilstand["attestasjoner"].append(
            {
                "digest": digest,
                "sha": sha,
                "repo": REPONAVN,
                "workflow": workflow or f"{REPONAVN}/{release_publish.SIGNER_WORKFLOW}",
            }
        )
        self.skriv(tilstand)

    def kall(self, monster: str) -> list[str]:
        return [k for k in self.les()["kall"] if re.search(monster, k)]


@pytest.fixture
def github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FalskGitHub:
    """Legg en `gh` på PATH som snakker med en tilstandsfil vi kan se inn i."""
    tilstand = tmp_path / "github.json"
    tilstand.write_text(
        json.dumps(
            {
                "repo": REPONAVN,
                "tags": {},
                "annoterte": {},
                "releaser": [],
                "assets": {},
                "attestasjoner": [],
                "neste_id": 100,
                "kall": [],
            }
        )
    )
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    skall = bin_ / "gh"
    skall.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{REPO / "tests" / "falsk_gh.py"}" "$@"\n')
    skall.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("GH_TILSTAND", str(tilstand))
    monkeypatch.delenv("GH_FEIL", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    return FalskGitHub(tilstand)


def kjor(repo: Path, *argv: str) -> int:
    return release_publish.main(["--repo-root", str(repo), *argv])


def publiser(repo: Path, sha: str, *ekstra: str) -> int:
    return kjor(repo, "publish", "--sha", sha, "--repo", REPONAVN, *ekstra)


def bygg(repo: Path, sha: str, mal: Path) -> str:
    return release_publish.bygg_zip(release_publish.Git(repo), sha, mal)


@pytest.fixture
def attestert(repo: Path, sha: str, github: FalskGitHub, tmp_path: Path) -> str:
    """Digesten for kandidaten, med en gyldig attestasjon registrert."""
    digest = bygg(repo, sha, tmp_path / "forhaand.zip")
    github.attester(digest, sha)
    return digest


# --------------------------------------------------------------------------
# Deterministisk bygg
# --------------------------------------------------------------------------


def test_to_uavhengige_bygg_gir_byte_lik_zip(repo: Path, sha: str, tmp_path: Path) -> None:
    """Uten dette er «samme artefakt» en påstand ingen kan etterprøve."""
    forste = tmp_path / "en" / "stromkalkulator.zip"
    andre = tmp_path / "to" / "stromkalkulator.zip"
    assert bygg(repo, sha, forste) == bygg(repo, sha, andre)
    assert forste.read_bytes() == andre.read_bytes()


def test_bygget_tar_bare_sporede_komponentfiler(repo: Path, sha: str, tmp_path: Path) -> None:
    """Usporet søppel i arbeidstreet skal ikke kunne bli med ut til brukerne."""
    (repo / KOMPONENT / "hemmelig.txt").write_text("usporet\n")
    (repo / KOMPONENT / "__pycache__").mkdir()
    (repo / KOMPONENT / "__pycache__" / "x.pyc").write_bytes(b"\x00")

    mal = tmp_path / "stromkalkulator.zip"
    bygg(repo, sha, mal)
    with zipfile.ZipFile(mal) as zipfil:
        navn = sorted(zipfil.namelist())
        tider = {info.date_time for info in zipfil.infolist()}
        rettigheter = {info.external_attr >> 16 for info in zipfil.infolist()}

    assert navn == ["__init__.py", "manifest.json", "sensor.py", "translations/nb.json"]
    assert "README.md" not in navn, "ZIP-en skal pakkes flatt fra komponentkatalogen"
    assert tider == {release_publish.ZIP_TID[:6]}
    assert rettigheter == {0o644}


def test_bygget_folger_sha_en_og_ikke_arbeidstreet(repo: Path, sha: str, tmp_path: Path) -> None:
    """Endringer som ikke er committet, hører ikke til kandidaten."""
    fasit = bygg(repo, sha, tmp_path / "fasit.zip")
    (repo / KOMPONENT / "sensor.py").write_text("SENSOR = 'endret uten commit'\n")
    assert bygg(repo, sha, tmp_path / "etterpaa.zip") == fasit


# --------------------------------------------------------------------------
# Fersk publisering
# --------------------------------------------------------------------------


def test_fersk_publisering_binder_tagg_zip_og_attestasjon(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    assert publiser(repo, sha) == release_publish.EXIT_OK

    assert github.tagg() == {"type": "commit", "sha": sha}
    release = github.release()
    assert release is not None
    assert release["draft"] is False
    assert release["target_commitish"] == sha
    assert hashlib.sha256(github.asset_innhold()).hexdigest() == attestert
    assert sha[:12] in release["body"], "SHA-en skal stå i noten, ikke bare i loggen"
    assert attestert in release["body"]
    assert "En ting" in release["body"], "CHANGELOG-seksjonen skal være body-en"


def test_uten_attestasjon_blir_ingenting_publisert(repo: Path, sha: str, github: FalskGitHub) -> None:
    """Ingen attestasjon, ingen release. Og ingen draft eller tagg å rydde."""
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.releaser == []
    assert github.tagg() is None


def test_attestasjon_pa_en_annen_commit_stopper(
    repo: Path, sha: str, github: FalskGitHub, tmp_path: Path
) -> None:
    """Nøyaktig feilen v1.16.0 har: ZIP-en er bygget fra en annen commit."""
    digest = bygg(repo, sha, tmp_path / "z.zip")
    github.attester(digest, sha="0" * 40)
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.releaser == []


def test_attestasjon_fra_feil_workflow_stopper(
    repo: Path, sha: str, github: FalskGitHub, tmp_path: Path
) -> None:
    digest = bygg(repo, sha, tmp_path / "z.zip")
    github.attester(digest, sha, workflow=f"{REPONAVN}/.github/workflows/noe-annet.yml")
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.releaser == []


def test_zip_som_ikke_er_bygget_fra_kandidaten_stopper(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, tmp_path: Path
) -> None:
    """`--zip` gir en ferdig fil. Den kontrolleres mot et nytt bygg av SHA-en."""
    fremmed = tmp_path / "fremmed.zip"
    with zipfile.ZipFile(fremmed, "w") as zipfil:
        zipfil.writestr("__init__.py", "noe annet")
    assert publiser(repo, sha, "--zip", str(fremmed)) == release_publish.EXIT_STOPP
    assert github.releaser == []


# --------------------------------------------------------------------------
# Gjenopptak
# --------------------------------------------------------------------------


def test_gjenopptak_etter_avbrutt_opplasting_bytter_ikke_riktig_asset(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filen kom fram, svaret gjorde ikke. Neste kjøring skal se det, ikke laste opp på nytt."""
    monkeypatch.setenv("GH_FEIL", "upload_etter_lagring,publish")
    assert publiser(repo, sha) != release_publish.EXIT_OK

    halvveis = github.release()
    assert halvveis is not None and halvveis["draft"] is True, "ingen offentlig release etter avbrudd"
    (asset,) = halvveis["assets"]

    monkeypatch.delenv("GH_FEIL")
    opplastinger_for = len(github.kall("uploads.github.com"))
    assert publiser(repo, sha) == release_publish.EXIT_OK

    ferdig = github.release()
    assert ferdig is not None
    assert ferdig["draft"] is False
    assert [a["id"] for a in ferdig["assets"]] == [asset["id"]], "det korrekte asset-et ble byttet"
    assert len(github.kall("uploads.github.com")) == opplastinger_for, "lastet opp på nytt unødig"
    assert hashlib.sha256(github.asset_innhold()).hexdigest() == attestert


def test_gjenopptak_etter_feilet_publisering(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_FEIL", "publish")
    assert publiser(repo, sha) == release_publish.EXIT_FEIL
    assert github.release()["draft"] is True

    monkeypatch.delenv("GH_FEIL")
    assert publiser(repo, sha) == release_publish.EXIT_OK
    assert github.release()["draft"] is False
    assert len(github.releaser) == 1, "gjenopptaket lagde en release nummer to"


def test_gjenopptak_gjenbruker_draften_og_skriver_ikke_over_body(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """En draft kan være redigert for hånd. Gjenopptak er ikke en grunn til å kaste det."""
    monkeypatch.setenv("GH_FEIL", "publish")
    publiser(repo, sha)
    tilstand = github.les()
    tilstand["releaser"][0]["body"] = "håndredigert"
    github.skriv(tilstand)

    monkeypatch.delenv("GH_FEIL")
    assert publiser(repo, sha) == release_publish.EXIT_OK
    assert github.release()["body"] == "håndredigert"


def test_korrupt_opplasting_stopper_framfor_a_publisere(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GH_FEIL", "upload_korrupt")
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.release()["draft"] is True, "en korrupt ZIP ble publisert"


def test_asset_med_annen_digest_byttes_ikke_automatisk(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HACS installerer nøyaktig denne filen. Vi vet ikke hva den er, så vi stopper."""
    monkeypatch.setenv("GH_FEIL", "upload_korrupt")
    publiser(repo, sha)
    forrige = github.asset_innhold()

    monkeypatch.delenv("GH_FEIL")
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.asset_innhold() == forrige, "det ukjente asset-et ble overskrevet"
    assert github.release()["draft"] is True


# --------------------------------------------------------------------------
# Tagger
# --------------------------------------------------------------------------


def test_tagg_pa_en_annen_sha_stopper_og_flyttes_ikke(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    github.sett_tagg(TAG, "1" * 40)
    assert publiser(repo, sha) == release_publish.EXIT_STOPP
    assert github.tagg()["sha"] == "1" * 40, "taggen ble flyttet"
    assert github.releaser == []


def test_tagg_fra_forrige_forsok_gjenbrukes(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    """Jobben feilet etter at taggen var dyttet. Den er riktig, og skal stå."""
    github.sett_tagg(TAG, sha)
    assert publiser(repo, sha) == release_publish.EXIT_OK
    assert github.kall("POST repos/.*/git/refs") == [], "forsøkte å opprette en tagg som fantes"


def test_annotert_tagg_derefereres(repo: Path, sha: str, github: FalskGitHub, attestert: str) -> None:
    """En annotert tagg peker på et tag-objekt. Uten dereferering ser den feil ut."""
    tilstand = github.les()
    tilstand["tags"][TAG] = {"type": "tag", "sha": "abc123"}
    tilstand["annoterte"]["abc123"] = sha
    github.skriv(tilstand)
    assert publiser(repo, sha) == release_publish.EXIT_OK


# --------------------------------------------------------------------------
# Allerede publisert
# --------------------------------------------------------------------------


def test_publisert_versjon_er_en_verifisert_noop(
    repo: Path, sha: str, github: FalskGitHub, attestert: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert publiser(repo, sha) == release_publish.EXIT_OK
    capsys.readouterr()

    # Main flytter seg videre med uendret manifestversjon. Ny commit, samme versjon.
    (repo / "README.md").write_text("noe nytt\n")
    _git(repo, "commit", "-qam", "etterpå")
    ny_sha = _git(repo, "rev-parse", "HEAD")

    assert publiser(repo, ny_sha) == release_publish.EXIT_OK
    ut = capsys.readouterr().out
    assert "Ingenting å gjøre" in ut
    assert "innhold" in ut and "tagg" in ut
    assert len(github.releaser) == 1


def test_publisert_release_uten_zip_stopper(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    """HACS har ingenting å hente. Det skal ikke gå stille forbi."""
    publiser(repo, sha)
    tilstand = github.les()
    tilstand["releaser"][0]["assets"] = []
    github.skriv(tilstand)
    assert publiser(repo, sha) == release_publish.EXIT_STOPP


def test_publisert_zip_med_feil_innhold_stopper(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    publiser(repo, sha)
    tilstand = github.les()
    (asset,) = tilstand["releaser"][0]["assets"]
    tilstand["assets"][asset["id"]] = _tom_zip().hex()
    github.skriv(tilstand)
    assert publiser(repo, sha) == release_publish.EXIT_STOPP


def _tom_zip() -> bytes:
    import io

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipfil:
        zipfil.writestr("__init__.py", "noe helt annet")
    return buffer.getvalue()


def test_verify_feller_der_plan_bare_advarer(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    """Eldre releaser kan ikke være byte-like. Da skal main ikke gå rød av dem,
    men `verify` skal fortsatt si fra."""
    publiser(repo, sha)
    tilstand = github.les()
    tilstand["attestasjoner"] = []
    github.skriv(tilstand)

    assert kjor(repo, "plan", "--sha", sha, "--repo", REPONAVN) == release_publish.EXIT_OK
    assert kjor(repo, "verify", "--sha", sha, "--repo", REPONAVN) == release_publish.EXIT_STOPP


def test_verify_pa_noe_som_ikke_er_sluppet_stopper(
    repo: Path, sha: str, github: FalskGitHub, attestert: str
) -> None:
    assert kjor(repo, "verify", "--sha", sha, "--repo", REPONAVN) == release_publish.EXIT_STOPP


# --------------------------------------------------------------------------
# Tørrkjøring og utfall
# --------------------------------------------------------------------------


def test_torrkjoring_skriver_ingenting(repo: Path, sha: str, github: FalskGitHub, attestert: str) -> None:
    assert publiser(repo, sha, "--dry-run") == release_publish.EXIT_OK
    assert github.releaser == []
    assert github.tagg() is None
    assert [k for k in github.les()["kall"] if k.startswith(("POST", "PATCH", "DELETE"))] == []


def test_plan_melder_utfallet_maskinlesbart(
    repo: Path,
    sha: str,
    github: FalskGitHub,
    attestert: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Workflowen skal ikke måtte grep-e norsk prosa for å vite om den skal bygge."""
    utfil = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(utfil))

    assert kjor(repo, "plan", "--sha", sha, "--repo", REPONAVN) == release_publish.EXIT_OK
    assert "utfall=klar\n" in utfil.read_text()

    publiser(repo, sha)
    utfil.write_text("")
    assert kjor(repo, "plan", "--sha", sha, "--repo", REPONAVN) == release_publish.EXIT_OK
    assert "utfall=noop\n" in utfil.read_text()


def test_make_latest_settes_eksplisitt(repo: Path, sha: str, github: FalskGitHub, attestert: str) -> None:
    """GitHub sin default gjør en gammel patch til «latest». Valget skal være vårt."""
    tilstand = github.les()
    tilstand["releaser"].append({"id": "1", "tag_name": "v99.0.0", "draft": False, "assets": [], "body": ""})
    github.skriv(tilstand)

    assert publiser(repo, sha) == release_publish.EXIT_OK
    assert github.release()["make_latest"] == "false"


# --------------------------------------------------------------------------
# Workflow og justfile
# --------------------------------------------------------------------------


def test_release_workflow_venter_pa_hele_ci_grafen() -> None:
    """HACS og Hassfest skal være med i det releasen venter på, ikke ved siden av."""
    ci = yaml.safe_load((REPO / ".github" / "workflows" / "ci.yml").read_text())
    release = yaml.safe_load((REPO / ".github" / "workflows" / "release.yml").read_text())

    assert {"test-unit", "check", "test-ha", "hacs", "hassfest"} <= set(ci["jobs"])
    # PyYAML leser den nakne nøkkelen `on` som True.
    assert "workflow_call" in ci[True], "ci.yml kan ikke kalles av release.yml"

    assert release["jobs"]["ci"]["uses"] == "./.github/workflows/ci.yml"
    assert release["jobs"]["release"]["needs"] == ["ci"]
    assert "workflow_run" not in release[True], (
        "workflow_run gir ikke releasen kontroll over hvilken commit som testes"
    )
    assert release["concurrency"]["cancel-in-progress"] is False


def test_workflowen_publiserer_til_slutt_og_attesterer_for_opplasting() -> None:
    """Rekkefølgen i filen er halve garantien. Endres den, er den ikke atomisk lenger."""
    steg = yaml.safe_load((REPO / ".github" / "workflows" / "release.yml").read_text())["jobs"]["release"][
        "steps"
    ]
    navn = [s.get("name", s.get("uses", "")) for s in steg]
    tekst = " ".join(str(s.get("run", "")) + str(s.get("uses", "")) for s in steg)

    assert navn.index("Bygg deterministisk ZIP") < navn.index("Attester bygget")
    assert navn.index("Attester bygget") < navn.index("Verifiser og publiser")
    assert "release_publish.py publish" in tekst
    assert "action-gh-release" not in tekst, (
        "action-gh-release publiserer med én gang og tar ikke target_commitish"
    )


def test_justfile_og_workflow_kaller_samme_kjerne() -> None:
    """Én flyt, ikke en for CI og en for hånd."""
    justfile = (REPO / "justfile").read_text()
    workflow = (REPO / ".github" / "workflows" / "release.yml").read_text()

    i_just = set(re.findall(r"release_publish\.py (\w+)", justfile))
    i_workflow = set(re.findall(r"release_publish\.py (\w+)", workflow))
    assert {"build", "plan", "verify"} <= i_just
    assert i_workflow <= i_just | {"publish"}
    assert "release-plan" in justfile and "release-zip" in justfile
