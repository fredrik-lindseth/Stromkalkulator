"""Own one disposable Compose project, built from a committed release ZIP.

Host side uses the standard library only. The API driver runs inside the HA
container, which already supplies aiohttp. No production URL is accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
import zipfile
from pathlib import Path

from fixture import ROOT, load_fixture, reconcile_june

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
MARKER = "stromkalkulator-e2e-v1"
IMAGE = "ghcr.io/home-assistant/home-assistant:2026.9.2@sha256:542890f4a7ef9269b7a5ac23ada303b327537c62fa0f866e49daebc61cb44caa"


def command(args: list[str], *, timeout: int = 180, env: dict | None = None) -> str:
    result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f"{args[0]} feilet ({result.returncode}): {result.stderr[-3000:]}")
    return result.stdout


def redact(text: str, secret_values: tuple[str, ...] = ()) -> str:
    for value in secret_values:
        if value:
            text = text.replace(value, "<redacted>")
    text = re.sub(r"(?i)(bearer\s+)[\w.~-]+", r"\1<redacted>", text)
    text = re.sub(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "<redacted>", text)
    return re.sub(
        r"""(?i)((?:access_token|refresh_token|password|auth_code)["']?\s*[:=]\s*["']?)[^\s,}"']+""",
        r"\1<redacted>",
        text,
    )


class Lab:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()
        self.state = json.loads((self.directory / "lab.json").read_text())
        project = self.state.get("project", "")
        if self.state.get("marker") != MARKER or not re.fullmatch(r"strom-e2e-[a-f0-9]{12}", project):
            raise ValueError("Dette er ikke en testlab laget av harnesset")
        if self.state.get("directory") != str(self.directory):
            raise ValueError("Flyttet/feil lab-mappe; nekter å styre et annet Compose-prosjekt")
        self.project = project
        self.env = {
            **os.environ,
            "E2E_RUN_DIR": str(self.directory),
            "E2E_HARNESS": str(HERE),
            "E2E_PORT": str(self.state["port"]),
        }

    def compose(self, *args: str, timeout: int = 180) -> str:
        return command(
            [
                "docker",
                "compose",
                "--project-name",
                self.project,
                "--file",
                str(HERE / "compose.yaml"),
                *args,
            ],
            timeout=timeout,
            env=self.env,
        )

    def driver(self, *args: str, timeout: int = 900) -> None:
        # Driver output is limited to named checks and counts; tokens stay on disk.
        print(
            self.compose("exec", "-T", "ha", "python", "/harness/driver.py", *args, timeout=timeout),
            end="",
            flush=True,
        )

    def evidence(self) -> None:
        destination = ARTIFACTS / self.project
        destination.mkdir(parents=True, exist_ok=True)
        credentials = self.directory / "config/e2e-auth.json"
        values = tuple(json.loads(credentials.read_text()).values()) if credentials.exists() else ()
        for filename in ("trace.jsonl", "report.json"):
            source = self.directory / "config" / filename
            if source.exists():
                (destination / filename).write_text(redact(source.read_text(), values))
        (destination / "version.json").write_text(
            json.dumps(
                {key: self.state[key] for key in ("project", "sha", "zip_sha256", "image", "fixture")},
                indent=2,
            )
        )
        try:
            log = self.compose("logs", "--no-color", "--tail", "2000", timeout=30)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            log = str(exc)
        (destination / "ha.log").write_text(redact(log, values))

    def down(self) -> None:
        # Only Compose-owned containers/network. Keep the temp config recoverable;
        # never upload it (contains this disposable user's credentials and storage).
        self.compose("down", "--timeout", "45", "--remove-orphans", timeout=90)
        print(f"Stoppet {self.project}. Midlertidig config er beholdt i {self.directory}.")


def prepare(args: argparse.Namespace) -> Lab:
    command(["docker", "info"], timeout=20)
    command(["docker", "compose", "version"], timeout=20)
    fixture = load_fixture(args.fixture)
    reference = reconcile_june(fixture)
    directory = Path(tempfile.mkdtemp(prefix="strom-e2e-")).resolve()
    config = directory / "config"
    config.mkdir(mode=0o700)
    (directory / "integration").mkdir()
    (config / "custom_components").mkdir()
    shutil.copyfile(HERE / "configuration.yaml", config / "configuration.yaml")
    (directory / "fixture.json").write_text(json.dumps({**fixture, "reference": reference}))
    sha = command(["git", "rev-parse", f"{args.sha}^{{commit}}"]).strip()
    archive = directory / "stromkalkulator.zip"
    command([sys.executable, "scripts/release_publish.py", "build", "--sha", sha, "--output", str(archive)])
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            target = directory / "integration" / item.filename
            if not target.resolve().is_relative_to(directory / "integration"):
                raise ValueError("Ugyldig sti i release-ZIP")
        zipped.extractall(directory / "integration")
    if not (directory / "integration/manifest.json").is_file():
        raise ValueError("Release-ZIP mangler manifest.json i roten")
    state = {
        "marker": MARKER,
        "directory": str(directory),
        "project": f"strom-e2e-{uuid.uuid4().hex[:12]}",
        "port": args.port,
        "sha": sha,
        "zip_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "image": IMAGE,
        "fixture": fixture["name"],
    }
    (directory / "lab.json").write_text(json.dumps(state, indent=2))
    auth = config / "e2e-auth.json"
    auth.write_text(json.dumps({"username": "testlab", "password": secrets.token_urlsafe(24)}))
    auth.chmod(0o600)
    ARTIFACTS.mkdir(exist_ok=True)
    (ARTIFACTS / "active-lab.txt").write_text(str(directory))
    print(f"Testlab: {directory}\nCommit: {sha}", flush=True)
    return Lab(directory)


def lifecycle(lab: Lab, args: argparse.Namespace) -> None:
    lab.driver("test_onboarding")
    lab.driver("test_energy_increase")
    lab.driver("checkpoint_restart")
    lab.compose("restart", "ha", timeout=90)
    lab.driver("test_restart_no_double_booking")
    for scenario in (
        "test_meter_change",
        "test_remove_optional",
        "test_invalid_unit_recovery",
        "test_missing_input_recovery",
        "test_meter_jump",
    ):
        lab.driver(scenario)
    lab.driver("replay", "--tick", str(args.tick), timeout=1200)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", choices=("run", "up", "replay", "scenario", "down", "cleanup"))
    result.add_argument("--target", choices=("current",), default="current")
    result.add_argument("--sha", default="HEAD", help="Kun committet kode pakkes av releasebyggeren")
    result.add_argument("--fixture", default="juni_2026")
    result.add_argument("--port", type=int, default=0, help="0 gir ledig loopback-port")
    result.add_argument("--run-dir", type=Path)
    result.add_argument(
        "--tick", type=float, default=0.05, help="Sekunder per fixture-time, pluss HA-kvittering"
    )
    result.add_argument("--name", default="test_energy_increase")
    result.add_argument(
        "--force-failure", action="store_true", help="Feil etter server-onboarding for cleanup-test"
    )
    return result


def main() -> int:
    args = parser().parse_args()
    if args.tick < 0 or not 0 <= args.port <= 65535:
        raise ValueError("Ugyldig tick eller port")
    lab = None
    keep = False
    try:
        if args.action in ("run", "up"):
            lab = prepare(args)
            lab.compose("up", "--detach", "--wait", "--wait-timeout", "180", timeout=600)
            lab.driver("bootstrap")
            if args.force_failure:
                raise AssertionError("Tvunget feil: kontroller cleanup og redigerte artifacts")
            if args.action == "up":
                lab.driver("test_onboarding")
                address = lab.compose("port", "ha", "8123").strip()
                print(f"Åpne http://{address}. Lokal pålogging: {lab.directory}/config/e2e-auth.json")
                print(f"Spill av: python3 tests_e2e/run.py replay --run-dir {lab.directory}")
                print(f"Stopp: python3 tests_e2e/run.py down --run-dir {lab.directory}")
                keep = True
            else:
                lifecycle(lab, args)
        else:
            directory = args.run_dir
            if args.action == "cleanup" and directory is None:
                active = ARTIFACTS / "active-lab.txt"
                if not active.exists():
                    return 0
                directory = Path(active.read_text().strip())
            if directory is None:
                raise ValueError("--run-dir kreves")
            lab = Lab(directory)
            keep = args.action in ("replay", "scenario")
            if args.action == "replay":
                lab.driver("replay", "--tick", str(args.tick), timeout=1200)
            elif args.action == "scenario":
                lab.driver(args.name, timeout=1200)
        return 0
    except (RuntimeError, ValueError, AssertionError, OSError, subprocess.TimeoutExpired) as exc:
        print(redact(str(exc)), file=sys.stderr)
        return 1
    finally:
        if lab is not None:
            try:
                lab.evidence()
            finally:
                if not keep:
                    lab.down()


def interrupted(_signum: int, _frame: object) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupted)
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
