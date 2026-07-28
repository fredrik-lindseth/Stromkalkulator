#!/usr/bin/env python3
"""Generer kapasitetstrinn for dso.py fra fri-nettleie.

Skrevet under incident 006, der fjorten nettselskap viste seg å ha en kopiert
mal i stedet for priser. Grunnen til at malen kom inn var at trinnene ble fylt
ut for hånd, en oppføring av gangen, uten kilde. Dette scriptet gjør det samme
arbeidet maskinelt: henter tersklene fra fri-nettleie, konverterer dem til vårt
format og skriver kilde og tariffdato i en kommentar over hver liste.

Bruk:
    uv run --with pyyaml python scripts/generer_kapasitetstrinn.py            # vis diff
    uv run --with pyyaml python scripts/generer_kapasitetstrinn.py --skriv    # skriv til dso.py
    uv run --with pyyaml python scripts/generer_kapasitetstrinn.py --dso vevig,linja

Default er tørrkjøring. Les diffen før du bruker --skriv.

Nettselskap i BESKYTTET røres ikke: der har vi en sterkere kilde enn
fri-nettleie, og den skal vinne. Legg til nye der du har verifisert mot
nettselskapets egen prisliste eller mot faktura.

Etter kjøring, kjør alltid:
    uv run --with pyyaml python scripts/sjekk_mot_fri_nettleie.py --bare-avvik
    pipx run --with hypothesis --with pyyaml pytest tests/ --ignore=tests/test_smoke_ha.py

Data fra https://github.com/kraftsystemet/fri-nettleie/ (CC-BY-4.0).
"""

from __future__ import annotations

import argparse
import importlib
import re
import sys
import types
from datetime import date
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DSO_PY = REPO_ROOT / "custom_components" / "stromkalkulator" / "dso.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
_pkg = types.ModuleType("_sk")
_pkg.__path__ = [str(REPO_ROOT / "custom_components" / "stromkalkulator")]  # type: ignore[attr-defined]
sys.modules["_sk"] = _pkg
DSO_LIST = importlib.import_module("_sk.dso").DSO_LIST
_const = importlib.import_module("_sk.const")

# Gjenbruker hentingen, mappingen og konverteringen fra drift-vakten, så de to
# aldri kan komme ut av takt om formatet hos fri-nettleie endrer seg.
sjekk = importlib.import_module("sjekk_mot_fri_nettleie")

# Nettselskap der vi har en bedre kilde enn fri-nettleie. Verdien er
# begrunnelsen, som også havner i rapporten.
BESKYTTET: dict[str, str] = {
    "bkk": "verifisert mot ekte BKK-fakturaer",
    "elvia": "verifisert mot Elvias eget tariffblad",
    "rakkestad_energi": "følger elvia",
    "nettselskapet": "verifisert mot nettselskapet.as",
    "glitre": "verifisert mot glitrenett.no",
    "area_nett_omrade1": "Areas eget prisblad, fri-nettleie er utdatert i topptrinnene",
    "area_nett_omrade2": "Areas eget prisblad",
    "area_nett_omrade3": "Areas eget prisblad",
    "area_nett": "utfaset, speiler område 2",
    "fjellnett": "fjellnett.no publiserer nyere tariff enn fri-nettleie",
}


def formater_trinn(trinn: list[tuple[float, int]]) -> list[str]:
    """Trinnliste som dso.py-linjer."""
    ut = []
    for grense, pris in trinn:
        g = 'float("inf")' if grense == float("inf") else f"{grense:g}"
        ut.append(f"            ({g}, {pris}),")
    return ut


def finn_blokk(linjer: list[str], dso_id: str) -> tuple[int, int]:
    """(indeks for kapasitetstrinn-linjen, indeks for avsluttende `],`)."""
    start = next(
        (i for i, linje in enumerate(linjer) if linje.strip() == f'"{dso_id}": {{'), None
    )
    if start is None:
        raise SystemExit(f"fant ikke DSO-blokk for {dso_id}")
    kap = None
    for i in range(start, len(linjer)):
        if linjer[i].strip().startswith('"kapasitetstrinn"'):
            kap = i
            break
        if i > start and re.match(r'^    "[a-z_0-9]+": \{$', linjer[i]):
            raise SystemExit(f"{dso_id}: traff neste DSO før kapasitetstrinn")
    if kap is None:
        raise SystemExit(f"fant ikke kapasitetstrinn for {dso_id}")
    slutt = next(i for i in range(kap + 1, len(linjer)) if linjer[i].strip() == "],")
    return kap, slutt


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dato", type=date.fromisoformat, default=date.today(),
                   help="Tariffdato å hente for (YYYY-MM-DD), default: i dag")
    p.add_argument("--dso", help="Komma-separert liste over DSO-IDer")
    p.add_argument("--skriv", action="store_true",
                   help="Skriv endringene til dso.py. Uten dette vises bare diffen.")
    args = p.parse_args()

    filter_ids = set(args.dso.split(",")) if args.dso else None
    remote = set(sjekk.list_remote_dsoer())
    tekst = DSO_PY.read_text(encoding="utf-8")
    linjer = tekst.split("\n")

    endringer: dict[str, dict[str, Any]] = {}
    hoppet: list[tuple[str, str]] = []

    for dso_id, entry in sorted(DSO_LIST.items()):
        if dso_id == "custom" or (filter_ids and dso_id not in filter_ids):
            continue
        if dso_id in BESKYTTET:
            hoppet.append((dso_id, f"beskyttet: {BESKYTTET[dso_id]}"))
            continue
        slug = sjekk.match_dso(dso_id, remote)
        if slug is None:
            hoppet.append((dso_id, "ingen match i fri-nettleie"))
            continue
        data = sjekk.hent_yaml(slug)
        tariff = sjekk.aktiv_tariff(data, args.dato) if data else None
        if tariff is None:
            hoppet.append((dso_id, "ingen aktiv husholdningstariff"))
            continue
        mva = 1 + _const.get_mva_sats(_const.resolve_avgiftssone(entry))
        nye = sjekk.deres_trinn(tariff, mva)
        if nye is None:
            metode = (tariff.get("fastledd") or {}).get("metode", "ukjent")
            hoppet.append((dso_id, f"fastledd-metode {metode}, ikke kW-trinn"))
            continue

        gamle = sjekk.vaare_trinn(entry)
        # Avvik under toleransen er avrunding, ikke prisendring. Å skrive dem om
        # gir støy i diffen uten at noe blir riktigere.
        if sjekk.sammenlign_fastledd(gamle, nye) is None and len(gamle) == len(nye):
            continue
        endringer[dso_id] = {"nye": nye, "gamle": gamle, "slug": slug,
                             "gyldig_fra": tariff["gyldig_fra"], "navn": entry["name"]}

    for dso_id, info in endringer.items():
        print(f"\n{dso_id} ({info['navn']}, fri-nettleie {info['slug']}, "
              f"tariff fra {info['gyldig_fra']})")
        print(f"  fra: {[(('inf' if g == float('inf') else g), pr) for g, pr in info['gamle']]}")
        print(f"  til: {[(('inf' if g == float('inf') else g), pr) for g, pr in info['nye']]}")

    if args.skriv and endringer:
        # Bakerst først, ellers forskyver tidligere innsettinger indeksene.
        for dso_id in sorted(endringer, key=lambda d: finn_blokk(linjer, d)[0], reverse=True):
            info = endringer[dso_id]
            kap, slutt = finn_blokk(linjer, dso_id)
            fra = kap - 1 if linjer[kap - 1].lstrip().startswith(
                "# Kapasitetstrinn: fri-nettleie") else kap
            linjer[fra:slutt + 1] = [
                f"        # Kapasitetstrinn: fri-nettleie {info['slug']}.yml, tariff "
                f"gyldig fra {info['gyldig_fra']} (hentet {args.dato})",
                '        "kapasitetstrinn": [',
                *formater_trinn(info["nye"]),
                "        ],",
            ]
        DSO_PY.write_text("\n".join(linjer), encoding="utf-8")

    print(f"\n# {len(endringer)} nettselskap med endring"
          f"{' (skrevet til dso.py)' if args.skriv and endringer else ' (tørrkjøring)'}")
    if hoppet:
        print(f"# {len(hoppet)} hoppet over:")
        for dso_id, grunn in hoppet:
            print(f"#   {dso_id}: {grunn}")
    if endringer and not args.skriv:
        print("# Kjør med --skriv for å oppdatere dso.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
