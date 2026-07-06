"""Verifiser Norgespris-linjen mot Nord Pools publiserte Final-priser.

Sammenligner tre tall per måned: Norgespris-kompensasjon beregnet med
HA-recorderens lagrede spotpriser, samme beregning med Nord Pools publiserte
Final-kvarterpriser, og fakturaens linje. Funn (juni 2026): med publiserte
priser reproduseres fakturalinjen eksakt. Avviket i den recorder-baserte
beregningen skyldes prisårgang: HA lagrer prisene slik de så ut ved
publisering, og på dager der FX-markedet var stengt på auksjonsdagen
(søndager, enkelte helligdager) er valutakursen foreløpig og korrigeres
senere til Final. Full bakgrunn: docs/research/norgespris-eksakt-match.md.

Priskilder, i prioritert rekkefølge per time:

1. _private/Måleverdier/nordpool_nok_kvarter_no5.json (publiserte
   Final-kvarterpriser, `just snapshot-kurs`). Timesavregning = snitt av 4 kvarter.
2. tests/fixtures/nordpool_eur_no5_2026.json x _private exchangeRate-arkivet
   (for dager som har falt ut av gratis-vinduet, f.eks. 1.-4. mai 2026).

kWh-kilder: HAN-fixturen (alltid), pluss Elhub-CSV når
_private/Måleverdier/elhub_<måned>.csv finnes. Elhub er fakturagrunnlaget
BKK leser, så Elhub x Final er den skarpeste sjekken: mai og juni 2026
traff fakturaen innenfor 0,005 kr. HAN-serien kan ha enkelttimer der
recorder-aggregatet byttet delta mellom nabotimer (mai 2026: 0,35 kr på
2. pinsedag), så den får romsligere forventning.

Måneder uten full prisdekning hoppes over. Kjøres uten nett.

    python3 scripts/research/verify_norgespris_eksakt.py
    python3 scripts/research/verify_norgespris_eksakt.py --emit-markdown
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_invoice_hourly as vih

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
NOK_ARKIV: Final[Path] = ROOT / "_private" / "Måleverdier" / "nordpool_nok_kvarter_no5.json"
EXR_ARKIV: Final[Path] = ROOT / "_private" / "Måleverdier" / "nordpool_exchangerate_no5.json"
EUR_FIXTURE: Final[Path] = ROOT / "tests" / "fixtures" / "nordpool_eur_no5_2026.json"
FIXTURES: Final[Path] = ROOT / "tests" / "fixtures"
GENERATED: Final[Path] = ROOT / "docs" / "research" / "_generated" / "verify_norgespris_eksakt.md"

MND_NR: Final[dict[str, int]] = {
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
}
UKEDAG: Final[list[str]] = ["man", "tir", "ons", "tor", "fre", "lør", "søn"]


def last_np_timespriser() -> dict[str, float]:
    """{time-start lokal ISO: NOK/kWh eks. mva} fra kvarterarkivet (snitt av 4 kvarter)."""
    if not NOK_ARKIV.exists():
        return {}
    out: dict[str, float] = {}
    for dag in json.loads(NOK_ARKIV.read_text(encoding="utf-8"))["daily"]:
        bucket: dict[str, list[float]] = {}
        for kv in dag["kvarter"]:
            time_iso = kv["start_local"][:14] + "00:00" + kv["start_local"][19:]
            bucket.setdefault(time_iso, []).append(kv["nok_mwh"])
        for iso, kvarter in bucket.items():
            out[iso] = sum(kvarter) / len(kvarter) / 1000.0
    return out


def last_fallback_priser() -> dict[str, float]:
    """EUR-fixture x exchangeRate-arkiv, for dager utenfor gratis-vinduet."""
    if not (EUR_FIXTURE.exists() and EXR_ARKIV.exists()):
        return {}
    exr = {e["date"]: e["rate"] for e in json.loads(EXR_ARKIV.read_text(encoding="utf-8"))["daily"]}
    out: dict[str, float] = {}
    for e in json.loads(EUR_FIXTURE.read_text(encoding="utf-8"))["hourly"]:
        rate = exr.get(e["start_local"][:10])
        if rate is not None:
            out[e["start_local"]] = e["eur_mwh"] * rate / 1000.0
    return out


def publiserte_priser(hours: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, int]] | None:
    """Publisert Final-pris for hver fixture-time, eller None ved hull."""
    np_pris = last_np_timespriser()
    fallback = last_fallback_priser()
    priser: dict[str, float] = {}
    kilder = {"arkiv": 0, "fallback": 0}
    for h in hours:
        iso = h["start_local"]
        if iso in np_pris:
            priser[iso] = np_pris[iso]
            kilder["arkiv"] += 1
        elif iso in fallback:
            priser[iso] = fallback[iso]
            kilder["fallback"] += 1
        else:
            return None
    return priser, kilder


def last_elhub(navn: str) -> dict[str, float] | None:
    """{time-start ISO: kWh} fra Elhub-CSV, eller None hvis fila mangler.

    Ser etter elhub_<måned>_<år>.csv og elhub_<måned>.csv under både
    _private/Måleverdier/ og Måleverdier/ (tracked demo-kopier).
    """
    maaned, aar = navn.split("_")
    kandidater = [
        ROOT / "_private" / "Måleverdier" / f"elhub_{maaned}_{aar}.csv",
        ROOT / "_private" / "Måleverdier" / f"elhub_{maaned}.csv",
        ROOT / "Måleverdier" / f"elhub_{maaned}_{aar}.csv",
        ROOT / "Måleverdier" / f"elhub_{maaned}.csv",
    ]
    for p in kandidater:
        if not p.exists():
            continue
        out: dict[str, float] = {}
        with p.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f, delimiter=";"):
                out[row["Fra"]] = float(row["Volum"].replace(",", "."))
        return out
    return None


def skiftede_kwh(hours: list[dict[str, Any]], shift_seconds: int) -> list[float]:
    """Samme 13-sekunders teleskop-korreksjon som verify_invoice_hourly.beregn()."""
    ut: list[float] = []
    for i, h in enumerate(hours):
        kwh = float(h["kwh"])
        if shift_seconds and i > 0:
            kwh -= shift_seconds / 3600 * (kwh - float(hours[i - 1]["kwh"]))
        ut.append(kwh)
    return ut


def komp_sum(kwhs: list[float], priser: list[float]) -> float:
    """Norgespris-kompensasjon: sum av (0,50 - spot inkl. mva) x kWh. Negativ = tilgode."""
    return sum(
        (vih.NORGESPRIS_INKL_MVA - p * vih.MVA_SATS) * kwh
        for kwh, p in zip(kwhs, priser, strict=True)
    )


def analyser_maaned(navn: str, shift_seconds: int) -> dict[str, Any] | None:
    fixture_fil = FIXTURES / f"bkk_{navn}_hourly.json"
    if not fixture_fil.exists():
        return None
    hours = json.loads(fixture_fil.read_text(encoding="utf-8"))["hours"]
    dekning = publiserte_priser(hours)
    if dekning is None:
        return None
    np_priser, kilder = dekning

    kwhs = skiftede_kwh(hours, shift_seconds)
    ha = [float(h["spot_nok_kwh_eks_mva"]) for h in hours]
    np_ = [np_priser[h["start_local"]] for h in hours]

    # Prisfidelitet HA-recorder mot publisert
    diffs = [(a - b) for a, b in zip(ha, np_, strict=True)]
    bitlike = sum(1 for d in diffs if abs(d) < 5e-7)
    naere = sum(1 for d in diffs if abs(d) < 1e-4)

    # Prisårgang: hele dager der HA avviker med tilnærmet konstant faktor
    per_dag: dict[str, list[tuple[float, float]]] = {}
    for h, a, b in zip(hours, ha, np_, strict=True):
        if abs(a - b) > 1e-4:
            per_dag.setdefault(h["start_local"][:10], []).append((a, b))
    aargang = []
    for dag, par in sorted(per_dag.items()):
        if len(par) < 20:
            continue
        ratioer = [a / b for a, b in par if b > 0.01]
        if not ratioer:
            continue
        snitt = sum(ratioer) / len(ratioer)
        konstant = max(ratioer) - min(ratioer) < 5e-4
        aargang.append({
            "dag": dag,
            "ukedag": UKEDAG[datetime.fromisoformat(dag).weekday()],
            "ratio": snitt,
            "konstant": konstant,
            "timer": len(par),
        })

    # Symmetri: timer der spot inkl. mva < 50 øre (kunden betaler mellomlegg)
    betaletimer = sum(1 for p in np_ if vih.NORGESPRIS_INKL_MVA - p * vih.MVA_SATS > 0)
    clamp = sum(
        (vih.NORGESPRIS_INKL_MVA - p * vih.MVA_SATS) * kwh
        for kwh, p in zip(kwhs, np_, strict=True)
        if vih.NORGESPRIS_INKL_MVA - p * vih.MVA_SATS <= 0
    )

    # Elhub-kWh x Final: skarpeste sjekk, når CSV-en finnes og dekker måneden
    komp_elhub = None
    elhub = last_elhub(navn)
    if elhub is not None and all(h["start_local"] in elhub for h in hours):
        komp_elhub = komp_sum([elhub[h["start_local"]] for h in hours], np_)

    faktura = vih.FAKTURAER[navn]["forventet_norgespris_kr"]
    return {
        "navn": navn,
        "faktura": faktura,
        "komp_ha": komp_sum(kwhs, ha),
        "komp_np": komp_sum(kwhs, np_),
        "komp_elhub": komp_elhub,
        "n_timer": len(hours),
        "kilder": kilder,
        "bitlike": bitlike,
        "naere": naere,
        "aargang": aargang,
        "betaletimer": betaletimer,
        "clamp_avvik": clamp - komp_sum(kwhs, np_),
    }


def print_konsoll(res: dict[str, Any]) -> None:
    print(f"=== {res['navn']}: Norgespris mot publiserte Final-priser ===")
    print(f"  priskilde: {res['kilder']['arkiv']} timer NOK-arkiv, "
          f"{res['kilder']['fallback']} timer EUR x EXR-fallback")
    print(f"  prisfidelitet HA vs publisert: {res['bitlike']}/{res['n_timer']} bit-like, "
          f"{res['naere']}/{res['n_timer']} innenfor 0,01 øre/kWh")
    if res["aargang"]:
        print("  prisårgang (hele dager der HA-prisen er en annen kurs-årgang):")
        for a in res["aargang"]:
            merke = "konstant faktor" if a["konstant"] else "varierende"
            print(f"    {a['dag']} {a['ukedag']}: HA/publisert = {a['ratio']:.5f} ({merke}, {a['timer']} timer)")
    print(f"  symmetri: {res['betaletimer']} timer med spot < 50 øre inkl. mva; "
          f"å klippe dem ville flyttet summen {res['clamp_avvik']:+.2f} kr")
    rader = [("HAN-kWh x HA-recorder ", res["komp_ha"]), ("HAN-kWh x Final       ", res["komp_np"])]
    if res["komp_elhub"] is not None:
        rader.append(("Elhub-kWh x Final     ", res["komp_elhub"]))
    for kilde, verdi in rader:
        print(f"  Norgespris, {kilde}: {verdi:+10.2f} kr, faktura {res['faktura']:+.2f}, "
              f"avvik {verdi - res['faktura']:+.3f}")
    if res["komp_elhub"] is None:
        print("  (ingen Elhub-CSV for måneden; last ned fra elhub.no for skarpeste sjekk)")
    print()


def emit_markdown(resultater: list[dict[str, Any]]) -> str:
    linjer = [
        "_Generert av_ `scripts/research/verify_norgespris_eksakt.py --emit-markdown` "
        "(krever de private prisarkivene, se `just snapshot-kurs`).",
        "",
        "| Måned | Faktura (kr) | HAN x HA-recorder | Avvik | HAN x Final | Avvik | Elhub x Final | Avvik |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in resultater:
        if r["komp_elhub"] is not None:
            elhub_celler = f"{r['komp_elhub']:+.2f} | {r['komp_elhub'] - r['faktura']:+.3f}"
        else:
            elhub_celler = "(mangler CSV) | "
        linjer.append(
            f"| {r['navn']} | {r['faktura']:+.2f} | {r['komp_ha']:+.2f} | "
            f"{r['komp_ha'] - r['faktura']:+.2f} | {r['komp_np']:+.2f} | "
            f"{r['komp_np'] - r['faktura']:+.2f} | {elhub_celler} |"
        )
    linjer += [
        "",
        "Prisårgang-dager (HA-recorderen har foreløpig kurs, publisert er Final):",
        "",
        "| Dag | Ukedag | HA/publisert | Timer |",
        "| --- | --- | ---: | ---: |",
    ]
    for r in resultater:
        for a in r["aargang"]:
            merke = "" if a["konstant"] else " (varierende)"
            linjer.append(f"| {a['dag']} | {a['ukedag']} | {a['ratio']:.5f}{merke} | {a['timer']} |")
    linjer += [
        "",
        "Symmetri: "
        + "; ".join(
            f"{r['navn']} har {r['betaletimer']} timer med spot under 50 øre inkl. mva "
            f"(å klippe dem ville flyttet summen {r['clamp_avvik']:+.2f} kr)"
            for r in resultater
        )
        + ". BKK fakturerer symmetrisk.",
    ]
    return "\n".join(linjer) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--faktura", choices=sorted(vih.FAKTURAER.keys()),
                   help="Kjør kun én måned (default: alle med prisdekning)")
    p.add_argument("--shift-seconds", type=int, default=13)
    p.add_argument("--emit-markdown", action="store_true",
                   help=f"Skriv {GENERATED.relative_to(ROOT)} for inject_generated.py")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    navn = [args.faktura] if args.faktura else sorted(
        vih.FAKTURAER, key=lambda n: (int(n.split("_")[1]), MND_NR[n.split("_")[0]])
    )
    resultater = []
    for n in navn:
        res = analyser_maaned(n, args.shift_seconds)
        if res is None:
            print(f"({n}: hoppet over, mangler fixture eller full prisdekning)")
            continue
        resultater.append(res)
        print_konsoll(res)

    if not resultater:
        print("Ingen måneder med full prisdekning. Kjør `just snapshot-kurs` først.", file=sys.stderr)
        return 1

    if args.emit_markdown:
        GENERATED.parent.mkdir(parents=True, exist_ok=True)
        GENERATED.write_text(emit_markdown(resultater), encoding="utf-8")
        print(f"Skrev {GENERATED.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
