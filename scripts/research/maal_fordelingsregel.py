"""Mål hva fordelingsregelen i avregningskontrakten koster, mot Elhub-fasit.

Bakgrunn: docs/kontrakter/avregning.md C1. Et målerdelta som spenner flere
avregningsintervaller kan fordeles jevnt over tid, eller snappes til
intervallet pollen startet eller endte i. Valget er tatt med Elhub som dommer,
og tallene i kontrakten kommer herfra.

Metode: Elhub-CSV for en måned er fasit på kWh per time, og timeprisen er
snittet av Nord Pools publiserte kvarterpriser. Fasitsummen er kWh x pris per
time. Så simuleres en kumulativ teller (lineær inne i hver time, som er den
beste antakelsen vi har når fasiten er timesoppløst), den leses av med et
pollintervall med jitter, og hver regel avregner det den ser. Avviket fra
fasiten og spennet over jitteren er det som rapporteres. Spennet er prisen på
invarianten: hvor mye avregningen flytter seg av polltiden alene.

Krever de private arkivene (`just snapshot-kurs` og Elhub-CSV fra elhub.no).
Kjøres uten nett.

    python3 scripts/research/maal_fordelingsregel.py
    python3 scripts/research/maal_fordelingsregel.py --maaned juli --seeds 50
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
PRIVAT: Final[Path] = ROOT / "_private" / "Måleverdier"
NOK_ARKIV: Final[Path] = PRIVAT / "nordpool_nok_kvarter_no5.json"
TIME: Final[timedelta] = timedelta(hours=1)
REGLER: Final[tuple[str, ...]] = ("jevn", "snap_slutt", "snap_start")


def les_elhub(maaned: str) -> list[tuple[datetime, float]]:
    """Timesvolum fra Elhub-eksporten, i UTC. Elhub er fakturagrunnlaget."""
    sti = PRIVAT / f"elhub_{maaned}.csv"
    if not sti.exists():
        sys.exit(f"Mangler {sti}. Last ned timesverdier fra elhub.no (BankID).")
    rader: list[tuple[datetime, float]] = []
    maanedsnr = None
    with sti.open(encoding="utf-8-sig") as fil:
        for rad in csv.DictReader(fil, delimiter=";"):
            fra = datetime.fromisoformat(rad["Fra"])
            if maanedsnr is None:
                maanedsnr = fra.month
            if fra.month != maanedsnr:
                continue
            rader.append((fra.astimezone(UTC), float(rad["Volum"].replace(",", "."))))
    rader.sort()
    return rader


def les_timespriser() -> dict[datetime, float]:
    """Timespris i NOK/kWh eks. mva: snitt av de fire kvarterprisene (A2).

    Uvektet snitt ved full presisjon, samme regning som prisruteregelen i A2.1
    og som verify_norgespris_eksakt.py. Går de tre fra hverandre, regner drift
    og etterkontroll ulikt, og da er sammenligningen under verdiløs.
    """
    if not NOK_ARKIV.exists():
        sys.exit(f"Mangler {NOK_ARKIV}. Kjør `just snapshot-kurs`.")
    arkiv = json.loads(NOK_ARKIV.read_text(encoding="utf-8"))
    per_time: dict[datetime, list[float]] = defaultdict(list)
    for dag in arkiv["daily"]:
        for kvarter in dag["kvarter"]:
            start = datetime.fromisoformat(kvarter["start_local"]).astimezone(UTC)
            per_time[start.replace(minute=0, second=0, microsecond=0)].append(kvarter["nok_mwh"])
    return {time: sum(v) / len(v) / 1000 for time, v in per_time.items() if len(v) == 4}


def _intervallstart(tidspunkt: datetime) -> datetime:
    return tidspunkt.replace(minute=0, second=0, microsecond=0)


def simuler(
    timer: list[tuple[datetime, float]],
    priser: dict[datetime, float],
    poll_sekunder: int,
    regel: str,
    seed: int,
) -> float:
    """Kroner en regel kommer fram til når telleren leses av med jitter."""
    # Jitter i en måling, ikke kryptografi.
    tilfeldig = random.Random(seed)
    start = timer[0][0]
    slutt = timer[-1][0] + TIME
    kumulativ = [0.0]
    for _, kwh in timer:
        kumulativ.append(kumulativ[-1] + kwh)

    def teller(naa: datetime) -> float:
        if naa <= start:
            return 0.0
        if naa >= slutt:
            return kumulativ[-1]
        indeks = int((naa - start).total_seconds() // 3600)
        andel = ((naa - start).total_seconds() % 3600) / 3600
        return kumulativ[indeks] + timer[indeks][1] * andel

    forrige = start + timedelta(seconds=tilfeldig.uniform(0, poll_sekunder))
    forrige_verdi = teller(forrige)
    kroner = forrige_verdi * priser[start]
    naa = forrige
    while naa < slutt:
        naa = min(slutt, naa + timedelta(seconds=poll_sekunder * tilfeldig.uniform(0.8, 1.2)))
        verdi = teller(naa)
        delta = verdi - forrige_verdi
        if regel == "snap_slutt":
            kroner += delta * priser.get(_intervallstart(naa), 0.0)
        elif regel == "snap_start":
            kroner += delta * priser.get(_intervallstart(forrige), 0.0)
        else:
            varighet = (naa - forrige).total_seconds()
            bit = forrige
            while bit < naa:
                intervall = _intervallstart(bit)
                neste = min(naa, intervall + TIME)
                kroner += delta * ((neste - bit).total_seconds() / varighet) * priser.get(intervall, 0.0)
                bit = neste
        forrige, forrige_verdi = naa, verdi
    return kroner


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maaned", default="juni", help="månedsnavn, som i elhub_<måned>.csv")
    parser.add_argument("--seeds", type=int, default=20, help="antall jitter-kjøringer per rad")
    args = parser.parse_args()

    priser = les_timespriser()
    timer = [(time, kwh) for time, kwh in les_elhub(args.maaned) if time in priser]
    if not timer:
        sys.exit(f"Prisarkivet dekker ingen timer i {args.maaned}. Gratis-API-et rekker ~2 måneder bakover.")

    fasit = sum(kwh * priser[time] for time, kwh in timer)
    print(f"{args.maaned}: {len(timer)} timer, {sum(k for _, k in timer):.3f} kWh")
    print(f"fasit (Elhub-kWh x timepris): {fasit:.2f} kr eks. mva\n")
    print(f"{'Poll':<10} {'Regel':<12} {'Avvik fra fasit':<26} Spenn")
    for poll, navn in ((300, "5 min"), (1800, "30 min"), (10800, "3 t (gap)")):
        for regel in REGLER:
            avvik = [simuler(timer, priser, poll, regel, seed) - fasit for seed in range(1, args.seeds + 1)]
            omraade = f"{min(avvik):+.2f} .. {max(avvik):+.2f} kr"
            print(f"{navn:<10} {regel:<12} {omraade:<26} {max(avvik) - min(avvik):.2f} kr")


if __name__ == "__main__":
    main()
