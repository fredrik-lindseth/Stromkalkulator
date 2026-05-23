"""Lagre daglige EUR/NOK-kurser fra Norges Bank som snapshot-fixture.

Hvorfor: gjør reverifisering av Norgespris-kompensasjon mulig uten internett.
NB-kursen brukes til å konvertere Nord Pool EUR/MWh til NOK/kWh per time.

Datakilde: Norges Bank SDMX-JSON API. ECB-konsertasjonskursen 14:15 CET,
publisert kun på bankdager. For helger/helligdager må du forward-fill'e
forrige bankdag.

Format på utfil tests/fixtures/nb_eur_nok_<år>.json:

    {
      "metadata": {
        "source": "data.norges-bank.no",
        "pair": "EUR/NOK",
        "type": "ECB-konsertasjonskurs 14:15 CET",
        "fetched_at": "...",
        "period": "2026-01-01 til 2026-05-31"
      },
      "daily": [
        {"date": "2026-01-02", "rate": 11.4567},
        ...
      ]
    }

Kjøres uten avhengigheter utover Python 3 standardbibliotek:

    python3 scripts/research/snapshot_nb_eur_nok.py \\
        --start 2026-01-01 --end 2026-05-31 \\
        --output tests/fixtures/nb_eur_nok_2026.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

NB_URL = (
    "https://data.norges-bank.no/api/data/EXR/B.EUR.NOK.SP"
    "?startPeriod={start}&endPeriod={end}&format=sdmx-json"
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--start", required=True, help="Startdato YYYY-MM-DD (inkl)")
    p.add_argument("--end", required=True, help="Sluttdato YYYY-MM-DD (inkl)")
    p.add_argument("--output", type=Path, required=True)
    return p.parse_args()


def fetch_rates(start: date, end: date) -> dict[str, float]:
    url = NB_URL.format(start=start.isoformat(), end=end.isoformat())
    req = urllib.request.Request(url, headers={"User-Agent": "snapshot_nb_eur_nok/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    obs = data["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
    periods = data["data"]["structure"]["dimensions"]["observation"][0]["values"]
    return {periods[int(i)]["id"]: float(v[0]) for i, v in obs.items()}


def main() -> int:
    args = parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)

    rates = fetch_rates(start, end)
    daily = [{"date": d, "rate": r} for d, r in sorted(rates.items())]

    out = {
        "metadata": {
            "source": "data.norges-bank.no",
            "pair": "EUR/NOK",
            "type": "ECB-konsertasjonskurs 14:15 CET, B.EUR.NOK.SP",
            "fetched_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "period": f"{start.isoformat()} til {end.isoformat()}",
            "n_bankdager": len(daily),
            "note": (
                "Kun publisert på bankdager. For helger/helligdager bruk "
                "forward-fill (siste publiserte kurs <= dagens dato)."
            ),
        },
        "daily": daily,
    }

    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"Skrev {len(daily)} bankdager til {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
