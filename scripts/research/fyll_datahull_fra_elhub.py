#!/usr/bin/env python3
"""Fyll HAN-datahull i en hourly-fixture med Elhub-kWh.

Timer der `kwh` er null fylles fra Elhub-CSV-en (fakturagrunnlaget BKK leser),
og merkes med `"kwh_kilde": "elhub"` slik at scripts som bryr seg om
proveniens (verify_norgespris_eksakt.py) kan holde dem utenfor HAN-summene.
`p_max_w` forblir null; Elhub har ikke effektdata.

Timer der HAN har målt en verdi overstyres aldri automatisk. Er en målt verdi
beviselig gal (som 29.07.2026 kl. 10: HAN målte 0,0 kWh med p_max 4623 W fordi
tpi-måleren frøs midt i timen), overstyres den eksplisitt med --overstyr og en
begrunnelse, som arkiveres i fixturens metadata.

Bruk:
    python3 scripts/research/fyll_datahull_fra_elhub.py \
        --fixture tests/fixtures/bkk_juli_2026_hourly.json \
        --elhub "_private/Måleverdier/elhub_juli.csv" \
        --overstyr "2026-07-29T10:00:00+02:00=HAN målte 0,0 kWh med p_max 4623 W; tpi frøs i denne timen"
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path


def les_elhub(sti: Path) -> dict[str, float]:
    ut: dict[str, float] = {}
    with sti.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f, delimiter=";"):
            ut[row["Fra"]] = float(row["Volum"].replace(",", "."))
    return ut


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--elhub", required=True, type=Path)
    parser.add_argument(
        "--overstyr",
        action="append",
        default=[],
        metavar="TIME=BEGRUNNELSE",
        help="Overstyr en HAN-målt time med Elhub-verdien. Krever begrunnelse.",
    )
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    elhub = les_elhub(args.elhub)

    overstyringer: dict[str, str] = {}
    for spec in args.overstyr:
        time, _, begrunnelse = spec.partition("=")
        if not begrunnelse:
            print(f"--overstyr {time!r} mangler begrunnelse (TIME=BEGRUNNELSE)")
            return 1
        overstyringer[time] = begrunnelse

    fylte: list[str] = []
    overstyrte: dict[str, dict[str, float | str]] = {}
    for h in fixture["hours"]:
        ts = h["start_local"]
        if h["kwh"] is None:
            if ts not in elhub:
                print(f"Elhub-CSV-en mangler {ts}; kan ikke fylle hullet komplett")
                return 1
            h["kwh"] = elhub[ts]
            h["kwh_kilde"] = "elhub"
            fylte.append(ts)
        elif ts in overstyringer:
            overstyrte[ts] = {
                "han_kwh": h["kwh"],
                "elhub_kwh": elhub[ts],
                "begrunnelse": overstyringer[ts],
            }
            h["kwh"] = elhub[ts]
            h["kwh_kilde"] = "elhub"

    ubrukte = set(overstyringer) - set(overstyrte)
    if ubrukte:
        print(f"--overstyr traff ingen målt time: {sorted(ubrukte)}")
        return 1

    datahull = fixture["metadata"].get("datahull", {})
    datahull.pop("ikke_fylt_fordi", None)
    datahull.pop("loses_ved", None)
    datahull["fylt_fra_elhub"] = {
        "kilde": args.elhub.name,
        "dato": date.today().isoformat(),
        "fylte_timer": len(fylte),
        "p_max_w": "forblir null for de fylte timene; Elhub har ikke effektdata",
        "overstyrte_timer": overstyrte,
    }
    fixture["metadata"]["datahull"] = datahull

    args.fixture.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"Fylte {len(fylte)} timer og overstyrte {len(overstyrte)} fra {args.elhub.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
