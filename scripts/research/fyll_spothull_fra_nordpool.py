#!/usr/bin/env python3
"""Fyll spotpris-hull i en hourly-fixture med Nord Pools publiserte Final-priser.

Timer der `spot_nok_kwh_eks_mva` er null fylles fra kvarterarkivet
(`_private/Måleverdier/nordpool_nok_kvarter_no5.json`, oppdatert med
`just snapshot-kurs`), og merkes med `"spot_kilde": "nordpool_publisert"`.
Merkingen finnes fordi verify_norgespris_eksakt.py måler hvor godt
HA-recorderens lagrede priser stemmer med de publiserte: fylte timer må
holdes utenfor den sammenligningen, ellers måler den seg selv.

Timesprisen er snittet av de fire kvarterprisene, samme avregning som
verify_norgespris_eksakt.py bruker. Timer uten fire kvarter i arkivet fylles
ikke; da er arkivet ufullstendig og bør snapshottes på nytt.

Timer der recorderen har en verdi overstyres aldri automatisk. Når
Nord Pool-sensoren faller ut midt i en time, lagrer recorderen et snitt av
bare den delen av timen den rakk å måle. Slike randtimer overstyres eksplisitt
med --overstyr og en begrunnelse, som arkiveres i fixturens metadata.

Bruk:
    python3 scripts/research/fyll_spothull_fra_nordpool.py \
        --fixture tests/fixtures/bkk_august_2026_hourly.json \
        --overstyr "2026-08-23T00:00:00+02:00=sensoren falt ut i denne timen; recorder-snittet dekker bare deler av den"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NOK_ARKIV = ROOT / "_private" / "Måleverdier" / "nordpool_nok_kvarter_no5.json"


def les_timespriser(sti: Path) -> dict[str, float]:
    """{time-start lokal ISO: NOK/kWh eks. mva}, kun timer med fire kvarter."""
    bucket: dict[str, list[float]] = {}
    for dag in json.loads(sti.read_text(encoding="utf-8"))["daily"]:
        for kv in dag["kvarter"]:
            time_iso = kv["start_local"][:14] + "00:00" + kv["start_local"][19:]
            bucket.setdefault(time_iso, []).append(kv["nok_mwh"])
    return {iso: sum(q) / len(q) / 1000.0 for iso, q in bucket.items() if len(q) == 4}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument("--arkiv", type=Path, default=NOK_ARKIV)
    parser.add_argument(
        "--overstyr",
        action="append",
        default=[],
        metavar="TIME=BEGRUNNELSE",
        help="Overstyr en recorder-målt time med den publiserte prisen. Krever begrunnelse.",
    )
    args = parser.parse_args()

    if not args.arkiv.exists():
        print(f"Finner ikke prisarkivet {args.arkiv}; kjør `just snapshot-kurs` først")
        return 1

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    priser = les_timespriser(args.arkiv)

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
        if h["spot_nok_kwh_eks_mva"] is None:
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke fylle hullet komplett")
                return 1
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = "nordpool_publisert"
            fylte.append(ts)
        elif ts in overstyringer:
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke overstyre timen")
                return 1
            overstyrte[ts] = {
                "recorder_nok_kwh": h["spot_nok_kwh_eks_mva"],
                "publisert_nok_kwh": round(priser[ts], 6),
                "begrunnelse": overstyringer[ts],
            }
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = "nordpool_publisert"

    ubrukte = set(overstyringer) - set(overstyrte)
    if ubrukte:
        print(f"--overstyr traff ingen målt time: {sorted(ubrukte)}")
        return 1

    spothull = fixture["metadata"].get("spothull", {})
    spothull["fylt_fra_nordpool"] = {
        "kilde": args.arkiv.name,
        "dato": date.today().isoformat(),
        "fylte_timer": len(fylte),
        "avregning": "snitt av fire publiserte Final-kvarterpriser",
        "overstyrte_timer": overstyrte,
    }
    fixture["metadata"]["spothull"] = spothull

    args.fixture.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"Fylte {len(fylte)} timer og overstyrte {len(overstyrte)} fra {args.arkiv.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
