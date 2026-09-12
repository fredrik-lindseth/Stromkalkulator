"""Vokter at det bare finnes én måte å kjøre testene på.

Bakgrunnen er konkret: `just test` og docs kjørte ekte-HA-testen i unit-miljøet
og feilet på collection, mens CI ekskluderte den riktig, og `ruff check` i
AGENTS.md var smalere enn det pre-commit faktisk kjørte. Begge deler er sprik
mellom filer som skal si det samme, og begge fikk stå fordi ingenting leste dem
sammen.

Denne fila leser justfile, AGENTS.md, docs/testing.md, docs/development.md,
.pre-commit-config.yaml og .github/workflows/ci.yml, og feiler når de ikke er
enige. Den kjører ingen tester; den sjekker at kommandoene er de samme.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]

JUSTFILE = REPO / "justfile"
AGENTS = REPO / "AGENTS.md"
TESTING = REPO / "docs" / "testing.md"
DEVELOPMENT = REPO / "docs" / "development.md"
PRECOMMIT = REPO / ".pre-commit-config.yaml"
CI = REPO / ".github" / "workflows" / "ci.yml"

# Oppskriftene som utgjør testinngangen. Andre just-oppskrifter (deploy,
# snapshot, verify) er ikke denne filas ansvar.
TEST_RECIPES = {"test", "test-unit", "check", "test-ha", "test-e2e"}

HA_TARGETS = {"minimum", "current"}

DOCS_MED_KOMMANDOER = (AGENTS, TESTING, DEVELOPMENT)


def _les(sti: Path) -> str:
    assert sti.is_file(), f"{sti.relative_to(REPO)} finnes ikke"
    return sti.read_text(encoding="utf-8")


def _just_recipes() -> dict[str, list[str]]:
    """Oppskriftsnavn til kroppslinjer, lest rett fra justfile.

    Parseren er med vilje enkel: en oppskrift starter i kolonne 0 på formen
    `navn [parametre]:` (ikke `:=`, som er variabeltilordning), og kroppen er
    de innrykkede linjene under.
    """
    recipes: dict[str, list[str]] = {}
    gjeldende: str | None = None
    for linje in _les(JUSTFILE).splitlines():
        if linje.startswith((" ", "\t")):
            if gjeldende:
                recipes[gjeldende].append(linje.strip())
            continue
        if not linje.strip() or linje.startswith("#"):
            continue
        treff = re.match(r"^([a-zA-Z][\w-]*)((?:\s+[^:\n]*)?):(?!=)\s*(.*)$", linje)
        if treff:
            gjeldende = treff.group(1)
            recipes.setdefault(gjeldende, [])
            # `test: test-unit check` har avhengighetene etter kolonet.
            if treff.group(3):
                recipes[gjeldende].append("# avhengigheter: " + treff.group(3))
        else:
            gjeldende = None
    return recipes


@pytest.fixture(scope="module")
def recipes() -> dict[str, list[str]]:
    return _just_recipes()


def test_justfile_har_hele_testinngangen(recipes: dict[str, list[str]]) -> None:
    mangler = TEST_RECIPES - recipes.keys()
    assert not mangler, f"justfile mangler oppskriftene {sorted(mangler)}"


def test_just_test_er_unit_pluss_kvalitet(recipes: dict[str, list[str]]) -> None:
    """`just test` skal ikke kunne bli noe annet enn de to andre til sammen."""
    kropp = " ".join(recipes["test"])
    assert "test-unit" in kropp and "check" in kropp, (
        "`just test` skal være test-unit + check, ellers betyr AGENTS.md sin "
        f"ene kommando noe annet enn den sier. Fant: {kropp!r}"
    )


def test_alle_just_kommandoer_i_docs_finnes(recipes: dict[str, list[str]]) -> None:
    """En doc som viser til en oppskrift som ikke finnes, er verre enn ingen doc."""
    for sti in DOCS_MED_KOMMANDOER:
        for navn in re.findall(r"just ([a-zA-Z][\w-]*)", _les(sti)):
            assert navn in recipes, (
                f"{sti.relative_to(REPO)} viser til `just {navn}`, som ikke finnes i justfile"
            )


def test_docs_har_ingen_gammel_pipx_kommando() -> None:
    """pipx-kommandoen var den gamle inngangen, og den samlet ekte-HA-testen."""
    for sti in DOCS_MED_KOMMANDOER:
        tekst = _les(sti)
        assert "pipx run" not in tekst, (
            f"{sti.relative_to(REPO)} står igjen med den gamle pipx-kommandoen. "
            "Den er erstattet av just-oppskriftene."
        )
        assert "test_smoke_ha" not in tekst, (
            f"{sti.relative_to(REPO)} viser til tests/test_smoke_ha.py, som er flyttet til tests_ha/"
        )


def test_ekte_ha_testen_er_flyttet_ut_av_unit_treet() -> None:
    assert not (REPO / "tests" / "test_smoke_ha.py").exists(), (
        "tests/test_smoke_ha.py er flyttet til tests_ha/; den kan ikke samles i unit-miljøet"
    )
    ha_tester = sorted((REPO / "tests_ha").glob("test_*.py"))
    assert ha_tester, "tests_ha/ har ingen testfiler. Tom collection er rødt, ikke grønt."
    assert (REPO / "tests_ha" / "conftest.py").is_file()
    assert (REPO / "tests_e2e" / "README.md").is_file()


def test_gruppene_i_pyproject_er_de_justfile_bruker(recipes: dict[str, list[str]]) -> None:
    pyproject = tomllib.loads(_les(REPO / "pyproject.toml"))
    grupper = set(pyproject["dependency-groups"])
    assert grupper == {"unit", "kvalitet", "ha-minimum", "ha-current"}, (
        f"uventede dependency-grupper: {sorted(grupper)}"
    )

    brukt = set()
    for kropp in recipes.values():
        brukt |= set(re.findall(r"--group \"?([\w-]+)", " ".join(kropp)))
    # `ha-$mal` settes fra target-variabelen, så den kommer ikke ut av regexen.
    brukt.discard("ha-$mal")
    assert {"unit", "kvalitet"} <= brukt, f"justfile bruker ikke unit og kvalitet: {sorted(brukt)}"


def test_ha_matrisen_er_den_samme_i_justfile_ci_og_docs(recipes: dict[str, list[str]]) -> None:
    kropp = "\n".join(recipes["test-ha"])
    i_justfile = {m for m in HA_TARGETS if re.search(rf"^\s*{m}\)", kropp, re.MULTILINE)}
    assert i_justfile == HA_TARGETS, (
        f"`just test-ha` godtar {sorted(i_justfile)}, forventet {sorted(HA_TARGETS)}"
    )

    ci = yaml.safe_load(_les(CI))
    i_ci = set(ci["jobs"]["test-ha"]["strategy"]["matrix"]["target"])
    assert i_ci == HA_TARGETS, f"ci.yml kjører {sorted(i_ci)}, justfile godtar {sorted(HA_TARGETS)}"

    testing = _les(TESTING)
    for mal in HA_TARGETS:
        assert f"just test-ha target={mal}" in testing, (
            f"docs/testing.md nevner ikke `just test-ha target={mal}`"
        )


def test_python_versjonene_i_justfile_star_i_docs(recipes: dict[str, list[str]]) -> None:
    """Matrisen i docs/testing.md skal ikke kunne råtne bort fra justfile."""
    tabell = _les(TESTING)
    for navn in ("test-unit", "check", "test-ha"):
        for versjon in re.findall(r"--python \"?3\.(\d+)", " ".join(recipes[navn])):
            assert f"3.{versjon}" in tabell, (
                f"justfile kjører {navn} på Python 3.{versjon}, men docs/testing.md nevner den ikke"
            )
    for versjon in re.findall(r"python=(3\.\d+)", "\n".join(recipes["test-ha"])):
        assert versjon in tabell, (
            f"`just test-ha` kjører Python {versjon}, men docs/testing.md nevner den ikke"
        )


def test_plugin_pinningene_star_i_docs() -> None:
    """HA-versjonen følger av plugin-versjonen, så begge må stå samme sted."""
    pyproject = tomllib.loads(_les(REPO / "pyproject.toml"))
    testing = _les(TESTING)
    for gruppe in ("ha-minimum", "ha-current"):
        (pin,) = [
            krav
            for krav in pyproject["dependency-groups"][gruppe]
            if krav.startswith("pytest-homeassistant-custom-component")
        ]
        versjon = pin.split("==")[1]
        assert versjon in testing, (
            f"{gruppe} er låst til plugin {versjon}, men docs/testing.md nevner den ikke"
        )


def test_hooken_kjorer_samme_oppskrift_som_justfile(recipes: dict[str, list[str]]) -> None:
    config = yaml.safe_load(_les(PRECOMMIT))
    (pytest_hook,) = [hook for repo in config["repos"] for hook in repo["hooks"] if hook["id"] == "pytest"]
    entry = pytest_hook["entry"].strip()
    assert entry.startswith("just "), (
        f"pre-commit-hooken kjører {entry!r} og ikke en just-oppskrift. Da kan den gå grønn "
        "på noe annet enn det AGENTS.md ber om."
    )
    navn = entry.split()[1]
    assert navn in recipes, f"pre-commit-hooken kaller `just {navn}`, som ikke finnes"
    assert pytest_hook["stages"] == ["pre-push"]


def test_ci_kjorer_bare_just_oppskrifter(recipes: dict[str, list[str]]) -> None:
    ci = yaml.safe_load(_les(CI))
    for navn in ("test-unit", "check", "test-ha"):
        assert navn in ci["jobs"], f"ci.yml mangler jobben {navn}"

    kalt = set()
    for jobb in ci["jobs"].values():
        for steg in jobb["steps"]:
            kommando = steg.get("run", "")
            for treff in re.findall(r"\bjust ([a-zA-Z][\w-]*)", kommando):
                kalt.add(treff)
            if "pytest " in kommando or "ruff " in kommando or "mypy " in kommando:
                raise AssertionError(
                    f"ci.yml kjører verktøyet direkte i steget {steg.get('name')!r}. "
                    "Alt som også kjøres lokalt skal gå gjennom en just-oppskrift."
                )
    for navn in kalt:
        assert navn in recipes, f"ci.yml kaller `just {navn}`, som ikke finnes i justfile"
    assert {"test-unit", "check", "test-ha"} <= kalt, (
        f"ci.yml kaller bare {sorted(kalt)}; forventet test-unit, check og test-ha"
    )
