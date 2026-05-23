"""Lagre time-for-time Nord Pool EUR/MWh-priser som snapshot-fixture.

Hvorfor: dataportal-api.nordpoolgroup.com låser eldre data bak innlogging
(kun siste ~30 dager er åpne). For å kunne reverifisere gamle fakturaer uten
internett-tilgang lagrer vi rådata lokalt.

Datakilde: hvakosterstrommen.no sin offentlige API. Den henter rådata fra
Nord Pool og republiserer EUR_per_kWh (= EUR/MWh / 1000) og NOK_per_kWh.
Vi bruker kun EUR_per_kWh herfra siden NOK-konverteringen deres er
forward-filled (samme kurs over flere dager) og ikke matcher BKKs same-day
ECB-kurs. NB EUR/NOK lagres separat i snapshot_nb_eur_nok.py.

Format på utfil tests/fixtures/nordpool_eur_<område>_<år>.json:

    {
      "metadata": {
        "source": "hvakosterstrommen.no (mirror av Nord Pool)",
        "area": "NO5",
        "currency": "EUR",
        "fetched_at": "2026-05-23T...",
        "period": "2026-01-01 til 2026-05-31"
      },
      "hourly": [
        {"start_local": "2026-01-01T00:00:00+01:00", "eur_mwh": 50.23},
        ...
      ]
    }

Kjøres uten avhengigheter utover Python 3 standardbibliotek:

    python3 scripts/research/snapshot_nordpool_eur.py \\
        --start 2026-01-01 --end 2026-05-31 --area NO5 \\
        --output tests/fixtures/nordpool_eur_no5_2026.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

HKS_URL = "https://www.hvakosterstrommen.no/api/v1/prices/{year}/{month:02d}-{day:02d}_{area}.json"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", required=True, help="Startdato YYYY-MM-DD (inkl)")
    p.add_argument("--end", required=True, help="Sluttdato YYYY-MM-DD (inkl)")
    p.add_argument("--area", default="NO5", help="Prisområde (NO1-NO5)")
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--delay", type=float, default=0.25, help="Sekunder mellom kall")
    return p.parse_args()


def fetch_day(d: date, area: str) -> list[dict]:
    url = HKS_URL.format(year=d.year, month=d.month, day=d.day, area=area)
    req = urllib.request.Request(url, headers={"User-Agent": "snapshot_nordpool_eur/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def daterange(start: date, end: date):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    hourly: list[dict] = []
    days_fetched = 0
    days_failed: list[str] = []

    for d in daterange(start, end):
        try:
            entries = fetch_day(d, args.area)
        except Exception as e:
            print(f"  {d} feilet: {e}", file=sys.stderr)
            days_failed.append(d.isoformat())
            continue
        for entry in entries:
            eur_mwh = round(entry["EUR_per_kWh"] * 1000, 4)
            hourly.append(
                {
                    "start_local": entry["time_start"],
                    "eur_mwh": eur_mwh,
                }
            )
        days_fetched += 1
        if args.delay:
            time.sleep(args.delay)

    out = {
        "metadata": {
            "source": "hvakosterstrommen.no (offentlig speil av Nord Pool day-ahead)",
            "area": args.area,
            "currency": "EUR",
            "unit": "EUR/MWh",
            "fetched_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "period": f"{start.isoformat()} til {end.isoformat()}",
            "days_fetched": days_fetched,
            "days_failed": days_failed,
            "note": (
                "Vi lagrer rådata i EUR/MWh siden NOK-konverteringen i HKS er "
                "forward-filled (samme kurs flere dager) og ikke matcher BKKs "
                "same-day ECB-kurs. Bruk snapshot_nb_eur_nok.py for daglige kurser."
            ),
        },
        "hourly": hourly,
    }

    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"Skrev {len(hourly)} hourly entries fra {days_fetched} dager "
        f"({len(days_failed)} feilet) til {args.output}"
    )
    return 1 if days_failed else 0


if __name__ == "__main__":
    sys.exit(main())
