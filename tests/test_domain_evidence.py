"""Evidens må avvise ufullstendig dekning og kunne knyttes til faktisk kilde."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from tests.replay.evidence import digest, inventory_failed, inventory_result, measurement, provenance
from tests.replay.inventory import required_cases

ROOT = Path(__file__).resolve().parents[1]


def _row(**overrides):
    values = {
        "nodeid": "test.py::test_month",
        "month": "juni_2026",
        "metric": "energy",
        "expected": 1,
        "actual": 1,
        "tolerance": 0.1,
        "unit": "kWh",
    }
    return measurement(**(values | overrides))


def test_exact_comparison_boundaries_and_signed_deviation():
    assert _row(actual=1.5, tolerance=0.5)["status"] == "passed"
    assert _row(actual=1.5, tolerance=0.5, comparison="abs_lt")["status"] == "failed"
    assert _row(actual=0.75, tolerance=0.5)["deviation"] == -0.25
    assert _row(actual=2, expected=[1, 2], tolerance=0, comparison="range_inclusive")["status"] == "passed"
    assert _row(actual=2, expected=[1, 2], tolerance=0, comparison="range_exclusive")["status"] == "failed"


@pytest.mark.parametrize(
    "values",
    [
        {"actual": float("nan")},
        {"expected": float("inf")},
        {"tolerance": -1},
        {"comparison": "unknown"},
        {"expected": [2, 1], "tolerance": 0, "comparison": "range_inclusive"},
    ],
)
def test_invalid_numeric_evidence_is_rejected(values):
    with pytest.raises(ValueError):
        _row(**values)


@pytest.mark.parametrize(
    "fault", ["missing", "uncollected", "skipped", "failed", "no_evidence", "wrong_month"]
)
def test_inventory_is_independent_of_collection_and_pass_count(fault):
    node = "test.py::test_month"
    required = {node: ("juni_2026",)}
    collected = {node}
    tests = {node: {"executed": True, "status": "passed"}}
    rows = [_row()]
    if fault == "missing":
        tests = {}
    elif fault == "uncollected":
        collected = set()
    elif fault in ("skipped", "failed"):
        tests[node]["status"] = fault
    elif fault == "no_evidence":
        rows = []
    else:
        rows[0]["month"] = "juli_2026"
    assert inventory_failed(inventory_result(required, collected, tests, rows))


def test_explicit_inventory_covers_both_replay_paths_and_invoice_reference():
    cases = required_cases()
    assert len(cases) == 118
    assert {m for months in cases.values() for m in months} == {
        "desember_2025",
        "februar_2026",
        "mars_2026",
        "april_2026",
        "mai_2026",
        "juni_2026",
        "juli_2026",
        "august_2026",
        "september_2026",
        "oktober_2026",
    }
    assert len(cases["tests/test_replay_hendelser.py::test_coordinatoren_treffer_fasiten"]) == 6


def _git(root, *args):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = str(root / ".git/config-empty-global")
    env["GIT_CONFIG_SYSTEM"] = str(root / ".git/config-empty-system")
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def evidence_repo(tmp_path):
    (tmp_path / "tests/fixtures").mkdir(parents=True)
    (tmp_path / "tests/fixtures/month.json").write_text('{"energy": 1}\n')
    (tmp_path / "uv.lock").write_text("version = 1\n")
    (tmp_path / ".gitignore").write_text("__pycache__/\n.pytest_cache/\ndist/\n_private/\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.name", "Evidence test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "fixture")
    return tmp_path


def test_provenance_uses_bytes_and_excludes_private_files(evidence_repo):
    root = evidence_repo
    first = provenance(root)
    assert first["source_clean"]
    assert len(first["commit_sha"]) == 40
    assert first == provenance(root)
    (root / "_private").mkdir()
    (root / "_private/token").write_text("SECRET_NOT_FOR_REPORT")
    assert first == provenance(root)
    (root / "tests/fixtures/month.json").write_text('{"energy": 2}\n')
    second = provenance(root)
    assert not second["source_clean"]
    assert first["source_key"] != second["source_key"]
    assert first["fixtures"] != second["fixtures"]
    (root / "uv.lock").write_text("version = 2\n")
    assert provenance(root)["lock_sha256"] != first["lock_sha256"]
    serialized = json.dumps(provenance(root))
    assert "SECRET_NOT_FOR_REPORT" not in serialized
    assert str(root) not in serialized


def _run_plugin(root, body, *args):
    (root / "conftest.py").write_text(
        "import tests.replay.evidence_plugin as plugin\n"
        "plugin.required_cases = lambda: {'test_case.py::test_month': ('juni_2026',)}\n"
    )
    (root / "test_case.py").write_text(body)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "test case")
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.replay.evidence_plugin",
            "test_case.py",
            "-q",
            "--domain-evidence-dir",
            "dist/evidence",
            *args,
        ],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
    )
    report = json.loads((root / "dist/evidence/domain-evidence.json").read_text())
    return result, report


GOOD_CASE = """def test_month(record_domain_evidence):
    record_domain_evidence(month='juni_2026', metric='energy', expected=1, actual=1, tolerance=0, unit='kWh')
"""


def test_plugin_produces_bound_json_junit_and_log(evidence_repo):
    result, report = _run_plugin(evidence_repo, GOOD_CASE, "--require-domain-inventory")
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["status"] == "passed"
    assert report["source_clean"]
    assert report["commit_sha"] == _git(evidence_repo, "rev-parse", "HEAD")
    assert report["inventory"]["required"]
    assert not inventory_failed(report["inventory"])
    assert report["results"][0]["deviation"] == 0
    assert report["versions"]["pytest"]
    assert report["commands"][0][:3] == ["python", "-m", "pytest"]
    directory = evidence_repo / "dist/evidence"
    xml = ET.parse(directory / "domain-evidence-junit.xml").getroot()
    assert xml.attrib["failures"] == "0"
    assert "juni_2026" in xml.find("testcase/system-out").text
    assert report["commit_sha"] in (directory / "domain-evidence.log").read_text()
    assert report["file_sha256"] == {
        name: digest(directory / name) for name in ("domain-evidence.log", "domain-evidence-junit.xml")
    }


@pytest.mark.parametrize(
    "case,args",
    [
        ("import pytest\ndef test_month(): pytest.skip('unavailable')\n", []),
        ("def test_other(): pass\n", []),
        (GOOD_CASE, ["-k", "absent"]),
        ("def test_month(): pass\n", []),
        (GOOD_CASE.replace("actual=1", "actual=2"), []),
    ],
)
def test_plugin_rejects_skipped_missing_deselected_or_unrecorded_case(evidence_repo, case, args):
    result, report = _run_plugin(evidence_repo, case, "--require-domain-inventory", *args)
    assert result.returncode != 0
    assert report["status"] == "failed"
    assert inventory_failed(report["inventory"])


def test_partial_run_can_report_but_cannot_claim_full_inventory(evidence_repo):
    result, report = _run_plugin(evidence_repo, "def test_other(): pass\n")
    assert result.returncode == 0
    assert not report["inventory"]["required"]
    assert report["inventory"]["missing"]


def test_changed_source_during_run_invalidates_evidence(evidence_repo):
    body = GOOD_CASE + "    from pathlib import Path\n    Path('uv.lock').write_text('changed')\n"
    result, report = _run_plugin(evidence_repo, body, "--require-domain-inventory")
    assert result.returncode != 0
    assert report["source_changed_during_run"]
    assert report["status"] == "failed"


def test_hook_git_environment_cannot_redirect_provenance_or_test_repository(evidence_repo, monkeypatch):
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY"):
        monkeypatch.setenv(name, str(evidence_repo / "not-the-repository"))
    result, report = _run_plugin(evidence_repo, GOOD_CASE, "--require-domain-inventory")
    assert result.returncode == 0, result.stdout + result.stderr
    assert report["source_clean"]
    assert report["commit_sha"] == _git(evidence_repo, "rev-parse", "HEAD")
