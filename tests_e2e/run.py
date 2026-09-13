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
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fixture import ROOT, load_fixture, reconcile_june

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"
MARKER = "stromkalkulator-e2e-v1"
# Utgaven oppgraderingsveien starter på. Taggen, ikke en SHA i teksten: da er
# det den brukerne faktisk har installert som blir testet, også etter en
# rebase. Se docs/testing.md.
SLUPPET = "v1.16.0"
# Døgnmaks i formen v1.16.0 selv skrev den. Datoene er i inneværende måned, for
# en toppdag fra forrige måned hører til `previous_month_top_3` og skal ikke
# telle i den nye måneden.
TOPPDAGER = {
    "{maaned}-02": {"kw": 6.4, "hour": 17},
    "{maaned}-05": {"kw": 5.1, "hour": 8},
    "{maaned}-09": {"kw": 4.75, "hour": 19},
}
TOPPDAGER_FORRIGE = {
    "2026-08-04": {"kw": 9.2, "hour": 18},
    "2026-08-17": {"kw": 8.1, "hour": 7},
    "2026-08-23": {"kw": 7.6, "hour": 20},
}
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
        felt = ("project", "sha", "zip_sha256", "image", "fixture", "fra_sha", "fra_versjon")
        (destination / "version.json").write_text(
            json.dumps({key: self.state[key] for key in felt if key in self.state}, indent=2)
        )
        try:
            log = self.compose("logs", "--no-color", "--tail", "2000", timeout=30)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            log = str(exc)
        (destination / "ha.log").write_text(redact(log, values))

    def versjon(self) -> str:
        return str(json.loads((self.directory / "integration/manifest.json").read_text())["version"])

    def oppgrader(self, revisjon: str) -> None:
        """Bytt den installerte utgaven under en HA som står stille.

        HA leser `custom_components` én gang ved oppstart, så filene må byttes
        mellom stopp og start. Gjøres det mens containeren kjører, laster HA
        fortsatt den gamle modulen fra minnet, og «oppgraderingen» ville vært
        en omstart av samme kode.
        """
        fra_sha, fra_versjon = self.state["sha"], self.versjon()
        self.compose("stop", "ha", timeout=90)
        sha, zip_sha256 = installer(self.directory, revisjon)
        self.state.update(sha=sha, zip_sha256=zip_sha256, fra_sha=fra_sha, fra_versjon=fra_versjon)
        (self.directory / "lab.json").write_text(json.dumps(self.state, indent=2))
        self.compose("start", "ha", timeout=180)
        print(f"Oppgradert fra {fra_versjon} ({fra_sha[:8]}) til {self.versjon()} ({sha[:8]})", flush=True)

    def lagring(self, entry_id: str) -> Path:
        return self.directory / "config/.storage" / f"stromkalkulator_{entry_id}"

    def skriv_lagring(self, entry_id: str, endringer: dict) -> None:
        """Endre nøkler HA alt har skrevet, mens HA står stille.

        Bare eksisterende nøkler kan endres. Skal en test si noe om en gammel
        lagringsfil, må formen komme fra utgaven som faktisk skrev den, ikke
        fra en håndskrevet etterligning av den.
        """
        fil = self.lagring(entry_id)
        lagret = json.loads(fil.read_text())
        ukjent = sorted(set(endringer) - set(lagret["data"]))
        if ukjent:
            raise ValueError(f"Nøkler som ikke står i lagringsfilen: {ukjent}")
        lagret["data"].update(endringer)
        fil.write_text(json.dumps(lagret))

    def entry_data(self, entry_id: str, endringer: dict) -> None:
        """Skriv om et config entry slik en eldre utgave etterlot det.

        Config-flowen i dag setter satsen fra katalogen og lar den ikke drifte.
        Den tilstanden vi vil prøve, den lagrede satsen som ikke er katalogens,
        kan bare komme fra en fil skrevet av en eldre utgave. Da skriver vi
        filen framfor å bygge en flow som ikke finnes.
        """
        fil = self.directory / "config/.storage/core.config_entries"
        lagret = json.loads(fil.read_text())
        for entry in lagret["data"]["entries"]:
            if entry["entry_id"] == entry_id:
                entry["data"] = {**entry["data"], **endringer}
                fil.write_text(json.dumps(lagret))
                return
        raise ValueError(f"Fant ikke config entry {entry_id}")

    def les_state(self) -> dict:
        return json.loads((self.directory / "config/e2e-state.json").read_text())

    def down(self) -> None:
        # Only Compose-owned containers/network. Keep the temp config recoverable;
        # never upload it (contains this disposable user's credentials and storage).
        self.compose("down", "--timeout", "45", "--remove-orphans", timeout=90)
        print(f"Stoppet {self.project}. Midlertidig config er beholdt i {self.directory}.")


def installer(directory: Path, revisjon: str) -> tuple[str, str]:
    """Legg en committet utgave i lab-mappens integrasjonskatalog.

    Selve katalogen gjenbrukes, for den er bind-montert inn i containeren.
    Byttes den ut med en ny katalog, peker monteringen på en inode som ikke
    finnes lenger, og oppgraderingen ville testet en tom integrasjon.
    """
    sha = command(["git", "rev-parse", f"{revisjon}^{{commit}}"]).strip()
    archive = directory / "stromkalkulator.zip"
    command([sys.executable, "scripts/release_publish.py", "build", "--sha", sha, "--output", str(archive)])
    target = directory / "integration"
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(archive) as zipped:
        for item in zipped.infolist():
            if not (target / item.filename).resolve().is_relative_to(target):
                raise ValueError("Ugyldig sti i release-ZIP")
        for child in sorted(target.iterdir()):
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        zipped.extractall(target)
    if not (target / "manifest.json").is_file():
        raise ValueError("Release-ZIP mangler manifest.json i roten")
    return sha, hashlib.sha256(archive.read_bytes()).hexdigest()


def prepare(args: argparse.Namespace) -> Lab:
    command(["docker", "info"], timeout=20)
    command(["docker", "compose", "version"], timeout=20)
    fixture = load_fixture(args.fixture)
    reference = reconcile_june(fixture)
    directory = Path(tempfile.mkdtemp(prefix="strom-e2e-")).resolve()
    config = directory / "config"
    config.mkdir(mode=0o700)
    (config / "custom_components").mkdir()
    shutil.copyfile(HERE / "configuration.yaml", config / "configuration.yaml")
    (directory / "fixture.json").write_text(json.dumps({**fixture, "reference": reference}))
    # `--fra` installerer en eldre utgave først; da er `--sha` det oppgraderingen
    # lander på, og lab.json bærer begge slik evidensen viser hele veien.
    sha, zip_sha256 = installer(directory, getattr(args, "fra", None) or args.sha)
    state = {
        "marker": MARKER,
        "directory": str(directory),
        "project": f"strom-e2e-{uuid.uuid4().hex[:12]}",
        "port": args.port,
        "sha": sha,
        "zip_sha256": zip_sha256,
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


def oppgraderingsveien(lab: Lab, args: argparse.Namespace) -> None:
    """Bygg et anlegg på den gamle utgaven, bytt utgave, og se om noe falt ut.

    Rekkefølgen er brukerens: BKK fra katalogen og et anlegg på Egendefinert
    settes opp med den gamle koden, akkumulatorene kjøres opp, en forrige måned
    legges inn i lagringsfilen den gamle koden selv skrev, og først da kommer
    dagens utgave. Alt annet ville testet dagens kode mot dagens kode.
    """
    lab.driver("test_onboarding")
    lab.driver("test_onboarding_egendefinert")
    lab.driver("seed_akkumulatorer", timeout=600)
    tilstand = lab.les_state()
    lab.compose("stop", "ha", timeout=90)
    maaned = datetime.now().strftime("%Y-%m")
    toppdager = {key.format(maaned=maaned): value for key, value in TOPPDAGER.items()}
    for entry_id in tilstand["utganger"]:
        lab.skriv_lagring(
            entry_id,
            {
                "previous_month_name": "2026-08",
                "previous_month_consumption": {"dag": 612.5, "natt": 421.125},
                "previous_month_cost": 1875.5,
                "previous_month_kapasitetsledd": 415.0,
                "previous_month_top_3": TOPPDAGER_FORRIGE,
                # Døgnmaks bokføres først når en klokketime er ferdig, så en
                # lab som lever i minutter har ingen. Uten disse ville
                # oppgraderingstesten sammenlignet Ukjent med Ukjent.
                "daily_max_power": toppdager,
            },
        )
    lab.compose("start", "ha", timeout=180)
    lab.driver("merk_oppgraderingsstart")
    lab.driver("checkpoint_oppgradering", timeout=600)
    lab.oppgrader(args.sha)
    lab.driver("test_oppgradering_beholder_akkumulatorene", timeout=600)
    lab.driver("test_baselinen_forkastes_en_gang")
    lab.driver("test_fastleddet_er_et_periodebelop")
    lab.driver("test_statistikken_folger_skiftet")
    lab.driver("test_egendefinert_uten_fastledd", timeout=600)
    lab.driver("test_satsvarsel_kun_ved_avvik")
    # Motprøven: skru den lagrede satsen bort fra katalogen slik en v1-migrering
    # etterlot den, og se at varselet da faktisk kommer.
    lab.compose("stop", "ha", timeout=90)
    lab.entry_data(
        tilstand["entry_id"],
        {"energiledd_dag": 0.5555, "energiledd_natt": 0.4444, "tariffmodus": "legacy_unconfirmed"},
    )
    lab.compose("start", "ha", timeout=180)
    lab.driver("test_satsvarsel_etter_avvik")


def vent(lab: Lab, minutter: float) -> None:
    lab.driver("vent_paa_grace", "--minutter", str(minutter), timeout=int(minutter * 60) + 300)


def vaktholdet(lab: Lab, args: argparse.Namespace) -> None:
    """Provoser feilene som skal varsle, og tilfellene som ikke skal.

    Utfallene måles i ekte tid, for terskelen er ekte tid. Et utfall kan ikke
    jukses fram her: skal laben si noe om et ekte utfall, må det vare like
    lenge som et ekte et. Frossen teller og strømbrudd seedes derimot gjennom
    lagringsfilen HA selv skrev, for begge handler om hva klokken sto på da HA
    startet, og det er nettopp det filen bærer.

    Grunnkjøringen venter ut grace-vinduet og lander på rundt 40 minutter.
    Spotcachen på to timer er den ene dyre biten, og den er avskrudd som
    default: `--cache-minutter 95` tar den med, og da tar kjøringen over to
    timer. Rangeringen mellom `spot_utfall` og utfallsraden er alt voktet i
    `tests/test_vakthold.py`, så den lange turen er en slippport og ikke noe
    man kjører hver dag.

    Template-sensorene i laben gjenoppstår ved omstart, så en omstart midt i
    et utfall friskmelder inputene. Omstartsvakten prøves derfor for seg, før
    utfallet.
    """
    lab.driver("test_onboarding")
    lab.driver("test_energy_increase")
    lab.driver("test_vakthold_stille_naar_alt_er_friskt")
    lab.driver("test_maalerbytte_varsler_ikke", timeout=600)
    lab.driver("test_sprang_varsler_med_riktig_sensor")
    lab.compose("restart", "ha", timeout=180)
    lab.driver("test_vakthold_tier_rett_etter_omstart")

    lab.driver("outage_han")
    lab.driver("outage_spot")
    lab.driver("test_vakthold_tier_innenfor_grace")
    vent(lab, args.minutter)
    lab.driver("test_vakthold_varsler_etter_grace")
    if args.cache_minutter > 0:
        # Spotprisen har fortsatt en fersk nok cache, så den meldes som utfall
        # og ikke som utløpt. Først når cachen er eldre enn to timer tar
        # spot_utfall over, og da skal utfallsraden for spot forsvinne.
        vent(lab, args.cache_minutter)
        lab.driver("test_vakthold_spot_utlopt")
    lab.driver("test_vakthold_delvis_friskmelding")
    lab.driver("test_vakthold_friskmelding")

    tilstand = lab.les_state()
    entry_id = tilstand["entry_id"]
    lab.compose("stop", "ha", timeout=90)
    naa = datetime.now(UTC)
    lab.skriv_lagring(
        entry_id,
        {
            "last_energy_increase": (naa - timedelta(hours=9)).isoformat(),
            "last_update": naa.isoformat(),
        },
    )
    lab.compose("start", "ha", timeout=180)
    lab.driver("test_frossen_teller_varsles")

    lab.compose("stop", "ha", timeout=90)
    naa = datetime.now(UTC)
    lab.skriv_lagring(
        entry_id,
        {
            "last_energy_increase": (naa - timedelta(hours=9)).isoformat(),
            "last_update": (naa - timedelta(hours=9)).isoformat(),
        },
    )
    lab.compose("start", "ha", timeout=180)
    lab.driver("test_strombrudd_er_ikke_frossen_teller")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "action", choices=("run", "up", "upgrade", "vakthold", "replay", "scenario", "down", "cleanup")
    )
    result.add_argument("--target", choices=("current",), default="current")
    result.add_argument("--sha", default="HEAD", help="Kun committet kode pakkes av releasebyggeren")
    result.add_argument(
        "--fra", default=SLUPPET, help="Utgaven `upgrade` starter på (default: taggen v1.16.0)"
    )
    result.add_argument(
        "--minutter", type=float, default=32.0, help="Ekte minutter `vakthold` venter ut grace-vinduet"
    )
    result.add_argument(
        "--cache-minutter",
        type=float,
        default=0.0,
        help="Ekte minutter til på toppen så spotcachen rekker å bli gammel. 95 tar med spot_utfall",
    )
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
    if args.minutter < 0:
        raise ValueError("Ugyldig ventetid")
    lab = None
    keep = False
    try:
        if args.action in ("run", "up", "upgrade", "vakthold"):
            # `upgrade` er den eneste som installerer noe annet enn `--sha`
            # først; de andre skal ikke kunne arve en `--fra` ved en glipp.
            args.fra = args.fra if args.action == "upgrade" else None
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
            elif args.action == "upgrade":
                oppgraderingsveien(lab, args)
            elif args.action == "vakthold":
                vaktholdet(lab, args)
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
