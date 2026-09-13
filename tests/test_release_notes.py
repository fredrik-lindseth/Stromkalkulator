"""Tester for uttrekket i scripts/release_notes.py.

Release-workflowen bygger body-en fra CHANGELOG.md. Går uttrekket i stykker,
får brukerne enten feil tekst eller en feilet release, så både det som finnes
og det som mangler må oppføre seg forutsigbart. Det samme gjelder de to
omskrivingene body-en får: absolutte lenker og løftet handlingskategori.

Body-en release.yml publiserer er den korte varianten, bygget av punktene som er
merket med `<!--kort-->`. Den har sine egne vakter: en seksjon under arbeid uten
et eneste merket punkt skal felle, og historikken, som aldri ble merket, skal gi
hele seksjonen framfor å krasje.
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

    def test_tom_handlingskategori_gir_exit_1(self, tmp_path, capsys):
        """Heller feilet release enn en naken overskrift hos alle brukerne."""
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "## [3.0.0]\n\n### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n",
            encoding="utf-8",
        )
        kode = release_notes.main(["3.0.0", "--changelog", str(changelog), "--repo-root", str(tmp_path)])
        assert kode == 1
        feil = capsys.readouterr().err
        assert "3.0.0" in feil
        assert "Dette må du gjøre selv" in feil

    def test_handlingskategori_med_bare_blanke_linjer_gir_exit_1(self, tmp_path, capsys):
        changelog = tmp_path / "CHANGELOG.md"
        changelog.write_text(
            "## [3.0.0]\n\n### Dette må du gjøre selv\n\n   \n\t\n\n### Fikset\n\n- En feil\n",
            encoding="utf-8",
        )
        kode = release_notes.main(["3.0.0", "--changelog", str(changelog), "--repo-root", str(tmp_path)])
        assert kode == 1
        feil = capsys.readouterr().err
        assert "3.0.0" in feil
        assert "Dette må du gjøre selv" in feil

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
            (REPO_ROOT / "custom_components" / "stromkalkulator" / "manifest.json").read_text(
                encoding="utf-8"
            )
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

    def test_referansedefinisjon_blir_absolutt(self, tmp_path):
        """`[tekst][r1]` har målet i definisjonen, så det er der det må rettes."""
        ut = self._om("Se [regler][r1].\n\n[r1]: docs/domain-rules.md", tmp_path)
        assert ut.endswith("[r1]: https://example.test/eier/repo/blob/v1.16.0/docs/domain-rules.md")
        assert "Se [regler][r1]." in ut

    def test_referansedefinisjon_beholder_tittelen(self, tmp_path):
        ut = self._om('[r1]: docs/domain-rules.md "Domene"', tmp_path)
        assert ut.endswith('/docs/domain-rules.md "Domene"')

    def test_absolutt_referansedefinisjon_star_urort(self, tmp_path):
        """CHANGELOG har en bunke compare-lenker som ikke skal røres."""
        tekst = "[0.13.0]: https://github.com/eier/repo/releases/tag/v0.13.0"
        assert self._om(tekst, tmp_path) == tekst

    def test_doed_referansedefinisjon_gir_feil(self, tmp_path):
        with pytest.raises(release_notes.LenkeFeil) as feil:
            self._om("[r1]: docs/finnes-ikke.md", tmp_path)
        assert "docs/finnes-ikke.md" in str(feil.value)

    def test_vinkelparentes_med_mellomrom_blir_absolutt(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / "docs" / "med mellomrom.md").write_text("x", encoding="utf-8")
        ut = release_notes.skriv_om_lenker(
            "[x](<docs/med mellomrom.md>)",
            "1.16.0",
            repo_root=repo,
            repo_url="https://example.test/eier/repo",
        )
        assert ut == "[x](https://example.test/eier/repo/blob/v1.16.0/docs/med%20mellomrom.md)"

    def test_doed_vinkelparentes_gir_feil(self, tmp_path):
        with pytest.raises(release_notes.LenkeFeil) as feil:
            self._om("[x](<docs/borte fil.md>)", tmp_path)
        assert "docs/borte fil.md" in str(feil.value)

    def test_absolutt_vinkelparentes_beholder_parentesene(self, tmp_path):
        tekst = "[x](<https://eksempel.test/a b>)"
        assert self._om(tekst, tmp_path) == tekst

    def test_autolenke_star_urort(self, tmp_path):
        """En autolenke må ha skjema for å være en lenke, så den er alltid absolutt."""
        tekst = "Se <https://eksempel.test/side>."
        assert self._om(tekst, tmp_path) == tekst

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
        ut = release_notes.loft_handlingskategori(self.SEKSJON, "3.0.0")
        assert ut.startswith("### Dette må du gjøre selv\n\n- Velg terskel i Configure")

    def test_de_andre_kategoriene_beholder_rekkefolgen(self):
        ut = release_notes.loft_handlingskategori(self.SEKSJON, "3.0.0")
        assert ut.index("### Lagt til") < ut.index("### Fikset")

    def test_ingenting_gaar_tapt(self):
        ut = release_notes.loft_handlingskategori(self.SEKSJON, "3.0.0")
        for punkt in ("Ny binary_sensor", "Velg terskel i Configure", "En feil"):
            assert punkt in ut

    def test_seksjon_uten_kategorien_er_uendret(self):
        seksjon = "### Fikset\n\n- En feil\n"
        assert release_notes.loft_handlingskategori(seksjon, "3.0.0") == seksjon

    def test_kategorien_staar_allerede_oeverst(self):
        seksjon = "### Dette må du gjøre selv\n\n- Gjør noe\n\n### Fikset\n\n- En feil\n"
        assert release_notes.loft_handlingskategori(seksjon, "3.0.0") == seksjon

    def test_stor_og_liten_bokstav_spiller_ingen_rolle(self):
        seksjon = "### Fikset\n\n- En feil\n\n### dette MÅ du gjøre selv\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon, "3.0.0")
        assert ut.startswith("### dette MÅ du gjøre selv")

    def test_tom_kategori_gir_feil(self):
        """En naken overskrift øverst i release-noten ser ødelagt ut."""
        seksjon = "### Dette må du gjøre selv\n\n### Fikset\n\n- En feil\n"
        with pytest.raises(release_notes.TomKategoriFeil) as feil:
            release_notes.loft_handlingskategori(seksjon, "3.0.0")
        assert feil.value.versjon == "3.0.0"
        assert "Dette må du gjøre selv" in feil.value.overskrift

    def test_tom_kategori_til_slutt_gir_feil(self):
        seksjon = "### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n"
        with pytest.raises(release_notes.TomKategoriFeil):
            release_notes.loft_handlingskategori(seksjon, "3.0.0")

    def test_kategori_med_bare_blanke_linjer_gir_feil(self):
        """Mellomrom og tab er like tomt som ingen linjer, som for seksjoner."""
        seksjon = "### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n\n   \n\t\n"
        with pytest.raises(release_notes.TomKategoriFeil):
            release_notes.loft_handlingskategori(seksjon, "3.0.0")

    def test_underoverskrift_teller_som_innhold(self):
        """`#### Noe` avslutter ikke blokken, så kategorien er ikke tom."""
        seksjon = "### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n\n#### Steg\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon, "3.0.0")
        assert ut.startswith("### Dette må du gjøre selv")

    def test_annen_tom_kategori_gaar_gjennom(self):
        """Vakten gjelder handlingskategorien, ikke alle overskrifter."""
        seksjon = "### Fikset\n\n### Dette må du gjøre selv\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon, "3.0.0")
        assert ut.startswith("### Dette må du gjøre selv")

    def test_kategorien_til_slutt_i_seksjonen(self):
        seksjon = "### Fikset\n\n- En feil\n\n### Dette må du gjøre selv\n\n- Gjør noe\n"
        ut = release_notes.loft_handlingskategori(seksjon, "3.0.0")
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


class TestDelIKategorier:
    """Punktene må kunne plukkes ut ett for ett, også når de går over flere linjer."""

    def test_punkter_havner_under_riktig_kategori(self):
        seksjon = "### Fikset\n\n- A\n- B\n\n### Lagt til\n\n- C\n"
        assert release_notes.del_i_kategorier(seksjon) == [
            (None, []),
            ("Fikset", ["- A", "- B"]),
            ("Lagt til", ["- C"]),
        ]

    def test_innrykket_fortsettelse_blir_med_i_punktet(self):
        seksjon = "### Fikset\n\n- Første linje\n  andre linje\n- Neste punkt\n"
        _, (_, punkter) = release_notes.del_i_kategorier(seksjon)
        assert punkter == ["- Første linje\n  andre linje", "- Neste punkt"]

    def test_tekst_for_forste_overskrift_holdes_for_seg(self):
        seksjon = "- Uten kategori\n\n### Fikset\n\n- A\n"
        assert release_notes.del_i_kategorier(seksjon)[0] == (None, ["- Uten kategori"])


class TestBygggKort:
    """Den korte noten er det HACS viser. Blir den tom, er den verre enn ingen."""

    SEKSJON = """### Dette må du gjøre selv

- Bekreft enhetsbyttet

### Fikset

- <!--kort--> Et punkt brukeren merker
- Et punkt som hører hjemme i hele loggen

### Lagt til

- <!--kort--> Enda et punkt brukeren merker
"""

    def test_tar_med_hele_handlingskategorien(self):
        kort = release_notes.bygg_kort(self.SEKSJON, "3.0.0")
        assert kort.startswith("### Dette må du gjøre selv")
        assert "- Bekreft enhetsbyttet" in kort

    def test_tar_med_de_merkede_punktene(self):
        kort = release_notes.bygg_kort(self.SEKSJON, "3.0.0")
        assert "Et punkt brukeren merker" in kort
        assert "Enda et punkt brukeren merker" in kort

    def test_lar_de_umerkede_punktene_ligge(self):
        kort = release_notes.bygg_kort(self.SEKSJON, "3.0.0")
        assert "hele loggen" not in kort

    def test_merket_selv_blir_ikke_med_ut(self):
        assert "<!--kort-->" not in release_notes.bygg_kort(self.SEKSJON, "3.0.0")

    def test_lenker_til_hele_endringsloggen(self):
        assert "](CHANGELOG.md)" in release_notes.bygg_kort(self.SEKSJON, "3.0.0")

    def test_seksjon_uten_merkede_punkter_gir_feil(self):
        """En kort note som bare er en lenke, sier ingenting."""
        seksjon = "### Fikset\n\n- Et punkt ingen har merket\n"
        with pytest.raises(release_notes.UmerketFeil) as feil:
            release_notes.bygg_kort(seksjon, "3.0.0")
        assert feil.value.versjon == "3.0.0"

    def test_merke_i_handlingskategorien_trengs_ikke(self):
        """Handlingskategorien blir med i sin helhet, så et merke der teller ikke."""
        seksjon = "### Dette må du gjøre selv\n\n- <!--kort--> Gjør noe\n\n### Fikset\n\n- En feil\n"
        with pytest.raises(release_notes.UmerketFeil):
            release_notes.bygg_kort(seksjon, "3.0.0")

    def test_uten_handlingskategori_star_bare_de_merkede(self):
        seksjon = "### Fikset\n\n- <!--kort--> Et punkt\n"
        kort = release_notes.bygg_kort(seksjon, "3.0.0")
        assert kort.startswith("### Det viktigste")

    def test_mellomrom_i_merket_godtas(self):
        seksjon = "### Fikset\n\n- <!-- kort --> Et punkt\n"
        assert "Et punkt" in release_notes.bygg_kort(seksjon, "3.0.0")


class TestErUnderArbeid:
    def test_oeverste_seksjon_er_under_arbeid(self):
        assert release_notes.er_under_arbeid(FALSK_CHANGELOG, "Ikke sluppet")

    def test_sluppet_seksjon_er_historikk(self):
        assert not release_notes.er_under_arbeid(FALSK_CHANGELOG, "2.0.0")


class TestByggKortBody:
    def _repo(self, tmp_path: Path) -> Path:
        (tmp_path / "CHANGELOG.md").write_text("x", encoding="utf-8")
        return tmp_path

    CHANGELOG = """# Changelog

## [3.0.0]

### Fikset

- <!--kort--> Et punkt brukeren merker
- Et punkt til

### Dette må du gjøre selv

- Bekreft enhetsbyttet
"""

    def test_kort_body_har_absolutt_changelog_lenke(self, tmp_path):
        body = release_notes.bygg_kort_body(
            self.CHANGELOG,
            "3.0.0",
            repo_root=self._repo(tmp_path),
            repo_url="https://example.test/eier/repo",
        )
        assert body is not None
        assert "https://example.test/eier/repo/blob/v3.0.0/CHANGELOG.md" in body

    @pytest.mark.parametrize("antall", [1, 2])
    def test_liten_release_beholder_alle_merkede_punkter(self, tmp_path, antall):
        """Faste overskrifter og lenke kan gjøre en liten kortnote lengre enn hele."""
        punkter = [f"- Rettet feil {nummer}" for nummer in range(antall)]
        changelog = "## [3.0.0]\n\n### Fikset\n\n" + "\n".join(f"{punkt} <!--kort-->" for punkt in punkter)
        root = self._repo(tmp_path)
        hele = release_notes.bygg_body(changelog, "3.0.0", repo_root=root)
        kort = release_notes.bygg_kort_body(changelog, "3.0.0", repo_root=root)
        assert hele is not None and kort is not None
        assert [linje.rstrip() for linje in kort.splitlines() if linje.startswith("- ")] == punkter
        assert "<!--kort-->" not in kort
        assert "/blob/v3.0.0/CHANGELOG.md" in kort
        assert len(kort) > len(hele)

    def test_tom_handlingskategori_feller_som_for(self, tmp_path):
        """Vakten mot naken overskrift gjelder begge veier ut av filen."""
        changelog = "## [3.0.0]\n\n### Dette må du gjøre selv\n\n### Fikset\n\n- <!--kort--> A\n"
        with pytest.raises(release_notes.TomKategoriFeil):
            release_notes.bygg_kort_body(changelog, "3.0.0", repo_root=self._repo(tmp_path))

    def test_umerket_seksjon_feller_nar_den_er_streng(self, tmp_path):
        changelog = "## [3.0.0]\n\n### Fikset\n\n- Et punkt\n"
        with pytest.raises(release_notes.UmerketFeil):
            release_notes.bygg_kort_body(changelog, "3.0.0", repo_root=self._repo(tmp_path))

    def test_umerket_historikk_gir_hele_seksjonen(self, tmp_path):
        """En sluppet note skal kunne hentes fram igjen uten at verktøyet krasjer."""
        changelog = "## [3.0.0]\n\n### Fikset\n\n- Et punkt\n"
        body = release_notes.bygg_kort_body(changelog, "3.0.0", repo_root=self._repo(tmp_path), streng=False)
        assert body is not None
        assert "Et punkt" in body

    def test_manglende_seksjon_gir_none(self, tmp_path):
        assert (
            release_notes.bygg_kort_body(
                self.CHANGELOG, "9.9.9", repo_root=self._repo(tmp_path), streng=False
            )
            is None
        )


class TestCliKort:
    def _changelog(self, tmp_path: Path, tekst: str) -> Path:
        sti = tmp_path / "CHANGELOG.md"
        sti.write_text(tekst, encoding="utf-8")
        return sti

    UMERKET = "# Changelog\n\n## [3.0.0]\n\n### Fikset\n\n- Et punkt ingen har merket\n"

    def test_kort_gir_exit_0_og_de_merkede_punktene(self, tmp_path, capsys):
        sti = self._changelog(
            tmp_path,
            "# Changelog\n\n## [3.0.0]\n\n### Fikset\n\n- <!--kort--> Viktig\n- Detalj\n",
        )
        kode = release_notes.main(["3.0.0", "--kort", "--changelog", str(sti), "--repo-root", str(tmp_path)])
        assert kode == 0
        ut = capsys.readouterr().out
        assert "Viktig" in ut
        assert "Detalj" not in ut

    def test_umerket_seksjon_under_arbeid_gir_exit_1(self, tmp_path, capsys):
        sti = self._changelog(tmp_path, self.UMERKET)
        kode = release_notes.main(["3.0.0", "--kort", "--changelog", str(sti), "--repo-root", str(tmp_path)])
        assert kode == 1
        feil = capsys.readouterr().err
        assert "3.0.0" in feil
        assert "<!--kort-->" in feil

    def test_umerket_historikk_gir_exit_0_og_en_merknad(self, tmp_path, capsys):
        sti = self._changelog(
            tmp_path,
            "# Changelog\n\n## [4.0.0]\n\n- <!--kort--> Nyere\n\n"
            "## [3.0.0]\n\n### Fikset\n\n- Et punkt ingen har merket\n",
        )
        kode = release_notes.main(["3.0.0", "--kort", "--changelog", str(sti), "--repo-root", str(tmp_path)])
        fanget = capsys.readouterr()
        assert kode == 0
        assert "Et punkt ingen har merket" in fanget.out
        assert "sluppet" in fanget.err

    def test_uten_kort_star_hele_seksjonen(self, tmp_path, capsys):
        sti = self._changelog(tmp_path, self.UMERKET)
        kode = release_notes.main(["3.0.0", "--changelog", str(sti), "--repo-root", str(tmp_path)])
        assert kode == 0
        assert "Et punkt ingen har merket" in capsys.readouterr().out


class TestEkteChangelogKort:
    """Vakten mot en tom kort note, på repoets egen fil."""

    def _changelog(self) -> str:
        return (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

    def test_seksjonen_under_arbeid_har_merkede_punkter(self):
        changelog = self._changelog()
        versjon = release_notes.kjente_versjoner(changelog)[0]
        seksjon = release_notes.finn_seksjon(changelog, versjon)
        assert seksjon is not None
        assert release_notes.merkede_punkter(seksjon), (
            f"Seksjonen '## [{versjon}]' har ingen punkter merket med "
            f"{release_notes.MERKE_TEKST}. Release-body-en er den korte noten, så "
            "merk punktene en bruker faktisk merker."
        )

    def test_kortmerket_staar_etter_teksten(self):
        """Starten av et punkt må være Markdown, også i GitHubs filvisning."""
        assert not any(linje.startswith("- <!--kort-->") for linje in self._changelog().splitlines())

    def test_lang_referansenote_er_vesentlig_kortere_enn_hele(self):
        """1.17.0 er den lange noten kortformatet ble laget for.

        En ny seksjon med ett eller to punkter kan ha alle merket. Da blir
        kortnoten lengre på grunn av den faste lenken, og det er gyldig.
        """
        changelog = self._changelog()
        versjon = "1.17.0"
        hele = release_notes.bygg_body(changelog, versjon)
        kort = release_notes.bygg_kort_body(changelog, versjon)
        assert hele is not None and kort is not None
        assert len(kort) < len(hele) / 2

    def test_kort_note_har_faa_punkter(self):
        changelog = self._changelog()
        versjon = release_notes.kjente_versjoner(changelog)[0]
        kort = release_notes.bygg_kort_body(changelog, versjon)
        assert kort is not None
        punkter = [linje for linje in kort.splitlines() if linje.startswith("- ")]
        assert len(punkter) <= 15, f"{len(punkter)} punkter er ikke en kort note"

    def test_alle_seksjoner_kan_bygges_kort(self):
        """Historikken er umerket, og skal gi noe fornuftig framfor å krasje."""
        changelog = self._changelog()
        for versjon in release_notes.kjente_versjoner(changelog):
            body = release_notes.bygg_kort_body(
                changelog, versjon, streng=release_notes.er_under_arbeid(changelog, versjon)
            )
            assert body
