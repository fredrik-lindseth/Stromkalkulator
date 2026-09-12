"""Vakt over icons.json, som er der ikonene til entitetene bor.

Fram til september 2026 lå ikonene som 53 `_attr_icon` spredt i sensor-,
binary_sensor- og button-klassene. Home Assistant henter dem fra `icons.json`
i dag, og forskjellen er ikke kosmetisk: et `_attr_icon` havner i
entitetsregisteret som `original_icon` og i state-attributtene, mens
`icons.json` slås opp i frontenden per `translation_key`. Det siste er det
brukeren kan overstyre uten at integrasjonen skriver over valget igjen.

Prisen for flyttingen er at koblingen mellom entitet og ikon ikke lenger står
i samme fil. Testene her er den koblingen: hver entitet med tekst skal ha et
ikon, hvert ikon skal peke på en entitet som finnes, og et nytt `_attr_icon`
skal felles her framfor å bli oppdaget som et manglende ikon hos en bruker.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

KOMPONENT = Path(__file__).parent.parent / "custom_components" / "stromkalkulator"
IKONER = KOMPONENT / "icons.json"
STRINGS = KOMPONENT / "strings.json"
PLATTFORMFILER = ("sensor.py", "binary_sensor.py", "button.py")

ATTR_ICON = re.compile(r"^\s*_attr_icon\b", re.MULTILINE)


def _entity(sti: Path) -> dict[str, dict[str, object]]:
    return json.loads(sti.read_text(encoding="utf-8"))["entity"]


def test_icons_json_finnes_og_er_gyldig() -> None:
    """En flyttet eller ødelagt fil skal felle vakten, ikke tømme den."""
    assert IKONER.is_file(), f"{IKONER} mangler"
    assert _entity(IKONER), "icons.json har ingen entiteter"


def test_samme_plattformer_som_strings() -> None:
    assert set(_entity(IKONER)) == set(_entity(STRINGS))


@pytest.mark.parametrize("plattform", sorted(_entity(STRINGS)))
def test_hver_entitet_har_et_ikon(plattform: str) -> None:
    """En entitet uten ikon faller stille tilbake på device_class-ikonet.

    Alle entitetene i integrasjonen har hatt et valgt ikon siden 1.0. Vil du
    heller ha standardikonet for en device_class, fjern ikonet her og skriv
    hvorfor, så vakten forteller neste økt at det var et valg.
    """
    mangler = sorted(set(_entity(STRINGS)[plattform]) - set(_entity(IKONER)[plattform]))
    assert not mangler, f"{plattform} mangler ikon i icons.json: {mangler}"


@pytest.mark.parametrize("plattform", sorted(_entity(STRINGS)))
def test_ingen_ikon_uten_entitet(plattform: str) -> None:
    """Et ikon på en nøkkel som ikke finnes er dødvekt ingen ser."""
    ekstra = sorted(set(_entity(IKONER)[plattform]) - set(_entity(STRINGS)[plattform]))
    assert not ekstra, f"{plattform} har ikon uten entitet i strings.json: {ekstra}"


def test_ikonverdiene_er_mdi() -> None:
    feil: list[str] = []
    for plattform, noekler in _entity(IKONER).items():
        for noekkel, verdi in noekler.items():
            assert isinstance(verdi, dict)
            standard = verdi.get("default")
            if not isinstance(standard, str) or not standard.startswith("mdi:"):
                feil.append(f"{plattform}.{noekkel} = {standard!r}")
    assert not feil, f"ikoner som ikke er mdi-navn: {feil}"


@pytest.mark.parametrize("fil", PLATTFORMFILER)
def test_ingen_attr_icon_igjen(fil: str) -> None:
    """Nye ikoner skal inn i icons.json, ikke tilbake i klassene."""
    kilde = (KOMPONENT / fil).read_text(encoding="utf-8")
    assert not ATTR_ICON.search(kilde), f"{fil} setter _attr_icon; flytt ikonet til icons.json"
