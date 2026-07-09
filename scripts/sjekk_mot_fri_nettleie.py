#!/usr/bin/env python3
"""Sammenlign DSO_LIST mot kraftsystemet/fri-nettleie.

Henter alle tariff-YAML-filer fra fri-nettleie (CC-BY-4.0), parser dag/natt
energiledd-satser (eks. mva og avgifter), og sammenligner med vår dso.py.
Rapporterer avvik per nettselskap.

Bruk:
    python scripts/sjekk_mot_fri_nettleie.py
    python scripts/sjekk_mot_fri_nettleie.py --dato 2026-07-01  # sesongprising
    python scripts/sjekk_mot_fri_nettleie.py --bare-avvik
    python scripts/sjekk_mot_fri_nettleie.py --dso bkk,tensio_tn

Data fra https://github.com/kraftsystemet/fri-nettleie/ (CC-BY-4.0).

Senere utvidelse: dette scriptet er strukturert slik at samme mapper og parser
kan generere const.py-data direkte. Se `match_dso()` og `hent_satser_aktiv_dato()`.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Importer dso.py direkte uten å gå via __init__.py som krever homeassistant.
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "_dso", REPO_ROOT / "custom_components" / "stromkalkulator" / "dso.py"
)
assert _spec and _spec.loader
_dso_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_dso_module)
DSO_LIST = _dso_module.DSO_LIST

GITHUB_API = "https://api.github.com/repos/kraftsystemet/fri-nettleie/contents/tariffer"
RAW_BASE = "https://raw.githubusercontent.com/kraftsystemet/fri-nettleie/main/tariffer"
TOLERANSE = 0.001  # NOK/kWh, 0,1 øre

# Kjente, bevisste avvik mot fri-nettleie: DSO-er der vi følger nettselskapets
# egen prisside framfor fri-nettleie fordi de spriker. Rapporteres, men teller
# ikke som drift (exit-kode). Fjern når fri-nettleie er oppdatert.
KJENTE_AVVIK: dict[str, str] = {
    "elvia": "elvia.no oppgir dag 46,60 øre inkl. (29,15 eks); fri-nettleie har 46,40 (28,99). "
    "Elvia er primærkilde. Meldt: github.com/kraftsystemet/fri-nettleie/issues/384.",
}

# Mapping mellom våre DSO-IDer og fri-nettleie sine filnavn. Hvis vår ID kan
# utledes direkte (med "-" → "_") trenger vi ikke oppføring her.
EKSPLISITT_MAPPING: dict[str, str] = {
    "tensio_tn": "tensio-tn",
    "tensio_ts": "tensio-ts",
    "de_nett": "denett",
    "asker_nett": "asker",
    "bindal_kraftnett": "bindalkraftlag",
    "bomlo_kraftnett": "bomlokraftnett",
    "barents_nett": "barentsnett",
    "ke_nett": "kenett",
    "holand_setskog": "holandogsetskogelverk",
    "indre_hordaland": "indrehordalandkraftnett",
    "jaren_everk": "jaereneverk",
    "modalen_kraftlag": "mostraum",
    "meloy_energi": "meloy",
    "noranett_andoy": "noranett-andoy",
    "noranett_hadsel": "noranett-hadsel",
    "nordvest_nett": "nordvest",
    "norefjell_nett": "norefjell",
    "r_nett": "rnett",
    "rk_nett": "rknett",
    "rakkestad_energi": "elvia",
    "fore": "foere",
    "foie": "foie",
    # fri-nettleie dropper "nett"/selskapsledd i slug; auto-utleding tar ikke dette.
    "etna_nett": "etna",
    "breheim_nett": "breheim",
    "straumen_nett": "straumen",
    "telemark_nett": "telemark",
    "vestmar_nett": "vestmar",
    "vang_energiverk": "vang",
    "uvdal_kraftforsyning": "uvdal",
    # area_nett har ingen ren match: fri-nettleie deler Area i fire regioner
    # (area-alle/lega/luostejok/nettinord) med ulik pris. Sjekkes manuelt.
}


@dataclass
class Avvik:
    """Ett avvik for ett DSO."""

    dso_id: str
    felt: str
    var: float | None
    deres: float | None
    delta: float | None = None


def gh_get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as r:
        import json
        return json.loads(r.read())


def hent_yaml(slug: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{RAW_BASE}/{slug}.yml", timeout=30) as r:
            return yaml.safe_load(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def list_remote_dsoer() -> list[str]:
    items = gh_get_json(GITHUB_API)
    return sorted(i["name"].removesuffix(".yml") for i in items if i["name"].endswith(".yml"))


def match_dso(var_id: str, remote_slugs: set[str]) -> str | None:
    """Map vår DSO-ID til fri-nettleie slug. None hvis ingen match."""
    if var_id in EKSPLISITT_MAPPING:
        slug = EKSPLISITT_MAPPING[var_id]
        return slug if slug in remote_slugs else None
    kandidater = [var_id, var_id.replace("_", "-"), var_id.replace("_", "")]
    for k in kandidater:
        if k in remote_slugs:
            return k
    return None


def aktiv_tariff(data: dict[str, Any], paa: date, kundegruppe: str = "husholdning") -> dict[str, Any] | None:
    """Finn tariffen som er gyldig på en gitt dato for en kundegruppe."""
    for t in data.get("tariffer", []):
        if kundegruppe not in t.get("kundegrupper", []):
            continue
        if date.fromisoformat(t["gyldig_fra"]) > paa:
            continue
        if "gyldig_til" in t and date.fromisoformat(t["gyldig_til"]) <= paa:
            continue
        return t
    return None


MAANED_MAP = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}


def unntak_matcher_dato(unntak: dict[str, Any], paa: date) -> bool:
    maaneder = unntak.get("måneder")
    if maaneder is None:
        return True
    return paa.month in {MAANED_MAP[m] for m in maaneder if m in MAANED_MAP}


def hent_satser_aktiv_dato(tariff: dict[str, Any], paa: date) -> tuple[float, float] | None:
    """Returner (dag, natt) energiledd i NOK/kWh for gitt dato. None hvis ukjent.

    grunnpris er typisk laveste sats (ofte natt-pris, men ved sesongprising kan
    den være sommer-natt mens vinter-natt ligger som unntak). Vi behandler
    grunnpris som default for både dag og natt, og lar unntak overstyre.
    """
    el = tariff.get("energiledd")
    if not el:
        return None
    grunn = el["grunnpris"] / 100
    dag = grunn
    natt = grunn
    for unntak in el.get("unntak") or []:
        if not unntak_matcher_dato(unntak, paa):
            continue
        navn = unntak.get("navn", "").lower()
        timer = unntak.get("timer", "")
        pris = unntak["pris"] / 100
        er_natt = "natt" in navn or timer.startswith("22-") or "22-5" in timer or "22-6" in timer
        er_dag = any(s in navn for s in ("dag", "høylast")) or "6-21" in timer or "6-22" in timer
        if er_natt:
            natt = pris
        elif er_dag:
            dag = pris
    return dag, natt


def sammenlign(remote_slugs: set[str], paa: date, bare_avvik: bool, filter_ids: set[str] | None) -> list[Avvik]:
    avvik: list[Avvik] = []
    for var_id, entry in sorted(DSO_LIST.items()):
        if filter_ids and var_id not in filter_ids:
            continue
        if var_id == "custom":
            continue
        slug = match_dso(var_id, remote_slugs)
        if slug is None:
            if not bare_avvik:
                print(f"[?] {var_id}: ingen match i fri-nettleie")
            avvik.append(Avvik(var_id, "match", None, None))
            continue
        data = hent_yaml(slug)
        if data is None:
            avvik.append(Avvik(var_id, "fetch", None, None))
            continue
        tariff = aktiv_tariff(data, paa)
        if tariff is None:
            print(f"[!] {var_id} ({slug}): ingen aktiv tariff for husholdning på {paa}")
            continue
        satser = hent_satser_aktiv_dato(tariff, paa)
        if satser is None:
            print(f"[!] {var_id} ({slug}): mangler energiledd i tariff")
            continue
        dag_deres, natt_deres = satser
        dag_var = float(entry["energiledd_dag_eks_mva"])
        natt_var = float(entry["energiledd_natt_eks_mva"])

        # Hvis vi har perioder, bruk den som matcher datoen
        perioder = entry.get("energiledd_perioder", [])
        for p in perioder:
            fra, til = p["fra"], p["til"]
            mm_dd = paa.strftime("%m-%d")
            if (fra <= til and fra <= mm_dd <= til) or (fra > til and (mm_dd >= fra or mm_dd <= til)):
                dag_var = float(p["dag_eks_mva"])
                natt_var = float(p["natt_eks_mva"])
                break

        d_dag = dag_var - dag_deres
        d_natt = natt_var - natt_deres
        avvikende = abs(d_dag) > TOLERANSE or abs(d_natt) > TOLERANSE
        if avvikende:
            avvik.append(Avvik(var_id, "dag", dag_var, dag_deres, d_dag))
            avvik.append(Avvik(var_id, "natt", natt_var, natt_deres, d_natt))
            print(
                f"[X] {var_id:20s} ({slug:25s})  "
                f"dag {dag_var * 100:>6.2f} vs {dag_deres * 100:>6.2f}  "
                f"natt {natt_var * 100:>6.2f} vs {natt_deres * 100:>6.2f}"
            )
        elif not bare_avvik:
            print(f"[OK] {var_id:20s} ({slug:25s})")
    return avvik


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dato", type=date.fromisoformat, default=date.today(),
                   help="Dato å sammenligne for (YYYY-MM-DD), default: i dag")
    p.add_argument("--bare-avvik", action="store_true",
                   help="Skriv bare ut avvik, ikke OK-rader")
    p.add_argument("--dso", help="Komma-separert liste over DSO-IDer å sjekke")
    args = p.parse_args()

    filter_ids = set(args.dso.split(",")) if args.dso else None

    print(f"# Sammenligning mot fri-nettleie for {args.dato}")
    print(f"# Toleranse: {TOLERANSE * 100:.2f} øre/kWh")
    print()
    remote = set(list_remote_dsoer())
    print(f"# {len(remote)} DSO-er tilgjengelig i fri-nettleie")
    print()
    avvik = sammenlign(remote, args.dato, args.bare_avvik, filter_ids)

    pris_avvik = [a for a in avvik if a.felt in ("dag", "natt")]
    ekte_avvik = [a for a in pris_avvik if a.dso_id not in KJENTE_AVVIK]
    kjente = sorted({a.dso_id for a in pris_avvik if a.dso_id in KJENTE_AVVIK})
    umatchet = sorted(a.dso_id for a in avvik if a.felt == "match")
    fetch_feil = sorted(a.dso_id for a in avvik if a.felt == "fetch")
    print()
    print(f"# Sammendrag: {len(ekte_avvik) // 2} DSO-er med uventet prisavvik over toleranse")
    if kjente:
        print(f"# {len(kjente)} kjent(e) avvik (følger nettselskapets egen side, ikke drift): {', '.join(kjente)}")
    # Umatchede DSO-er kan ikke auto-sjekkes og må verifiseres manuelt mot kilde.
    # De skjules ellers i --bare-avvik, og det er nettopp der drift sniker seg inn.
    if umatchet:
        print(f"# {len(umatchet)} uten match i fri-nettleie (sjekk manuelt): {', '.join(umatchet)}")
    if fetch_feil:
        print(f"# {len(fetch_feil)} feilet henting: {', '.join(fetch_feil)}")
    return 1 if ekte_avvik else 0


if __name__ == "__main__":
    sys.exit(main())
