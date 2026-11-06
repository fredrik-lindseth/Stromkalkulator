"""Release evidence must prove the candidate and survive a readback."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_evidence as evidence


@pytest.fixture
def files() -> dict[str, bytes]:
    log, xml = b"test log", b"<testsuite/>"
    report = {
        "schema_version": 1,
        "commit_sha": "a" * 40,
        "source_clean": True,
        "source_changed_during_run": False,
        "source_key": "b" * 64,
        "lock_sha256": "c" * 64,
        "fixtures": {"f": "d" * 64},
        "versions": {"python": "3"},
        "commands": [["pytest"]],
        "status": "passed",
        "inventory": {
            "required": True,
            "expected": ["test"],
            "executed": ["test"],
            **{key: [] for key in ("missing", "skipped", "uncollected", "missing_evidence", "failed")},
        },
        "tests": [{"nodeid": "test", "status": "passed", "duration_seconds": 1}],
        "results": [
            {
                "nodeid": "test",
                "month": "2026-01",
                "metric": "cost",
                "expected": 1,
                "actual": 1,
                "deviation": 0,
                "tolerance": 0,
                "unit": "NOK",
                "comparison": "abs_le",
                "status": "passed",
            }
        ],
        "file_sha256": {
            "domain-evidence.log": hashlib.sha256(log).hexdigest(),
            "domain-evidence-junit.xml": hashlib.sha256(xml).hexdigest(),
        },
    }
    return {
        "domain-evidence.json": json.dumps(report).encode(),
        "domain-evidence.log": log,
        "domain-evidence-junit.xml": xml,
    }


def alter(files: dict[str, bytes], key: str, value: object) -> dict[str, bytes]:
    changed = copy.copy(files)
    report = json.loads(changed["domain-evidence.json"])
    if key.startswith("inventory."):
        report["inventory"][key.split(".")[1]] = value
    else:
        report[key] = value
    changed["domain-evidence.json"] = json.dumps(report).encode()
    return changed


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("commit_sha", "b" * 40),
        ("source_clean", False),
        ("status", "failed"),
        ("inventory.missing", ["test"]),
        ("inventory.skipped", ["test"]),
        ("inventory.executed", []),
        ("results", []),
    ],
)
def test_rejects_invalid_report(files: dict[str, bytes], key: str, value: object) -> None:
    with pytest.raises(evidence.EvidenceError):
        evidence.validate(alter(files, key, value), "a" * 40)


def test_packaging_and_corruption(files: dict[str, bytes], tmp_path: Path) -> None:
    path = tmp_path / "evidence.zip"
    evidence.write_zip(files, path)
    first = path.read_bytes()
    evidence.write_zip(files, path)
    assert path.read_bytes() == first
    evidence.from_zip(path, "a" * 40)
    files["domain-evidence.log"] = b"corrupt"
    with pytest.raises(evidence.EvidenceError):
        evidence.validate(files, "a" * 40)
    path.write_bytes(b"corrupt")
    with pytest.raises(evidence.EvidenceError):
        evidence.from_zip(path, "a" * 40)


def test_rerun_compares_source_and_requirements(files: dict[str, bytes]) -> None:
    original = evidence.validate(files, "a" * 40)
    rerun = copy.deepcopy(original)
    rerun["tests"][0]["duration_seconds"] = 5
    assert evidence.same_source(original, rerun)
    rerun["source_key"] = "e" * 64
    assert not evidence.same_source(original, rerun)


@pytest.mark.parametrize("status", ["failed", "unknown"])
def test_rejects_failed_or_unknown_optional_test(files: dict[str, bytes], status: str) -> None:
    tests = [{"nodeid": "test", "status": "passed"}, {"nodeid": "other", "status": status}]
    with pytest.raises(evidence.EvidenceError):
        evidence.validate(alter(files, "tests", tests), "a" * 40)


def test_optional_skip_allowed_but_duplicate_test_rejected(files: dict[str, bytes]) -> None:
    tests = [{"nodeid": "test", "status": "passed"}, {"nodeid": "other", "status": "skipped"}]
    evidence.validate(alter(files, "tests", tests), "a" * 40)
    tests.append({"nodeid": "test", "status": "skipped"})
    with pytest.raises(evidence.EvidenceError):
        evidence.validate(alter(files, "tests", tests), "a" * 40)


@pytest.mark.parametrize("extra", ["directory", "symlink"])
def test_directory_rejects_non_files(files: dict[str, bytes], tmp_path: Path, extra: str) -> None:
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    if extra == "directory":
        (tmp_path / "extra").mkdir()
    else:
        (tmp_path / "extra").symlink_to(tmp_path / "domain-evidence.log")
    with pytest.raises(evidence.EvidenceError):
        evidence.from_directory(tmp_path, "a" * 40)
