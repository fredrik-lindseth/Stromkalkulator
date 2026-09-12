"""Selvkonsistens i packages/stromkalkulator_test.yaml.

Testpakken er YAML som lever på HA, ikke Python, så ingenting i den vanlige
suiten fanget at en entitetsreferanse pekte i løse luften. Denne filen sjekker
det som kan sjekkes uten nett: at pakken parser, at test-sensorene den viser
til er definert i pakken selv, og at referansene til integrasjonen svarer til
en sensor integrasjonen faktisk lager.

Instansspesifikke entity-id-er (device-prefiks, HAs dedup-nummerering) kan bare
verifiseres mot en kjørende HA. Det gjør scripts/sjekk_testpakke.py. Nederst
testes at scriptets henting av pakken fra HA skiller ssh-feil fra manglende fil.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

try:
    import yaml  # noqa: F401
except ModuleNotFoundError as feil:  # pragma: no cover
    raise ModuleNotFoundError(
        "pyyaml mangler, og da kan ikke testpakken sjekkes. "
        "Kjør suiten med `pipx run --with hypothesis --with pyyaml pytest ...`, "
        "eller installer pyyaml i miljøet. Denne filen skal feile, ikke skippe: "
        "en vakt som hopper over seg selv vakter ingenting."
    ) from feil

import sjekk_testpakke  # noqa: E402
from sjekk_testpakke import (  # noqa: E402
    definerte_entiteter,
    les_pakke,
    refererte_entiteter,
    slugify,
)

PAKKE = REPO_ROOT / "packages" / "stromkalkulator_test.yaml"
NB_JSON = REPO_ROOT / "custom_components" / "stromkalkulator" / "translations" / "nb.json"


@pytest.fixture(scope="module")
def pakke() -> dict:
    return les_pakke(PAKKE)


@pytest.fixture(scope="module")
def integrasjonsslugger() -> dict[str, set[str]]:
    """Entity-id-slugger integrasjonen kan lage, per domene, fra nb.json."""
    data = json.loads(NB_JSON.read_text(encoding="utf-8"))
    entiteter = data.get("entity", {})
    return {
        domene: {slugify(oppforing["name"]) for oppforing in nøkler.values() if oppforing.get("name")}
        for domene, nøkler in entiteter.items()
    }


def test_pakken_definerer_sensorer(pakke: dict) -> None:
    definert = definerte_entiteter(pakke)
    assert definert, "testpakken definerer ingen template-sensorer"
    assert "sensor.test_alle_tester_ok" in definert, "samlesensoren mangler"


def test_unique_id_er_unike(pakke: dict) -> None:
    ider = [
        oppforing["unique_id"]
        for blokk in pakke["template"]
        for oppforinger in blokk.values()
        for oppforing in oppforinger
        if "unique_id" in oppforing
    ]
    antall_sensorer = len(definerte_entiteter(pakke))
    assert len(ider) == antall_sensorer, "en eller flere sensorer mangler unique_id"
    assert len(set(ider)) == len(ider), f"duplikate unique_id: {ider}"


def test_alle_test_referanser_er_definert_i_pakken(pakke: dict) -> None:
    """En test-sensor som viser til en annen test-sensor må finne den her."""
    definert = set(definerte_entiteter(pakke))
    test_referanser = {ref for ref in refererte_entiteter(pakke) if ref.split(".", 1)[1].startswith("test_")}
    assert test_referanser, "fant ingen test_-referanser, regexen er antagelig ødelagt"
    assert test_referanser <= definert, (
        f"refererer til test-sensorer som ikke finnes i pakken: {sorted(test_referanser - definert)}"
    )


def test_samlesensoren_teller_bare_egne_sensorer(pakke: dict) -> None:
    """«Alle tester OK» skal telle sensorer pakken selv definerer."""
    definert = definerte_entiteter(pakke)
    samlet = next(
        oppforing
        for blokk in pakke["template"]
        for oppforinger in blokk.values()
        for oppforing in oppforinger
        if slugify(oppforing["name"]) == "test_alle_tester_ok"
    )
    talt = {ref for ref in refererte_entiteter({"x": samlet["state"]}) if ref.startswith("sensor.test_")}
    assert talt, "samlesensoren teller ingenting"
    assert talt <= set(definert)


def test_referanser_til_integrasjonen_finnes(pakke: dict, integrasjonsslugger: dict[str, set[str]]) -> None:
    """Ikke-test-referanser skal svare til en sensor integrasjonen lager.

    Entity-id-en på en gitt instans kan ha device-navnet som prefiks, og HA
    legger på `_2`/`_3` når flere entiteter deler navn, så begge formene
    godtas.
    """
    ukjente = []
    for ref in sorted(refererte_entiteter(pakke)):
        domene, objekt = ref.split(".", 1)
        if objekt.startswith("test_"):
            continue
        kjente = integrasjonsslugger.get(domene, set())
        treff = any(
            objekt == slug
            or objekt.endswith(f"_{slug}")
            or (objekt.startswith(f"{slug}_") and objekt[len(slug) + 1 :].isdigit())
            for slug in kjente
        )
        if not treff:
            ukjente.append(ref)
    assert not ukjente, (
        f"testpakken refererer til entiteter integrasjonen ikke lager (navn endret i translations/nb.json?): {ukjente}"
    )


def test_ingen_utdaterte_stromstotte_terskler() -> None:
    """2024- og 2025-tersklene skal ikke stå igjen som aktiv beregning.

    Driften i stromkalkulator-5uwhkc var nettopp dette: HA-kopien regnet med
    2024-terskelen. Historikk-kommentaren får stå, tallene i templatene ikke.
    """
    aktive = [
        linje.strip()
        for linje in PAKKE.read_text(encoding="utf-8").splitlines()
        if "{%" in linje and ("0.9125" in linje or "0.9375" in linje)
    ]
    assert not aktive, f"utdatert strømstøtte-terskel i bruk: {aktive}"


class TestHentFjernfil:
    """«ssh feilet» og «filen finnes ikke» er to forskjellige svar.

    Blandet sammen får du beskjed om å deploye en pakke som kanskje ligger på
    HA alt, den dagen nettet er nede.
    """

    def _kjor(self, monkeypatch, returkode: int, stderr: str = "") -> str | None:
        def falsk_run(*_args, **_kwargs):
            return subprocess.CompletedProcess(
                args=[], returncode=returkode, stdout="innhold\n", stderr=stderr
            )

        monkeypatch.setattr(sjekk_testpakke.subprocess, "run", falsk_run)
        return sjekk_testpakke.hent_fjernfil("ha-local")

    def test_ssh_feil_hever(self, monkeypatch):
        with pytest.raises(RuntimeError, match="ssh mot ha-local feilet"):
            self._kjor(monkeypatch, 255, stderr="Could not resolve hostname")

    def test_manglende_fil_gir_none(self, monkeypatch):
        assert self._kjor(monkeypatch, 1) is None

    def test_funnet_fil_gir_innhold(self, monkeypatch):
        assert self._kjor(monkeypatch, 0) == "innhold\n"
