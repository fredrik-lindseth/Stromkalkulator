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
        "name": "BKK (Bergen)",
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
