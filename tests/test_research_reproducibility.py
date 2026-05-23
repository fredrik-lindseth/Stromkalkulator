"""Drift-test: docs/research/_generated/ skal være stabil mellom regenereringer.

Strategi:
1. Snapshot innholdet i `docs/research/_generated/` til en temp-mappe
2. Kjør `just verify-all` (eller `make verify-all` som fallback)
3. Sammenlign nye filer mot snapshot

Hvis testen feiler er det enten fordi:
- En kilde (rate, formel, fixture) er endret uten at output er commit'a
- Scriptet er ikke deterministisk (eks. flytende timestamp i metadata)

Hopper over hvis verken `just` eller `make` er installert.
"""

from __future__ import annotations

import filecmp
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GENERATED = ROOT / "docs" / "research" / "_generated"


def _runner() -> list[str] | None:
    """Returner kommando-prefiks for verify-all, eller None hvis ingen finnes."""
    if shutil.which("just"):
        return ["just", "verify-all"]
    if shutil.which("make") and (ROOT / "Makefile").exists():
        return ["make", "verify-all"]
    return None


def test_research_verify_all_is_deterministic() -> None:
    runner = _runner()
    if runner is None:
        pytest.skip("Verken `just` eller `make` tilgjengelig — hopper over drift-test")

    if not GENERATED.exists():
        pytest.skip(f"{GENERATED.relative_to(ROOT)} finnes ikke ennå (første kjøring)")

    with tempfile.TemporaryDirectory() as tmp:
        snapshot = Path(tmp) / "before"
        shutil.copytree(GENERATED, snapshot)

        result = subprocess.run(
            runner,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"verify-all feilet (returncode {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

        cmp = filecmp.dircmp(snapshot, GENERATED)
        differences = cmp.diff_files + cmp.left_only + cmp.right_only
        if differences:
            details: list[str] = []
            for name in cmp.diff_files:
                a = (snapshot / name).read_text()
                b = (GENERATED / name).read_text()
                details.append(f"--- {name} drift ---\nFør:\n{a}\nEtter:\n{b}")
            if cmp.left_only:
                details.append(f"Filer kun i snapshot (slettet av regen): {cmp.left_only}")
            if cmp.right_only:
                details.append(f"Filer kun etter regen (nye): {cmp.right_only}")
            pytest.fail(
                "Drift i docs/research/_generated/ etter regen. Enten har scriptene "
                "endret seg og dette er commit'a, eller scriptene er ikke "
                "deterministiske.\n\n" + "\n\n".join(details)
            )
