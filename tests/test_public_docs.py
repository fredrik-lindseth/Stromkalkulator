"""Guard public documentation and exercise the scanner on isolated examples."""

from pathlib import Path

from scripts.check_public_docs import ROOT, scan, scan_file


def test_public_docs() -> None:
    findings = scan(ROOT)
    assert not findings, "\n" + "\n".join(findings)


def test_private_references_in_raw_markdown(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "`stromkalkulator-zzzz999` `effektvakt-yyyy888`\n"
        "[lenke](https://dogcats.example/issue/xyz)\n"
        "```\n/Users/example/private/file\n/home/example/private/file\n```\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 5
    assert all("privat referanse" in item for item in results)


def test_prose_masks_code_urls_and_explicit_ui(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        '"Jeg har Norgespris" og romertall VI.\n'
        "[profil](https://github.com/fredrik-lindseth) `vi`\n"
        "```text\nJeg og Fredrik\n```\n"
        "Vi endret dette. «Jeg gjorde det.» tasken og avgjørelse for saken.\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 4
    assert all(":6: redaksjonell prosa:" in item for item in results)


def test_credits_and_sources_remain_visible_without_masking_quotes(tmp_path: Path) -> None:
    doc = tmp_path / "doc.md"
    doc.write_text(
        "Kilde: [NVE](https://example.org/fredrik/kilde).\n"
        "Kreditering: [bidragsyter](https://github.com/fredrik-lindseth).\n"
        "«vi beregner», sa kilden. fredrik skrev dette. jeg vet ikke.\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 3
    assert all(":3: redaksjonell prosa:" in item for item in results)
    assert any(item.endswith(": vi") for item in results)
    assert any(item.endswith(": fredrik") for item in results)
    assert any(item.endswith(": jeg") for item in results)


def test_relative_reference_image_and_encoded_links(tmp_path: Path) -> None:
    (tmp_path / "mappe med rom").mkdir()
    (tmp_path / "mappe med rom" / "bilde.png").touch()
    doc = tmp_path / "doc.md"
    doc.write_text(
        "![bilde](mappe%20med%20rom/bilde.png)\n"
        "[mappe](<mappe med rom/>) [referanse][fil]\n"
        "[fil]: mappe%20med%20rom/bilde.png\n"
        "[nett](https://example.org/ikke-lokal) [feil](mangler.md)\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 1
    assert ":4: mangler lenkemål: mangler.md" in results[0]


def test_released_changelog_checks_private_references_only(tmp_path: Path) -> None:
    doc = tmp_path / "CHANGELOG.md"
    doc.write_text(
        "# Logg\n## [Unreleased]\nVi planlegger. [feil](missing.md)\n"
        "## [1.0.0]\nVi gjorde. [gammel](missing.md) `effektvakt-zzzz999`\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 3
    assert sum("privat referanse i publisert historikk" in item for item in results) == 1
    assert sum("redaksjonell prosa" in item for item in results) == 1
    assert sum("mangler lenkemål" in item for item in results) == 1


def test_retired_labels_only_in_current_prose(tmp_path: Path) -> None:
    doc = tmp_path / "CHANGELOG.md"
    doc.write_text(
        "# Logg\n## [Unreleased]\n"
        "L3a L3b L3c K0 K1 K2; B1 C1 D1.\n"
        "`L3a K0` [lenke](https://example.org/L3b/K1)\n"
        "```text\nL3c K2\n```\n"
        "## [1.0.0]\nL3a K0\n",
        encoding="utf-8",
    )
    results = scan_file(tmp_path, doc)
    assert len(results) == 6
    assert all(":3: utgått arbeidsmerking:" in item for item in results)
    assert {item.rsplit(": ", 1)[-1] for item in results} == {"L3a", "L3b", "L3c", "K0", "K1", "K2"}
