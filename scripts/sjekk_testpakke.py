#!/usr/bin/env python3
"""Sjekk at testpakken i repoet stemmer med den som kjører på Home Assistant.

`packages/stromkalkulator_test.yaml` finnes to steder: her i repoet og
installert på HA. De har driftet fra hverandre før uten at noe fanget det
(stromkalkulator-5uwhkc), så dette scriptet sammenligner de to og slår opp
hver entitetsreferanse i pakken mot faktiske states.

Tre ting sjekkes:

1. Filen på HA er byte-identisk med repoets.
2. Hver entitet pakken refererer til finnes i state-maskinen.
3. Hver test-sensor pakken definerer står i en grei tilstand, altså ikke FEIL,
   unavailable eller unknown.

Exit 0 hvis alt er grønt, 1 ellers.

Bruk:
    python3 scripts/sjekk_testpakke.py
    python3 scripts/sjekk_testpakke.py --states states.json
    python3 scripts/sjekk_testpakke.py --hopp-over-fil

`--states` leser en JSON-dump i stedet for å spørre HA, og hopper da over
filsammenligningen av seg selv. `--hopp-over-fil` gjør det samme mot en
kjørende HA.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PAKKE = REPO_ROOT / "packages" / "stromkalkulator_test.yaml"
FJERN_STI = "/config/packages/stromkalkulator_test.yaml"
SSH_OPTS = ["-o", "IdentitiesOnly=yes"]

# states('x.y'), state_attr("x.y", ...), is_state('x.y', ...), expand(...)
REF_MONSTER = re.compile(
    r"""(?:states|state_attr|is_state|is_state_attr|expand|device_id|area_id)\s*\(\s*"""
    r"""["']([a-z_]+\.[a-z0-9_]+)["']"""
)

# Tilstander som ikke er en bestått test.
DARLIGE_TILSTANDER = {"FEIL", "unavailable", "unknown", "SENSOR MANGLER"}

# Samlesensoren i pakken, som rapporterer "X/Y OK".
SAMLESENSOR = "sensor.test_alle_tester_ok"
SAMLEMONSTER = re.compile(r"^(\d+)\s*/\s*(\d+)")


def slugify(navn: str) -> str:
    """Samme entity-id-slug som Home Assistant lager av et sensornavn."""
    tekst = navn.lower()
    for fra, til in (("ø", "o"), ("æ", "ae"), ("å", "a"), ("ß", "ss")):
        tekst = tekst.replace(fra, til)
    tekst = unicodedata.normalize("NFKD", tekst)
    tekst = "".join(c for c in tekst if not unicodedata.combining(c))
    tekst = re.sub(r"[^a-z0-9]+", "_", tekst)
    return tekst.strip("_")


def les_pakke(sti: Path) -> dict[str, Any]:
    with sti.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{sti} er ikke et YAML-objekt")
    return data


def definerte_entiteter(pakke: dict[str, Any]) -> dict[str, str]:
    """Entity-id -> navn for alt template-pakken selv definerer."""
    funnet: dict[str, str] = {}
    blokker = pakke.get("template") or []
    if isinstance(blokker, dict):
        blokker = [blokker]
    for blokk in blokker:
        if not isinstance(blokk, dict):
            continue
        for domene, oppforinger in blokk.items():
            if domene not in ("sensor", "binary_sensor"):
                continue
            if isinstance(oppforinger, dict):
                oppforinger = [oppforinger]
            for oppforing in oppforinger or []:
                navn = (oppforing or {}).get("name")
                if navn:
                    funnet[f"{domene}.{slugify(str(navn))}"] = str(navn)
    return funnet


def _strenger(node: Any) -> list[str]:
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [s for v in node.values() for s in _strenger(v)]
    if isinstance(node, list):
        return [s for v in node for s in _strenger(v)]
    return []


def refererte_entiteter(pakke: dict[str, Any]) -> set[str]:
    return {treff for tekst in _strenger(pakke) for treff in REF_MONSTER.findall(tekst)}


def hent_states_fra_ha(host: str) -> dict[str, str]:
    kommando = 'curl -s -H "Authorization: Bearer $SUPERVISOR_TOKEN" http://supervisor/core/api/states'
    resultat = subprocess.run(
        ["ssh", *SSH_OPTS, host, kommando],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultat.returncode != 0:
        raise RuntimeError(f"ssh mot {host} feilet ({resultat.returncode}): {resultat.stderr.strip()}")
    return _parse_states(resultat.stdout, f"{host} (supervisor-proxy)")


def _parse_states(rå: str, kilde: str) -> dict[str, str]:
    try:
        data = json.loads(rå)
    except json.JSONDecodeError as feil:
        raise RuntimeError(f"Fikk ikke JSON fra {kilde}: {feil}") from feil
    if not isinstance(data, list):
        raise RuntimeError(f"Forventet en liste med states fra {kilde}")
    return {e["entity_id"]: e.get("state", "") for e in data if "entity_id" in e}


def hent_fjernfil(host: str) -> str | None:
    resultat = subprocess.run(
        ["ssh", *SSH_OPTS, host, f"cat {FJERN_STI}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if resultat.returncode != 0:
        return None
    return resultat.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="ha-local", help="ssh-vert (default ha-local)")
    parser.add_argument(
        "--states",
        type=Path,
        help="les states fra en JSON-fil i stedet for å spørre HA",
    )
    parser.add_argument(
        "--hopp-over-fil",
        action="store_true",
        help="ikke sammenlign pakkefilen på HA med repoets",
    )
    args = parser.parse_args()

    pakke = les_pakke(PAKKE)
    definert = definerte_entiteter(pakke)
    referert = refererte_entiteter(pakke)

    if args.states:
        states = _parse_states(args.states.read_text(encoding="utf-8"), str(args.states))
    else:
        states = hent_states_fra_ha(args.host)

    problemer: list[str] = []

    # 1. Filen på HA mot repoets.
    if args.states or args.hopp_over_fil:
        print("Pakkefil: hoppet over")
    else:
        fjern = hent_fjernfil(args.host)
        lokal = PAKKE.read_text(encoding="utf-8")
        if fjern is None:
            problemer.append(f"fant ikke {FJERN_STI} på {args.host}")
            print(f"Pakkefil: MANGLER på {args.host}")
        elif fjern != lokal:
            problemer.append(f"{FJERN_STI} på {args.host} er ulik repoets pakke (kjør `just deploy-testpakke`)")
            print("Pakkefil: DRIFT, ulik repoets")
        else:
            print("Pakkefil: identisk med repoets")

    # 2. Referanser.
    mangler = sorted(e for e in referert if e not in states and e not in definert)
    print(f"Referanser: {len(referert)} sjekket, {len(mangler)} manglende")
    for entitet in mangler:
        problemer.append(f"referanse finnes ikke på HA: {entitet}")
        print(f"  MANGLER  {entitet}")

    # 3. Test-sensorenes tilstand.
    ok = 0
    for entitet in sorted(definert):
        tilstand = states.get(entitet)
        if tilstand is None:
            problemer.append(f"test-sensor mangler på HA: {entitet}")
            print(f"  MANGLER  {entitet}")
            continue
        tilstand = tilstand.strip()
        if tilstand in DARLIGE_TILSTANDER:
            problemer.append(f"{entitet} står i {tilstand}")
            print(f"  {tilstand:<8} {entitet}")
        else:
            ok += 1
            print(f"  OK       {entitet} = {tilstand}")
    print(f"Test-sensorer: {ok}/{len(definert)} i grei tilstand")

    # 4. Samlesensoren skal si X/X, ikke bare finnes.
    samlet = (states.get(SAMLESENSOR) or "").strip()
    treff = SAMLEMONSTER.match(samlet)
    if not treff:
        problemer.append(f"{SAMLESENSOR} sier {samlet!r}, forventet «X/Y OK»")
        print(f"Samlet: uleselig ({samlet!r})")
    elif treff.group(1) != treff.group(2):
        problemer.append(f"{SAMLESENSOR} sier {samlet}, ikke alle kjernetestene er OK")
        print(f"Samlet: {samlet}")
    else:
        print(f"Samlet: {samlet}")

    if problemer:
        print()
        print(f"{len(problemer)} problem(er):")
        for problem in problemer:
            print(f"  - {problem}")
        return 1

    print()
    print("Testpakken er i takt med HA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
