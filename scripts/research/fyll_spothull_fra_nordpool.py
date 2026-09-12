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

Randtimen i starten av et hull fylles også. Når Nord Pool-sensoren faller ut
presis ved døgnskiftet, går den `unknown` kl. 00:00:00 og `unavailable` noen
sekunder senere. HAs statistikk-kompilator regner timesnittet bare over
numeriske states, så staten fra 23:45-kvarteret kvelden før blir båret gjennom
hele time 00. Recorderen har da en verdi for timen, men det er ikke en måling
av timen. Slike timer kjennes igjen automatisk: time 00 rett før et hull, der
recorder-verdien ligger innenfor 0,5 øre/kWh av forrige døgns 23:45-kvarter.
De fylles fra arkivet og merkes som de andre, med begrunnelsen arkivert i
fixturens metadata.

Andre timer der recorderen har en verdi overstyres aldri automatisk. Faller
sensoren ut midt i en time, lagrer recorderen et snitt av bare den delen av
timen den rakk å måle. Slike tilfeller overstyres eksplisitt med --overstyr og
en begrunnelse, som også arkiveres i metadata.

Bruk:
    python3 scripts/research/fyll_spothull_fra_nordpool.py \
        --fixture tests/fixtures/bkk_august_2026_hourly.json \
        --overstyr "2026-08-23T12:00:00+02:00=sensoren falt ut midt i timen; recorder-snittet dekker bare deler av den"
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
NOK_ARKIV = ROOT / "_private" / "Måleverdier" / "nordpool_nok_kvarter_no5.json"

# Hvor nær forrige døgns 23:45-kvarter en time 00 må ligge for å regnes som
# randtime. 0,5 øre/kWh dekker kurs-årgangen mellom recorderens publiseringskurs
# og arkivets, som er noen tideler av en øre.
RANDTIME_TOLERANSE_NOK = 0.005
RANDTIME_BEGRUNNELSE = "randtime_forrige_kvarter"
FYLT_MERKE = "nordpool_publisert"


def les_arkiv(sti: Path) -> tuple[dict[str, float], dict[str, float]]:
    """(timespriser, kvarterpriser) i NOK/kWh eks. mva, nøklet på lokal ISO.

    Timespriser tas bare med når alle fire kvarter finnes; ellers er arkivet
    ufullstendig for timen.
    """
    kvarter: dict[str, float] = {}
    bucket: dict[str, list[float]] = {}
    for dag in json.loads(sti.read_text(encoding="utf-8"))["daily"]:
        for kv in dag["kvarter"]:
            kvarter[kv["start_local"]] = kv["nok_mwh"] / 1000.0
            time_iso = kv["start_local"][:14] + "00:00" + kv["start_local"][19:]
            bucket.setdefault(time_iso, []).append(kv["nok_mwh"])
    timer = {iso: sum(q) / len(q) / 1000.0 for iso, q in bucket.items() if len(q) == 4}
    return timer, kvarter


def er_hull(time: dict[str, object]) -> bool:
    """Timen mangler recorder-måling, enten fortsatt tom eller alt fylt herfra."""
    return time["spot_nok_kwh_eks_mva"] is None or time.get("spot_kilde") == FYLT_MERKE


def forrige_kvarter_iso(ts: str) -> str:
    """Lokal ISO for kvarteret som starter 15 minutter før en timestart."""
    return (datetime.fromisoformat(ts) - timedelta(minutes=15)).isoformat()


def finn_randtimer(
    hours: list[dict[str, object]], kvarter: dict[str, float]
) -> dict[str, float]:
    """Time 00 rett før et hull, der recorder-verdien er forrige døgns 23:45.

    Sensoren går `unknown` presis 00:00:00 og `unavailable` få sekunder senere.
    HAs statistikk-kompilator snitter bare over numeriske states, så staten fra
    23:45-kvarteret bæres gjennom hele time 00. Verdien er da ikke en måling av
    timen, og timen hører til hullet.
    """
    treff: dict[str, float] = {}
    for i, h in enumerate(hours[:-1]):
        ts = str(h["start_local"])
        verdi = h["spot_nok_kwh_eks_mva"]
        if verdi is None or ts[11:13] != "00" or not er_hull(hours[i + 1]):
            continue
        if h.get("spot_kilde") == FYLT_MERKE:
            # Alt fylt i en tidligere kjøring; verdien er arkivets, ikke
            # recorderens, så regelen kan ikke prøves på nytt.
            continue
        forrige = kvarter.get(forrige_kvarter_iso(ts))
        if forrige is None or abs(float(verdi) - forrige) > RANDTIME_TOLERANSE_NOK:
            continue
        treff[ts] = forrige
    return treff


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
    hours = fixture["hours"]
    priser, kvarter = les_arkiv(args.arkiv)

    overstyringer: dict[str, str] = {}
    for spec in args.overstyr:
        time, _, begrunnelse = spec.partition("=")
        if not begrunnelse:
            print(f"--overstyr {time!r} mangler begrunnelse (TIME=BEGRUNNELSE)")
            return 1
        overstyringer[time] = begrunnelse

    # Randtimene finnes før hullene fylles: etterpå ser en fylt time 00 ut som
    # en hvilken som helst arkivpris. Tidligere kjøringers randtimer beholdes så
    # scriptet kan kjøres om igjen uten å miste begrunnelsen.
    nye_rand = finn_randtimer(hours, kvarter)
    tidligere = (
        fixture["metadata"].get("spothull", {}).get("fylt_fra_nordpool", {}).get("randtimer", {})
    )
    fortsatt_merket = {
        str(h["start_local"]) for h in hours if h.get("spot_kilde") == FYLT_MERKE
    }
    randtimer: dict[str, dict[str, float | str]] = {
        ts: data for ts, data in tidligere.items() if ts in fortsatt_merket
    }

    fylte: list[str] = []
    overstyrte: dict[str, dict[str, float | str]] = {}
    for h in hours:
        ts = str(h["start_local"])
        if h["spot_nok_kwh_eks_mva"] is None:
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke fylle hullet komplett")
                return 1
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = FYLT_MERKE
            fylte.append(ts)
        elif ts in nye_rand:
            if ts not in priser:
                print(f"Prisarkivet mangler {ts}; kan ikke fylle randtimen")
                return 1
            randtimer[ts] = {
                "recorder_nok_kwh": h["spot_nok_kwh_eks_mva"],
                "forrige_kvarter_nok_kwh": round(nye_rand[ts], 6),
                "publisert_nok_kwh": round(priser[ts], 6),
                "begrunnelse": RANDTIME_BEGRUNNELSE,
            }
            h["spot_nok_kwh_eks_mva"] = round(priser[ts], 6)
            h["spot_kilde"] = FYLT_MERKE
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
            h["spot_kilde"] = FYLT_MERKE

    ubrukte = set(overstyringer) - set(overstyrte)
    if ubrukte:
        print(f"--overstyr traff ingen målt time: {sorted(ubrukte)}")
        return 1

    merkede = sum(1 for h in hours if h.get("spot_kilde") == FYLT_MERKE)
    spothull = fixture["metadata"].get("spothull", {})
    spothull["fylt_fra_nordpool"] = {
        "kilde": args.arkiv.name,
        "dato": date.today().isoformat(),
        "fylte_timer": merkede,
        "avregning": "snitt av fire publiserte Final-kvarterpriser",
        "randtimer": dict(sorted(randtimer.items())),
        "overstyrte_timer": overstyrte,
    }
    fixture["metadata"]["spothull"] = spothull

    args.fixture.write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"Fylte {len(fylte)} timer (herav {len(nye_rand)} randtimer) og "
        f"overstyrte {len(overstyrte)} fra {args.arkiv.name}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
