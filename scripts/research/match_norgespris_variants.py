"""Prøv mange NOK-omregnings-varianter mot BKK-fakturaen til vi finner perfekt match.

Henter rå EUR/MWh + EXR (Nord Pools egen valutakurs) fra hvakosterstrommen.no
(speil av Nord Pool day-ahead), EUR/NOK fra Norges Bank, forbruk fra Elhub-CSV.
Beregner forbruksvektet snittspot per variant og sammenligner med fakturaen.

Bakgrunn: docs/research/nok-omregning.md.

Varianter:
    A: Nord Pools daglige EXR (samme kurs som Nord Pool selv publiserer NOK-pris med)
    B: NB same-day forward-fill (forrige verifisering: 0.79 kr avvik)
    C: NB previous-bankday (T-1)
    D: NB månedssnitt aritmetisk
    E: NB månedssnitt forbruksvektet
    F: ECB-kurs (samme kilde som NB siden 2016 — tatt med som sanity check)

Kjøres uten tredjeparts-avhengigheter (Python 3.11+ stdlib).

Flagg:
    --emit-markdown    Skriv en deterministisk Markdown-tabell til
                       docs/research/_generated/match_norgespris_variants.md.
                       Tvinger --no-network: bruker NP-snapshot for å gi
                       reproduserbar output uten live HKS-kall.
    --no-network       Bruk kun lokale fixturer (nordpool_eur_no5_<år>.json
                       for EUR/MWh + EXR, nb_eur_nok_<år>.json for kurs).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

# --- Konfig (april 2026, NO5, BKK) ---

YEAR: Final[int] = 2026
MONTH: Final[int] = 4
DELIVERY_AREA: Final[str] = "NO5"

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
ELHUB_CSV: Final[Path] = ROOT / "Måleverdier" / "elhub_april.csv"
NB_SNAPSHOT: Final[Path] = ROOT / "tests" / "fixtures" / "nb_eur_nok_2026.json"
NP_SNAPSHOT: Final[Path] = ROOT / "tests" / "fixtures" / "nordpool_eur_no5_2026.json"
GENERATED_DIR: Final[Path] = ROOT / "docs" / "research" / "_generated"

FAKTURA_FORBRUK_KWH: Final[float] = 1381.83
FAKTURA_NORGESPRIS_KOMPENSASJON_KR: Final[float] = -1427.89
NORGESPRIS_FASTPRIS_INKL_MVA: Final[float] = 0.50
MVA_SATS: Final[float] = 1.25

# Implisitt snittspot eks. mva utledet fra Norgespris-linjen:
#   rate_per_kwh = -1427.89 / 1381.83 = -1.0333...
#   inkl_mva = 0.50 - rate_per_kwh = 1.5333...
#   eks_mva = 1.5333 / 1.25 = 1.22667...
FAKTURA_IMPLISITT_EKS_MVA: Final[float] = (
    NORGESPRIS_FASTPRIS_INKL_MVA
    - (FAKTURA_NORGESPRIS_KOMPENSASJON_KR / FAKTURA_FORBRUK_KWH)
) / MVA_SATS

HKS_URL: Final[str] = (
    "https://www.hvakosterstrommen.no/api/v1/prices/{year}/{month:02d}-{day:02d}_{area}.json"
)


@dataclass(frozen=True)
class HourPoint:
    iso: str          # ISO-time med +HH:MM offset
    day: str          # YYYY-MM-DD
    eur_per_kwh: float
    eur_mwh: float
    nordpool_exr: float
    nordpool_nok_per_kwh: float   # NOK_per_kWh rett fra HKS (Nord Pool sin egen avrunding)
    kwh: float


def http_json(url: str) -> object:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "match_norgespris_variants/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fetch_hks_day(d: date, area: str) -> list[dict]:
    return http_json(HKS_URL.format(year=d.year, month=d.month, day=d.day, area=area))


def load_elhub_hourly(path: Path) -> dict[str, float]:
    """Returner {iso_local_hour_no_minutes: kwh}."""
    out: dict[str, float] = {}
    with path.open() as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            dt = datetime.fromisoformat(row[0])
            kwh = float(row[3].replace(",", "."))
            key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
            out[key] = kwh
    return out


def load_nb_rates() -> dict[str, float]:
    data = json.loads(NB_SNAPSHOT.read_text())
    return {e["date"]: float(e["rate"]) for e in data["daily"]}


def forward_fill(days: list[str], rates: dict[str, float]) -> dict[str, float]:
    filled: dict[str, float] = {}
    last: float | None = None
    sorted_rates = sorted(rates.items())
    for d, r in sorted_rates:
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
    """For hver dag, bruk siste publiserte NB-kurs FØR (ikke samme dag)."""
    filled: dict[str, float] = {}
    sorted_dates = sorted(rates)
    for d in days:
        prev = [r for r in sorted_dates if r < d]
        if not prev:
            raise RuntimeError(f"Ingen tidligere kurs før {d}")
        filled[d] = rates[prev[-1]]
    return filled


def fetch_april_hours(area: str) -> list[HourPoint]:
    """Hent alle timer i april fra HKS (live API-kall)."""
    points: list[HourPoint] = []
    first = date(YEAR, MONTH, 1)
    next_month = date(YEAR + (MONTH // 12), (MONTH % 12) + 1, 1)
    d = first
    while d < next_month:
        entries = fetch_hks_day(d, area)
        for e in entries:
            iso = e["time_start"]  # 2026-04-15T00:00:00+02:00
            hour_iso = datetime.fromisoformat(iso).replace(
                minute=0, second=0, microsecond=0
            ).isoformat()
            points.append(
                HourPoint(
                    iso=hour_iso,
                    day=iso[:10],
                    eur_per_kwh=float(e["EUR_per_kWh"]),
                    eur_mwh=float(e["EUR_per_kWh"]) * 1000.0,
                    nordpool_exr=float(e["EXR"]),
                    nordpool_nok_per_kwh=float(e["NOK_per_kWh"]),
                    kwh=0.0,
                )
            )
        time.sleep(0.2)
        d += timedelta(days=1)
    return points


def load_april_hours_from_snapshot(nb_rates: dict[str, float]) -> list[HourPoint]:
    """Bygg HourPoints fra NP-snapshot + NB-kurs (helt uten internett).

    NP-snapshot inneholder kun EUR/MWh — ikke Nord Pools egen EXR eller deres
    avrundede NOK_per_kWh. For variant A (Nord Pool EXR) og F/G/H (HKS NOK)
    bruker vi NB same-day forward-fill som proxy. Det er dokumentert i den
    genererte tabellen.
    """
    data = json.loads(NP_SNAPSHOT.read_text())
    prefix = f"{YEAR}-{MONTH:02d}"
    days_in_month = sorted(
        {e["start_local"][:10] for e in data["hourly"] if e["start_local"].startswith(prefix)}
    )
    nb_same = forward_fill(days_in_month, nb_rates)
    points: list[HourPoint] = []
    for e in data["hourly"]:
        iso = e["start_local"]
        if not iso.startswith(prefix):
            continue
        day = iso[:10]
        eur_mwh = float(e["eur_mwh"])
        eur_per_kwh = eur_mwh / 1000.0
        proxy_rate = nb_same[day]
        points.append(
            HourPoint(
                iso=iso,
                day=day,
                eur_per_kwh=eur_per_kwh,
                eur_mwh=eur_mwh,
                nordpool_exr=proxy_rate,  # proxy: NB same-day (snapshot mangler EXR)
                nordpool_nok_per_kwh=eur_per_kwh * proxy_rate,
                kwh=0.0,
            )
        )
    return points


def attach_kwh(points: list[HourPoint], elhub: dict[str, float]) -> list[HourPoint]:
    out: list[HourPoint] = []
    for p in points:
        # Elhub ISO bruker samme format som HKS time_start
        kwh = elhub.get(p.iso, 0.0)
        out.append(
            HourPoint(
                p.iso, p.day, p.eur_per_kwh, p.eur_mwh,
                p.nordpool_exr, p.nordpool_nok_per_kwh, kwh
            )
        )
    return out


def weighted_avg_nok_eks_mva(
    points: list[HourPoint], rate_for_hour: Callable[[HourPoint], float]
) -> tuple[float, float]:
    """Returner (forbruksvektet NOK/kWh eks. mva, total kWh)."""
    total_kwh = sum(p.kwh for p in points)
    if total_kwh <= 0:
        return 0.0, 0.0
    weighted = sum(p.eur_per_kwh * rate_for_hour(p) * p.kwh for p in points)
    return weighted / total_kwh, total_kwh


def kompensasjon(snitt_eks_mva: float, forbruk: float) -> float:
    """Norgespris-kompensasjon (negativt tall hvis spotpris > 0,50)."""
    snitt_inkl_mva = snitt_eks_mva * MVA_SATS
    return (NORGESPRIS_FASTPRIS_INKL_MVA - snitt_inkl_mva) * forbruk


def print_variant(
    name: str,
    snitt_eks_mva: float,
    forbruk: float,
) -> None:
    komp = kompensasjon(snitt_eks_mva, forbruk)
    avvik = komp - FAKTURA_NORGESPRIS_KOMPENSASJON_KR
    print(
        f"  {name:<46} "
        f"snitt={snitt_eks_mva:.6f}  "
        f"komp={komp:+.2f}  "
        f"avvik={avvik:+.2f} kr  ({avvik/abs(FAKTURA_NORGESPRIS_KOMPENSASJON_KR)*100:+.3f}%)"
    )


def compute_variants(
    points: list[HourPoint],
    nb_rates: dict[str, float],
    *,
    no_network: bool,
) -> tuple[list[dict], dict]:
    """Beregn alle varianter. Returner (variant-rader, meta).

    Hver rad: {label, snitt_eks_mva, komp_kr, avvik_kr, avvik_pct, note}
    """
    days = sorted({p.day for p in points})
    nb_same = forward_fill(days, nb_rates)
    nb_prev = previous_bankday_fill(days, nb_rates)
    nb_apr_arith = sum(r for d, r in nb_rates.items() if d.startswith(f"{YEAR}-{MONTH:02d}"))
    nb_apr_count = sum(1 for d in nb_rates if d.startswith(f"{YEAR}-{MONTH:02d}"))
    nb_arith_avg = nb_apr_arith / nb_apr_count if nb_apr_count else 0.0

    daily_kwh: dict[str, float] = defaultdict(float)
    for p in points:
        daily_kwh[p.day] += p.kwh
    weighted_num = sum(daily_kwh[d] * nb_same[d] for d in days)
    weighted_den = sum(daily_kwh[d] for d in days)
    nb_weighted_avg = weighted_num / weighted_den if weighted_den else 0.0

    total_kwh = sum(p.kwh for p in points)
    nb_next: dict[str, float] = {}
    sorted_nb = sorted(nb_rates.items())
    for d in days:
        nxt = [r for r in sorted_nb if r[0] >= d]
        if not nxt:
            raise RuntimeError(f"Ingen kurs på/etter {d}")
        nb_next[d] = nxt[0][1]

    exr_note = " (proxy: NB same-day, snapshot mangler EXR)" if no_network else ""

    def rate_exr(p: HourPoint) -> float:
        return p.nordpool_exr

    def rate_nb_same(p: HourPoint) -> float:
        return nb_same[p.day]

    def rate_nb_prev(p: HourPoint) -> float:
        return nb_prev[p.day]

    def rate_nb_arith(_p: HourPoint) -> float:
        return nb_arith_avg

    def rate_nb_weighted(_p: HourPoint) -> float:
        return nb_weighted_avg

    def rate_mixed(p: HourPoint) -> float:
        wd = datetime.fromisoformat(p.iso).weekday()
        return nb_same[p.day] if wd < 5 else p.nordpool_exr

    rows: list[dict] = []

    def add(label: str, snitt: float, note: str = "") -> None:
        komp = kompensasjon(snitt, FAKTURA_FORBRUK_KWH)
        avvik = komp - FAKTURA_NORGESPRIS_KOMPENSASJON_KR
        rows.append({
            "label": label,
            "snitt_eks_mva": snitt,
            "komp_kr": komp,
            "avvik_kr": avvik,
            "avvik_pct": avvik / abs(FAKTURA_NORGESPRIS_KOMPENSASJON_KR) * 100,
            "note": note,
        })

    for label, fn, n in [
        ("A: Nord Pool EXR (daglig)", rate_exr, exr_note),
        ("B: NB same-day forward-fill", rate_nb_same, ""),
        ("C: NB previous-bankday (T-1)", rate_nb_prev, ""),
        ("D: NB aritmetisk månedssnitt", rate_nb_arith, ""),
        ("E: NB forbruksvektet månedssnitt", rate_nb_weighted, ""),
    ]:
        snitt, _ = weighted_avg_nok_eks_mva(points, fn)
        add(label, snitt, n)

    nok_eks_mva_hks = sum(p.nordpool_nok_per_kwh * p.kwh for p in points) / total_kwh
    add("F: HKS NOK_per_kWh direkte", nok_eks_mva_hks, exr_note)

    nok_round4 = sum(round(p.nordpool_nok_per_kwh, 4) * p.kwh for p in points) / total_kwh
    add("G: HKS NOK avrundet per time (4d)", nok_round4, exr_note)

    nok_round5 = sum(round(p.nordpool_nok_per_kwh, 5) * p.kwh for p in points) / total_kwh
    add("H: HKS NOK avrundet per time (5d)", nok_round5, exr_note)

    snitt_next, _ = weighted_avg_nok_eks_mva(points, lambda p: nb_next[p.day])
    add("I: NB next-bankday (T+1)", snitt_next, "")

    snitt_mixed, _ = weighted_avg_nok_eks_mva(points, rate_mixed)
    add("J: NB ukedag + NP-EXR helg", snitt_mixed, exr_note)

    weighted_eur_per_kwh = sum(p.eur_per_kwh * p.kwh for p in points) / total_kwh
    implied_rate = FAKTURA_IMPLISITT_EKS_MVA / weighted_eur_per_kwh

    meta = {
        "total_kwh": total_kwh,
        "weighted_eur_per_kwh": weighted_eur_per_kwh,
        "implied_match_rate": implied_rate,
        "nb_arith_avg": nb_arith_avg,
        "nb_weighted_avg": nb_weighted_avg,
        "exr_arith_avg": sum(p.nordpool_exr for p in points) / len(points) if points else 0.0,
        "exr_weighted_avg": (
            sum(p.nordpool_exr * p.kwh for p in points) / total_kwh if total_kwh else 0.0
        ),
        "no_network": no_network,
    }
    return rows, meta


def render_markdown(rows: list[dict], meta: dict) -> str:
    """Returner deterministisk Markdown-tabell + meta-seksjon."""
    best = min(rows, key=lambda r: abs(r["avvik_kr"]))
    lines: list[str] = []
    lines.append(
        f"_Generert av_ `scripts/research/match_norgespris_variants.py --emit-markdown` "
        f"(april {YEAR}, {DELIVERY_AREA}, kun lokale fixturer)."
    )
    lines.append("")
    lines.append(
        f"Faktura: forbruk {FAKTURA_FORBRUK_KWH:.3f} kWh, "
        f"Norgespris-kompensasjon {FAKTURA_NORGESPRIS_KOMPENSASJON_KR:.2f} kr. "
        f"Implisitt snittspot eks. mva: {FAKTURA_IMPLISITT_EKS_MVA:.6f} NOK/kWh."
    )
    lines.append("")
    lines.append("| Variant | Snitt eks. mva | Komp (kr) | Avvik (kr) | Avvik (%) |")
    lines.append("| --- | ---: | ---: | ---: | ---: |")
    for r in rows:
        label = r["label"] + (" " + r["note"] if r["note"] else "")
        lines.append(
            f"| {label} "
            f"| {r['snitt_eks_mva']:.6f} "
            f"| {r['komp_kr']:+.2f} "
            f"| {r['avvik_kr']:+.2f} "
            f"| {r['avvik_pct']:+.3f} % |"
        )
    lines.append("")
    lines.append(
        f"**Beste variant:** {best['label']} "
        f"({best['avvik_kr']:+.2f} kr / {best['avvik_pct']:+.3f} %)."
    )
    lines.append("")
    lines.append("### Reverse-engineering")
    lines.append("")
    lines.append("| Kurs | Verdi |")
    lines.append("| --- | ---: |")
    lines.append(f"| Forbruksvektet EUR/kWh | {meta['weighted_eur_per_kwh']:.6f} |")
    lines.append(f"| Implisitt single-rate NOK/EUR | {meta['implied_match_rate']:.4f} |")
    lines.append(f"| Nord Pool EXR snitt (aritmetisk) | {meta['exr_arith_avg']:.4f} |")
    lines.append(f"| Nord Pool EXR snitt (vektet) | {meta['exr_weighted_avg']:.4f} |")
    lines.append(f"| NB aritmetisk månedssnitt | {meta['nb_arith_avg']:.4f} |")
    lines.append(f"| NB forbruksvektet snitt | {meta['nb_weighted_avg']:.4f} |")
    if meta["no_network"]:
        lines.append("")
        lines.append(
            "> Kjørt i `--no-network`-modus. NP-snapshot inneholder kun rå EUR/MWh, "
            "ikke Nord Pools egen EXR. Variantene A, F, G, H, J bruker NB same-day "
            "som proxy for EXR (markert i tabellen). For nøyaktige tall mot Nord "
            "Pools faktiske valutakurs, kjør uten `--no-network` med live HKS-data."
        )
    return "\n".join(lines) + "\n"


def print_text_report(rows: list[dict], meta: dict) -> None:
    print(f"=== Variant-matrise for Norgespris-spot {YEAR}-{MONTH:02d} ({DELIVERY_AREA}) ===\n")
    print(f"Faktura: forbruk {FAKTURA_FORBRUK_KWH} kWh, "
          f"Norgespris-komp {FAKTURA_NORGESPRIS_KOMPENSASJON_KR} kr")
    print(f"Implisitt snittspot eks. mva: {FAKTURA_IMPLISITT_EKS_MVA:.6f} NOK/kWh\n")
    print(f"=== Varianter (avvik vs faktura {FAKTURA_NORGESPRIS_KOMPENSASJON_KR:.2f} kr) ===\n")
    for r in rows:
        label = r["label"] + (" " + r["note"] if r["note"] else "")
        print(
            f"  {label:<60} snitt={r['snitt_eks_mva']:.6f}  "
            f"komp={r['komp_kr']:+.2f}  "
            f"avvik={r['avvik_kr']:+.2f} kr  ({r['avvik_pct']:+.3f}%)"
        )
    print()
    print("=== Reverse-engineer: hvilken konstant kurs ville matchet eksakt? ===")
    print(f"  Forbruksvektet EUR/kWh:    {meta['weighted_eur_per_kwh']:.6f}")
    print(f"  Implisitt single-rate:     {meta['implied_match_rate']:.4f} NOK/EUR")
    print(f"  Nord Pool EXR snitt:       {meta['exr_arith_avg']:.4f}")
    print(f"  Nord Pool EXR vektet:      {meta['exr_weighted_avg']:.4f}")
    print(f"  NB aritmetisk månedssnitt: {meta['nb_arith_avg']:.4f}")
    print(f"  NB forbruksvektet snitt:   {meta['nb_weighted_avg']:.4f}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--emit-markdown",
        action="store_true",
        help="Skriv resultatet som Markdown til docs/research/_generated/ "
             "(impliserer --no-network for reproduserbarhet)",
    )
    p.add_argument(
        "--no-network",
        action="store_true",
        help="Bruk kun lokale fixturer, ingen live HKS-kall",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Sti for Markdown-output (default: docs/research/_generated/"
             "match_norgespris_variants.md)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    no_network = args.no_network or args.emit_markdown

    elhub = load_elhub_hourly(ELHUB_CSV)
    nb_rates = load_nb_rates()

    if no_network:
        points = load_april_hours_from_snapshot(nb_rates)
    else:
        points = fetch_april_hours(DELIVERY_AREA)
    points = attach_kwh(points, elhub)

    rows, meta = compute_variants(points, nb_rates, no_network=no_network)

    if args.emit_markdown:
        out = args.output or (GENERATED_DIR / "match_norgespris_variants.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(rows, meta))
        print(f"Skrev {out.relative_to(ROOT)}")
        return 0

    print_text_report(rows, meta)
    return 0


if __name__ == "__main__":
    sys.exit(main())
