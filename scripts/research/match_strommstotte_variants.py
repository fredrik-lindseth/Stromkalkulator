"""Variant-matrise: hvilken strømstøtte-formel matcher BKKs "uten Norgespris"-tall?

Bakgrunn: docs/begrensninger.md §4. Brukeren har Norgespris, så strømstøtten
er teoretisk. På bkk.no vises et "uten Norgespris"-tall som er
spot inkl. mva minus strømstøtte, time-for-time. For april 2026:

  BKK viser:        1377 kr
  Vår beregning:    1347 kr (rapportert av bruker)
  Avvik:            30 kr (≈ 2 %)

Vår kode bruker STROMSTOTTE_LEVEL = 0,9625 inkl. mva (77 øre + 25 % mva, 2026)
og rate 0,90. Forskrift 2025-09-08-1791 §5 bekrefter dette for 2026.

Dette scriptet kjører ulike kombinasjoner av:
  - terskel inkl. mva (87,5 / 91,25 / 93,75 / 96,25)
  - refusjonsrate (75 / 80 / 90 / 95 / 100 %)
  - mva-håndtering (terskel inkl. vs eks. mva)
  - aggregering (time-for-time vs månedsnitt)
  - avrunding (per time, per dag, per måned)

mot fakturadataene i tests/fixtures/bkk_april_2026_hourly.json, og rapporterer
hvilken kombinasjon som treffer 1377 kr nøyaktig.

Kjøres uten tredjeparts-avhengigheter (Python 3.11+ stdlib).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
FIXTURE: Final[Path] = ROOT / "tests" / "fixtures" / "bkk_april_2026_hourly.json"
GENERATED_DIR: Final[Path] = ROOT / "docs" / "research" / "_generated"

# Mål: hva "uten Norgespris"-tallet på BKK viser for april 2026
TARGET_BKK: Final[float] = 1377.0
USER_OBSERVED_OURS: Final[float] = 1347.0

MVA: Final[float] = 1.25

# Terskler — verdier i NOK/kWh inkl. mva
TERSKLER_INKL = {
    "2023 (70 øre)": 0.875,
    "2024 (73 øre)": 0.9125,
    "2025 (75 øre)": 0.9375,
    "2026 (77 øre)": 0.9625,  # vår faktiske kode
}

RATES = {
    "55 %": 0.55,
    "75 %": 0.75,
    "80 %": 0.80,
    "90 %": 0.90,  # vår faktiske kode
    "95 %": 0.95,
    "100 %": 1.00,
}


@dataclass(frozen=True)
class HourPoint:
    iso: str
    kwh: float
    spot_eks_mva: float

    @property
    def spot_inkl_mva(self) -> float:
        return self.spot_eks_mva * MVA


def load_hours() -> list[HourPoint]:
    data = json.loads(FIXTURE.read_text())
    return [
        HourPoint(h["start_local"], h["kwh"], h["spot_nok_kwh_eks_mva"])
        for h in data["hours"]
    ]


def netto_spot_etter_stotte(
    hours: list[HourPoint],
    terskel_inkl: float,
    rate: float,
    *,
    round_hour: int | None = None,
    round_day: int | None = None,
) -> tuple[float, float, float]:
    """Returner (spot_kost_inkl_mva, stotte_total, netto = spot - stotte).

    round_hour: hvis satt, round(stotte_per_kwh, N) per time
    round_day: hvis satt, round(støtte_total_per_dag, N) etter time-summering
    """
    spot_kost = 0.0
    stotte_per_day: dict[str, float] = {}
    for h in hours:
        spot_kost += h.spot_inkl_mva * h.kwh
        if h.spot_inkl_mva > terskel_inkl:
            stotte_per_kwh = (h.spot_inkl_mva - terskel_inkl) * rate
            if round_hour is not None:
                stotte_per_kwh = round(stotte_per_kwh, round_hour)
            stotte = stotte_per_kwh * h.kwh
            day = h.iso[:10]
            stotte_per_day[day] = stotte_per_day.get(day, 0.0) + stotte

    if round_day is not None:
        stotte_total = sum(round(v, round_day) for v in stotte_per_day.values())
    else:
        stotte_total = sum(stotte_per_day.values())

    return spot_kost, stotte_total, spot_kost - stotte_total


def netto_spot_monthly_avg(
    hours: list[HourPoint], terskel_inkl: float, rate: float
) -> tuple[float, float, float]:
    """Beregn strømstøtte basert på månedsnitt (FEIL etter forskrift, men test)."""
    total_kwh = sum(h.kwh for h in hours)
    spot_kost = sum(h.spot_inkl_mva * h.kwh for h in hours)
    weighted_spot_inkl = spot_kost / total_kwh
    if weighted_spot_inkl > terskel_inkl:
        stotte_per_kwh = (weighted_spot_inkl - terskel_inkl) * rate
        stotte_total = stotte_per_kwh * total_kwh
    else:
        stotte_total = 0.0
    return spot_kost, stotte_total, spot_kost - stotte_total


def netto_terskel_eks_mva(
    hours: list[HourPoint], terskel_eks: float, rate: float
) -> tuple[float, float, float]:
    """Sammenligning og refusjon i eks. mva-rom, deretter * 1.25 på slutten."""
    total_stotte_eks = 0.0
    for h in hours:
        if h.spot_eks_mva > terskel_eks:
            total_stotte_eks += (h.spot_eks_mva - terskel_eks) * rate * h.kwh
    spot_kost_inkl = sum(h.spot_inkl_mva * h.kwh for h in hours)
    stotte_inkl = total_stotte_eks * MVA
    return spot_kost_inkl, stotte_inkl, spot_kost_inkl - stotte_inkl


def report(label: str, netto: float) -> None:
    diff_bkk = netto - TARGET_BKK
    diff_us = netto - USER_OBSERVED_OURS
    marker = ""
    if abs(diff_bkk) < 1.0:
        marker = "  ← MATCH BKK"
    elif abs(diff_us) < 1.0:
        marker = "  ← match brukerens 1347"
    print(
        f"  {label:<58} netto={netto:8.2f}  Δbkk={diff_bkk:+7.2f}  Δ1347={diff_us:+7.2f}{marker}"
    )


def compute_markdown_rows(hours: list[HourPoint]) -> tuple[list[dict], dict]:
    """Beregn de viktigste variant-tallene som rader for Markdown-tabellen."""
    total_kwh = sum(h.kwh for h in hours)
    spot_kost_inkl = sum(h.spot_inkl_mva * h.kwh for h in hours)

    rows: list[dict] = []

    def add(label: str, netto: float, kategori: str) -> None:
        rows.append({
            "kategori": kategori,
            "label": label,
            "netto": netto,
            "delta_bkk": netto - TARGET_BKK,
            "delta_us": netto - USER_OBSERVED_OURS,
        })

    # A: forskriftens metode (time-for-time) — viser bare gjeldende kombinasjon + 2025
    for tname, terskel in TERSKLER_INKL.items():
        for rname, rate in RATES.items():
            _, _, netto = netto_spot_etter_stotte(hours, terskel, rate)
            add(f"terskel={tname}, rate={rname}", netto, "A: time-for-time")

    # B: snitt-basert
    for tname, terskel in TERSKLER_INKL.items():
        _, _, netto = netto_spot_monthly_avg(hours, terskel, 0.90)
        add(f"snitt-basert: terskel={tname}, rate=90 %", netto, "B: månedsnitt")

    # C: eks. mva-sammenligning
    for label, terskel_eks in [("70 øre", 0.70), ("73 øre", 0.73), ("75 øre", 0.75), ("77 øre", 0.77)]:
        _, _, netto = netto_terskel_eks_mva(hours, terskel_eks, 0.90)
        add(f"eks-mva: terskel={label}, rate=90 %", netto, "C: eks-mva")

    # D: avrunding (gjeldende terskel 96,25 øre, 90 %)
    for round_h in [None, 4, 5]:
        for round_d in [None, 2, 4]:
            _, _, netto = netto_spot_etter_stotte(
                hours, 0.9625, 0.90, round_hour=round_h, round_day=round_d
            )
            add(f"round_hour={round_h}, round_day={round_d}", netto, "D: avrunding")

    # E: brute-force minste avvik for terskel og rate
    best_terskel = 0.9625
    best_terskel_netto = 0.0
    best_diff = 1e9
    for t_int in range(8000, 10000):
        t = t_int / 10000
        _, _, netto = netto_spot_etter_stotte(hours, t, 0.90)
        d = abs(netto - TARGET_BKK)
        if d < best_diff:
            best_diff = d
            best_terskel = t
            best_terskel_netto = netto

    best_rate = 0.90
    best_rate_netto = 0.0
    best_diff = 1e9
    for r_int in range(50, 100):
        r = r_int / 100
        _, _, netto = netto_spot_etter_stotte(hours, 0.9625, r)
        d = abs(netto - TARGET_BKK)
        if d < best_diff:
            best_diff = d
            best_rate = r
            best_rate_netto = netto

    meta = {
        "total_kwh": total_kwh,
        "spot_kost_inkl": spot_kost_inkl,
        "vektet_spot_eks_mva": spot_kost_inkl / MVA / total_kwh,
        "vektet_spot_inkl_mva": spot_kost_inkl / total_kwh,
        "target_bkk": TARGET_BKK,
        "user_observed_ours": USER_OBSERVED_OURS,
        "best_terskel": best_terskel,
        "best_terskel_netto": best_terskel_netto,
        "best_rate": best_rate,
        "best_rate_netto": best_rate_netto,
    }
    return rows, meta


def render_markdown(rows: list[dict], meta: dict) -> str:
    lines: list[str] = []
    lines.append(
        "_Generert av_ `scripts/research/match_strommstotte_variants.py --emit-markdown` "
        "(april 2026, NO5, BKK; kun lokale fixturer)."
    )
    lines.append("")
    lines.append(
        f"Datapunkter: {len([1 for _ in range(0)]) or 720} timer (april 2026), "
        f"total {meta['total_kwh']:.3f} kWh. "
        f"Vektet spot eks. mva: {meta['vektet_spot_eks_mva']:.6f} NOK/kWh. "
        f"Vektet spot inkl. mva: {meta['vektet_spot_inkl_mva']:.6f} NOK/kWh. "
        f"Total spot uten støtte: {meta['spot_kost_inkl']:.2f} kr."
    )
    lines.append("")
    lines.append(
        f"Referansetall: BKK \"uten Norgespris\" = {meta['target_bkk']:.2f} kr, "
        f"brukers observerte fra vår kode = {meta['user_observed_ours']:.2f} kr."
    )
    lines.append("")
    by_kat: dict[str, list[dict]] = {}
    for r in rows:
        by_kat.setdefault(r["kategori"], []).append(r)
    for kat in sorted(by_kat):
        lines.append(f"### {kat}")
        lines.append("")
        lines.append("| Variant | Netto (kr) | Δ BKK 1377 | Δ vår 1347 |")
        lines.append("| --- | ---: | ---: | ---: |")
        for r in by_kat[kat]:
            marker = ""
            if abs(r["delta_bkk"]) < 1.0:
                marker = " match BKK"
            elif abs(r["delta_us"]) < 1.0:
                marker = " match vår"
            lines.append(
                f"| {r['label']}{marker} "
                f"| {r['netto']:.2f} "
                f"| {r['delta_bkk']:+.2f} "
                f"| {r['delta_us']:+.2f} |"
            )
        lines.append("")
    lines.append("### Brute-force minste avvik")
    lines.append("")
    lines.append("| Søk | Beste verdi | Netto (kr) | Δ BKK |")
    lines.append("| --- | ---: | ---: | ---: |")
    lines.append(
        f"| Terskel (rate=90 % fast) "
        f"| {meta['best_terskel']:.4f} inkl. mva ({meta['best_terskel']/MVA*100:.3f} øre) "
        f"| {meta['best_terskel_netto']:.2f} "
        f"| {meta['best_terskel_netto'] - meta['target_bkk']:+.2f} |"
    )
    lines.append(
        f"| Rate (terskel=0.9625 fast) "
        f"| {meta['best_rate']*100:.0f} % "
        f"| {meta['best_rate_netto']:.2f} "
        f"| {meta['best_rate_netto'] - meta['target_bkk']:+.2f} |"
    )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--emit-markdown",
        action="store_true",
        help="Skriv resultatet som Markdown til docs/research/_generated/",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output-sti (default: docs/research/_generated/"
             "match_strommstotte_variants.md)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hours = load_hours()

    if args.emit_markdown:
        rows, meta = compute_markdown_rows(hours)
        out = args.output or (GENERATED_DIR / "match_strommstotte_variants.md")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(rows, meta))
        print(f"Skrev {out.relative_to(ROOT)}")
        return 0

    return _print_full_report(hours)


def _print_full_report(hours: list[HourPoint]) -> int:
    total_kwh = sum(h.kwh for h in hours)
    spot_kost_inkl = sum(h.spot_inkl_mva * h.kwh for h in hours)

    print(f"=== Strømstøtte-variant-matrise, april 2026 (NO5, BKK) ===\n")
    print(f"Datapunkter: {len(hours)} timer, total {total_kwh:.3f} kWh")
    print(f"Vektet snitt spotpris eks. mva: {spot_kost_inkl/MVA/total_kwh:.6f}")
    print(f"Vektet snitt spotpris inkl. mva: {spot_kost_inkl/total_kwh:.6f}")
    print(f"Total spot inkl. mva (uten støtte): {spot_kost_inkl:.2f} kr")
    print()
    print(f"Mål: BKK \"uten Norgespris\"           = {TARGET_BKK:.2f} kr")
    print(f"Brukers observerte tall fra vår kode = {USER_OBSERVED_OURS:.2f} kr")
    print()

    # === A: Time-for-time med ulike terskler og rater ===
    print("=== A: Time-for-time (forskriftens metode) ===")
    print("    Terskel inkl. mva sammenlignes mot spotpris inkl. mva per time.")
    print(f"    {'Variant':<58} {'netto':>8}  {'Δbkk':>7}  {'Δ1347':>7}")
    for tname, terskel in TERSKLER_INKL.items():
        for rname, rate in RATES.items():
            _, _, netto = netto_spot_etter_stotte(hours, terskel, rate)
            report(f"terskel={tname:<14} rate={rname}", netto)
    print()

    # === B: Månedsnitt (vanlig feil) ===
    print("=== B: Snitt-basert (potensiell feil — IKKE forskriftsmetode) ===")
    print("    Bruker forbruksvektet månedsnitt mot terskel.")
    for tname, terskel in TERSKLER_INKL.items():
        for rname, rate in [("90 %", 0.90)]:
            _, _, netto = netto_spot_monthly_avg(hours, terskel, rate)
            report(f"snitt-basert: terskel={tname:<14} rate={rname}", netto)
    print()

    # === C: Mva-orientering — terskel oppgitt eks. mva ===
    print("=== C: Sammenligning i eks. mva-rom (også vanlig feiltolkning) ===")
    print("    Terskel og spotpris sammenlignes eks. mva, støtte multipliseres med 1.25.")
    for label, terskel_eks in [
        ("70 øre", 0.70),
        ("73 øre", 0.73),
        ("75 øre", 0.75),
        ("77 øre", 0.77),
    ]:
        for rname, rate in [("90 %", 0.90)]:
            _, _, netto = netto_terskel_eks_mva(hours, terskel_eks, rate)
            report(f"eks-mva-sammenligning: terskel={label:<6} rate={rname}", netto)
    print()

    # === D: Hybridvarianter (mva-rekkefølge, avrunding) ===
    print("=== D: Avrunding (vår faktiske terskel 96,25 øre, 90 %) ===")
    base = 0.9625
    for round_h in [None, 4, 5]:
        for round_d in [None, 2, 4]:
            _, _, netto = netto_spot_etter_stotte(
                hours, base, 0.90, round_hour=round_h, round_day=round_d
            )
            report(f"round_hour={round_h} round_day={round_d}", netto)
    print()

    # === E: BKKs "uten Norgespris" — hypotese ===
    print("=== E: Hypotese — hva slags formel matcher BKKs 1377 kr? ===")
    print("    Brute-force på terskel (rate 90 % fast):")
    best_terskel = None
    best_diff = 1e9
    for t_int in range(8000, 10000):
        t = t_int / 10000
        _, _, netto = netto_spot_etter_stotte(hours, t, 0.90)
        d = abs(netto - TARGET_BKK)
        if d < best_diff:
            best_diff = d
            best_terskel = t
            best_netto = netto
    print(f"    Beste match (rate 90 %): terskel={best_terskel:.4f} inkl. mva")
    print(f"      → eks. mva: {best_terskel/MVA*100:.3f} øre")
    print(f"      → netto: {best_netto:.2f} kr (avvik {best_netto - TARGET_BKK:+.2f} kr)")
    print()
    print(f"    Brute-force på rate (terskel 0.9625 fast):")
    best_rate = None
    best_diff = 1e9
    for r_int in range(50, 100):
        r = r_int / 100
        _, _, netto = netto_spot_etter_stotte(hours, 0.9625, r)
        d = abs(netto - TARGET_BKK)
        if d < best_diff:
            best_diff = d
            best_rate = r
            best_netto = netto
    print(f"    Beste match (terskel 0.9625): rate={best_rate*100:.0f} %")
    print(f"      → netto: {best_netto:.2f} kr (avvik {best_netto - TARGET_BKK:+.2f} kr)")
    print()

    # === F: Tibber prismodell-påslag (relevant?) ===
    # Brukeren har Norgespris og Tibber er kraftleverandøren. Tibbers påslag (per
    # 2026 ~10 øre/kWh) er IKKE en del av strømstøtte-formelen — strømstøtten
    # baserer seg på elspotpris i budområdet (forskrift §3), ikke
    # kraftleverandørens pris.
    print("=== F: Tibber-påslag (skal IKKE påvirke strømstøtte) ===")
    print("    Strømstøtte = funksjon av elspotpris i budområdet (forskrift §3).")
    print("    Påslag fra kraftleverandør inngår ikke. Sjekk likevel:")
    for paaslag in [0.01, 0.03, 0.0399, 0.05, 0.10]:
        # Hvis vi feilaktig brukte (spot + påslag) som basis for støtteberegning:
        new_hours = [
            HourPoint(h.iso, h.kwh, h.spot_eks_mva + paaslag) for h in hours
        ]
        _, _, netto = netto_spot_etter_stotte(new_hours, 0.9625, 0.90)
        report(f"hvis vi la til {paaslag*100:.2f} øre påslag på spot", netto)
    print()

    # === G: Verifisering av "vår faktiske" beregning ===
    print("=== G: Verifisering: matcher 1347 vår faktiske kode? ===")
    _, stotte_oss, netto_oss = netto_spot_etter_stotte(hours, 0.9625, 0.90)
    print(f"    Med STROMSTOTTE_LEVEL = 0.9625, RATE = 0.90 (gjeldende kode):")
    print(f"      støtte total = {stotte_oss:.2f} kr")
    print(f"      netto spot etter støtte = {netto_oss:.2f} kr")
    print(f"      avvik vs brukerens påstand 1347: {netto_oss - USER_OBSERVED_OURS:+.2f} kr")
    print()
    print(f"    Hvis vi feilaktig brukte STROMSTOTTE_LEVEL = 0.9125 (2024):")
    _, stotte_old, netto_old = netto_spot_etter_stotte(hours, 0.9125, 0.90)
    print(f"      støtte total = {stotte_old:.2f} kr")
    print(f"      netto spot etter støtte = {netto_old:.2f} kr")
    print(f"      avvik vs brukerens påstand 1347: {netto_old - USER_OBSERVED_OURS:+.2f} kr")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
