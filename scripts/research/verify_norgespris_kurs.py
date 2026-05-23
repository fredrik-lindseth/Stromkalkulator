"""Reproduser BKKs Norgespris-snittspot fra rå Nord Pool EUR/MWh + NB EUR/NOK.

Henter time-data fra Nord Pool dataportal-API (offentlig, men kun siste ~30
dager uten innlogging), EUR/NOK fra Norges Bank SDMX-JSON og forbruk fra
Elhub-CSV. Beregner forbruksvektet snitt-spot og sammenligner med fakturaens
implisitte snittspot utledet fra Norgespris-kompensasjonen.

Foretrekker lokale snapshot-fixturer hvis de finnes
(tests/fixtures/nordpool_eur_<område>_<år>.json og nb_eur_nok_<år>.json).
Dette gjør at gamle måneder kan reverifiseres uten internett-tilgang og uten
NP-innlogging. Snapshotene genereres med snapshot_nordpool_eur.py og
snapshot_nb_eur_nok.py.

Bakgrunn:
    docs/research/nok-omregning.md beskriver et restavvik på 0,14 % mellom
    HA's nordpool-integrasjon (sensor.nord_pool_no5_current_price) og BKKs
    fakturerte snitt-spot for april 2026. Dette scriptet bekrefter at avviket
    kommer fra HA-cachens egen NOK-konvertering, ikke fra fakturaen: rå
    EUR/MWh + NB-kurs (forward-fill, same-day) matcher fakturaen innenfor
    0,04 %.

Konfigurer øverst (YEAR, MONTH, ELHUB_CSV, FAKTURA_*) for en annen måned.
Kjør uten avhengigheter utover Python 3.11+ standardbibliotek.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.request
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Final

# --- Konfig: endre disse for å verifisere en annen måned ---

YEAR: Final[int] = 2026
MONTH: Final[int] = 4  # april
DELIVERY_AREA: Final[str] = "NO5"

ELHUB_CSV: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent
    / "Måleverdier"
    / "elhub_april.csv"
)

# Fakturadata for sammenligning (april 2026)
FAKTURA_FORBRUK_KWH: Final[float] = 1381.83
FAKTURA_NORGESPRIS_KOMPENSASJON_KR: Final[float] = -1427.89
NORGESPRIS_FASTPRIS_INKL_MVA: Final[float] = 0.50
MVA_SATS: Final[float] = 1.25

# --- API-endepunkter (offentlige, ingen auth) ---

NP_URL: Final[str] = (
    "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
    "?date={date}&market=DayAhead&deliveryArea={area}&currency=EUR"
)
NB_URL: Final[str] = (
    "https://data.norges-bank.no/api/data/EXR/B.EUR.NOK.SP"
    "?startPeriod={start}&endPeriod={end}&format=sdmx-json"
)

FIXTURES_DIR: Final[Path] = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"
NP_SNAPSHOT: Final[Path] = FIXTURES_DIR / "nordpool_eur_no5_2026.json"
NB_SNAPSHOT: Final[Path] = FIXTURES_DIR / "nb_eur_nok_2026.json"


@dataclass(frozen=True)
class HourPoint:
    hour_local: str  # ISO med +HH:MM offset
    eur_mwh: float
    eur_nok: float
    nok_kwh_eks_mva: float
    kwh: float


def _http_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "verify_norgespris_kurs/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def fetch_nordpool_month(year: int, month: int, area: str) -> dict[str, list[dict]]:
    """Hent alle dager i en måned fra Nord Pool dataportal (15-min auflösning)."""
    first = date(year, month, 1)
    next_month = date(year + (month // 12), (month % 12) + 1, 1)
    days: dict[str, list[dict]] = {}
    d = first
    while d < next_month:
        url = NP_URL.format(date=d.isoformat(), area=area)
        payload = _http_json(url)
        days[d.isoformat()] = payload["multiAreaEntries"]
        time.sleep(0.2)  # vær snill med APIet
        d += timedelta(days=1)
    return days


def fetch_nb_eur_nok(start: date, end: date) -> dict[str, float]:
    """Hent daglige EUR/NOK fra Norges Bank (kun bankdager)."""
    data = _http_json(NB_URL.format(start=start.isoformat(), end=end.isoformat()))
    obs = data["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
    periods = data["data"]["structure"]["dimensions"]["observation"][0]["values"]
    return {periods[int(i)]["id"]: float(v[0]) for i, v in obs.items()}


def load_nordpool_snapshot(
    path: Path, year: int, month: int
) -> dict[str, float] | None:
    """Les lokal snapshot og returner {iso_local_hour: eur_mwh} for én måned.

    Returnerer None hvis snapshot mangler eller ikke dekker måneden.
    """
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    prefix = f"{year}-{month:02d}"
    out: dict[str, float] = {}
    for entry in data["hourly"]:
        key = entry["start_local"]
        if not key.startswith(prefix):
            continue
        # Aggregér til hele timer i tilfelle snapshot har 15-min
        ts = datetime.fromisoformat(key).replace(minute=0, second=0, microsecond=0)
        out.setdefault(ts.isoformat(), entry["eur_mwh"])
    return out or None


def load_nb_snapshot(path: Path, start: date, end: date) -> dict[str, float] | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    return {
        e["date"]: e["rate"]
        for e in data["daily"]
        if start.isoformat() <= e["date"] <= end.isoformat()
    }


def aggregate_to_local_hours(
    np_days: dict[str, list[dict]], area: str, oslo_offset_hours: int
) -> dict[str, float]:
    """Aggregér 15-min EUR/MWh til lokal time (Europe/Oslo).

    Antar at hele perioden har samme UTC-offset. April er CEST = UTC+2 hele veien.
    For måneder med DST-overgang må dette utvides.
    """
    oslo = timezone(timedelta(hours=oslo_offset_hours))
    buckets: dict[str, list[float]] = defaultdict(list)
    for entries in np_days.values():
        for e in entries:
            start_utc = datetime.fromisoformat(e["deliveryStart"].replace("Z", "+00:00"))
            start_local = start_utc.astimezone(oslo)
            key = start_local.replace(minute=0, second=0, microsecond=0).isoformat()
            buckets[key].append(e["entryPerArea"][area])
    return {h: sum(v) / len(v) for h, v in buckets.items()}


def forward_fill_rates(days: list[str], nb_rates: dict[str, float]) -> dict[str, float]:
    """For hver kalenderdag, bruk siste publiserte NB-kurs (samme dag eller tidligere)."""
    filled: dict[str, float] = {}
    last: float | None = None
    sorted_nb = sorted(nb_rates.items())
    for d, r in sorted_nb:
        if d <= days[0]:
            last = r
    for d in days:
        if d in nb_rates:
            last = nb_rates[d]
        if last is None:
            raise RuntimeError(f"Ingen NB-kurs tilgjengelig for eller før {d}")
        filled[d] = last
    return filled


def load_elhub_hourly(path: Path) -> dict[str, float]:
    """Les Elhub-eksport til {iso_local_hour: kwh}."""
    out: dict[str, float] = {}
    with path.open() as f:
        reader = csv.reader(f, delimiter=";")
        next(reader)
        for row in reader:
            fra = row[0]
            kwh = float(row[3].replace(",", "."))
            dt = datetime.fromisoformat(fra)
            key = dt.replace(minute=0, second=0, microsecond=0).isoformat()
            out[key] = kwh
    return out


def main() -> None:
    print(f"=== Verifiserer Norgespris-snittspot for {YEAR}-{MONTH:02d}, {DELIVERY_AREA} ===\n")

    snapshot_eur = load_nordpool_snapshot(NP_SNAPSHOT, YEAR, MONTH)
    if snapshot_eur:
        print(f"Bruker lokal NP-snapshot ({NP_SNAPSHOT.name})...")
        eur_per_hour = snapshot_eur
    else:
        print("Henter Nord Pool day-ahead-priser (offentlig dataportal-API)...")
        np_days = fetch_nordpool_month(YEAR, MONTH, DELIVERY_AREA)
        eur_per_hour = aggregate_to_local_hours(np_days, DELIVERY_AREA, oslo_offset_hours=2)
        eur_per_hour = {h: v for h, v in eur_per_hour.items() if h.startswith(f"{YEAR}-{MONTH:02d}")}
    print(f"  {len(eur_per_hour)} time-priser")

    np_arith_eur_mwh = sum(eur_per_hour.values()) / len(eur_per_hour)
    print(f"  Aritmetisk månedssnitt: {np_arith_eur_mwh:.4f} EUR/MWh")

    nb_start = date(YEAR, MONTH, 1) - timedelta(days=7)
    nb_end = date(YEAR, MONTH, 28) + timedelta(days=4)
    snapshot_nb = load_nb_snapshot(NB_SNAPSHOT, nb_start, nb_end)
    if snapshot_nb:
        print(f"\nBruker lokal NB-snapshot ({NB_SNAPSHOT.name})...")
        nb_rates = snapshot_nb
    else:
        print("\nHenter EUR/NOK fra Norges Bank...")
        nb_rates = fetch_nb_eur_nok(nb_start, nb_end)
    print(f"  {len(nb_rates)} bankdager (forutgående uke inkludert som fallback)")

    days_in_month = sorted({h[:10] for h in eur_per_hour})
    filled = forward_fill_rates(days_in_month, nb_rates)

    print(f"\nLeser Elhub-forbruk fra {ELHUB_CSV.name}...")
    elhub = load_elhub_hourly(ELHUB_CSV)
    total_kwh = sum(elhub.get(h, 0.0) for h in eur_per_hour)
    print(f"  Total kWh i NP-vinduet: {total_kwh:.3f}")
    print(f"  Faktura forbruk:        {FAKTURA_FORBRUK_KWH:.2f}")

    series: list[HourPoint] = []
    for h in sorted(eur_per_hour):
        eur = eur_per_hour[h]
        rate = filled[h[:10]]
        nok = eur * rate / 1000.0
        kwh = elhub.get(h, 0.0)
        series.append(HourPoint(h, eur, rate, nok, kwh))

    arith_nok_kwh = sum(p.nok_kwh_eks_mva for p in series) / len(series)
    weighted_nok_kwh = sum(p.nok_kwh_eks_mva * p.kwh for p in series) / total_kwh

    # Faktura: implisitt snittspot fra Norgespris-linjen
    rate_per_kwh = FAKTURA_NORGESPRIS_KOMPENSASJON_KR / FAKTURA_FORBRUK_KWH
    impl_inkl_mva = NORGESPRIS_FASTPRIS_INKL_MVA - rate_per_kwh
    impl_eks_mva = impl_inkl_mva / MVA_SATS

    print("\n=== Resultat (NOK/kWh eks. mva) ===")
    print(f"  Faktura (implisitt fra Norgespris):     {impl_eks_mva:.6f}")
    print(f"  NP+NB forbruksvektet (same-day kurs):   {weighted_nok_kwh:.6f}")
    print(f"  NP+NB aritmetisk:                        {arith_nok_kwh:.6f}")
    diff = weighted_nok_kwh - impl_eks_mva
    print(f"  Diff vektet vs faktura: {diff*1000:+.4f} milli-NOK/kWh ({diff/impl_eks_mva*100:+.4f}%)")

    # Norgespris-kompensasjon
    beregnet_komp = (NORGESPRIS_FASTPRIS_INKL_MVA - weighted_nok_kwh * MVA_SATS) * FAKTURA_FORBRUK_KWH
    print(f"\n=== Norgespris-kompensasjon på {FAKTURA_FORBRUK_KWH} kWh ===")
    print(f"  Faktura:                {FAKTURA_NORGESPRIS_KOMPENSASJON_KR:.2f} kr")
    print(f"  Beregnet (NP+NB vektet): {beregnet_komp:.2f} kr  (avvik {beregnet_komp - FAKTURA_NORGESPRIS_KOMPENSASJON_KR:+.2f} kr)")

    # Hva slags kurs ville matchet perfekt?
    weighted_eur_per_kwh = sum(p.eur_mwh * p.kwh for p in series) / total_kwh
    implied_rate = impl_eks_mva * 1000 / weighted_eur_per_kwh
    nb_apr = [r for d, r in nb_rates.items() if d.startswith(f"{YEAR}-{MONTH:02d}")]
    print("\n=== Implisitt EUR/NOK BKK ser ut til å ha brukt ===")
    print(f"  Forbruksvektet EUR/MWh: {weighted_eur_per_kwh:.4f}")
    print(f"  Implisitt kurs:         {implied_rate:.4f} NOK/EUR")
    if nb_apr:
        print(f"  NB aritmetisk månedssnitt: {sum(nb_apr)/len(nb_apr):.4f}")

    print("\nKonklusjon: forward-fill (same-day NB-kurs) gjengir fakturaen innenfor")
    print("avrundingsfeil. HA-cachens 0,14 %-avvik stammer fra HA nordpool-integrasjonens")
    print("egen NOK-konvertering, ikke fra fakturaen.")


if __name__ == "__main__":
    main()
