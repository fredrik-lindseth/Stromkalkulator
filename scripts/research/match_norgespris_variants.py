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
"""

from __future__ import annotations

import csv
import json
import sys
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable, Final

# --- Konfig (april 2026, NO5, BKK) ---

YEAR: Final[int] = 2026
MONTH: Final[int] = 4
DELIVERY_AREA: Final[str] = "NO5"

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
ELHUB_CSV: Final[Path] = ROOT / "Måleverdier" / "elhub_april.csv"
NB_SNAPSHOT: Final[Path] = ROOT / "tests" / "fixtures" / "nb_eur_nok_2026.json"

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
    """Hent alle timer i april fra HKS."""
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


def main() -> int:
    print(f"=== Variant-matrise for Norgespris-spot {YEAR}-{MONTH:02d} ({DELIVERY_AREA}) ===\n")
    print(f"Faktura: forbruk {FAKTURA_FORBRUK_KWH} kWh, "
          f"Norgespris-komp {FAKTURA_NORGESPRIS_KOMPENSASJON_KR} kr")
    print(f"Implisitt snittspot eks. mva: {FAKTURA_IMPLISITT_EKS_MVA:.6f} NOK/kWh\n")

    print(f"Leser Elhub-forbruk fra {ELHUB_CSV.name}...")
    elhub = load_elhub_hourly(ELHUB_CSV)
    print(f"  {len(elhub)} timer i CSV")

    print("Henter HKS-data for april (rate-limited)...")
    points = fetch_april_hours(DELIVERY_AREA)
    points = attach_kwh(points, elhub)
    print(f"  {len(points)} timer hentet, "
          f"sum kWh i NP-vinduet: {sum(p.kwh for p in points):.3f}")

    print(f"Leser NB EUR/NOK fra {NB_SNAPSHOT.name}...")
    nb_rates = load_nb_rates()

    days = sorted({p.day for p in points})
    nb_same = forward_fill(days, nb_rates)
    nb_prev = previous_bankday_fill(days, nb_rates)
    nb_apr_arith = sum(r for d, r in nb_rates.items() if d.startswith(f"{YEAR}-{MONTH:02d}"))
    nb_apr_count = sum(1 for d in nb_rates if d.startswith(f"{YEAR}-{MONTH:02d}"))
    nb_arith_avg = nb_apr_arith / nb_apr_count

    # Forbruksvektet NB-månedssnitt: vekt hver NB-kurs med kWh på dagene den dekker
    daily_kwh: dict[str, float] = defaultdict(float)
    for p in points:
        daily_kwh[p.day] += p.kwh
    weighted_num = sum(daily_kwh[d] * nb_same[d] for d in days)
    weighted_den = sum(daily_kwh[d] for d in days)
    nb_weighted_avg = weighted_num / weighted_den

    print(f"  NB same-day forward-fill, snitt over månedsdagene: "
          f"{sum(nb_same.values())/len(nb_same):.4f}")
    print(f"  NB aritmetisk månedssnitt (kun bankdager): {nb_arith_avg:.4f}")
    print(f"  NB forbruksvektet månedssnitt: {nb_weighted_avg:.4f}")
    print()

    print("=== Varianter (avvik vs faktura -1427,89 kr) ===\n")

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

    for label, fn in [
        ("A: Nord Pool EXR (daglig, fra HKS)", rate_exr),
        ("B: NB same-day forward-fill", rate_nb_same),
        ("C: NB previous-bankday (T-1)", rate_nb_prev),
        ("D: NB aritmetisk månedssnitt", rate_nb_arith),
        ("E: NB forbruksvektet månedssnitt", rate_nb_weighted),
    ]:
        snitt, forbruk = weighted_avg_nok_eks_mva(points, fn)
        print_variant(label, snitt, forbruk)

    # F: HKS NOK_per_kWh direkte (= Nord Pools egen NOK-pris time-for-time, inkl. NPs runding)
    total_kwh = sum(p.kwh for p in points)
    nok_eks_mva_hks = sum(p.nordpool_nok_per_kwh * p.kwh for p in points) / total_kwh
    print_variant("F: HKS NOK_per_kWh direkte (NP-runding)", nok_eks_mva_hks, total_kwh)

    # G: HKS NOK_per_kWh avrundet per time til 4 desimaler (BKK kan gjøre dette)
    nok_round4 = sum(round(p.nordpool_nok_per_kwh, 4) * p.kwh for p in points) / total_kwh
    print_variant("G: HKS NOK_per_kWh avrundet per time (4d)", nok_round4, total_kwh)

    # H: HKS NOK_per_kWh avrundet til 5 desimaler (HKS publiserer typisk 5d)
    nok_round5 = sum(round(p.nordpool_nok_per_kwh, 5) * p.kwh for p in points) / total_kwh
    print_variant("H: HKS NOK_per_kWh avrundet per time (5d)", nok_round5, total_kwh)

    # I: NB next-bankday (T+1) forward-fill — kursen som publiseres dagen etter
    nb_next: dict[str, float] = {}
    sorted_nb = sorted(nb_rates.items())
    for d in days:
        nxt = [r for r in sorted_nb if r[0] >= d]
        if not nxt:
            raise RuntimeError(f"Ingen kurs på/etter {d}")
        nb_next[d] = nxt[0][1]
    snitt_next, _ = weighted_avg_nok_eks_mva(points, lambda p: nb_next[p.day])
    print_variant("I: NB next-bankday (T+1)", snitt_next, total_kwh)

    # J: Blandet — NB same-day for ukedag, NP EXR for helg
    def rate_mixed(p: HourPoint) -> float:
        wd = datetime.fromisoformat(p.iso).weekday()
        return nb_same[p.day] if wd < 5 else p.nordpool_exr
    snitt_mixed, _ = weighted_avg_nok_eks_mva(points, rate_mixed)
    print_variant("J: NB ukedag + NP-EXR helg", snitt_mixed, total_kwh)

    # Bonus: matchet kurs (single-rate som ville gitt eksakt match)
    weighted_eur_per_kwh = sum(p.eur_per_kwh * p.kwh for p in points) / sum(p.kwh for p in points)
    implied_rate = FAKTURA_IMPLISITT_EKS_MVA / weighted_eur_per_kwh
    print()
    print(f"=== Reverse-engineer: hvilken konstant kurs ville matchet eksakt? ===")
    print(f"  Forbruksvektet EUR/kWh: {weighted_eur_per_kwh:.6f}")
    print(f"  Implisitt single-rate:  {implied_rate:.4f} NOK/EUR")
    print(f"  Nord Pool EXR snitt:    {sum(p.nordpool_exr for p in points)/len(points):.4f}")
    print(f"  Nord Pool EXR vektet:   "
          f"{sum(p.nordpool_exr * p.kwh for p in points)/sum(p.kwh for p in points):.4f}")
    print(f"  NB aritmetisk månedssnitt: {nb_arith_avg:.4f}")
    print(f"  NB forbruksvektet snitt:   {nb_weighted_avg:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
