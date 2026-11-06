"""Validate and package the invoice evidence produced by the candidate CI run."""

from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

FILES = ("domain-evidence.json", "domain-evidence.log", "domain-evidence-junit.xml")
ASSET = "domain-evidence.zip"


class EvidenceError(ValueError):
    """Evidence is missing, corrupt, or does not prove the candidate."""


def validate(files: dict[str, bytes], sha: str) -> dict[str, Any]:
    """Check report consistency and file digests; the inventory itself is CI-supplied."""
    if set(files) != set(FILES):
        raise EvidenceError(f"forventet nøyaktig {FILES}, fikk {sorted(files)}")
    try:
        report = json.loads(files[FILES[0]])
        if not isinstance(report, dict):
            raise ValueError("rapporten er ikke et objekt")
        if report.get("schema_version") != 1 or report.get("commit_sha") != sha:
            raise ValueError("feil skjemaversjon eller kandidat-SHA")
        if report.get("source_clean") is not True or report.get("source_changed_during_run") is not False:
            raise ValueError("kilden er skitten eller endret under kjøringen")
        if report.get("status") != "passed":
            raise ValueError("testkjøringen besto ikke")
        for key in ("source_key", "lock_sha256"):
            if not isinstance(report.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", report[key]):
                raise ValueError(f"ugyldig {key}")
        for key in ("fixtures", "versions", "commands"):
            if not report.get(key):
                raise ValueError(f"mangler {key}")
        inventory = report["inventory"]
        expected, executed = inventory["expected"], inventory["executed"]
        if (
            inventory["required"] is not True
            or not expected
            or not isinstance(expected, list)
            or not isinstance(executed, list)
        ):
            raise ValueError("obligatorisk inventar mangler")
        if len(set(expected)) != len(expected) or set(expected) != set(executed):
            raise ValueError("inventaret ble ikke kjørt komplett")
        for key in ("missing", "skipped", "uncollected", "missing_evidence", "failed"):
            if inventory[key] != []:
                raise ValueError(f"inventar {key} er ikke tom")
        results = report["results"]
        if not isinstance(results, list) or not results or set(expected) - {r["nodeid"] for r in results}:
            raise ValueError("faktiske fakturaresultater mangler")
        for result in results:
            if result["status"] != "passed" or not all(
                result.get(k) is not None
                for k in (
                    "nodeid",
                    "month",
                    "metric",
                    "expected",
                    "actual",
                    "deviation",
                    "tolerance",
                    "unit",
                    "comparison",
                )
            ):
                raise ValueError("ugyldig fakturaresultat")
            actual, deviation, tolerance = (float(result[k]) for k in ("actual", "deviation", "tolerance"))
            if not all(math.isfinite(n) for n in (actual, deviation, tolerance)) or tolerance < 0:
                raise ValueError("ugyldig fakturaverdi")
            comparison = result["comparison"]
            expected_value = result["expected"]
            if comparison in ("abs_le", "abs_lt"):
                expected_number = float(expected_value)
                calculated = actual - expected_number
                passed = (
                    abs(calculated) <= tolerance if comparison == "abs_le" else abs(calculated) < tolerance
                )
            elif comparison in ("range_inclusive", "range_exclusive"):
                lower, upper = map(float, expected_value)
                if not all(math.isfinite(n) for n in (lower, upper)) or lower > upper or tolerance != 0:
                    raise ValueError("ugyldig intervall")
                calculated = actual - min(max(actual, lower), upper)
                passed = (
                    lower <= actual <= upper if comparison == "range_inclusive" else lower < actual < upper
                )
            else:
                raise ValueError("ukjent sammenligning")
            if (
                not math.isfinite(calculated)
                or not math.isclose(calculated, deviation, abs_tol=1e-9)
                or not passed
            ):
                raise ValueError("måleresultatet stemmer ikke med grensen")
        tests = report["tests"]
        if not isinstance(tests, list) or any(t["status"] not in {"passed", "skipped"} for t in tests):
            raise ValueError("ugyldig eller feilet testresultat")
        nodeids = [t["nodeid"] for t in tests]
        if len(nodeids) != len(set(nodeids)) or set(expected) - {
            t["nodeid"] for t in tests if t["status"] == "passed"
        }:
            raise ValueError("beståtte testresultater mangler")
        hashes = report["file_sha256"]
        for name in FILES[1:]:
            if not files[name] or hashes[name] != hashlib.sha256(files[name]).hexdigest():
                raise ValueError(f"filen {name} mangler eller har feil digest")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as err:
        raise EvidenceError(f"ugyldig fakturabevis: {err}") from err
    return report


def from_directory(path: Path, sha: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    try:
        entries = list(path.iterdir())
        if any(p.is_symlink() or not p.is_file() for p in entries):
            raise EvidenceError("bevismappen skal bare inneholde vanlige filer")
        files = {p.name: p.read_bytes() for p in entries}
    except OSError as err:
        raise EvidenceError(f"kan ikke lese fakturabevis i {path}: {err}") from err
    return files, validate(files, sha)


def write_zip(files: dict[str, bytes], path: Path) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])


def from_zip(path: Path, sha: str) -> dict[str, Any]:
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != set(FILES):
                raise EvidenceError("ZIP har feil eller dupliserte filer")
            return validate({name: archive.read(name) for name in names}, sha)
    except (OSError, zipfile.BadZipFile, RuntimeError) as err:
        raise EvidenceError(f"kan ikke lese bevis-ZIP: {err}") from err


def same_source(first: dict[str, Any], second: dict[str, Any]) -> bool:
    """Allow reruns with different durations, but only with identical source and requirements."""
    return all(
        first[key] == second[key] for key in ("commit_sha", "source_key", "fixtures", "lock_sha256")
    ) and set(first["inventory"]["expected"]) == set(second["inventory"]["expected"])
