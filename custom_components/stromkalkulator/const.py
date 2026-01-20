"""Constants for Strømkalkulator integration."""
from typing import Final

DOMAIN: Final = "stromkalkulator"

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
    "lede": {
        "name": "Lede",
        "energiledd_dag": 0.3048,  # 30,48 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3048,  # Ingen dag/natt-forskjell
        "url": "https://www.lede.no/nettleie/nettleiepriser",
        "kapasitetstrinn": [
            (5, 294),    # 0-5 kW: 293,75 kr/mnd
            (10, 503),   # 5-10 kW: 502,50 kr/mnd
            (15, 708),   # 10-15 kW: 707,50 kr/mnd
            (20, 916),   # 15-20 kW: 916,25 kr/mnd
            (25, 1124),  # 20-25 kW: 1123,75 kr/mnd
            (float("inf"), 1746),  # 25-50 kW: 1746,25 kr/mnd
        ],
    },
    "lnett": {
        "name": "Lnett",
        "energiledd_dag": 0.32,  # 32 øre/kWh inkl. mva (2026)
        "energiledd_natt": 0.17,  # 17 øre/kWh inkl. mva (2026)
        "url": "https://www.l-nett.no/nettleie/nettleiepriser-privat",
        "kapasitetstrinn": [
            (2, 150),    # 0-2 kW: 150 kr/mnd
            (5, 250),    # 2-5 kW: 250 kr/mnd
            (10, 400),   # 5-10 kW: 400 kr/mnd
            (15, 650),   # 10-15 kW: 650 kr/mnd
            (20, 900),   # 15-20 kW: 900 kr/mnd
            (float("inf"), 1150),  # 20-25 kW: 1150 kr/mnd
        ],
    },
    "norgesnett": {
        "name": "Norgesnett",
        "energiledd_dag": 0.3549,  # 35,49 øre/kWh inkl. mva (2026, dag 06-22)
        "energiledd_natt": 0.2677,  # 26,77 øre/kWh inkl. mva (2026, natt 22-06)
        "url": "https://norgesnett.no/kunde/nettleie/nettleiepriser/",
        "kapasitetstrinn": [
            (2, 118),    # 0-2 kW: 117,89 kr/mnd
            (5, 196),    # 2-5 kW: 196,49 kr/mnd
            (10, 323),   # 5-10 kW: 323,12 kr/mnd
            (15, 575),   # 10-15 kW: 574,63 kr/mnd
            (20, 763),   # 15-20 kW: 763,25 kr/mnd
            (25, 947),   # 20-25 kW: 946,65 kr/mnd
            (50, 1467),  # 25-50 kW: 1467,13 kr/mnd
            (75, 2297),  # 50-75 kW: 2296,76 kr/mnd
            (100, 3126), # 75-100 kW: 3126,38 kr/mnd
            (float("inf"), 5067),  # >100 kW: 5066,84 kr/mnd
        ],
    },
    "arva": {
        "name": "Arva",
        "energiledd_dag": 0.231,  # 23,1 øre/kWh inkl. mva (2026, dag 06-22)
        "energiledd_natt": 0.116,  # 11,6 øre/kWh inkl. mva (2026, natt 22-06)
        "url": "https://www.arva.no/kunde/nettleie/nettleiepriser",
        "kapasitetstrinn": [
            (2, 85),     # 0-2 kW: 85 kr/mnd
            (5, 201),    # 2-5 kW: 201 kr/mnd
            (10, 398),   # 5-10 kW: 398 kr/mnd
            (15, 595),   # 10-15 kW: 595 kr/mnd
            (20, 792),   # 15-20 kW: 792 kr/mnd
            (25, 989),   # 20-25 kW: 989 kr/mnd
            (50, 1972),  # 25-50 kW: 1972 kr/mnd
            (75, 2955),  # 50-75 kW: 2955 kr/mnd
            (100, 3938), # 75-100 kW: 3938 kr/mnd
            (float("inf"), 5945),  # >100 kW: 5945 kr/mnd
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
DEFAULT_NAME: Final = "Strømkalkulator"
