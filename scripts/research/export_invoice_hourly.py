"""Eksporter time-for-time-data fra HA recorder-DB for én faktureringsmåned.

Hva: leser statistics-tabellen i Home Assistant sin SQLite-DB og skriver
time-oppløst forbruk (kWh), spotpris (NOK/kWh eks. mva) og maks effekt (W)
til en JSON-fil med samme format som tests/fixtures/bkk_april_2026_hourly.json.

Hvorfor: input til verify_invoice_hourly.py for sammenligning mot faktura.
Holder oss på standardbiblioteket så scriptet kan kjøres direkte i HA-OS-
kontaineren uten å installere noe.

Hvordan kjøres: på HA-host (ha-local) via SSH, mot recorder-DB.

    python3 export_invoice_hourly.py \\
        --year 2026 --month 4 \\
        --output /tmp/bkk_april_2026_hourly.json \\
        --fakturanr 012345683

Resultatfilen scp-es ned lokalt og brukes som fixture.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Oslo")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, required=True)
    p.add_argument("--month", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--db-path", type=Path, default=Path("/config/home-assistant_v2.db"))
    p.add_argument(
        "--tpi-entity",
        action="append",
        default=None,
        help=(
            "Akkumulert kWh-sensor. Kan oppgis flere ganger som fallback-kjede; "
            "data fra senere flagg overskriver tidligere ved overlapp. "
            "Default: sensor.pow_u_ams_tpi"
        ),
    )
    p.add_argument("--spot-entity", default="sensor.nord_pool_no5_current_price")
    p.add_argument(
        "--p-entity",
        action="append",
        default=None,
        help=(
            "Effekt-sensor (watt). Kan oppgis flere ganger som fallback-kjede. "
            "Default: sensor.pow_u_ams_p"
        ),
    )
    p.add_argument("--fakturanr", default="")
    args = p.parse_args()
    if not args.tpi_entity:
        args.tpi_entity = ["sensor.pow_u_ams_tpi"]
    if not args.p_entity:
        args.p_entity = ["sensor.pow_u_ams_p"]
    return args


def month_bounds_local(year: int, month: int) -> tuple[datetime, datetime]:
    """Returner (start, end) som tz-aware datetimes i Europe/Oslo."""
    start = datetime(year, month, 1, tzinfo=TZ)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=TZ)
    else:
        end = datetime(year, month + 1, 1, tzinfo=TZ)
    return start, end


def load_meta_ids(con: sqlite3.Connection, entities: list[str]) -> dict[str, int]:
    placeholders = ",".join("?" for _ in entities)
    rows = con.execute(
        f"SELECT id, statistic_id FROM statistics_meta WHERE statistic_id IN ({placeholders})",
        entities,
    ).fetchall()
    ids = {r["statistic_id"]: r["id"] for r in rows}
    missing = [e for e in entities if e not in ids]
    if missing:
        sys.exit(f"Mangler statistics_meta for: {missing}")
    return ids


def merge_entity_chain(
    con: sqlite3.Connection,
    entities: list[str],
    meta: dict[str, int],
    fetcher,
    *fetch_args,
) -> dict[float, float]:
    """Slå sammen data fra flere entiteter, senere entitet vinner ved overlapp.

    Bruksmønster: tibber-puls-meter dekker jan-30, deretter overtar pow-u_tpi.
    """
    merged: dict[float, float] = {}
    for ent in entities:
        merged.update(fetcher(con, meta[ent], *fetch_args))
    return merged


def fetch_tpi_states(con, meta_id, start_ts, end_ts) -> dict[float, float]:
    """Hent tpi-state ved hver hourly time-grense, inkludert end_ts."""
    rows = con.execute(
        "SELECT start_ts, state FROM statistics "
        "WHERE metadata_id = ? AND start_ts >= ? AND start_ts <= ? ORDER BY start_ts",
        (meta_id, start_ts, end_ts),
    ).fetchall()
    return {r["start_ts"]: r["state"] for r in rows if r["state"] is not None}


def fetch_hourly_column(con, meta_id, column, start_ts, end_ts) -> dict[float, float]:
    """Hent mean eller max per time innenfor [start_ts, end_ts)."""
    rows = con.execute(
        f"SELECT start_ts, {column} FROM statistics "
        "WHERE metadata_id = ? AND start_ts >= ? AND start_ts < ? ORDER BY start_ts",
        (meta_id, start_ts, end_ts),
    ).fetchall()
    return {r["start_ts"]: r[column] for r in rows if r[column] is not None}


def iter_hour_starts(start: datetime, end: datetime):
    """Gå time for time fra start (inkl.) til end (eks.) i lokal tid.

    Bruker UTC-aritmetikk for å håndtere DST-skifter riktig: en mars-dag har
    23 reelle timer, en oktober-dag har 25. Statistics-tabellen lagrer UTC-
    tidsstempler, så vi gir tilbake både lokal og UTC-representasjon.
    """
    cur_utc = start.astimezone(ZoneInfo("UTC"))
    end_utc = end.astimezone(ZoneInfo("UTC"))
    while cur_utc < end_utc:
        yield cur_utc.astimezone(TZ), cur_utc
        cur_utc += timedelta(hours=1)


def build_hours(
    tpi: dict[float, float],
    spot: dict[float, float],
    p_max: dict[float, float],
    start: datetime,
    end: datetime,
) -> list[dict]:
    hours: list[dict] = []
    for local_dt, utc_dt in iter_hour_starts(start, end):
        ts = utc_dt.timestamp()
        next_ts = ts + 3600

        kwh = None
        if ts in tpi and next_ts in tpi:
            kwh = round(tpi[next_ts] - tpi[ts], 3)

        spot_val = spot.get(ts)
        if spot_val is not None:
            spot_val = round(spot_val, 6)

        p_val = p_max.get(ts)
        if p_val is not None:
            p_val = round(float(p_val), 1)

        hours.append(
            {
                "start_local": local_dt.isoformat(timespec="seconds"),
                "kwh": kwh,
                "spot_nok_kwh_eks_mva": spot_val,
                "p_max_w": p_val,
            }
        )
    return hours


def main() -> None:
    args = parse_args()

    if not args.db_path.exists():
        sys.exit(f"Finner ikke DB-fil: {args.db_path}")

    start, end = month_bounds_local(args.year, args.month)
    start_ts = start.timestamp()
    end_ts = end.timestamp()

    con = sqlite3.connect(f"file:{args.db_path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    all_entities = [*args.tpi_entity, args.spot_entity, *args.p_entity]
    meta = load_meta_ids(con, all_entities)

    tpi = merge_entity_chain(con, args.tpi_entity, meta, fetch_tpi_states, start_ts, end_ts)
    spot = fetch_hourly_column(con, meta[args.spot_entity], "mean", start_ts, end_ts)
    p_max = merge_entity_chain(con, args.p_entity, meta, fetch_hourly_column, "max", start_ts, end_ts)

    hours = build_hours(tpi, spot, p_max, start, end)

    tpi_start = tpi.get(start_ts)
    tpi_end = tpi.get(end_ts)
    if tpi_start is None or tpi_end is None:
        print(
            f"ADVARSEL: mangler tpi-state ved periodegrense "
            f"(start={tpi_start}, end={tpi_end})",
            file=sys.stderr,
        )

    navn = f"{start.strftime('%B').lower()}_{args.year}"

    out = {
        "metadata": {
            "navn": navn,
            "fakturanr": args.fakturanr,
            "periode_start_local": start.isoformat(timespec="seconds"),
            "periode_end_local": end.isoformat(timespec="seconds"),
            "tidssone": "Europe/Oslo",
            "kilde_forbruk": (
                ", ".join(args.tpi_entity)
                + " (Akkumulert meter, delta per time, fallback-kjede)"
            ),
            "kilde_spotpris": f"{args.spot_entity} (eks. mva, multipliser med 1.25 for inkl. mva)",
            "kilde_p_max": (
                ", ".join(args.p_entity)
                + " (Active import i watt, max per time, fallback-kjede)"
            ),
            "tpi_start_kwh": tpi_start,
            "tpi_end_kwh": tpi_end,
        },
        "hours": hours,
    }

    args.output.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False))
    print(
        f"Skrev {len(hours)} timer til {args.output} "
        f"(tpi-delta: {(tpi_end or 0) - (tpi_start or 0):.3f} kWh)"
    )


if __name__ == "__main__":
    main()
