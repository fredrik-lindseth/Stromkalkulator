"""Variant-matrise for NOK-omregning kjørt over flere måneder.

Generalisering av `match_norgespris_variants.py`. Bruker lokale fixturer
istedenfor live HKS-kall:

    tests/fixtures/bkk_<maaned>_<aar>_hourly.json   -> kWh + spot (HA-cache)
    tests/fixtures/nordpool_eur_no5_2026.json       -> rå EUR/MWh fra Nord Pool
    tests/fixtures/nb_eur_nok_2026.json             -> NB EUR/NOK daily

Kjør:

    python3 scripts/research/match_norgespris_alle_maaneder.py            # alle måneder
    python3 scripts/research/match_norgespris_alle_maaneder.py 2026 4     # bare april
    python3 scripts/research/match_norgespris_alle_maaneder.py --emit-markdown

Krever ingen tredjeparts-avhengigheter.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
FIXTURE_DIR: Final[Path] = ROOT / "tests" / "fixtures"
NB_SNAPSHOT: Final[Path] = FIXTURE_DIR / "nb_eur_nok_2026.json"
NP_SNAPSHOT: Final[Path] = FIXTURE_DIR / "nordpool_eur_no5_2026.json"
GENERATED_DIR: Final[Path] = ROOT / "docs" / "research" / "_generated"

NORGESPRIS_FASTPRIS_INKL_MVA: Final[float] = 0.50
MVA_SATS: Final[float] = 1.25

# Faktura-tall per måned (kopiert fra scripts/research/verify_invoice_hourly.py).
# None = ingen faktura tilgjengelig eller annen ordning (gammel strømstøtte).
MAANED_NAVN: dict[int, str] = {
    1: "januar", 2: "februar", 3: "mars", 4: "april",
    5: "mai", 6: "juni", 7: "juli", 8: "august",
    9: "september", 10: "oktober", 11: "november", 12: "desember",
}

FAKTURAER: dict[tuple[int, int], dict[str, float] | None] = {
    (2025, 12): None,  # gammel strømstøtte, ikke Norgespris
    (2026, 1): None,   # ingen faktura mottatt
    (2026, 2): {
        "forbruk_total_kwh": 1673.786,
        "norgespris_kr": -1821.64,
    },
    (2026, 3): {
        "forbruk_total_kwh": 1553.217,
        "norgespris_kr": -1550.68,
    },
    (2026, 4): {
        "forbruk_total_kwh": 1381.827,
        "norgespris_kr": -1427.89,
    },
}


@dataclass(frozen=True)
class HourPoint:
    iso: str
    day: str
    eur_mwh: float
    kwh: float


def fixture_path(year: int, month: int) -> Path:
    """Stien til BKK-hourly-fixture for gitt år/måned."""
    name = MAANED_NAVN[month]
    return FIXTURE_DIR / f"bkk_{name}_{year}_hourly.json"


def load_bkk_hours(year: int, month: int) -> list[dict]:
    p = fixture_path(year, month)
    with p.open() as f:
        return json.load(f)["hours"]


def load_np_eur() -> dict[str, float]:
    """{start_local_iso: eur_mwh} for hele NP-fixturen."""
    with NP_SNAPSHOT.open() as f:
        data = json.load(f)
    return {h["start_local"]: float(h["eur_mwh"]) for h in data["hourly"]}


def load_nb_rates() -> dict[str, float]:
    with NB_SNAPSHOT.open() as f:
        data = json.load(f)
    return {e["date"]: float(e["rate"]) for e in data["daily"]}


def forward_fill(days: list[str], rates: dict[str, float]) -> dict[str, float]:
    filled: dict[str, float] = {}
    last: float | None = None
    for d, r in sorted(rates.items()):
        if d <= days[0]:
            last = r
    for d in days:
        if d in rates:
            last = rates[d]
        if last is None:
            raise RuntimeError(f"Ingen kurs for/før {d}")
        filled[d] = last
    return filled


def previous_bankday_fill(days: list[str], rates: dict[str, float]) -> dict[str, float]:
    filled: dict[str, float] = {}
    sorted_dates = sorted(rates)
    for d in days:
        prev = [r for r in sorted_dates if r < d]
        if not prev:
            raise RuntimeError(f"Ingen tidligere kurs før {d}")
        filled[d] = rates[prev[-1]]
    return filled


def next_bankday_fill(days: list[str], rates: dict[str, float]) -> dict[str, float]:
    filled: dict[str, float] = {}
    sorted_dates = sorted(rates)
    for d in days:
        nxt = [r for r in sorted_dates if r >= d]
        if not nxt:
            raise RuntimeError(f"Ingen kurs på/etter {d}")
        filled[d] = rates[nxt[0]]
    return filled


def build_points(year: int, month: int, np_eur: dict[str, float]) -> list[HourPoint]:
    """Lag HourPoints fra BKK-fixture + NP EUR/MWh."""
    out: list[HourPoint] = []
    for h in load_bkk_hours(year, month):
        kwh = h.get("kwh")
        if kwh is None:
            # Hopp over hull i HAN-data; ingen forbruk å vekte.
            continue
        iso = h["start_local"]
        eur_mwh = np_eur.get(iso)
        if eur_mwh is None:
            raise RuntimeError(f"Ingen NP-pris for {iso}")
        out.append(
            HourPoint(iso=iso, day=iso[:10], eur_mwh=float(eur_mwh), kwh=float(kwh))
        )
    return out


def weighted_avg_nok_eks_mva(
    points: list[HourPoint], rate_for_hour: Callable[[HourPoint], float]
) -> tuple[float, float]:
    total_kwh = sum(p.kwh for p in points)
    if total_kwh <= 0:
        return 0.0, 0.0
    weighted = sum((p.eur_mwh / 1000.0) * rate_for_hour(p) * p.kwh for p in points)
    return weighted / total_kwh, total_kwh


def kompensasjon(snitt_eks_mva: float, forbruk: float) -> float:
    snitt_inkl_mva = snitt_eks_mva * MVA_SATS
    return (NORGESPRIS_FASTPRIS_INKL_MVA - snitt_inkl_mva) * forbruk


def maaned_label(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def kjor_maaned(year: int, month: int, np_eur: dict[str, float],
                nb_rates: dict[str, float]) -> dict[str, dict[str, float]] | None:
    """Returner {variant_navn: {snitt, komp, avvik_kr, avvik_pct}} eller None hvis ingen faktura."""
    faktura = FAKTURAER.get((year, month))
    if faktura is None:
        print(f"  Hopper over {maaned_label(year, month)}: ingen Norgespris-faktura tilgjengelig")
        return None

    try:
        points = build_points(year, month, np_eur)
    except FileNotFoundError as e:
        print(f"  Hopper over {maaned_label(year, month)}: mangler fixture ({e})")
        return None

    forbruk_faktura = faktura["forbruk_total_kwh"]
    norgespris_faktura = faktura["norgespris_kr"]
    total_kwh = sum(p.kwh for p in points)

    days = sorted({p.day for p in points})
    nb_same = forward_fill(days, nb_rates)
    nb_prev = previous_bankday_fill(days, nb_rates)
    nb_next = next_bankday_fill(days, nb_rates)

    # NB månedssnitt (aritmetisk over bankdager i måneden)
    prefix = maaned_label(year, month)
    nb_month_rates = [r for d, r in nb_rates.items() if d.startswith(prefix)]
    nb_arith_avg = sum(nb_month_rates) / len(nb_month_rates) if nb_month_rates else 0.0

    # NB forbruksvektet snitt over månedens dager (same-day forward-fill)
    daily_kwh: dict[str, float] = defaultdict(float)
    for p in points:
        daily_kwh[p.day] += p.kwh
    weighted_num = sum(daily_kwh[d] * nb_same[d] for d in days)
    weighted_den = sum(daily_kwh[d] for d in days)
    nb_weighted_avg = weighted_num / weighted_den if weighted_den else 0.0

    raters: list[tuple[str, Callable[[HourPoint], float]]] = [
        ("B: NB same-day forward-fill", lambda p: nb_same[p.day]),
        ("C: NB previous-bankday (T-1)", lambda p: nb_prev[p.day]),
        ("D: NB aritmetisk månedssnitt", lambda _p: nb_arith_avg),
        ("E: NB forbruksvektet månedssnitt", lambda _p: nb_weighted_avg),
        ("I: NB next-bankday (T+1)", lambda p: nb_next[p.day]),
    ]

    results: dict[str, dict[str, float]] = {}
    for label, fn in raters:
        snitt, _ = weighted_avg_nok_eks_mva(points, fn)
        # Bruk fakturaens forbruk i komp-beregningen for likhet med faktura-summen.
        # (Alternativt total_kwh fra fixturen; de er nesten like.)
        komp = kompensasjon(snitt, forbruk_faktura)
        avvik = komp - norgespris_faktura
        results[label] = {
            "snitt_eks_mva": snitt,
            "komp_kr": komp,
            "avvik_kr": avvik,
            "avvik_pct": avvik / abs(norgespris_faktura) * 100,
        }

    # Bonus: reverse-engineering, hvilken konstant kurs ville matchet?
    weighted_eur_per_kwh = sum(p.eur_mwh / 1000.0 * p.kwh for p in points) / total_kwh
    faktura_implied_eks_mva = (
        NORGESPRIS_FASTPRIS_INKL_MVA - (norgespris_faktura / forbruk_faktura)
    ) / MVA_SATS
    implied_rate = faktura_implied_eks_mva / weighted_eur_per_kwh

    results["_meta"] = {
        "forbruk_total_kwh": total_kwh,
        "forbruk_faktura_kwh": forbruk_faktura,
        "norgespris_faktura_kr": norgespris_faktura,
        "nb_arith_avg": nb_arith_avg,
        "nb_weighted_avg": nb_weighted_avg,
        "implied_match_rate": implied_rate,
        "weighted_eur_per_kwh": weighted_eur_per_kwh,
    }
    return results


def print_maaned(year: int, month: int, res: dict[str, dict[str, float]]) -> None:
    label = maaned_label(year, month)
    meta = res["_meta"]
    print(f"\n=== {label} ===")
    print(f"  Forbruk: faktura {meta['forbruk_faktura_kwh']:.3f} kWh, "
          f"fixture {meta['forbruk_total_kwh']:.3f} kWh")
    print(f"  Norgespris-komp faktura: {meta['norgespris_faktura_kr']:.2f} kr")
    print(f"  NB månedssnitt aritm: {meta['nb_arith_avg']:.4f}, "
          f"vektet: {meta['nb_weighted_avg']:.4f}")
    print(f"  Implisitt match-kurs: {meta['implied_match_rate']:.4f} NOK/EUR")
    print()
    print(f"  {'Variant':<40} {'snitt':>10} {'komp':>12} {'avvik kr':>10} {'avvik %':>10}")
    for label_v, v in res.items():
        if label_v == "_meta":
            continue
        print(f"  {label_v:<40} {v['snitt_eks_mva']:>10.6f} "
              f"{v['komp_kr']:>+12.2f} {v['avvik_kr']:>+10.2f} "
              f"{v['avvik_pct']:>+9.3f}%")


def print_oppsummering(per_maaned: dict[tuple[int, int], dict]) -> None:
    print("\n\n=== OPPSUMMERING: avvik (kr) per variant per måned ===\n")
    variants = [
        "B: NB same-day forward-fill",
        "C: NB previous-bankday (T-1)",
        "D: NB aritmetisk månedssnitt",
        "E: NB forbruksvektet månedssnitt",
        "I: NB next-bankday (T+1)",
    ]
    header = f"  {'Måned':<10}"
    for v in variants:
        short = v.split(":")[0]
        header += f" {short:>10}"
    header += f" {'Beste':>20}"
    print(header)
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        row = f"  {maaned_label(y, m):<10}"
        avvik_per_variant: list[tuple[str, float]] = []
        for v in variants:
            avvik = res[v]["avvik_kr"]
            row += f" {avvik:>+10.2f}"
            avvik_per_variant.append((v, avvik))
        best = min(avvik_per_variant, key=lambda x: abs(x[1]))
        row += f"  {best[0].split(':')[0]:>10} ({best[1]:+.2f})"
        print(row)

    print("\n=== Avvik (%) per variant per måned ===\n")
    print(header)
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        row = f"  {maaned_label(y, m):<10}"
        for v in variants:
            pct = res[v]["avvik_pct"]
            row += f" {pct:>+9.3f}%"
        print(row)

    print("\n=== Implisitte match-kurser (reverse-engineering) ===\n")
    print(f"  {'Måned':<10} {'match NOK/EUR':>15} {'NB arith':>12} "
          f"{'NB vektet':>12} {'diff vs NB-arith':>18}")
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        meta = res["_meta"]
        diff_arith = meta["implied_match_rate"] - meta["nb_arith_avg"]
        print(f"  {maaned_label(y, m):<10} {meta['implied_match_rate']:>15.4f} "
              f"{meta['nb_arith_avg']:>12.4f} {meta['nb_weighted_avg']:>12.4f} "
              f"{diff_arith:>+18.4f}")


def render_markdown(per_maaned: dict[tuple[int, int], dict]) -> str:
    """Returner deterministisk Markdown med tabell per måned + oppsummering."""
    variants = [
        "B: NB same-day forward-fill",
        "C: NB previous-bankday (T-1)",
        "D: NB aritmetisk månedssnitt",
        "E: NB forbruksvektet månedssnitt",
        "I: NB next-bankday (T+1)",
    ]
    lines: list[str] = []
    lines.append(
        "_Generert av_ `scripts/research/match_norgespris_alle_maaneder.py --emit-markdown` "
        "(alle måneder med Norgespris-faktura, kun lokale fixturer)."
    )
    lines.append("")
    lines.append("## Avvik (kr) per variant per måned")
    lines.append("")
    header = "| Måned | " + " | ".join(v.split(":")[0] for v in variants) + " | Beste |"
    sep = "| --- |" + " ---: |" * len(variants) + " :--- |"
    lines.append(header)
    lines.append(sep)
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        row = f"| {maaned_label(y, m)} |"
        avvik_per_variant: list[tuple[str, float]] = []
        for v in variants:
            avvik = res[v]["avvik_kr"]
            row += f" {avvik:+.2f} |"
            avvik_per_variant.append((v, avvik))
        best = min(avvik_per_variant, key=lambda x: abs(x[1]))
        row += f" {best[0].split(':')[0]} ({best[1]:+.2f}) |"
        lines.append(row)
    lines.append("")
    lines.append("## Avvik (%) per variant per måned")
    lines.append("")
    lines.append("| Måned | " + " | ".join(v.split(":")[0] for v in variants) + " |")
    lines.append("| --- |" + " ---: |" * len(variants))
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        row = f"| {maaned_label(y, m)} |"
        for v in variants:
            row += f" {res[v]['avvik_pct']:+.3f} % |"
        lines.append(row)
    lines.append("")
    lines.append("## Implisitte match-kurser (reverse-engineering)")
    lines.append("")
    lines.append("| Måned | match NOK/EUR | NB arith | NB vektet | diff vs NB-arith |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for (y, m), res in sorted(per_maaned.items()):
        if res is None:
            continue
        meta = res["_meta"]
        diff_arith = meta["implied_match_rate"] - meta["nb_arith_avg"]
        lines.append(
            f"| {maaned_label(y, m)} | {meta['implied_match_rate']:.4f} "
            f"| {meta['nb_arith_avg']:.4f} | {meta['nb_weighted_avg']:.4f} "
            f"| {diff_arith:+.4f} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("year", nargs="?", type=int, help="(valgfritt) år")
    p.add_argument("month", nargs="?", type=int, help="(valgfritt) maaned 1-12")
    p.add_argument(
        "--emit-markdown",
        action="store_true",
        help="Skriv Markdown til docs/research/_generated/",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output-sti (default: docs/research/_generated/"
             "match_norgespris_alle_maaneder.md)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    np_eur = load_np_eur()
    nb_rates = load_nb_rates()

    # Hvis argumenter: kjør én måned. Ellers alle med faktura tilgjengelig.
    if args.year and args.month:
        target: list[tuple[int, int]] = [(args.year, args.month)]
    else:
        target = [k for k, v in FAKTURAER.items() if v is not None]

    per_maaned: dict[tuple[int, int], dict] = {}
    for (y, m) in sorted(target):
        if not args.emit_markdown:
            print(f"\n--- Kjører {maaned_label(y, m)} ---")
        res = kjor_maaned(y, m, np_eur, nb_rates)
        if res is not None:
            per_maaned[(y, m)] = res
            if not args.emit_markdown:
                print_maaned(y, m, res)

    if args.emit_markdown:
        out = args.output or (GENERATED_DIR / "match_norgespris_alle_maaneder.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(per_maaned))
        print(f"Skrev {out.relative_to(ROOT)}")
        return 0

    if len(per_maaned) > 1:
        print_oppsummering(per_maaned)
    return 0


if __name__ == "__main__":
    sys.exit(main())
