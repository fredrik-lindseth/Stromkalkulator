"""Constants for Strømkalkulator integration."""
from typing import Final

from .tso import TSO_LIST  # noqa: F401 - re-exported for backward compatibility

DOMAIN: Final = "stromkalkulator"

# Config keys
CONF_POWER_SENSOR: Final = "power_sensor"
CONF_SPOT_PRICE_SENSOR: Final = "spot_price_sensor"
CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: Final = "electricity_provider_price_sensor"
CONF_TSO: Final = "tso"
CONF_ENERGILEDD_DAG: Final = "energiledd_dag"
CONF_ENERGILEDD_NATT: Final = "energiledd_natt"
CONF_AVGIFTSSONE: Final = "avgiftssone"

# Avgiftssoner for forbruksavgift og mva
# - standard: Full forbruksavgift + mva (Sør-Norge: NO1, NO2, NO5)
# - nord_norge: Redusert forbruksavgift + mva-fritak (Nordland, Troms utenom tiltakssonen)
# - tiltakssone: Forbruksavgift-fritak + mva-fritak (Finnmark + 7 kommuner i Nord-Troms)
AVGIFTSSONE_STANDARD: Final = "standard"
AVGIFTSSONE_NORD_NORGE: Final = "nord_norge"
AVGIFTSSONE_TILTAKSSONE: Final = "tiltakssone"

AVGIFTSSONE_OPTIONS: Final = {
    AVGIFTSSONE_STANDARD: "Sør-Norge (full avgift + mva)",
    AVGIFTSSONE_NORD_NORGE: "Nord-Norge (redusert avgift, mva-fritak)",
    AVGIFTSSONE_TILTAKSSONE: "Tiltakssonen (avgiftsfritak, mva-fritak)",
}


# Default values (BKK)
DEFAULT_ENERGILEDD_DAG: Final = 0.4613
DEFAULT_ENERGILEDD_NATT: Final = 0.2329
DEFAULT_TSO: Final = "bkk"

# Strømstøtte
# Kilde: https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
#
# Historikk (terskelverdi eks. mva → inkl. 25% mva):
# - 2021 (des): 70 øre eks. mva → 87,50 øre inkl. mva, 55% kompensasjon
# - 2022 (jan-aug): 70 øre → 87,50 øre, 80% kompensasjon
# - 2022 (sep) - 2023 (aug): 70 øre → 87,50 øre, 90% kompensasjon (med unntak apr-mai 2023: 80%)
# - 2023 (sep-des): 70 øre → 87,50 øre, 90% kompensasjon, time-for-time
# - 2024: 73 øre eks. mva → 91,25 øre inkl. mva, 90% kompensasjon
# - 2025: 75 øre eks. mva → 93,75 øre inkl. mva, 90% kompensasjon
# - 2026+: Ikke fastsatt ennå, antar samme som 2025
#
# Merk: Fra 1. oktober 2025 kan husholdninger velge Norgespris (40 øre/kWh eks. mva)
# som alternativ til strømstøtte. Se NORGESPRIS_* konstantene.
#
# Verdiene under er inkl. mva (spotpris fra Nord Pool er inkl. mva)
STROMSTOTTE_LEVEL: Final = 0.9375  # 75 øre eks. mva × 1,25 = 93,75 øre inkl. mva (2025)
STROMSTOTTE_RATE: Final = 0.9  # 90% kompensasjon over terskel

# Norgespris (fra 1. oktober 2025)
# Kilde: https://www.regjeringen.no/no/tema/energi/strom/regjeringens-stromtiltak/id2900232/
#
# Norgespris er en valgfri ordning der husholdninger får strøm til fast pris.
# Pris: 40 øre/kWh eks. mva (50 øre/kWh inkl. mva i Sør-Norge, 40 øre i Nord-Norge pga mva-fritak)
# Grenser: 5000 kWh/mnd for bolig, 1000 kWh/mnd for fritidsbolig
# Bindingstid: Ut kalenderåret, må velges på nytt hvert år
#
# NB: Strømkalkulator beregner strømstøtte automatisk. Hvis bruker har Norgespris,
# bør de bruke sensor uten strømstøtte eller sette opp manuell pris.
NORGESPRIS_EKS_MVA: Final = 0.40  # 40 øre/kWh eks. mva (2025-2026)
NORGESPRIS_INKL_MVA: Final = 0.50  # 50 øre/kWh inkl. mva (Sør-Norge)
NORGESPRIS_MAX_KWH_BOLIG: Final = 5000  # Max 5000 kWh/mnd for bolig
NORGESPRIS_MAX_KWH_FRITID: Final = 1000  # Max 1000 kWh/mnd for fritidsbolig

# Offentlige avgifter (NOK/kWh eks. mva, oppdateres årlig)
# Kilde: https://www.skatteetaten.no/bedrift-og-organisasjon/avgifter/saravgifter/om/elektrisk-kraft/
#
# Forbruksavgift 2026 (NYTT fra 2026 - forenklet struktur):
# - Alminnelig sats: 7,13 øre/kWh hele året (ingen sesongvariasjon)
# - Redusert sats: 0,60 øre/kWh (industri, bergverk, fjernvarme, skip, næringsvirksomhet i tiltakssonen)
# - Fritak: 0 øre/kWh (husholdninger i tiltakssonen, veksthus, tog, solceller m.m.)
#
# For husholdninger:
# - Sør-Norge (NO1, NO2, NO5): 7,13 øre/kWh (alminnelig sats)
# - Nord-Norge (NO3, NO4): 7,13 øre/kWh (alminnelig sats, samme som Sør-Norge fra 2026)
# - Tiltakssonen (Finnmark + 7 kommuner i Nord-Troms): 0 øre/kWh (fritak)
#
# Enova-avgift: 1,0 øre/kWh (alle regioner, hele året, også i tiltakssonen)
# MVA: 25% i Sør-Norge, fritak for husholdninger i Nord-Norge og tiltakssonen
#
# For 2027-satser, sjekk: https://www.skatteetaten.no/satser/elektrisk-kraft/

# 2026: Flat sats hele året, ingen sesongvariasjon
FORBRUKSAVGIFT_ALMINNELIG: Final = 0.0713  # 7,13 øre/kWh eks. mva (husholdninger)
FORBRUKSAVGIFT_REDUSERT: Final = 0.0060    # 0,60 øre/kWh eks. mva (næring i tiltakssonen)

ENOVA_AVGIFT: Final = 0.01  # 1,0 øre/kWh eks. mva (fast, alle regioner inkl. tiltakssonen)
MVA_SATS: Final = 0.25  # 25% mva


def get_forbruksavgift(avgiftssone: str, month: int) -> float:
    """Get forbruksavgift based on avgiftssone.

    Fra 2026 er det flat sats hele året (ingen sesongvariasjon).
    Month-parameteren beholdes for bakoverkompatibilitet.

    Args:
        avgiftssone: One of 'standard', 'nord_norge', 'tiltakssone'
        month: Month number (1-12) - ikke lenger brukt fra 2026

    Returns:
        Forbruksavgift in NOK/kWh (eks. mva)
    """
    # Tiltakssonen har fritak for forbruksavgift (husholdninger)
    if avgiftssone == AVGIFTSSONE_TILTAKSSONE:
        return 0.0

    # Fra 2026: Samme sats for alle husholdninger (standard og nord_norge)
    # Alminnelig sats: 7,13 øre/kWh hele året
    return FORBRUKSAVGIFT_ALMINNELIG


def get_mva_sats(avgiftssone: str) -> float:
    """Get MVA rate based on avgiftssone.

    Args:
        avgiftssone: One of 'standard', 'nord_norge', 'tiltakssone'

    Returns:
        MVA rate (0.0 or 0.25)
    """
    # Nord-Norge og tiltakssonen har mva-fritak for husholdninger
    if avgiftssone in (AVGIFTSSONE_NORD_NORGE, AVGIFTSSONE_TILTAKSSONE):
        return 0.0
    return MVA_SATS


def get_default_avgiftssone(prisomrade: str) -> str:
    """Get default avgiftssone based on price area.

    Args:
        prisomrade: Price area (NO1-NO5)

    Returns:
        Default avgiftssone for the price area
    """
    if prisomrade in ("NO3", "NO4"):
        return AVGIFTSSONE_NORD_NORGE
    return AVGIFTSSONE_STANDARD

# Helligdager (YYYY-MM-DD for bevegelige, MM-DD for faste)
# Faste helligdager
HELLIGDAGER_FASTE: Final = [
    "01-01",  # Nyttårsdag
    "05-01",  # Arbeidernes dag
    "05-17",  # Grunnlovsdag
    "12-25",  # 1. juledag
    "12-26",  # 2. juledag
]

# Bevegelige helligdager (må oppdateres årlig)
HELLIGDAGER_BEVEGELIGE: Final = [
    # 2026
    "2026-04-02",  # Skjærtorsdag
    "2026-04-03",  # Langfredag
    "2026-04-05",  # 1. påskedag
    "2026-04-06",  # 2. påskedag
    "2026-05-14",  # Kristi himmelfartsdag
    "2026-05-24",  # 1. pinsedag
    "2026-05-25",  # 2. pinsedag
    # 2027
    "2027-03-25",  # Skjærtorsdag
    "2027-03-26",  # Langfredag
    "2027-03-28",  # 1. påskedag
    "2027-03-29",  # 2. påskedag
    "2027-05-06",  # Kristi himmelfartsdag
    "2027-05-16",  # 1. pinsedag
    "2027-05-17",  # 2. pinsedag (sammenfaller med 17. mai)
]

# Sensor types
SENSOR_ENERGILEDD: Final = "energiledd"
SENSOR_KAPASITETSTRINN: Final = "kapasitetstrinn"
SENSOR_TOTAL_PRICE: Final = "total_price"

# Defaults
DEFAULT_NAME: Final = "Strømkalkulator"
