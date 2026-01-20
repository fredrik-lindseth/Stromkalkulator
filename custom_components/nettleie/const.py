"""Constants for Nettleie integration."""
from typing import Final

DOMAIN: Final = "nettleie"

# Config keys
CONF_POWER_SENSOR: Final = "power_sensor"
CONF_SPOT_PRICE_SENSOR: Final = "spot_price_sensor"
CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: Final = "electricity_provider_price_sensor"
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
        "energiledd_dag": 0.3640,  # 36,40 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2640,  # 26,40 øre/kWh inkl. avgifter (2026)
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
        # Trinn 1-5 fra nettside, trinn 6-10 fra PDF tariffblad_1_0_standard-tariff_privat_20260101.pdf
        "kapasitetstrinn": [
            (2, 125),
            (5, 190),
            (10, 300),
            (15, 410),
            (20, 520),
            (25, 655),   # Fra PDF
            (50, 1135),  # Fra PDF
            (75, 1750),  # Fra PDF
            (100, 2370), # Fra PDF
            (float("inf"), 4225),  # Fra PDF
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
        "energiledd_dag": 0.3604,  # 36,04 øre/kWh (2026, Trondheim)
        "energiledd_natt": 0.2292,  # 22,92 øre/kWh (2026, Trondheim)
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "kapasitetstrinn": [
            (2, 122),
            (5, 218),
            (10, 371),
            (15, 547),
            (20, 724),
            (25, 901),
            (50, 1547),
            (75, 2429),
            (100, 3312),
            (150, 4782),
            (200, 6545),
            (300, 9483),
            (400, 13014),
            (500, 16539),
            (float("inf"), 20068),
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

# Offentlige avgifter (øre/kWh eks. mva, oppdateres årlig)
# Kilde: https://www.skatteetaten.no/satser/elektrisk-kraft/
FORBRUKSAVGIFT: Final = 0.1669  # 16,69 øre/kWh (2025)
ENOVA_AVGIFT: Final = 0.0125  # 1,25 øre/kWh (fast)
MVA_SATS: Final = 0.25  # 25% mva

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
