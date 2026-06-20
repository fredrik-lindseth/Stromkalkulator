"""Tester 12:00 CET-hypotesen mot Bloomberg-data.

Hypotesen (docs/research/nok-omregning.md): BKK bruker Nord Pools preliminære
interbankkurs kl. 12:00 CET, ikke Norges Banks 14:15 CET-kurs, til å regne om
EUR-spotpris til NOK for Norgespris-kompensasjonen. Prediksjonen var at avviket
mot fakturaen skulle krympe mot null når vi byttet NB-kursen mot den ekte
12:00-kursen.

Dette scriptet kjører fakturasammenligningen med begge kurskildene side om side,
ved å gjenbruke beregningslogikken i match_norgespris_alle_maaneder.py.

Bloomberg-fixturen ligger under _private/ (lisensiert data, ikke committet).
Generer den først med snapshot_bloomberg_eur_nok.py. Mangler den, hopper
scriptet over Bloomberg-kolonnen og forklarer hvordan du lager den.

    python3 scripts/research/match_norgespris_bloomberg.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

from match_norgespris_alle_maaneder import (
    FAKTURAER,
    MVA_SATS,
    NORGESPRIS_FASTPRIS_INKL_MVA,
    build_points,
    forward_fill,
    kompensasjon,
    load_nb_rates,
    load_np_eur,
    maaned_label,
    weighted_avg_nok_eks_mva,
)

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
BLOOMBERG_SNAPSHOT: Final[Path] = (
    ROOT / "_private" / "Måleverdier" / "bloomberg_eur_nok_1200cet_2026.json"
)


def load_bloomberg_rates() -> dict[str, float] | None:
    if not BLOOMBERG_SNAPSHOT.exists():
        return None
    data = json.loads(BLOOMBERG_SNAPSHOT.read_text())
    return {e["date"]: float(e["rate"]) for e in data["daily"]}


def evaluer(year: int, month: int, np_eur: dict[str, float],
            rates: dict[str, float]) -> dict[str, float] | None:
    """Forbruksvektet kompensasjon + avvik for én kurskilde, eller None ved manglende dekning."""
    points = build_points(year, month, np_eur)
    days = sorted({p.day for p in points})
    try:
        filled = forward_fill(days, rates)
    except RuntimeError:
        return None
    snitt, _ = weighted_avg_nok_eks_mva(points, lambda p: filled[p.day])
    f = FAKTURAER[(year, month)]
    komp = kompensasjon(snitt, f["forbruk_total_kwh"])
    avvik = komp - f["norgespris_kr"]
    daily_kwh: dict[str, float] = defaultdict(float)
    for p in points:
        daily_kwh[p.day] += p.kwh
    vektet_kurs = sum(daily_kwh[d] * filled[d] for d in days) / sum(daily_kwh.values())
    return {
        "snitt_eks_mva": snitt,
        "komp_kr": komp,
        "avvik_kr": avvik,
        "avvik_pct": avvik / abs(f["norgespris_kr"]) * 100,
        "vektet_kurs": vektet_kurs,
    }


def implisitt_match_kurs(year: int, month: int, np_eur: dict[str, float]) -> float:
    points = build_points(year, month, np_eur)
    tot = sum(p.kwh for p in points)
    weur = sum(p.eur_mwh / 1000 * p.kwh for p in points) / tot
    f = FAKTURAER[(year, month)]
    implied_eks = (
        NORGESPRIS_FASTPRIS_INKL_MVA - f["norgespris_kr"] / f["forbruk_total_kwh"]
    ) / MVA_SATS
    return implied_eks / weur


def main() -> int:
    np_eur = load_np_eur()
    nb_rates = load_nb_rates()
    bb_rates = load_bloomberg_rates()

    if bb_rates is None:
        print(f"Mangler {BLOOMBERG_SNAPSHOT.relative_to(ROOT)}.")
        print("Lag den med:")
        print("  uv run --with openpyxl python "
              "scripts/research/snapshot_bloomberg_eur_nok.py")
        return 1

    maaneder = [k for k, v in FAKTURAER.items() if v is not None]
    print("=== 12:00 CET-hypotesen mot Bloomberg ===\n")
    print(f"{'Måned':8} {'kilde':16} {'vektet kurs':>12} {'komp kr':>11} "
          f"{'avvik kr':>9} {'avvik %':>9}")
    forbedring: list[tuple[str, float, float]] = []
    for (y, m) in sorted(maaneder):
        nb = evaluer(y, m, np_eur, nb_rates)
        bb = evaluer(y, m, np_eur, bb_rates)
        implied = implisitt_match_kurs(y, m, np_eur)
        if nb is None:
            continue
        label = maaned_label(y, m)
        print(f"{label:8} {'NB 14:15':16} {nb['vektet_kurs']:>12.4f} "
              f"{nb['komp_kr']:>+11.2f} {nb['avvik_kr']:>+9.2f} {nb['avvik_pct']:>+8.3f}%")
        if bb is None:
            print(f"{'':8} {'BBG 12:00':16} {'(ingen dekning denne måneden)':>43}")
        else:
            print(f"{'':8} {'BBG 12:00':16} {bb['vektet_kurs']:>12.4f} "
                  f"{bb['komp_kr']:>+11.2f} {bb['avvik_kr']:>+9.2f} {bb['avvik_pct']:>+8.3f}%")
            forbedring.append((label, abs(nb["avvik_kr"]), abs(bb["avvik_kr"])))
        print(f"{'':8} {'implisitt match':16} {implied:>12.4f}")
        print()

    if forbedring:
        print("=== Krymper avviket med 12:00-kursen? ===")
        for label, nb_abs, bb_abs in forbedring:
            retning = "JA, mindre" if bb_abs < nb_abs else "NEI, større/likt"
            print(f"  {label}: |NB| {nb_abs:.2f} -> |BBG| {bb_abs:.2f}  ({retning})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
