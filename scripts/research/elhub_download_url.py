"""Lag Elhubs CSV-lenke for én måned; åpnes i nettleseren etter BankID-innlogging."""

from __future__ import annotations

import argparse
from datetime import date
from urllib.parse import urlencode


def download_url(metering_point: str, year: int, month: int) -> str:
    """Samme GET-endepunkt som Min sides «Last ned måleverdier»."""
    if len(metering_point) != 18 or not metering_point.isascii() or not metering_point.isdigit():
        raise ValueError("Målepunkt-ID må være 18 sifre")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    query = urlencode(
        {"filter[startDate]": start.isoformat(), "filter[endDate]": end.isoformat(), "locale": "nb"}
    )
    return (
        f"https://minside.elhub.no/api/metering-points/{metering_point}"
        f"/metering-values/interval-volume.csv?{query}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metering-point", required=True, help="Målepunkt-ID fra fakturaen")
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--month", required=True, type=int)
    args = parser.parse_args()
    try:
        url = download_url(args.metering_point, args.year, args.month)
    except ValueError as exc:
        parser.error(str(exc))
    print(url)


if __name__ == "__main__":
    main()
