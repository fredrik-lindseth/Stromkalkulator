"""Reproduserer NOK-omregning for Norgespris-kompensasjonen i BKK april 2026.

Henter EUR/NOK-kurser fra Norges Bank, regner ut implisitt EUR-snittpris
basert på HA's cachede NOK-priser og fakturas implisitte snittspot,
og sammenligner.

Kjøres uten avhengigheter utover Python 3 standardbibliotek.

Bakgrunn: se docs/research/nok-omregning.md
"""

from __future__ import annotations

import json
import urllib.request
from typing import Final

# --- Inputs fra empirisk undersøkelse 2026-05-22 ---

# Vektet snitt av sensor.nord_pool_no5_current_price (statistics.mean per time),
# vektet med sensor.pow_u_ams_tpi-delta (kWh per time) for april 2026.
# Beregnet i tests/fixtures/bkk_april_2026_hourly.json.
HA_CACHE_NOK_PER_KWH_EKS_MVA: Final[float] = 1.2284

# Faktura 012345683, BKK april 2026: Norgespris-snittpris -1.0333 kr/kWh.
# Implisitt snittspot inkl. mva = 0.50 - (-1.0333) = 1.5333 kr/kWh.
# (Norgespris-fastpris er 0.50 kr/kWh inkl. mva i NORGESPRIS_INKL_MVA_STANDARD.)
FAKTURA_SNITT_INKL_MVA: Final[float] = 1.5333

# Norges Bank SDMX-JSON API. NB-middelkurs er mid-point i interbankmarkedet
# ved 14:15 CET-snapshot, publisert ~16:00 CET (synket med ECB sin
# euro reference rate siden 1. juli 2016). Merk: dette er IKKE den kursen
# Nord Pool bruker. Nord Pool henter interbankkurs 12:00 CET og hedger
# senere med to banker for offisiell sluttkurs.
NB_URL: Final[str] = (
    "https://data.norges-bank.no/api/data/EXR/B.EUR.NOK.SP"
    "?startPeriod=2026-04-01&endPeriod=2026-04-30&format=sdmx-json"
)


def fetch_nb_eur_nok_rates() -> dict[str, float]:
    """Hent daglige EUR/NOK fra Norges Bank for april 2026."""
    with urllib.request.urlopen(NB_URL) as resp:
        data = json.loads(resp.read())

    obs = data["data"]["dataSets"][0]["series"]["0:0:0:0"]["observations"]
    periods = data["data"]["structure"]["dimensions"]["observation"][0]["values"]

    rates: dict[str, float] = {}
    for idx_str, val_list in obs.items():
        date = periods[int(idx_str)]["id"]
        rates[date] = float(val_list[0])
    return rates


def main() -> None:
    rates = fetch_nb_eur_nok_rates()
    avg_nb = sum(rates.values()) / len(rates)

    print(f"=== NB EUR/NOK april 2026 ({len(rates)} bankdager) ===")
    print(f"  Første:           {min(rates.items())}")
    print(f"  Siste:            {max(rates.items())}")
    print(f"  Aritmetisk snitt: {avg_nb:.4f} NOK/EUR")
    print()

    faktura_eks_mva = FAKTURA_SNITT_INKL_MVA / 1.25

    print("=== Sammenligning NOK/kWh eks. mva ===")
    print(f"  HA-cache (vektet snitt): {HA_CACHE_NOK_PER_KWH_EKS_MVA:.4f} NOK/kWh")
    print(f"  Faktura (implisitt):     {faktura_eks_mva:.4f} NOK/kWh")
    diff_nok = HA_CACHE_NOK_PER_KWH_EKS_MVA - faktura_eks_mva
    pct = diff_nok / faktura_eks_mva * 100
    print(f"  Differanse:              {diff_nok:+.4f} NOK/kWh ({pct:+.3f}%)")
    print()

    ha_eur_mwh = HA_CACHE_NOK_PER_KWH_EKS_MVA * 1000 / avg_nb
    fakt_eur_mwh = faktura_eks_mva * 1000 / avg_nb

    print(f"=== Implisitt EUR/MWh (med NB-snittkurs {avg_nb:.3f}) ===")
    print(f"  HA-cache: {ha_eur_mwh:.3f} EUR/MWh")
    print(f"  Faktura:  {fakt_eur_mwh:.3f} EUR/MWh")
    diff_eur = ha_eur_mwh - fakt_eur_mwh
    print(f"  Diff:     {diff_eur:+.3f} EUR/MWh ({diff_eur/fakt_eur_mwh*100:+.3f}%)")
    print()

    implied_kurs = HA_CACHE_NOK_PER_KWH_EKS_MVA * 1000 / fakt_eur_mwh
    print("=== Reverse: hvilken EUR/NOK-kurs ville matchet faktura? ===")
    print(f"  Implisitt: {implied_kurs:.4f} NOK/EUR")
    print(f"  NB-snitt:  {avg_nb:.4f} NOK/EUR")
    print(f"  Diff:      {implied_kurs - avg_nb:+.4f}")
    print()
    print("Tolkning: BKK bruker enten litt annen snittberegning av samme kurs")
    print("(forbruksvektet vs aritmetisk), eller en annen kurskilde enn NB.")
    print("Avviket er innenfor 0.15% og forklarer Norgespris-restavviket.")


if __name__ == "__main__":
    main()
