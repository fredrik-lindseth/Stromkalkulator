"""Konverter Bloomberg EUR/NOK-uttrekk (xlsx) til JSON-fixture.

Leser Bloomberg-uttrekket (EUR/NOK daglig snapshot 12:00 Europe/Berlin,
jan-apr 2026) og skriver en JSON-fixture på samme form som nb_eur_nok_2026.json.
Resultatet er dokumentert i docs/research/bloomberg-verifisering.md:

    {"metadata": {...}, "daily": [{"date": "2026-01-02", "rate": 11.80381}, ...]}

`rate` settes til PX_MID (mid-pris), som er det bestillingen ba om. Bid/ask/last
beholdes som ekstra felter for sporbarhet.

Bloomberg-data er lisensiert og kan IKKE redistribueres. Både råfila og denne
fixturen ligger derfor under _private/ (gitignored). Hold dem der.

Kjør (openpyxl er ikke en repo-avhengighet, så bruk uv):

    uv run --with openpyxl python scripts/research/snapshot_bloomberg_eur_nok.py

Kolonneoppsettet under speiler arket slik det kom fra terminalen:
BDH-formlene ligger i rad 3, datapunktene fra rad 5. Fire blokker side om side
(PX_LAST@12, PX_BID/ASK@12, PX_MID@12, PX_LAST daglig close).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

try:
    import openpyxl
except ImportError:
    sys.exit(
        "openpyxl mangler. Kjør via uv:\n"
        "  uv run --with openpyxl python scripts/research/snapshot_bloomberg_eur_nok.py"
    )

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
DEFAULT_XLSX: Final[Path] = ROOT / "_private" / "Måleverdier" / "fredrik_xr_data.xlsx"
DEFAULT_OUT: Final[Path] = ROOT / "_private" / "Måleverdier" / "bloomberg_eur_nok_1200cet_2026.json"

# 0-indekserte kolonner i arket (se modul-docstring).
COL_DATE: Final[int] = 3
COL_LAST_1200: Final[int] = 4
COL_BID: Final[int] = 7
COL_ASK: Final[int] = 8
COL_MID: Final[int] = 11
COL_LAST_CLOSE: Final[int] = 14
FIRST_DATA_ROW: Final[int] = 4  # 0-indeksert (rad 5 i arket)


def convert(xlsx: Path) -> list[dict]:
    wb = openpyxl.load_workbook(xlsx, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    daily: list[dict] = []
    for r in rows[FIRST_DATA_ROW:]:
        d = r[COL_DATE]
        if d is None:
            continue
        mid = r[COL_MID]
        if mid is None:
            continue
        daily.append(
            {
                "date": d.date().isoformat(),
                "rate": round(float(mid), 5),
                "px_mid_1200": round(float(mid), 5),
                "px_last_1200": _opt(r[COL_LAST_1200]),
                "bid_1200": _opt(r[COL_BID]),
                "ask_1200": _opt(r[COL_ASK]),
                "px_last_close": _opt(r[COL_LAST_CLOSE]),
            }
        )
    daily.sort(key=lambda e: e["date"])
    return daily


def _opt(v: object) -> float | None:
    return round(float(v), 5) if isinstance(v, (int, float)) else None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.xlsx.exists():
        print(f"Finner ikke {args.xlsx}", file=sys.stderr)
        return 2

    daily = convert(args.xlsx)
    if not daily:
        print("Ingen datapunkter funnet i arket", file=sys.stderr)
        return 1

    out = {
        "metadata": {
            "source": "Bloomberg terminal (BDH), EURNOK Curncy",
            "pair": "EUR/NOK",
            "type": "interbank spot snapshot 12:00 Europe/Berlin (CET/CEST), PX_MID",
            "period": f"{daily[0]['date']} til {daily[-1]['date']}",
            "n_bankdager": len(daily),
            "license": "Bloomberg-data er lisensiert, IKKE redistribuer. Hold under _private/.",
            "note": (
                "rate = PX_MID @ 12:00 Berlin. Bid/ask/last beholdt for sporbarhet. "
                "For helger/helligdager: forward-fill siste publiserte kurs <= dato."
            ),
        },
        "daily": daily,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print(f"Skrev {args.output} ({len(daily)} bankdager)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
