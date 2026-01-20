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
# Transmission System Operators (TSO) with default values
# Format: {tso_id: {name, prisomrade, supported, energiledd_dag, energiledd_natt, url, kapasitetstrinn}}
#
# supported: True = har priser, False = mangler priser (trenger bidrag)
# For å legge til priser for et nettselskap:
# 1. Finn nettleiepriser på nettselskapets nettside (url-feltet)
# 2. Sett energiledd_dag og energiledd_natt i NOK/kWh (inkl. avgifter)
# 3. Legg til kapasitetstrinn som liste med tupler: (kW-grense, kr/mnd)
# 4. Sett supported til True
TSO_LIST: Final = {
    "bkk": {
        "name": "BKK",
        "prisomrade": "NO5",
        "supported": True,
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
        "prisomrade": "NO1",
        "supported": True,
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
        "prisomrade": "NO1",
        "supported": True,
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
        "prisomrade": "NO3",
        "supported": True,
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
        "prisomrade": "NO2",
        "supported": True,
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
        "prisomrade": "NO2",
        "supported": True,
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
        "prisomrade": "NO1",
        "supported": True,
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
        "prisomrade": "NO4",
        "supported": True,
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
    "fagne": {
        "name": "Fagne",
        "prisomrade": "NO2",
        "supported": True,
        "energiledd_dag": 0.4516,  # 45,16 øre/kWh inkl. mva (2026, dag 06-22)
        "energiledd_natt": 0.3516,  # 35,16 øre/kWh inkl. mva (2026, natt 22-06)
        "url": "https://fagne.no/kunde-og-nettleie/nettleie-priser-og-vilkar/priser-privatkunder/",
        "kapasitetstrinn": [
            (5, 360),    # 0-5 kW: 360 kr/mnd
            (10, 460),   # 5-10 kW: 460 kr/mnd
            (15, 560),   # 10-15 kW: 560 kr/mnd
            (20, 660),   # 15-20 kW: 660 kr/mnd
            (25, 760),   # 20-25 kW: 760 kr/mnd
            (50, 2200),  # 25-50 kW: 2200 kr/mnd
            (75, 3200),  # 50-75 kW: 3200 kr/mnd
            (100, 4200), # 75-100 kW: 4200 kr/mnd
            (float("inf"), 5200),  # >100 kW: 5200 kr/mnd
        ],
    },
    "foie": {
        "name": "Føie",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag": 0.3079,  # 30,79 øre/kWh inkl. mva (2026, dag 06-22)
        "energiledd_natt": 0.2266,  # 22,66 øre/kWh inkl. mva (2026, natt 22-06)
        "url": "https://www.foie.no/nettleie/priser",
        "kapasitetstrinn": [
            (2, 238),    # 0-2 kW: 237,5 kr/mnd
            (5, 294),    # 2-5 kW: 293,8 kr/mnd
            (10, 419),   # 5-10 kW: 418,8 kr/mnd
            (15, 663),   # 10-15 kW: 662,5 kr/mnd
            (20, 838),   # 15-20 kW: 837,5 kr/mnd
            (25, 1075),  # 20-25 kW: 1075 kr/mnd
            (50, 1438),  # 25-50 kW: 1437,5 kr/mnd
            (75, 2375),  # 50-75 kW: 2375 kr/mnd
            (float("inf"), 3000),  # 75+ kW: 3000 kr/mnd
        ],
    },
    "linea": {
        "name": "Linea",
        "prisomrade": "NO4",
        "supported": True,
        # Helgeland (NO4) - mva-fritak for husholdninger
        # Priser eks. avgifter: dag 23,5, natt 13,5 øre/kWh
        # + forbruksavgift 9,16 + Enova 1,0 = totalt dag 33,66, natt 23,66 øre/kWh
        "energiledd_dag": 0.3366,  # 33,66 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.2366,  # 23,66 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://www.linea.no/no/kunde/nettleie/nettleiepriser",
        "kapasitetstrinn": [
            (2, 225),    # 0-2 kW: 225 kr/mnd
            (5, 225),    # 2-5 kW: 225 kr/mnd
            (10, 349),   # 5-10 kW: 349 kr/mnd
            (15, 491),   # 10-15 kW: 491 kr/mnd
            (20, 633),   # 15-20 kW: 633 kr/mnd
            (25, 776),   # 20-25 kW: 776 kr/mnd
            (50, 1297),  # 25-50 kW: 1297 kr/mnd
            (75, 2008),  # 50-75 kW: 2008 kr/mnd
            (100, 2719), # 75-100 kW: 2719 kr/mnd
            (150, 3905), # 100-150 kW: 3905 kr/mnd
            (200, 5326), # 150-200 kW: 5326 kr/mnd
            (300, 7693), # 200-300 kW: 7693 kr/mnd
            (400, 10541), # 300-400 kW: 10541 kr/mnd
            (500, 13383), # 400-500 kW: 13383 kr/mnd
            (float("inf"), 16228),  # 500+ kW: 16228 kr/mnd
        ],
    },
    "noranett": {
        "name": "Noranett",
        "prisomrade": "NO4",
        "supported": True,
        # Hålogaland (NO4) - mva-fritak for husholdninger
        # Priser eks. avgifter: 0,8 øre/kWh (ingen dag/natt-forskjell)
        # + forbruksavgift 9,16 + Enova 1,0 = totalt 10,96 øre/kWh
        "energiledd_dag": 0.1096,  # 10,96 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.1096,  # 10,96 øre/kWh inkl. avgifter (2026)
        "url": "https://www.noranett.no/nettleiepriser/category2415.html",
        "kapasitetstrinn": [
            (2, 310),    # 0-2 kW: 310 kr/mnd
            (4, 440),    # 2-4 kW: 440 kr/mnd
            (6, 530),    # 4-6 kW: 530 kr/mnd
            (8, 610),    # 6-8 kW: 610 kr/mnd
            (10, 680),   # 8-10 kW: 680 kr/mnd
            (15, 750),   # 10-15 kW: 750 kr/mnd
            (20, 890),   # 15-20 kW: 890 kr/mnd
            (25, 1200),  # 20-25 kW: 1200 kr/mnd
            (30, 1400),  # 25-30 kW: 1400 kr/mnd
            (35, 1700),  # 30-35 kW: 1700 kr/mnd
            (40, 1900),  # 35-40 kW: 1900 kr/mnd
            (45, 2100),  # 40-45 kW: 2100 kr/mnd
            (50, 2400),  # 45-50 kW: 2400 kr/mnd
            (75, 3600),  # 50-75 kW: 3600 kr/mnd
            (100, 5300), # 75-100 kW: 5300 kr/mnd
            (125, 7100), # 100-125 kW: 7100 kr/mnd
            (150, 8900), # 125-150 kW: 8900 kr/mnd
            (175, 10700), # 150-175 kW: 10700 kr/mnd
            (200, 12500), # 175-200 kW: 12500 kr/mnd
            (float("inf"), 17800),  # 200+ kW: 17800 kr/mnd
        ],
    },
    "elinett": {
        "name": "Elinett",
        "prisomrade": "NO3",
        "supported": True,
        "energiledd_dag": 0.3846,  # 38,46 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.2846,  # 28,46 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://www.elinett.no/kunde/nettleie-2/nettleie",
        "kapasitetstrinn": [
            (2, 251),    # 0-2 kW: 251 kr/mnd
            (5, 314),    # 2-5 kW: 314 kr/mnd
            (10, 376),   # 5-10 kW: 376 kr/mnd
            (15, 627),   # 10-15 kW: 627 kr/mnd
            (20, 753),   # 15-20 kW: 753 kr/mnd
            (25, 878),   # 20-25 kW: 878 kr/mnd
            (50, 1254),  # 25-50 kW: 1254 kr/mnd
            (75, 1379),  # 50-75 kW: 1379 kr/mnd
            (100, 1505), # 75-100 kW: 1505 kr/mnd
            (float("inf"), 1881),  # >100 kW: 1881 kr/mnd
        ],
    },
    "mellom": {
        "name": "Mellom",
        "prisomrade": "NO3",
        "supported": True,
        "energiledd_dag": 0.3721,  # 37,21 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.2934,  # 29,34 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://mellom.no/nettleiepriser/",
        "kapasitetstrinn": [
            (2, 254),    # 0-2 kW: 254 kr/mnd
            (5, 380),    # 2-5 kW: 380 kr/mnd
            (10, 631),   # 5-10 kW: 631 kr/mnd
            (15, 834),   # 10-15 kW: 834 kr/mnd
            (20, 1056),  # 15-20 kW: 1056 kr/mnd
            (25, 1323),  # 20-25 kW: 1323 kr/mnd
            (50, 1666),  # 25-50 kW: 1666 kr/mnd
            (float("inf"), 2226),  # >50 kW: 2226 kr/mnd
        ],
    },
    "linja": {
        "name": "Linja",
        "prisomrade": "NO5",
        "supported": True,
        "energiledd_dag": 0.3814,  # 38,14 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.2939,  # 29,39 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://www.linja.no/nettleige",
        "kapasitetstrinn": [
            (2, 275),    # 0-2 kW: 275 kr/mnd
            (5, 343),    # 2-5 kW: 343 kr/mnd
            (10, 411),   # 5-10 kW: 411 kr/mnd
            (15, 686),   # 10-15 kW: 686 kr/mnd
            (20, 824),   # 15-20 kW: 824 kr/mnd
            (25, 960),   # 20-25 kW: 960 kr/mnd
            (50, 1373),  # 25-50 kW: 1373 kr/mnd
            (75, 1510),  # 50-75 kW: 1510 kr/mnd
            (100, 1646), # 75-100 kW: 1646 kr/mnd
            (float("inf"), 2059),  # >100 kW: 2059 kr/mnd
        ],
    },
    "nettselskapet": {
        "name": "Nettselskapet",
        "prisomrade": "NO3",
        "supported": True,
        # Har ulike sommer/vinter-priser, bruker vinterpriser (høyest)
        # Vinter dag: 15,88 øre + 9,16 (elavgift) + 1,0 (Enova) = 26,04 øre/kWh
        # Vinter natt: 3,38 øre + 9,16 + 1,0 = 13,54 øre/kWh
        "energiledd_dag": 0.2604,  # 26,04 øre/kWh inkl. avgifter (2026, vinter dag)
        "energiledd_natt": 0.1354,  # 13,54 øre/kWh inkl. avgifter (2026, vinter natt)
        "url": "https://nettselskapet.as/strompris",
        "kapasitetstrinn": [
            (2, 138),    # 0-2 kW: 137,50 kr/mnd
            (5, 250),    # 2-5 kW: 250 kr/mnd
            (10, 425),   # 5-10 kW: 425 kr/mnd
            (15, 625),   # 10-15 kW: 625 kr/mnd
            (20, 813),   # 15-20 kW: 812,50 kr/mnd
            (25, 1025),  # 20-25 kW: 1025 kr/mnd
            (50, 1750),  # 25-50 kW: 1750 kr/mnd
            (float("inf"), 2750),  # 50-75 kW: 2750 kr/mnd
        ],
    },
    "custom": {
        "name": "Egendefinert",
        "prisomrade": "NO1",  # Default til NO1, kan overstyres i config
        "supported": True,
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
    # =========================================================================
    # Nettselskaper som mangler priser (supported: False)
    # Bidra gjerne med priser! Se README.md for instruksjoner.
    # =========================================================================
    "alut": {
        "name": "Alut",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "area_nett": {
        "name": "Area Nett",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "asker_nett": {
        "name": "Asker Nett",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "barents_nett": {
        "name": "Barents Nett",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "bindal_kraftnett": {
        "name": "Bindal Kraftnett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "breheim_nett": {
        "name": "Breheim Nett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "bomlo_kraftnett": {
        "name": "Bømlo Kraftnett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "de_nett": {
        "name": "De Nett",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "elmea": {
        "name": "Elmea",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "enida": {
        "name": "Enida",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "everket": {
        "name": "Everket",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "fjellnett": {
        "name": "Fjellnett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "fore": {
        "name": "Føre",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "griug": {
        "name": "Griug",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "haringnett": {
        "name": "Haringnett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "havnett": {
        "name": "Havnett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "holand_setskog": {
        "name": "Høland og Setskog Elverk",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "indre_hordaland": {
        "name": "Indre Hordaland Kraftnett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "jaren_everk": {
        "name": "Jæren Everk",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "ke_nett": {
        "name": "KE Nett",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "klive": {
        "name": "Klive",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "kystnett": {
        "name": "Kystnett",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "lucerna": {
        "name": "Lucerna",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "lysna": {
        "name": "Lysna",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "meloy_energi": {
        "name": "Meløy Energi",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "midtnett": {
        "name": "Midtnett",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "modalen_kraftlag": {
        "name": "Modalen Kraftlag",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "netera": {
        "name": "Netera",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "noranett_andoy": {
        "name": "Noranett Andøy",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "noranett_hadsel": {
        "name": "Noranett Hadsel",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "nordvest_nett": {
        "name": "Nordvest Nett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "norefjell_nett": {
        "name": "Norefjell Nett",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "r_nett": {
        "name": "R-Nett",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "rakkestad_energi": {
        "name": "Rakkestad Energi",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "rk_nett": {
        "name": "RK Nett",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "romsdalsnett": {
        "name": "Romsdalsnett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "s_nett": {
        "name": "S-Nett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "skjakernett": {
        "name": "Skjåkernett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "stannum": {
        "name": "Stannum",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "stram": {
        "name": "Stram",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "straumen_nett": {
        "name": "Straumen Nett",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "straumnett": {
        "name": "Straumnett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "svabo_industrinett": {
        "name": "Svabo Industrinett",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "sygnir": {
        "name": "Sygnir",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "sor_aurdal_energi": {
        "name": "Sør Aurdal Energi",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "tendranett": {
        "name": "Tendranett",
        "prisomrade": "NO5",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "telemark_nett": {
        "name": "Telemark Nett",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "uvdal_kraftforsyning": {
        "name": "Uvdal Kraftforsyning",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "vang_energiverk": {
        "name": "Vang Energiverk",
        "prisomrade": "NO1",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "vestall": {
        "name": "Vestall",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "vestmar_nett": {
        "name": "Vestmar Nett",
        "prisomrade": "NO2",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "vevig": {
        "name": "Vevig",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "viermie": {
        "name": "Viermie",
        "prisomrade": "NO3",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
    "vissi": {
        "name": "Vissi",
        "prisomrade": "NO4",
        "supported": False,
        "energiledd_dag": 0,
        "energiledd_natt": 0,
        "url": "",
        "kapasitetstrinn": [],
    },
}

# Default values (BKK)
DEFAULT_ENERGILEDD_DAG: Final = 0.4613
DEFAULT_ENERGILEDD_NATT: Final = 0.2329
DEFAULT_TSO: Final = "bkk"

# Strømstøtte
STROMSTOTTE_LEVEL: Final = 0.9125
STROMSTOTTE_RATE: Final = 0.9

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
