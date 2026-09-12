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

import json
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
HACS = REPO / "hacs.json"
UV_LOCK = REPO / "uv.lock"

# Filene som har lov til å nevne en HA-versjon i klartekst. Hver forekomst
# sjekkes mot hacs.json og uv.lock, så en kopi som ikke er oppdatert feller.
FILER_MED_HA_VERSJON = (JUSTFILE, AGENTS, TESTING, DEVELOPMENT, REPO / "pyproject.toml", HACS)

HA_VERSJON = re.compile(r"\b20\d\d\.\d+\.\d+\b")

# Oppskriftene som utgjør testinngangen. Andre just-oppskrifter (deploy,
# snapshot, verify) er ikke denne filas ansvar.
TEST_RECIPES = {"test", "test-unit", "check", "test-ha", "test-e2e"}

HA_TARGETS = {"minimum", "current"}

# Det `just check` faktisk skal gjøre. Vakten sjekket at oppskriften het
# «check», ikke at den kjørte noe, så mypy, ruff format eller vulture kunne
# falle ut uten at noe felte. Bredden står med: `ruff check .` dekker hele
# repoet, og en smalning til custom_components/ ville gått grønt på scripts/.
CHECK_KOMMANDOER: tuple[tuple[str, str], ...] = (
    ("ruff check .", "ruff"),
    ("ruff format --check .", "format"),
    ("mypy custom_components/stromkalkulator/", "mypy"),
    ("vulture custom_components/stromkalkulator", "vulture"),
)

DOCS_MED_KOMMANDOER = (AGENTS, TESTING, DEVELOPMENT)


def _ha_versjon_per_mal(recipes: dict[str, list[str]]) -> dict[str, str]:
    """HA-versjonen hver ha-gruppe faktisk løser til, lest ut av uv.lock.

    Gruppene pinner en plugin-versjon, og det er den som drar inn
    homeassistant. Uten dette oppslaget kan noen heve hacs.json uten at
    `just test-ha target=minimum` tester noe annet enn før.
    """
    lock = tomllib.loads(_les(UV_LOCK))
    pakker = [p for p in lock["package"] if p["name"] == "homeassistant"]
    assert pakker, "uv.lock har ingen homeassistant. Da vakter denne testen ingenting."

    kropp = "\n".join(recipes["test-ha"])
    per_mal: dict[str, str] = {}
    for mal in sorted(HA_TARGETS):
        (python,) = re.findall(rf"^\s*{mal}\)\s*python=(3\.\d+)", kropp, re.MULTILINE)
        treff = [p for p in pakker if any(python in m for m in p.get("resolution-markers", []))]
        assert len(treff) == 1, (
            f"fant {len(treff)} homeassistant i uv.lock for Python {python} ({mal}); forventet nøyaktig én"
        )
        per_mal[mal] = treff[0]["version"]
    return per_mal


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


def test_just_check_kjorer_alle_fire_sjekkene(recipes: dict[str, list[str]]) -> None:
    """AGENTS.md lover fire sjekker. Faller én ut, skal vakten felle det."""
    kropp = "\n".join(recipes["check"])
    for kommando, _ in CHECK_KOMMANDOER:
        assert kommando in kropp, (
            f"`just check` kjører ikke {kommando!r}. AGENTS.md lover ruff check, "
            "ruff format --check, mypy og vulture, og det er denne oppskriften "
            "som er lovet."
        )


def test_agents_md_navngir_de_samme_fire_sjekkene() -> None:
    """Teksten skal ikke kunne love tre av fire uten at noe sier fra."""
    tekst = _les(AGENTS)
    for _, verktoy in CHECK_KOMMANDOER:
        assert verktoy in tekst, (
            f"AGENTS.md nevner ikke {verktoy} i «Før commit», men `just check` kjører den"
        )


def test_just_test_unit_kjorer_hele_testtreet(recipes: dict[str, list[str]]) -> None:
    """En smalning til én fil ville gitt grønt på resten uten å si fra."""
    kropp = " ".join(recipes["test-unit"])
    assert re.search(r"pytest tests/(?:\s|$|\{)", kropp), (
        f"`just test-unit` kjører ikke hele tests/. Fant: {kropp!r}"
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


def test_hacs_json_er_kilden_til_minimumsversjonen(recipes: dict[str, list[str]]) -> None:
    """`just test-ha target=minimum` må teste det hacs.json lover brukerne.

    Uten denne koblingen kan hacs.json heves uten at minimum-miljøet endrer
    seg, og da tester vi noe annet enn løftet.
    """
    lovet = json.loads(_les(HACS))["homeassistant"]
    testet = _ha_versjon_per_mal(recipes)["minimum"]
    assert lovet == testet, (
        f"hacs.json lover HA {lovet}, men ha-minimum i uv.lock løser til {testet}. Hev begge, eller ingen."
    )


def test_ingen_ha_versjon_star_skrevet_for_hand(recipes: dict[str, list[str]]) -> None:
    """Ni kopier av «2025.1.0» hadde ingenting som holdt dem i synk.

    Nå har de det: hver HA-versjon som står i klartekst i justfile, AGENTS.md,
    docs eller pyproject må være en av de to uv.lock faktisk løser.
    """
    gyldige = set(_ha_versjon_per_mal(recipes).values())
    for sti in FILER_MED_HA_VERSJON:
        for linjenr, linje in enumerate(_les(sti).splitlines(), start=1):
            for funnet in HA_VERSJON.findall(linje):
                assert funnet in gyldige, (
                    f"{sti.relative_to(REPO)}:{linjenr} nevner HA {funnet}, men uv.lock "
                    f"løser {sorted(gyldige)}. Rett kopien eller lås gruppen på nytt."
                )


def test_begge_ha_versjonene_star_i_versjonstabellen(recipes: dict[str, list[str]]) -> None:
    tabell = _les(TESTING)
    for mal, versjon in _ha_versjon_per_mal(recipes).items():
        assert versjon in tabell, (
            f"`just test-ha target={mal}` kjører HA {versjon}, men docs/testing.md nevner den ikke"
        )
