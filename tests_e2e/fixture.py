"""Export only anonymous hourly values; never mount raw fixture metadata."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("start_local", "kwh", "spot_nok_kwh_eks_mva", "p_max_w")


def load_fixture(name: str = "juni_2026") -> dict:
    """Select checked-in public fixture by basename, with an explicit allowlist."""
    files = {p.name[4:-12]: p for p in (ROOT / "tests/fixtures").glob("bkk_*_hourly.json")}
    if name not in files:
        raise ValueError(f"Ukjent fixture {name!r}. Velg blant {sorted(files)}")
    raw = json.loads(files[name].read_text())
    hours = [{key: row[key] for key in FIELDS} for row in raw["hours"]]
    if not hours:
        raise ValueError("Tom fixture")
    previous = None
    for row in hours:
        start = datetime.fromisoformat(row["start_local"])
        if start.utcoffset() is None or (previous and start.timestamp() - previous != 3600):
            raise ValueError("Fixture må ha sammenhengende timer med tidssone")
        previous = start.timestamp()
        for field in FIELDS[1:]:
            value = row[field]
            if value is None and field != "kwh":
                continue  # Missing source observations remain missing, never invented.
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"Ugyldig {field}")
        if row["kwh"] < 0 or row["kwh"] > 25:
            raise ValueError("Timeenergi utenfor avspillerens 0-25 kWh-vindu")
    return {"name": name, "hours": hours}


def reconcile_june(fixture: dict) -> dict:
    """Independent source check for June, not a claim about HA wall-clock tariffs.

    June 2026 has no Norwegian public holidays. The reference is the verified
    June bill transcribed in tests/test_faktura_bkk.py (FAKTURA_JUNI_2026).
    Restricting this oracle to June avoids silently guessing other holidays.
    """
    if fixture["name"] != "juni_2026":
        return {"verified": False, "reason": "Fakturareferanse er bare låst for juni_2026"}
    hours = fixture["hours"]
    start = datetime.fromisoformat(hours[0]["start_local"])
    end = datetime.fromisoformat(hours[-1]["start_local"]) + timedelta(hours=1)
    if (start.isoformat(), end.isoformat(), len(hours)) != (
        "2026-06-01T00:00:00+02:00",
        "2026-07-01T00:00:00+02:00",
        720,
    ):
        raise ValueError("Juni-fixturen dekker ikke hele fakturamåneden")
    day = sum(
        row["kwh"]
        for row in hours
        if (dt := datetime.fromisoformat(row["start_local"])).weekday() < 5 and 6 <= dt.hour < 22
    )
    total = sum(row["kwh"] for row in hours)
    actual = {"total_kwh": total, "day_kwh": day, "night_kwh": total - day}
    expected = {"total_kwh": 1033.628, "day_kwh": 590.646, "night_kwh": 442.982}
    # Measured source differences: total -2 Wh, day +36 Wh, night -38 Wh.
    # Hourly snapshots do not reproduce the invoice's split to the last Wh.
    tolerance = {"total_kwh": 0.01, "day_kwh": 0.05, "night_kwh": 0.05}
    for field, value in expected.items():
        if not math.isclose(actual[field], value, abs_tol=tolerance[field]):
            raise AssertionError(f"Fixture/faktura-avvik i {field}: {actual[field]} != {value}")
    return {
        "verified": True,
        "actual": actual,
        "invoice": expected,
        "tolerance_kwh": tolerance,
        "difference_kwh": {key: round(actual[key] - value, 6) for key, value in expected.items()},
    }
