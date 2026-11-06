"""Pytest-integrasjon for fullstendighetsvakt og fakturaevidens."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.replay.evidence import (
    inventory_failed,
    inventory_result,
    measurement,
    provenance,
    versions,
    write_reports,
)
from tests.replay.inventory import required_cases


def pytest_addoption(parser):
    group = parser.getgroup("domain-evidence")
    group.addoption("--domain-evidence-dir", help="Write domain JSON, JUnit and result log here")
    group.addoption("--require-domain-inventory", action="store_true", help="Require every invoice case")


def pytest_configure(config):
    config.addinivalue_line("markers", "full_replay: complete monthly coordinator replay")
    if config.getoption("domain_evidence_dir") or config.getoption("require_domain_inventory"):
        config.pluginmanager.register(EvidencePlugin(config), "domain_evidence_recorder")


@pytest.fixture
def record_domain_evidence(request):
    """Registrer før assert; targeted pytest trenger ingen rapportinnstilling."""
    recorder = request.config.pluginmanager.get_plugin("domain_evidence_recorder")

    def record(**values):
        row = measurement(nodeid=request.node.nodeid, **values)
        if recorder is not None:
            recorder.results.append(row)

    return record


class EvidencePlugin:
    def __init__(self, config):
        self.config = config
        self.root = Path(config.rootpath)
        self.results = []
        self.collected = set()
        self.tests = {}
        self.before = provenance(self.root)
        self.problems = []

    def pytest_collection_finish(self, session):
        self.collected = {item.nodeid for item in session.items}

    def pytest_runtest_logreport(self, report):
        test = self.tests.setdefault(
            report.nodeid,
            {"nodeid": report.nodeid, "status": "passed", "executed": False, "duration_seconds": 0.0},
        )
        test["duration_seconds"] += report.duration
        if report.when == "call":
            test["executed"] = True
        if report.failed or (hasattr(report, "wasxfail") and report.passed):
            test["status"] = "failed"
        elif report.skipped and test["status"] != "failed":
            test["status"] = "skipped"

    def pytest_sessionfinish(self, session, exitstatus):
        required = self.config.getoption("require_domain_inventory")
        inventory = inventory_result(required_cases(), self.collected, self.tests, self.results)
        inventory["required"] = required
        if required and inventory_failed(inventory):
            self.problems.append("Required invoice cases missing, skipped, failed or without evidence")
        if any(row["status"] != "passed" for row in self.results):
            self.problems.append("Numeric domain evidence failed")
        after = provenance(self.root)
        changed = self.before["source_key"] != after["source_key"]
        if changed:
            self.problems.append("Sources changed during validation")
        if self.problems and exitstatus == 0:
            session.exitstatus = pytest.ExitCode.TESTS_FAILED
        report = {
            "schema_version": 1,
            **self.before,
            "source_changed_during_run": changed,
            "status": "passed" if session.exitstatus == 0 else "failed",
            "inventory": inventory,
            "versions": versions(self.root),
            "commands": [
                [
                    "python",
                    "-m",
                    "pytest",
                    *(
                        str(arg).replace(str(self.root), ".").replace(str(Path.home()), "~")
                        for arg in self.config.invocation_params.args
                    ),
                ]
            ],
            "results": self.results,
            "tests": [self.tests[n] for n in sorted(self.tests)],
        }
        directory = self.config.getoption("domain_evidence_dir")
        if directory:
            write_reports(Path(directory), report)

    def pytest_terminal_summary(self, terminalreporter):
        for problem in self.problems:
            terminalreporter.write_sep("!", problem, red=True)
