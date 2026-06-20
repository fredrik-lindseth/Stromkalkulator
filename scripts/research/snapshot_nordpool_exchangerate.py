"""Arkiver Nord Pools egne daglige EUR/NOK-kurser (exchangeRate) for et budområde.

Nord Pool publiserer kursen de faktisk bruker til NOK-omregning av day-ahead-
prisene i feltet `exchangeRate` på NOK-svaret fra DayAheadPrices-API-et. Det er
denne kursen (state=Final, etter to-banks-hedge) som strømleverandører/netteiere
fakturerer Norgespris og spotpris mot, jf. forskrift om kraftomsetning § 7-6.

Se docs/research/bloomberg-verifisering.md (Veien videre) for hvorfor dette er
den riktige kursen, og hvordan den sporer Norges Bank dagen før (D-1).

VIKTIG: Det gratis anonyme API-et serverer bare om lag de siste 2 månedene;
eldre datoer gir 401. Kjør derfor jevnlig (minst månedlig) for å fange opp
ferske leveringsdøgn før de faller ut. Scriptet MERGER inn i et arkiv, så hver
kjøring utvider historikken uten å miste eldre dager.

Enkleste bruk (ingen argumenter: siste 60 dager, NO5, merge inn i arkivet):

    just snapshot-kurs
    # eller
    python3 scripts/research/snapshot_nordpool_exchangerate.py

Krever kun standardbibliotek.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
ARCHIVE_DIR: Final[Path] = ROOT / "_private" / "Måleverdier"
API: Final[str] = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
# Default UA: ren Python-urllib blokkeres (403), en nettleser-UA slipper gjennom.
UA: Final[str] = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
LOOKBACK_DAYS: Final[int] = 60


def default_output(area: str) -> Path:
    return ARCHIVE_DIR / f"nordpool_exchangerate_{area.lower()}.json"


def fetch_day(d: date, area: str) -> tuple[float | None, str | None, str]:
    url = f"{API}?date={d.isoformat()}&market=DayAhead&deliveryArea={area}&currency=NOK"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            j = json.load(r)
        states = j.get("areaStates") or [{}]
        return j.get("exchangeRate"), states[0].get("state"), "ok"
    except urllib.error.HTTPError as e:
        return None, None, f"HTTP{e.code}"
    except Exception as e:  # nettverk/timeout
        return None, None, f"err:{type(e).__name__}"


def load_archive(path: Path) -> dict[str, dict]:
    """Eksisterende arkiv som {date: entry}, eller tomt hvis fila mangler."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {e["date"]: e for e in data.get("daily", [])}


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--area", default="NO5", help="Budområde (default NO5)")
    p.add_argument("--start", help="Første leveringsdato (default: i dag minus 60 dager)")
    p.add_argument("--end", help="Siste leveringsdato (default: i dag)")
    p.add_argument("--output", type=Path, help="JSON-arkiv (default: _private/Måleverdier/...)")
    p.add_argument("--no-merge", action="store_true", help="Skriv kun nyhentede dager, ikke merge inn i arkivet")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    today = date.today()
    start = date.fromisoformat(args.start) if args.start else today - timedelta(days=LOOKBACK_DAYS)
    end = date.fromisoformat(args.end) if args.end else today
    output = args.output or default_output(args.area)

    archive = {} if args.no_merge else load_archive(output)
    before = len(archive)

    misses: list[str] = []
    d = start
    while d <= end:
        rate, state, status = fetch_day(d, args.area)
        if status == "ok" and rate is not None:
            archive[d.isoformat()] = {"date": d.isoformat(), "rate": rate, "state": state}
        else:
            misses.append(f"{d.isoformat()}:{status}")
        d += timedelta(days=1)

    daily = [archive[k] for k in sorted(archive)]
    if not daily:
        print(f"Ingen kurser i arkivet. Avvist: {', '.join(misses) or '(ukjent)'}", file=sys.stderr)
        return 1

    out = {
        "metadata": {
            "source": "Nord Pool Data Portal API (DayAheadPrices, currency=NOK)",
            "field": "exchangeRate (state=Final, post to-banks-hedge)",
            "pair": "EUR/NOK",
            "area": args.area,
            "period": f"{daily[0]['date']} til {daily[-1]['date']}",
            "n_dager": len(daily),
            "note": (
                "Kurs per LEVERINGSDØGN (snapshot tatt på auksjonsdagen D-1). "
                "Anonymt API serverer kun om lag de siste 2 månedene; eldre gir 401. "
                "Arkivet merges på tvers av kjøringer."
            ),
        },
        "daily": daily,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    added = len(archive) - before
    print(f"Arkiv: {output.relative_to(ROOT)}")
    print(f"  {len(daily)} dager totalt ({daily[0]['date']} til {daily[-1]['date']}), "
          f"{added} nye denne kjøringen.")
    if misses:
        out_of_window = [m for m in misses if m.endswith("HTTP401")]
        other = [m for m in misses if not m.endswith("HTTP401")]
        if out_of_window:
            print(f"  {len(out_of_window)} dager utenfor gratis-vindu (HTTP401), forventet.")
        if other:
            print(f"  Andre avvik: {', '.join(other[:6])}" + (" ..." if len(other) > 6 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
