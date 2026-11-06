"""Genererte tabeller skal oppdateres også i temamapper."""

from pathlib import Path

import pytest

from scripts.research import inject_generated


@pytest.fixture
def research(tmp_path, monkeypatch):
    directory = tmp_path / "docs" / "research"
    generated = directory / "_generated"
    generated.mkdir(parents=True)
    (generated / "resultat.md").write_text("Ny tabell\n")
    monkeypatch.setattr(inject_generated, "ROOT", tmp_path)
    monkeypatch.setattr(inject_generated, "RESEARCH_DIR", directory)
    monkeypatch.setattr(inject_generated, "GENERATED_DIR", generated)
    return directory


def document(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Forklaring\n\n<!-- BEGIN GENERATED: resultat -->\n"
        "Gammel tabell\n<!-- END GENERATED -->\n\nVidere lesning.\n"
    )
    return path


def test_oppdaterer_rot_og_undermapper(research):
    files = [document(research / name) for name in ("README.md", "priser/norgespris.md")]

    assert inject_generated.main() == 0

    for path in files:
        assert path.read_text() == (
            "# Forklaring\n\n<!-- BEGIN GENERATED: resultat -->\n"
            "Ny tabell\n<!-- END GENERATED -->\n\nVidere lesning.\n"
        )


@pytest.mark.parametrize(
    "name",
    [
        "_generated/egen-tabell.md",
        "_private/notat.md",
        ".cache/notat.md",
        "priser/_utkast/notat.md",
        "priser/.skjult.md",
    ],
)
def test_lar_genererte_og_private_filer_staa(research, name):
    path = document(research / name)
    before = path.read_bytes()

    assert inject_generated.main() == 0
    assert path.read_bytes() == before


def test_uendret_tabell_skrives_ikke_pa_nytt(research, monkeypatch):
    document(research / "priser/norgespris.md")
    assert inject_generated.main() == 0

    def unexpected_write(*args, **kwargs):
        pytest.fail("Uendret dokument skal ikke skrives på nytt")

    monkeypatch.setattr(Path, "write_text", unexpected_write)
    assert inject_generated.main() == 0
