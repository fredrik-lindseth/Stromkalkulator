"""Reproduserer BKK-fakturaberegningen fra timesdata og sammenligner med faktura.

Leser hourly JSON-fixture, beregner linje-for-linje og differ mot faktura-fixturen
i tests/test_faktura_bkk.py. Kun Python 3 standardbibliotek.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

# --- Konstanter (speiler const.py og dso.py for BKK 2026) ---

DAY_RATE_START_HOUR = 6
DAY_RATE_END_HOUR = 22

BKK_ENERGILEDD_DAG_INKL_MVA = 0.35963  # NOK/kWh
BKK_ENERGILEDD_NATT_INKL_MVA = 0.13125
BKK_FORBRUKSAVGIFT_INKL_MVA = 0.08913
BKK_ENOVAAVGIFT_INKL_MVA = 0.0125
NORGESPRIS_INKL_MVA = 0.50  # 50 øre/kWh inkl. mva (Sør-Norge)
MVA_SATS = 1.25  # spot eks. mva * 1.25 = inkl. mva

BKK_KAPASITETSTRINN = [
    (2.0, 155),
    (5.0, 250),
    (10.0, 415),
    (15.0, 600),
    (20.0, 770),
    (25.0, 940),
    (50.0, 1800),
    (75.0, 2650),
    (100.0, 3500),
    (float("inf"), 6900),
]

# Helligdager 2026 (utvid her for andre år)
HELLIGDAGER: dict[int, set[date]] = {
    2026: {
        date(2026, 1, 1), date(2026, 4, 2), date(2026, 4, 3),
        date(2026, 4, 5), date(2026, 4, 6), date(2026, 5, 1),
        date(2026, 5, 14), date(2026, 5, 17), date(2026, 5, 24),
        date(2026, 5, 25), date(2026, 12, 25), date(2026, 12, 26),
    },
}

# Faktura-fixtures (kopi av relevante felter fra tests/test_faktura_bkk.py).
FAKTURAER: dict[str, dict[str, Any]] = {
    "februar_2026": {
        "forbruk_dag_kwh": 893.615,
        "forbruk_natt_kwh": 780.171,
        "forbruk_total_kwh": 1673.786,
        "forventet_energiledd_dag_kr": 321.36,
        "forventet_energiledd_natt_kr": 102.40,
        "forventet_forbruksavgift_kr": 149.17,
        "forventet_enovaavgift_kr": 20.93,
        "forventet_kapasitet_kr": 415.00,
        "forventet_norgespris_kr": -1821.64,
        "forventet_nettleie_kr": 1008.86,
        "forventet_total_kr": -812.78,
    },
    "mars_2026": {
        "forbruk_dag_kwh": 831.768,
        "forbruk_natt_kwh": 721.449,
        "forbruk_total_kwh": 1553.217,
        "forventet_energiledd_dag_kr": 299.13,
        "forventet_energiledd_natt_kr": 94.69,
        "forventet_forbruksavgift_kr": 138.43,
        "forventet_enovaavgift_kr": 19.41,
        "forventet_kapasitet_kr": 250.00,
        "forventet_norgespris_kr": -1550.68,
        "forventet_nettleie_kr": 801.66,
        "forventet_total_kr": -749.02,
    },
    "april_2026": {
        "forbruk_dag_kwh": 620.829,
        "forbruk_natt_kwh": 760.998,
        "forbruk_total_kwh": 1381.827,
        "forventet_energiledd_dag_kr": 223.26,
        "forventet_energiledd_natt_kr": 99.88,
        "forventet_forbruksavgift_kr": 123.16,
        "forventet_enovaavgift_kr": 17.28,
        "forventet_kapasitet_kr": 250.00,
        "forventet_norgespris_kr": -1427.89,
        "forventet_nettleie_kr": 713.58,
        "forventet_total_kr": -714.31,
    },
}


def er_helligdag(d: date) -> bool:
    return d in HELLIGDAGER.get(d.year, set())


def er_dagtid(ts: datetime) -> bool:
    """Dag-tariff: mandag-fredag 06-21 (slutt 22), ikke helligdag."""
    if ts.weekday() >= 5 or er_helligdag(ts.date()):
        return False
    return DAY_RATE_START_HOUR <= ts.hour < DAY_RATE_END_HOUR


def finn_kapasitetstrinn(snitt_kw: float) -> tuple[float, int]:
    for grense, kr in BKK_KAPASITETSTRINN:
        if snitt_kw <= grense:
            return grense, kr
    return BKK_KAPASITETSTRINN[-1]


def beregn(hours: list[dict[str, Any]], shift_seconds: int = 13) -> dict[str, float]:
    total_kwh = 0.0
    forbruk_dag = 0.0
    forbruk_natt = 0.0
    norgespris_sum = 0.0

    # Maks effekt per dato (W -> kW)
    maks_per_dato: dict[date, float] = {}

    for i, h in enumerate(hours):
        ts = datetime.fromisoformat(h["start_local"])
        kwh = float(h["kwh"])
        spot_eks = float(h["spot_nok_kwh_eks_mva"])

        # Shift-korreksjon: HAN-broadcast ved HH:00:N inneholder tpi(HH:00:00),
        # så tpi-diffen trenger -N/3600 x (p_mean_HH - p_mean_HH-1) per time.
        # Teleskopisk over måneden: kun første/siste time-snitt teller.
        if shift_seconds and i > 0:
            delta = shift_seconds / 3600 * (kwh - float(hours[i - 1]["kwh"]))
            kwh = kwh - delta

        total_kwh += kwh
        if er_dagtid(ts):
            forbruk_dag += kwh
        else:
            forbruk_natt += kwh

        # Norgespris-kompensasjon per time
        norgespris_sum += (NORGESPRIS_INKL_MVA - spot_eks * MVA_SATS) * kwh

        # Kapasitetsledd bruker timesgjennomsnitt av effekt (kWh/h = kW),
        # ikke øyeblikkstopp p_max_w. BKK regner snitt av topp 3 dager.
        d = ts.date()
        if kwh > maks_per_dato.get(d, 0.0):
            maks_per_dato[d] = kwh

    topp3 = sorted(maks_per_dato.values(), reverse=True)[:3]
    snitt_topp3 = sum(topp3) / len(topp3) if topp3 else 0.0
    kap_grense, kap_kr = finn_kapasitetstrinn(snitt_topp3)

    energiledd_dag = forbruk_dag * BKK_ENERGILEDD_DAG_INKL_MVA
    energiledd_natt = forbruk_natt * BKK_ENERGILEDD_NATT_INKL_MVA
    forbruksavgift = total_kwh * BKK_FORBRUKSAVGIFT_INKL_MVA
    enova = total_kwh * BKK_ENOVAAVGIFT_INKL_MVA
    nettleie = energiledd_dag + energiledd_natt + forbruksavgift + enova + kap_kr
    total = nettleie + norgespris_sum

    return {
        "total_kwh": total_kwh,
        "forbruk_dag_kwh": forbruk_dag,
        "forbruk_natt_kwh": forbruk_natt,
        "energiledd_dag_kr": energiledd_dag,
        "energiledd_natt_kr": energiledd_natt,
        "forbruksavgift_kr": forbruksavgift,
        "enovaavgift_kr": enova,
        "kapasitet_kr": float(kap_kr),
        "kapasitet_snitt_kw": snitt_topp3,
        "kapasitet_grense_kw": kap_grense,
        "norgespris_kr": norgespris_sum,
        "nettleie_kr": nettleie,
        "total_kr": total,
    }


def innenfor_toleranse(navn: str, beregnet: float, faktura: float) -> bool:
    diff = beregnet - faktura
    if navn == "Total inkl. Norgespris":
        return abs(diff) <= 5.0
    if abs(faktura) < 0.001:
        return abs(diff) <= 0.01
    return abs(diff) / abs(faktura) <= 0.01


def print_rad(navn: str, beregnet: float, faktura: float, enhet: str = "kr") -> bool:
    diff = beregnet - faktura
    tegn = "+" if diff >= 0 else ""
    ok = innenfor_toleranse(navn, beregnet, faktura)
    desimaler = 3 if enhet == "kWh" else 2
    print(
        f"| {navn:<28} | {beregnet:>12.{desimaler}f} | {faktura:>12.{desimaler}f} "
        f"| {tegn}{diff:>8.{desimaler}f} | {'OK' if ok else 'AVVIK'} |"
    )
    return ok


def main() -> int:
    p = argparse.ArgumentParser(description="Verifiser BKK-faktura mot timesdata.")
    p.add_argument("--hourly", required=True, type=Path, help="Sti til hourly JSON-fixture")
    p.add_argument("--faktura", required=True, choices=sorted(FAKTURAER.keys()), help="Faktura-fixture-navn")
    p.add_argument(
        "--shift-seconds", type=int, default=13,
        help=(
            "Sek HAN-broadcast er forsinket etter timeskifte. "
            "Default 13 = Fredriks Kaifa MA304H3E + Pow-U (10s i maler + 3s transmisjon). "
            "Aidon/Pow-U: typisk 10-15. Kamstrup HAN-NVE: typisk 5-10. "
            "Tibber Pulse: ukjent, eksperimenter selv. 0 skrur av korreksjonen."
        ),
    )
    args = p.parse_args()

    if not args.hourly.exists():
        print(f"Finner ikke {args.hourly}", file=sys.stderr)
        return 2

    with args.hourly.open() as f:
        data = json.load(f)

    hours = data.get("hours", [])
    if not hours:
        print("Ingen timer i fixturen", file=sys.stderr)
        return 2

    beregnet = beregn(hours, shift_seconds=args.shift_seconds)
    f = FAKTURAER[args.faktura]

    print(f"=== BKK {args.faktura} verifikasjon (shift={args.shift_seconds}s) ===\n")
    print(f"Antall timer: {len(hours)}")
    print(f"Kapasitet: snitt topp 3 = {beregnet['kapasitet_snitt_kw']:.3f} kW "
          f"-> trinn {beregnet['kapasitet_grense_kw']} kW, "
          f"{int(beregnet['kapasitet_kr'])} kr\n")
    print(f"| {'Linje':<28} | {'Beregnet':>12} | {'Faktura':>12} | {'Avvik':>9} | Status |")
    print(f"|{'-' * 30}|{'-' * 14}|{'-' * 14}|{'-' * 10}|{'-' * 8}|")

    ok = True
    ok &= print_rad("Total kWh", beregnet["total_kwh"], f["forbruk_total_kwh"], "kWh")
    ok &= print_rad("Forbruk dag kWh", beregnet["forbruk_dag_kwh"], f["forbruk_dag_kwh"], "kWh")
    ok &= print_rad("Forbruk natt kWh", beregnet["forbruk_natt_kwh"], f["forbruk_natt_kwh"], "kWh")
    ok &= print_rad("Energiledd dag", beregnet["energiledd_dag_kr"], f["forventet_energiledd_dag_kr"])
    ok &= print_rad("Energiledd natt", beregnet["energiledd_natt_kr"], f["forventet_energiledd_natt_kr"])
    ok &= print_rad("Forbruksavgift", beregnet["forbruksavgift_kr"], f["forventet_forbruksavgift_kr"])
    ok &= print_rad("Enovaavgift", beregnet["enovaavgift_kr"], f["forventet_enovaavgift_kr"])
    ok &= print_rad("Kapasitet", beregnet["kapasitet_kr"], f["forventet_kapasitet_kr"])
    ok &= print_rad("Nettleie sum", beregnet["nettleie_kr"], f["forventet_nettleie_kr"])
    ok &= print_rad("Norgespris-komp", beregnet["norgespris_kr"], f["forventet_norgespris_kr"])
    ok &= print_rad("Total inkl. Norgespris", beregnet["total_kr"], f["forventet_total_kr"])

    print()
    print("Alt innenfor toleranse" if ok else "Avvik utenfor toleranse")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
