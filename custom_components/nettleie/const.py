"""Constants for Nettleie integration."""
from typing import Final

DOMAIN: Final = "nettleie"

# Config keys
CONF_POWER_SENSOR: Final = "power_sensor"
CONF_SPOT_PRICE_SENSOR: Final = "spot_price_sensor"
CONF_TSO: Final = "tso"
CONF_ENERGILEDD_DAG: Final = "energiledd_dag"
CONF_ENERGILEDD_NATT: Final = "energiledd_natt"
# Transmission System Operators (TSO) with default values
# Format: {tso_id: {name, energiledd_dag, energiledd_natt, kapasitetstrinn}}
TSO_LIST: Final = {
    "bkk": {
        "name": "BKK",
        "energiledd_dag": 0.4613,
        "energiledd_natt": 0.2329,
        "url": "https://www.bkk.no/nettleiepriser/priser-privatkunder",
        "kapasitetstrinn": [
            (2, 155),
            (5, 250),
            (10, 415),
            (15, 600),
            (20, 770),
            (25, 940),
            (50, 1800),
            (75, 2650),
            (100, 3500),
            (float("inf"), 6900),
        ],
    },
    "elvia": {
        "name": "Elvia",
        "energiledd_dag": 0.3979,  # 31,83 øre/kWh inkl. avgifter
        "energiledd_natt": 0.2479,  # 19,83 øre/kWh inkl. avgifter
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
        "kapasitetstrinn": [
            (2, 176),
            (5, 276),
            (10, 436),
            (15, 636),
            (20, 836),
            (25, 1061),
            (50, 1836),
            (75, 2836),
            (100, 3836),
            (float("inf"), 6836),
        ],
    },
    "glitre": {
        "name": "Glitre Nett",
        "energiledd_dag": 0.4091,  # 40,91 øre/kWh inkl. avgifter (fra 1. jan 2026)
        "energiledd_natt": 0.2591,  # 25,91 øre/kWh inkl. avgifter (fra 1. jan 2026)
        "url": "https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde",
        "kapasitetstrinn": [
            (2, 160),
            (5, 205),
            (10, 350),
            (15, 725),
            (20, 940),
            (25, 1180),
            (50, 1825),
            (75, 2890),
            (100, 3850),
            (float("inf"), 6250),
        ],
    },
    "tensio": {
        "name": "Tensio",
        "energiledd_dag": 0.3850,  # Ca. 38,50 øre/kWh inkl. avgifter
        "energiledd_natt": 0.2350,  # Ca. 23,50 øre/kWh inkl. avgifter
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "kapasitetstrinn": [
            (2, 175),
            (5, 262),
            (10, 437),
            (15, 625),
            (20, 812),
            (25, 1000),
            (50, 1750),
            (75, 2625),
            (100, 3500),
            (float("inf"), 6125),
        ],
    },
    "custom": {
        "name": "Egendefinert",
        "energiledd_dag": 0.40,
        "energiledd_natt": 0.20,
        "url": "",
        "kapasitetstrinn": [
            (2, 150),
            (5, 250),
            (10, 400),
            (15, 600),
            (20, 800),
            (25, 1000),
            (50, 1800),
            (75, 2600),
            (100, 3500),
            (float("inf"), 7000),
        ],
    },
}

# Default values (BKK)
DEFAULT_ENERGILEDD_DAG: Final = 0.4613
DEFAULT_ENERGILEDD_NATT: Final = 0.2329
DEFAULT_TSO: Final = "bkk"

# Strømstøtte
STROMSTOTTE_LEVEL: Final = 0.9125
STROMSTOTTE_RATE: Final = 0.9

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
DEFAULT_NAME: Final = "Nettleie"
