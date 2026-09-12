"""Bygg fasit-fixturene replay-testene måler mot.

Skriver to sett filer til tests/fixtures/ fra arkivene i _private/Måleverdier/:

* `elhub_<måned>_<år>.json` -- intervallenergi per time fra Elhub-CSV-en.
  Dette er fakturagrunnlaget BKK leser, uavhengig av HAN-måleren og dermed av
  om HAN-leseren var nede. Bare `Fra` og `Volum` tas med; kundenavn,
  målepunkt-ID og registreringstidspunkt blir liggende i den private CSV-en.

* `final_pris_<måned>_<år>.json` -- Nord Pools publiserte Final-priser, en rad
  per time med de fire kvarterprisene og timesnittet (A2 i
  docs/kontrakter/avregning.md: uvektet snitt, ingen mellomavrunding). For
  dager som har falt ut av gratis-vinduet i NOK-arkivet brukes EUR-fixturen
  ganget med exchangeRate-arkivet, og raden merkes `kilde: "fallback"` med
  `kvarter: null`.

Prisregningen er med vilje identisk med `verify_norgespris_eksakt.py`, så
replay-fasiten og etterkontrollen mot faktura regner på samme tall.

    python3 scripts/research/lag_replay_fixtures.py
    python3 scripts/research/lag_replay_fixtures.py --sjekk

`--sjekk` skriver ingenting, men feiler hvis fixturene på disk ikke er det
scriptet ville skrevet nå. Det er den kjøringen CI kan bruke.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_norgespris_eksakt as vne

ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
FIXTURES: Final[Path] = ROOT / "tests" / "fixtures"
PRIVAT: Final[Path] = ROOT / "_private" / "Måleverdier"
NOK_ARKIV: Final[Path] = PRIVAT / "nordpool_nok_kvarter_no5.json"

OMRADE: Final[str] = "NO5"

# Måneder å forsøke. Den som mangler kilde hoppes over med en linje på stdout;
# det er ikke en feil, arkivene rekker bare et par måneder bakover.
MANEDER: Final[list[str]] = [
    "februar_2026",
    "mars_2026",
    "april_2026",
    "mai_2026",
    "juni_2026",
    "juli_2026",
    "august_2026",
]


def _maned_prefiks(navn: str) -> str:
    """`juni_2026` -> `2026-06`."""
    maaned, aar = navn.split("_")
    return f"{aar}-{vne.MND_NR[maaned]:02d}"


def _kvarter_per_time() -> dict[str, list[float]]:
    """{time-start lokal ISO: [NOK/kWh eks. mva per kvarter]} fra NOK-arkivet."""
    if not NOK_ARKIV.exists():
        return {}
    ut: dict[str, list[float]] = {}
    for dag in json.loads(NOK_ARKIV.read_text(encoding="utf-8"))["daily"]:
        for kv in dag["kvarter"]:
            time_iso = kv["start_local"][:14] + "00:00" + kv["start_local"][19:]
            ut.setdefault(time_iso, []).append(kv["nok_mwh"] / 1000.0)
    return ut


def bygg_elhub(navn: str) -> dict[str, Any] | None:
    """Intervallenergi per time for én fakturamåned, eller None uten CSV."""
    rader = vne.last_elhub(navn)
    if rader is None:
        return None
    prefiks = _maned_prefiks(navn)
    timer = [
        {"start_local": iso, "kwh": kwh} for iso, kwh in sorted(rader.items()) if iso.startswith(prefiks)
    ]
    if not timer:
        return None
    return {
        "metadata": {
            "navn": navn,
            "kilde": "Elhub, måleserie «KWH 60 Forbruk», kvalitet «Målt»",
            "tidssone": "Europe/Oslo",
            "opplosning_minutter": 60,
            "timer": len(timer),
            "sum_kwh": round(sum(t["kwh"] for t in timer), 3),
            "generert_av": "scripts/research/lag_replay_fixtures.py",
        },
        "hours": timer,
    }


def bygg_final_pris(navn: str, timenokler: list[str]) -> dict[str, Any] | None:
    """Final-pris per time, eller None hvis én eneste time mangler dekning."""
    kvarter = _kvarter_per_time()
    fallback = vne.last_fallback_priser()
    timer: list[dict[str, Any]] = []
    kilder = {"arkiv": 0, "fallback": 0}
    for iso in timenokler:
        if iso in kvarter:
            kv = kvarter[iso]
            timer.append(
                {
                    "start_local": iso,
                    "nok_per_kwh_eks_mva": sum(kv) / len(kv),
                    "kvarter": kv,
                    "kilde": "arkiv",
                }
            )
            kilder["arkiv"] += 1
        elif iso in fallback:
            timer.append(
                {
                    "start_local": iso,
                    "nok_per_kwh_eks_mva": fallback[iso],
                    "kvarter": None,
                    "kilde": "fallback",
                }
            )
            kilder["fallback"] += 1
        else:
            return None
    return {
        "metadata": {
            "navn": navn,
            "omrade": OMRADE,
            "revisjon": "final",
            "tidssone": "Europe/Oslo",
            "opplosning_minutter": 15,
            "timepris": "uvektet snitt av kvarterprisene, ingen mellomavrunding (A2)",
            "timer": len(timer),
            "kilder": kilder,
            "generert_av": "scripts/research/lag_replay_fixtures.py",
        },
        "hours": timer,
    }


def _skriv(sti: Path, data: dict[str, Any], sjekk: bool) -> bool:
    """Skriv filen, eller sammenlign mot disk når `sjekk`. True = i orden."""
    tekst = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    if sjekk:
        if not sti.exists():
            print(f"MANGLER {sti.relative_to(ROOT)}")
            return False
        if sti.read_text(encoding="utf-8") != tekst:
            print(f"AVVIK   {sti.relative_to(ROOT)}")
            return False
        print(f"ok      {sti.relative_to(ROOT)}")
        return True
    sti.write_text(tekst, encoding="utf-8")
    print(f"skrev   {sti.relative_to(ROOT)} ({sti.stat().st_size // 1024} kB)")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sjekk", action="store_true", help="Ikke skriv; feil hvis disk avviker")
    args = p.parse_args(argv if argv is not None else sys.argv[1:])

    if not PRIVAT.exists():
        print(f"{PRIVAT.relative_to(ROOT)} finnes ikke. Kjør `just snapshot-kurs` først.", file=sys.stderr)
        return 1

    alt_ok = True
    for navn in MANEDER:
        elhub = bygg_elhub(navn)
        if elhub is None:
            print(f"({navn}: ingen Elhub-CSV, hoppet over)")
        else:
            alt_ok &= _skriv(FIXTURES / f"elhub_{navn}.json", elhub, args.sjekk)

        # Prisfixturen følger timenøklene fra Elhub når de finnes, ellers
        # HAN-fixturens. Da dekker den de samme timene som energifasiten.
        if elhub is not None:
            nokler = [t["start_local"] for t in elhub["hours"]]
        else:
            han = FIXTURES / f"bkk_{navn}_hourly.json"
            if not han.exists():
                continue
            nokler = [h["start_local"] for h in json.loads(han.read_text(encoding="utf-8"))["hours"]]
        pris = bygg_final_pris(navn, nokler)
        if pris is None:
            print(f"({navn}: ufullstendig prisdekning, ingen final_pris-fixture)")
            continue
        alt_ok &= _skriv(FIXTURES / f"final_pris_{navn}.json", pris, args.sjekk)

    return 0 if alt_ok else 1


if __name__ == "__main__":
    sys.exit(main())
