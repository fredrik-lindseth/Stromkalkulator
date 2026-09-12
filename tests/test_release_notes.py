"""Tester for uttrekket i scripts/release_notes.py.

Release-workflowen bygger body-en fra CHANGELOG.md. Går uttrekket i stykker,
får brukerne enten feil tekst eller en feilet release, så både det som finnes
og det som mangler må oppføre seg forutsigbart. Det samme gjelder de to
omskrivingene body-en får: absolutte lenker og løftet handlingskategori.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

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

    def test_doed_relativ_lenke_gir_exit_1(self, tmp_path, capsys):
        """Heller feilet release enn en lenke som peker i tomme luften."""
        repo = tmp_path / "repo"
        repo.mkdir()
        changelog = repo / "CHANGELOG.md"
        changelog.write_text("## [3.0.0]\n\n- Se [regler](docs/finnes-ikke.md)\n", encoding="utf-8")
        kode = release_notes.main(["3.0.0", "--changelog", str(changelog), "--repo-root", str(repo)])
        assert kode == 1
        feil = capsys.readouterr().err
        assert "docs/finnes-ikke.md" in feil
        assert "CHANGELOG.md" in feil

    def test_body_har_absolutte_lenker_og_loftet_kategori(self, tmp_path, capsys):
        repo = tmp_path / "repo"
        (repo / "docs").mkdir(parents=True)
        (repo / "docs" / "sensorer.md").write_text("x", encoding="utf-8")
        changelog = repo / "CHANGELOG.md"
        changelog.write_text(
            "## [3.0.0]\n\n### Fikset\n\n- Se [sensorer](docs/sensorer.md)\n\n"
            "### Dette må du gjøre selv\n\n- Velg terskel\n",
            encoding="utf-8",
        )
        kode = release_notes.main(["3.0.0", "--changelog", str(changelog), "--repo-root", str(repo)])
        assert kode == 0
        ut = capsys.readouterr().out
        assert ut.startswith("### Dette må du gjøre selv")
        assert "](docs/sensorer.md)" not in ut
        assert "/blob/v3.0.0/docs/sensorer.md" in ut


class TestEkteChangelog:
    """Uttrekket må virke mot repoets egen fil, ikke bare mot fixturen."""

    def test_sluppet_versjon_har_innhold(self):
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        seksjon = release_notes.finn_seksjon(changelog, "1.16.0")
        assert seksjon is not None
        assert "last_reset" in seksjon

    def test_body_for_sluppet_versjon_har_ingen_relative_lenker(self):
        """Alt som limes inn på releasesiden må virke utenfor repoet."""
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        body = release_notes.bygg_body(changelog, "1.15.0")
        assert body is not None
        assert "](docs/" not in body
        assert "/blob/v1.15.0/docs/incidents/" in body

    def test_alle_seksjoner_kan_bygges(self):
        """En relativ lenke som råtner skal felles her, ikke i release-jobben."""
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        for versjon in release_notes.kjente_versjoner(changelog):
            release_notes.bygg_body(changelog, versjon)

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


class TestSkrivOmLenker:
    """Relative lenker er døde på releasesiden og må bli absolutte."""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "docs" / "incidents").mkdir(parents=True)
        (tmp_path / "docs" / "incidents" / "006-kapasitetstrinn.md").write_text("x", encoding="utf-8")
        (tmp_path / "docs" / "domain-rules.md").write_text("x", encoding="utf-8")
        (tmp_path / "CHANGELOG.md").write_text("x", encoding="utf-8")
        return tmp_path

    def _om(self, tekst: str, tmp_path: Path, versjon: str = "1.16.0") -> str:
        return release_notes.skriv_om_lenker(
            tekst,
            versjon,
            repo_root=self._repo(tmp_path),
            repo_url="https://example.test/eier/repo",
        )

    def test_relativ_fil_blir_absolutt_mot_taggen(self, tmp_path):
        ut = self._om("Se [incident 006](docs/incidents/006-kapasitetstrinn.md).", tmp_path)
        assert ut == (
            "Se [incident 006](https://example.test/eier/repo/blob/v1.16.0/docs/incidents/006-kapasitetstrinn.md)."
        )

    def test_bruker_taggen_ikke_main(self, tmp_path):
        ut = self._om("[a](docs/domain-rules.md)", tmp_path, versjon="2.3.4")
        assert "/blob/v2.3.4/" in ut
        assert "/blob/main/" not in ut

    def test_ikke_sluppet_faller_til_main(self, tmp_path):
        ut = self._om("[a](docs/domain-rules.md)", tmp_path, versjon="Ikke sluppet")
        assert "/blob/main/" in ut

    def test_absolutt_url_star_urort(self, tmp_path):
        tekst = "Rapportert i [#14](https://github.com/eier/repo/issues/14) og <https://x.test>."
        assert self._om(tekst, tmp_path) == tekst

    def test_mailto_star_urort(self, tmp_path):
        tekst = "[skriv](mailto:noen@example.test)"
        assert self._om(tekst, tmp_path) == tekst

    def test_anker_i_changelog_peker_paa_filen_i_repoet(self, tmp_path):
        ut = self._om("Se [over](#lagt-til).", tmp_path)
        assert ut == "Se [over](https://example.test/eier/repo/blob/v1.16.0/CHANGELOG.md#lagt-til)."

    def test_anker_paa_relativ_fil_beholdes(self, tmp_path):
        ut = self._om("[regler](docs/domain-rules.md#sensor-enheter)", tmp_path)
        assert ut.endswith("/blob/v1.16.0/docs/domain-rules.md#sensor-enheter)")

    def test_punktum_skraastrek_strippes(self, tmp_path):
        ut = self._om("[regler](./docs/domain-rules.md)", tmp_path)
        assert ut == "[regler](https://example.test/eier/repo/blob/v1.16.0/docs/domain-rules.md)"

    def test_bildelenke_skrives_ogsaa_om(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / "docs" / "skjermbilde.png").write_text("x", encoding="utf-8")
        ut = release_notes.skriv_om_lenker(
            "![skjermbilde](docs/skjermbilde.png)",
            "1.16.0",
            repo_root=repo,
            repo_url="https://example.test/eier/repo",
        )
        assert ut == "![skjermbilde](https://example.test/eier/repo/blob/v1.16.0/docs/skjermbilde.png)"

    def test_tittel_etter_maalet_beholdes(self, tmp_path):
        ut = self._om('[regler](docs/domain-rules.md "Domene")', tmp_path)
        assert ut.endswith('/docs/domain-rules.md "Domene")')

    def test_fil_som_ikke_finnes_gir_feil(self, tmp_path):
        with pytest.raises(release_notes.LenkeFeil) as feil:
            self._om("[borte](docs/finnes-ikke.md)", tmp_path)
        assert "docs/finnes-ikke.md" in str(feil.value)

    def test_alle_manglende_lenker_naevnes(self, tmp_path):
        with pytest.raises(release_notes.LenkeFeil) as feil:
            self._om("[a](docs/en.md) og [b](docs/to.md)", tmp_path)
        assert "docs/en.md" in str(feil.value)
        assert "docs/to.md" in str(feil.value)

    def test_sti_ut_av_repoet_gir_feil(self, tmp_path):
        (tmp_path.parent / "utenfor.md").write_text("x", encoding="utf-8")
        with pytest.raises(release_notes.LenkeFeil):
            self._om("[ut](../utenfor.md)", tmp_path)

    def test_tekst_uten_lenker_er_uendret(self, tmp_path):
        tekst = "### Fikset\n\n- Et punkt uten lenke"
        assert self._om(tekst, tmp_path) == tekst


class TestLoftHandlingskategori:
    """Beskjeden om at brukeren må gjøre noe skal aldri drukne."""

    SEKSJON = """### Lagt til

- Ny binary_sensor

### Dette må du gjøre selv

- Velg terskel i Configure

### Fikset

- En feil
"""

    def test_kategorien_flyttes_oeverst(self):
        ut = release_notes.loft_handlingskategori(self.SEKSJON)
        assert ut.startswith("### Dette må du gjøre selv\n\n- Velg terskel i Configure")

    def test_de_andre_kategoriene_beholder_rekkefolgen(self):
        ut = release_notes.loft_handlingskategori(self.SEKSJON)
        assert ut.index("### Lagt til") < ut.index("### Fikset")

    def test_ingenting_gaar_tapt(self):
        ut = release_notes.loft_handlingskategori(self.SEKSJON)
        for punkt in ("Ny binary_sensor", "Velg terskel i Configure", "En feil"):
            assert punkt in ut

    def test_seksjon_uten_kategorien_er_uendret(self):
        seksjon = "### Fikset\n\n- En feil\n"
        assert release_notes.loft_handlingskategori(seksjon) == seksjon

    def test_kategorien_staar_allerede_oeverst(self):
        seksjon = "### Dette må du gjøre selv\n\n- Gjør noe\n\n### Fikset\n\n- En feil\n"
        assert release_notes.loft_handlingskategori(seksjon) == seksjon

    def test_stor_og_liten_bokstav_spiller_ingen_rolle(self):
        seksjon = "### Fikset\n\n- En feil\n\n### dette MÅ du gjøre selv\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon)
        assert ut.startswith("### dette MÅ du gjøre selv")

    def test_kategorien_til_slutt_i_seksjonen(self):
        seksjon = "### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon)
        assert ut.startswith("### Dette må du gjøre selv")
        assert ut.rstrip().endswith("- En feil")


class TestByggBody:
    """bygg_body er det release.yml faktisk får."""

    CHANGELOG = """# Changelog

## [3.0.0]

### Fikset

- Se [regler](docs/domain-rules.md)

### Dette må du gjøre selv

- Bekreft enhetsbyttet
"""

    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "domain-rules.md").write_text("x", encoding="utf-8")
        return tmp_path

    def test_loft_og_omskriving_i_samme_body(self, tmp_path):
        body = release_notes.bygg_body(
            self.CHANGELOG,
            "3.0.0",
            repo_root=self._repo(tmp_path),
            repo_url="https://example.test/eier/repo",
        )
        assert body is not None
        assert body.startswith("### Dette må du gjøre selv")
        assert "https://example.test/eier/repo/blob/v3.0.0/docs/domain-rules.md" in body

    def test_manglende_seksjon_gir_none(self, tmp_path):
        assert release_notes.bygg_body(self.CHANGELOG, "9.9.9", repo_root=self._repo(tmp_path)) is None
