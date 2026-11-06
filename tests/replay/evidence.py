"""Numeriske kontrollresultater og proveniens uten rå måledata eller miljøvariabler."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def digest(path: Path) -> str:
    """SHA-256 av filinnholdet, ikke mtime eller et tidligere testresultat."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _command(root: Path, *args: str) -> str:
    # Pre-push kan eksportere arbeidsrepoets indeks og metadata. Proveniensen
    # gjelder root, ikke en GIT_DIR/GIT_INDEX_FILE arvet fra en hook.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    return subprocess.check_output(args, cwd=root, env=env, text=True, stderr=subprocess.DEVNULL).strip()


def provenance(root: Path) -> dict:
    """Bind kilde, offentlige fixturer og lockfil til denne kjøringen."""
    tracked = _command(root, "git", "ls-files", "-z").split("\0")
    # Nye kildefiler må inngå også før commit. Rapporter/venv/private filer skal
    # ikke inngå, og ingen innhold eller lokale absoluttstier havner i JSON-en.
    untracked = _command(root, "git", "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    source = set(tracked) | {
        p for p in untracked if p.startswith(("tests/", "scripts/", "custom_components/", ".github/"))
    }
    hashes = {}
    for name in sorted(source):
        if not name or name.startswith(("_private/", "dist/")):
            continue
        path = root / name
        hashes[name] = digest(path) if path.is_file() and not path.is_symlink() else "missing-or-symlink"
    fixtures = {
        p.relative_to(root).as_posix(): digest(p)
        for p in sorted((root / "tests/fixtures").rglob("*"))
        if p.is_file() and not p.is_symlink() and "__pycache__" not in p.parts
    }
    return {
        "commit_sha": _command(root, "git", "rev-parse", "HEAD"),
        "source_clean": not bool(_command(root, "git", "status", "--porcelain", "--untracked-files=normal")),
        "source_key": hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
        "fixtures": fixtures,
        "lock_sha256": digest(root / "uv.lock"),
    }


def versions(root: Path) -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in ("pytest", "pytest-cov"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = "not-installed"
    for name in ("uv", "just"):
        try:
            result[name] = _command(root, name, "--version")
        except (OSError, subprocess.CalledProcessError):
            result[name] = "not-available"
    return result


def measurement(*, nodeid, month, metric, expected, actual, tolerance, unit, comparison="abs_le") -> dict:
    """Registrer nøyaktig grense og fortegnet avvik før testens assert."""
    actual, tolerance = float(actual), float(tolerance)
    if not math.isfinite(actual) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError("Evidence requires finite values and a nonnegative tolerance")
    if comparison in ("range_inclusive", "range_exclusive"):
        lower, upper = map(float, expected)
        if not all(map(math.isfinite, (lower, upper))) or lower > upper or tolerance != 0:
            raise ValueError("Evidence interval must be ordered, finite, and have tolerance=0")
        expected = [lower, upper]
        deviation = actual - min(max(actual, lower), upper)
        passed = lower <= actual <= upper if comparison == "range_inclusive" else lower < actual < upper
    elif comparison in ("abs_le", "abs_lt"):
        expected = float(expected)
        if not math.isfinite(expected):
            raise ValueError("Evidence requires a finite expectation")
        deviation = actual - expected
        passed = abs(deviation) <= tolerance if comparison == "abs_le" else abs(deviation) < tolerance
    else:
        raise ValueError(f"Unsupported evidence comparison: {comparison}")
    return {
        "nodeid": nodeid,
        "month": month,
        "metric": metric,
        "expected": expected,
        "actual": actual,
        "deviation": deviation,
        "tolerance": tolerance,
        "unit": unit,
        "comparison": comparison,
        "status": "passed" if passed else "failed",
    }


def inventory_result(required: dict, collected: set, tests: dict, results: list) -> dict:
    """Et grønt utvalg kan aldri erstatte hele det eksplisitte inventaret."""
    expected = set(required)
    executed = {n for n in expected if tests.get(n, {}).get("executed", False)}
    skipped = {n for n in expected if tests.get(n, {}).get("status") == "skipped"}
    failed = {n for n in expected if tests.get(n, {}).get("status") == "failed"}
    months: dict[str, set] = {}
    for row in results:
        months.setdefault(row["nodeid"], set()).add(row["month"])
        if row["status"] != "passed" and row["nodeid"] in expected:
            failed.add(row["nodeid"])
    missing_evidence = {n for n, wanted in required.items() if not set(wanted) <= months.get(n, set())}
    return {
        "expected": sorted(expected),
        "executed": sorted(executed),
        "missing": sorted(expected - executed),
        "skipped": sorted(skipped),
        "uncollected": sorted(expected - collected),
        "missing_evidence": sorted(missing_evidence),
        "failed": sorted(failed),
    }


def inventory_failed(inventory: dict) -> bool:
    return any(inventory[k] for k in ("missing", "skipped", "uncollected", "missing_evidence", "failed"))


def write_reports(directory: Path, report: dict) -> None:
    """JSON, ren resultatlogg og JUnit med samme numeriske evidens.

    Loggen og XML-en gjengir ikke captured stdout, tracebacks eller miljøet.
    """
    directory.mkdir(parents=True, exist_ok=True)
    rows_by_test: dict[str, list] = {}
    for row in report["results"]:
        rows_by_test.setdefault(row["nodeid"], []).append(row)
    suite = ET.Element("testsuite", name="domain-evidence")
    log = [f"status={report['status']} commit={report['commit_sha']} source={report['source_key']}"]
    failures = skips = 0
    for test in report["tests"]:
        nodeid = test["nodeid"]
        case = ET.SubElement(suite, "testcase", name=nodeid, time=str(test["duration_seconds"]))
        if test["status"] == "failed":
            ET.SubElement(case, "failure", message="pytest or domain assertion failed")
            failures += 1
        elif test["status"] == "skipped":
            ET.SubElement(case, "skipped")
            skips += 1
        if nodeid in rows_by_test:
            ET.SubElement(case, "system-out").text = json.dumps(rows_by_test[nodeid], sort_keys=True)
        log.append(f"{test['status']} {nodeid}")
    if report["status"] == "failed":
        case = ET.SubElement(suite, "testcase", name="full-domain-validation")
        ET.SubElement(case, "failure", message="Incomplete or failed validation; see JSON inventory")
        failures += 1
    suite.set("tests", str(len(suite)))
    suite.set("failures", str(failures))
    suite.set("skipped", str(skips))
    ET.indent(suite)
    ET.ElementTree(suite).write(
        directory / "domain-evidence-junit.xml", encoding="utf-8", xml_declaration=True
    )
    log.extend(json.dumps(row, sort_keys=True) for row in report["results"])
    log.append("inventory=" + json.dumps(report["inventory"], sort_keys=True))
    (directory / "domain-evidence.log").write_text("\n".join(log) + "\n")
    report["file_sha256"] = {
        name: digest(directory / name) for name in ("domain-evidence.log", "domain-evidence-junit.xml")
    }
    (directory / "domain-evidence.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
