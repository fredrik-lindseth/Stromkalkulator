"""Tester for uttrekket i scripts/release_notes.py.

Release-workflowen bygger body-en fra CHANGELOG.md. Går uttrekket i stykker,
får brukerne enten feil tekst eller en feilet release, så både det som finnes
og det som mangler må oppføre seg forutsigbart.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

release_notes = importlib.import_module("release_notes")

FALSK_CHANGELOG = """# Changelog

Format basert på Keep a Changelog.

## [Ikke sluppet]

### Lagt til

- Noe som ikke er sluppet

## [2.0.0]

### Fikset

- **Et punkt**: med detalj

### Endret

- Et punkt til

## [1.9.0] - 2026-01-30

- Gammel stil med dato i overskriften

## [1.8.0]

## [1.7.0]

- Siste seksjon i filen
"""


class TestFinnSeksjon:
    """finn_seksjon skal gi teksten under overskriften, uten naboseksjoner."""

    def test_henter_hele_seksjonen(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "2.0.0")
        assert seksjon is not None
        assert seksjon.startswith("### Fikset")
        assert "**Et punkt**: med detalj" in seksjon
        assert "Et punkt til" in seksjon

    def test_tar_ikke_med_overskriften_selv(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "2.0.0")
        assert seksjon is not None
        assert "## [2.0.0]" not in seksjon

    def test_lekker_ikke_inn_i_neste_seksjon(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "2.0.0")
        assert seksjon is not None
        assert "Gammel stil" not in seksjon
        assert "## [1.9.0]" not in seksjon

    def test_tar_ikke_med_ikke_sluppet_over(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "2.0.0")
        assert seksjon is not None
        assert "Noe som ikke er sluppet" not in seksjon

    def test_overskrift_med_dato_treffer(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "1.9.0")
        assert seksjon == "- Gammel stil med dato i overskriften"

    def test_siste_seksjon_i_filen_leses_til_slutten(self):
        seksjon = release_notes.finn_seksjon(FALSK_CHANGELOG, "1.7.0")
        assert seksjon == "- Siste seksjon i filen"

    def test_tom_seksjon_regnes_som_manglende(self):
        assert release_notes.finn_seksjon(FALSK_CHANGELOG, "1.8.0") is None

    def test_seksjon_med_bare_blanke_linjer_regnes_som_manglende(self):
        """Mellomrom og tab på linjene er like tomt som ingen linjer."""
        changelog = "## [1.8.0]\n   \n\t\n## [1.7.0]\n\n- x\n"
        assert release_notes.finn_seksjon(changelog, "1.8.0") is None

    def test_ukjent_versjon_gir_none(self):
        assert release_notes.finn_seksjon(FALSK_CHANGELOG, "9.9.9") is None

    def test_delvis_treff_gir_ikke_seksjon(self):
        """Versjonen «2.0» skal ikke plukke opp seksjonen for 2.0.0."""
        assert release_notes.finn_seksjon(FALSK_CHANGELOG, "2.0") is None


class TestKjenteVersjoner:
    def test_lister_alle_overskriftene_i_rekkefolge(self):
        assert release_notes.kjente_versjoner(FALSK_CHANGELOG) == [
            "Ikke sluppet",
            "2.0.0",
            "1.9.0",
            "1.8.0",
            "1.7.0",
        ]


class TestCli:
    """Exit-koden er det release.yml og ci.yml faktisk henger på."""

    def _changelog(self, tmp_path: Path) -> Path:
        sti = tmp_path / "CHANGELOG.md"
        sti.write_text(FALSK_CHANGELOG, encoding="utf-8")
        return sti

    def test_treff_gir_exit_0_og_skriver_seksjonen(self, tmp_path, capsys):
        kode = release_notes.main(["2.0.0", "--changelog", str(self._changelog(tmp_path))])
        assert kode == 0
        assert "**Et punkt**: med detalj" in capsys.readouterr().out

    def test_v_prefiks_godtas(self, tmp_path, capsys):
        kode = release_notes.main(["v2.0.0", "--changelog", str(self._changelog(tmp_path))])
        assert kode == 0
        assert "**Et punkt**: med detalj" in capsys.readouterr().out

    def test_manglende_seksjon_gir_exit_1(self, tmp_path, capsys):
        kode = release_notes.main(["9.9.9", "--changelog", str(self._changelog(tmp_path))])
        assert kode == 1
        feil = capsys.readouterr().err
        assert "9.9.9" in feil
        assert "2.0.0" in feil  # viser hva som faktisk står i filen

    def test_manglende_fil_gir_exit_1(self, tmp_path, capsys):
        kode = release_notes.main(["1.0.0", "--changelog", str(tmp_path / "finnes-ikke.md")])
        assert kode == 1
        assert "finnes-ikke.md" in capsys.readouterr().err


class TestEkteChangelog:
    """Uttrekket må virke mot repoets egen fil, ikke bare mot fixturen."""

    def test_sluppet_versjon_har_innhold(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        seksjon = release_notes.finn_seksjon(changelog, "1.16.0")
        assert seksjon is not None
        assert "last_reset" in seksjon

    def test_manifest_versjonen_er_enten_sluppet_eller_under_arbeid(self):
        """En bumpet manifest-versjon uten CHANGELOG-seksjon stopper releasen.

        Svakere enn porten i ci.yml, som spør GitHub om taggen finnes: lokalt
        vet testen ikke om versjonen er sluppet, så den godtar også at CHANGELOG
        bare har en `[Ikke sluppet]`-seksjon å skrive i.
        """
        manifest = json.loads(
            (REPO_ROOT / "custom_components" / "stromkalkulator" / "manifest.json").read_text(encoding="utf-8")
        )
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        versjoner = release_notes.kjente_versjoner(changelog)
        assert manifest["version"] in versjoner or "Ikke sluppet" in versjoner
