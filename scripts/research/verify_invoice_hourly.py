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
    "mai_2026": {
        "forbruk_dag_kwh": 518.142,
        "forbruk_natt_kwh": 661.161,
        "forbruk_total_kwh": 1179.303,
        "forventet_energiledd_dag_kr": 186.34,
        "forventet_energiledd_natt_kr": 86.77,
        "forventet_forbruksavgift_kr": 105.10,
        "forventet_enovaavgift_kr": 14.74,
        "forventet_kapasitet_kr": 250.00,
        "forventet_norgespris_kr": -1032.56,
        "forventet_nettleie_kr": 642.95,
        "forventet_total_kr": -389.61,
    },
    "juni_2026": {
        "forbruk_dag_kwh": 590.646,
        "forbruk_natt_kwh": 442.982,
        "forbruk_total_kwh": 1033.628,
        "forventet_energiledd_dag_kr": 212.41,
        "forventet_energiledd_natt_kr": 58.14,
        "forventet_forbruksavgift_kr": 92.11,
        "forventet_enovaavgift_kr": 12.93,
        "forventet_kapasitet_kr": 250.00,
        "forventet_norgespris_kr": -363.54,
        "forventet_nettleie_kr": 625.59,
        "forventet_total_kr": 262.05,
    },
    "juli_2026": {
        "forbruk_dag_kwh": 514.414,
        "forbruk_natt_kwh": 424.349,
        "forbruk_total_kwh": 938.763,
        "forventet_energiledd_dag_kr": 185.00,
        "forventet_energiledd_natt_kr": 55.70,
        "forventet_forbruksavgift_kr": 83.67,
        "forventet_enovaavgift_kr": 11.73,
        "forventet_kapasitet_kr": 250.00,
        "forventet_norgespris_kr": -807.50,
        "forventet_nettleie_kr": 586.10,
        "forventet_total_kr": -221.40,
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


def shift_korriger(hours: list[dict[str, Any]], shift_seconds: int) -> list[float | None]:
    """Shift-korrigert kWh per time, `None` der fixturen mangler måling.

    Shift-korreksjon: HAN-broadcast ved HH:00:N inneholder tpi(HH:00:00), så
    tpi-diffen trenger -N/3600 x (p_mean_HH - p_mean_HH-1) per time. Teleskopisk
    over en sammenhengende serie: kun første/siste time-snitt teller. Ved et
    datahull brytes teleskopet, så korreksjonen starter på nytt etter hullet.
    """
    ut: list[float | None] = []
    forrige: float | None = None
    for h in hours:
        rå = h.get("kwh")
        if rå is None:
            ut.append(None)
            forrige = None
            continue
        kwh = float(rå)
        if shift_seconds and forrige is not None:
            kwh -= shift_seconds / 3600 * (kwh - forrige)
        ut.append(kwh)
        forrige = float(rå)
    return ut


def beregn(hours: list[dict[str, Any]], shift_seconds: int = 13) -> dict[str, float]:
    total_kwh = 0.0
    forbruk_dag = 0.0
    forbruk_natt = 0.0
    norgespris_sum = 0.0
    manglende = 0

    # Maks effekt per dato (W -> kW)
    maks_per_dato: dict[date, float] = {}

    korrigert = shift_korriger(hours, shift_seconds)

    for h, kwh in zip(hours, korrigert, strict=True):
        ts = datetime.fromisoformat(h["start_local"])
        spot_eks = float(h["spot_nok_kwh_eks_mva"])

        if kwh is None:
            manglende += 1
            continue

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
        "manglende_timer": float(manglende),
        "dekkede_timer": float(len(hours) - manglende),
    }


def innenfor_toleranse(navn: str, beregnet: float, faktura: float) -> bool:
    diff = beregnet - faktura
    if navn == "Total inkl. Norgespris":
        return abs(diff) <= 5.0
    if abs(faktura) < 0.001:
        return abs(diff) <= 0.01
    return abs(diff) / abs(faktura) <= 0.01


def print_rad(navn: str, beregnet: float, faktura: float, enhet: str = "kr", delvis: bool = False) -> bool:
    """Skriv én sammenligningsrad. `delvis` = linjen dekker ikke hele perioden.

    En delvis linje kan ikke sammenlignes med fakturaen i det hele tatt, så den
    rapporteres som DELVIS og teller verken som OK eller AVVIK.
    """
    diff = beregnet - faktura
    tegn = "+" if diff >= 0 else ""
    ok = innenfor_toleranse(navn, beregnet, faktura)
    desimaler = 3 if enhet == "kWh" else 2
    status = "DELVIS" if delvis else ("OK" if ok else "AVVIK")
    print(
        f"| {navn:<28} | {beregnet:>12.{desimaler}f} | {faktura:>12.{desimaler}f} "
        f"| {tegn}{diff:>8.{desimaler}f} | {status:<6} |"
    )
    return True if delvis else ok


def print_datahull(hours: list[dict[str, Any]], f: dict[str, Any], beregnet: dict[str, float],
                   shift_seconds: int) -> None:
    """Restanalyse når fixturen har timer uten måling.

    Volumlinjene kan ikke sammenlignes direkte, men fakturaen minus det vi
    faktisk har målt gir et restforbruk og en implisitt Norgespris-sats for
    hullet. Ligger restsatsen innenfor spennet av faktiske timepriser i hullet,
    er fakturaen konsistent med modellen vår også der vi mangler data.
    """
    manglende = [h for h, k in zip(hours, shift_korriger(hours, shift_seconds), strict=True) if k is None]
    dag_timer = sum(1 for h in manglende if er_dagtid(datetime.fromisoformat(h["start_local"])))

    print(f"\nDatahull: {len(manglende)} av {len(hours)} timer mangler måling "
          f"({manglende[0]['start_local']} - {manglende[-1]['start_local']}), "
          f"{dag_timer} dag-timer og {len(manglende) - dag_timer} natt/helg-timer.")
    print("Volumlinjene over dekker bare de målte timene og er derfor merket DELVIS.\n")

    rest_total = f["forbruk_total_kwh"] - beregnet["total_kwh"]
    rest_dag = f["forbruk_dag_kwh"] - beregnet["forbruk_dag_kwh"]
    rest_natt = f["forbruk_natt_kwh"] - beregnet["forbruk_natt_kwh"]
    print(f"Restforbruk fakturaen tilskriver hullet: {rest_total:.3f} kWh "
          f"({rest_dag:.3f} dag, {rest_natt:.3f} natt/helg)")
    if dag_timer:
        print(f"  snitt dag: {rest_dag / dag_timer:.3f} kWh/h over {dag_timer} timer")
    if len(manglende) - dag_timer:
        print(f"  snitt natt/helg: {rest_natt / (len(manglende) - dag_timer):.3f} kWh/h "
              f"over {len(manglende) - dag_timer} timer")

    rest_np = f["forventet_norgespris_kr"] - beregnet["norgespris_kr"]
    if abs(rest_total) > 1e-6:
        implisitt = rest_np / rest_total * 100
        satser = [
            (NORGESPRIS_INKL_MVA - float(h["spot_nok_kwh_eks_mva"]) * MVA_SATS) * 100
            for h in manglende
        ]
        print(f"Implisitt Norgespris-sats for hullet: {implisitt:.3f} øre/kWh "
              f"({rest_np:.2f} kr / {rest_total:.3f} kWh)")
        print(f"  faktiske timesatser i hullet: {min(satser):.3f} til {max(satser):.3f} øre/kWh, "
              f"uvektet snitt {sum(satser) / len(satser):.3f}")
        innenfor = min(satser) <= implisitt <= max(satser)
        print(f"  {'innenfor' if innenfor else 'UTENFOR'} spennet -> fakturaen er "
              f"{'konsistent' if innenfor else 'IKKE konsistent'} med modellen i hullet")


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

    hull = int(beregnet["manglende_timer"]) > 0

    print(f"=== BKK {args.faktura} verifikasjon (shift={args.shift_seconds}s) ===\n")
    print(f"Antall timer: {len(hours)} "
          f"({int(beregnet['dekkede_timer'])} med måling, {int(beregnet['manglende_timer'])} uten)")
    print(f"Kapasitet: snitt topp 3 = {beregnet['kapasitet_snitt_kw']:.3f} kW "
          f"-> trinn {beregnet['kapasitet_grense_kw']} kW, "
          f"{int(beregnet['kapasitet_kr'])} kr\n")
    print(f"| {'Linje':<28} | {'Beregnet':>12} | {'Faktura':>12} | {'Avvik':>9} | Status |")
    print(f"|{'-' * 30}|{'-' * 14}|{'-' * 14}|{'-' * 10}|{'-' * 8}|")

    ok = True
    ok &= print_rad("Total kWh", beregnet["total_kwh"], f["forbruk_total_kwh"], "kWh", hull)
    ok &= print_rad("Forbruk dag kWh", beregnet["forbruk_dag_kwh"], f["forbruk_dag_kwh"], "kWh", hull)
    ok &= print_rad("Forbruk natt kWh", beregnet["forbruk_natt_kwh"], f["forbruk_natt_kwh"], "kWh", hull)
    ok &= print_rad("Energiledd dag", beregnet["energiledd_dag_kr"], f["forventet_energiledd_dag_kr"], "kr", hull)
    ok &= print_rad("Energiledd natt", beregnet["energiledd_natt_kr"], f["forventet_energiledd_natt_kr"], "kr", hull)
    ok &= print_rad("Forbruksavgift", beregnet["forbruksavgift_kr"], f["forventet_forbruksavgift_kr"], "kr", hull)
    ok &= print_rad("Enovaavgift", beregnet["enovaavgift_kr"], f["forventet_enovaavgift_kr"], "kr", hull)
    ok &= print_rad("Kapasitet", beregnet["kapasitet_kr"], f["forventet_kapasitet_kr"])
    ok &= print_rad("Nettleie sum", beregnet["nettleie_kr"], f["forventet_nettleie_kr"], "kr", hull)
    ok &= print_rad("Norgespris-komp", beregnet["norgespris_kr"], f["forventet_norgespris_kr"], "kr", hull)
    ok &= print_rad("Total inkl. Norgespris", beregnet["total_kr"], f["forventet_total_kr"], "kr", hull)

    print()
    if not ok:
        print("Avvik utenfor toleranse")
    elif hull:
        print("Sammenlignbare linjer innenfor toleranse; volumlinjene er ikke sammenlignbare")
    else:
        print("Alt innenfor toleranse")
    if hull:
        print_datahull(hours, f, beregnet, args.shift_seconds)
    print_norgespris_eksakt(args.faktura, args.shift_seconds)
    return 0 if ok else 1


def print_norgespris_eksakt(faktura_navn: str, shift_seconds: int) -> None:
    """Informativ tilleggssjekk: Norgespris mot Nord Pools publiserte Final-priser.

    HA-recorderen kan ha en annen prisårgang enn BKK fakturerer fra (foreløpig
    vs Final valutakurs på dager der FX-markedet var stengt). Med publiserte
    priser skal linjen treffe fakturaen tilnærmet eksakt; juni 2026 traff på
    øret. Se docs/research/norgespris-eksakt-match.md. Krever de private
    prisarkivene (`just snapshot-kurs`); hopper stille over hvis de mangler.
    """
    try:
        import verify_norgespris_eksakt as vne
        res = vne.analyser_maaned(faktura_navn, shift_seconds)
    except Exception as e:  # aldri la tilleggssjekken velte hovedverifiseringen
        print(f"\n(Norgespris eksakt-sjekk hoppet over: {type(e).__name__}: {e})")
        return
    if res is None:
        print("\n(Norgespris eksakt-sjekk hoppet over: mangler prisarkiv for måneden, "
              "kjør `just snapshot-kurs`)")
        return
    if res["manglende_timer"]:
        print(f"\nNorgespris mot publiserte Final-priser: {res['komp_np']:+.2f} kr over de "
              f"{res['n_timer']} målte timene. Ikke sammenlignbar med fakturalinjen "
              f"({res['faktura']:+.2f} kr) så lenge {res['manglende_timer']} timer mangler måling.")
        return
    avvik = res["komp_np"] - res["faktura"]
    print(f"\nNorgespris mot publiserte Final-priser: {res['komp_np']:+.2f} kr, "
          f"faktura {res['faktura']:+.2f}, avvik {avvik:+.2f} kr")
    print("  (forventet |avvik| <= 0.05 kr; større avvik tyder på prisårgang- eller "
          "kWh-avvik, se docs/research/norgespris-eksakt-match.md)")


if __name__ == "__main__":
    sys.exit(main())
