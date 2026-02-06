"""Transmission System Operators (nettselskap) data for Strømkalkulator.

Alle priser er hentet fra nettselskapenes offisielle nettsider (se url-felt).
Prisene er oppgitt i NOK/kWh inkl. mva (Sør-Norge) eller eks. mva (Nord-Norge).

Kilde for nettselskap-liste: Elhub (https://elhub.no/nettselskaper/)
Kilde for kapasitetstrinn-struktur: NVE (https://www.nve.no/reguleringsmyndigheten/)

Sist oppdatert: Januar 2026 (2026-priser)
"""

from typing import Final, NotRequired, TypedDict

# Type for kapasitetstrinn: tuple of (kW-grense, kr/mnd)
type KapasitetstrinnTuple = tuple[float, int]


# Type for kapasitetstrinn dict format (used by some TSOs like Barents Nett)
class KapasitetstrinnDict(TypedDict):
    """Kapasitetstrinn entry in dict format."""

    min: int
    max: int
    pris: int


class TSOEntry(TypedDict):
    """Type definition for a TSO (Transmission System Operator) entry."""

    name: str
    prisomrade: str
    supported: bool
    energiledd_dag: float
    energiledd_natt: float
    url: str
    kapasitetstrinn: list[KapasitetstrinnTuple | KapasitetstrinnDict]
    tiltakssone: NotRequired[bool]


# Transmission System Operators (TSO) with default values
# Format: {tso_id: {name, prisomrade, supported, energiledd_dag, energiledd_natt, url, kapasitetstrinn}}
#
# supported: True = har priser, False = mangler priser (trenger bidrag)
# For å legge til priser for et nettselskap:
# 1. Finn nettleiepriser på nettselskapets nettside (url-feltet)
# 2. Sett energiledd_dag og energiledd_natt i NOK/kWh (inkl. avgifter)
# 3. Legg til kapasitetstrinn som liste med tupler: (kW-grense, kr/mnd)
# 4. Sett supported til True
TSO_LIST: Final[dict[str, TSOEntry]] = {
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
            (25, 655),  # Fra PDF
            (50, 1135),  # Fra PDF
            (75, 1750),  # Fra PDF
            (100, 2370),  # Fra PDF
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
            (5, 294),  # 0-5 kW: 293,75 kr/mnd
            (10, 503),  # 5-10 kW: 502,50 kr/mnd
            (15, 708),  # 10-15 kW: 707,50 kr/mnd
            (20, 916),  # 15-20 kW: 916,25 kr/mnd
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
            (2, 150),  # 0-2 kW: 150 kr/mnd
            (5, 250),  # 2-5 kW: 250 kr/mnd
            (10, 400),  # 5-10 kW: 400 kr/mnd
            (15, 650),  # 10-15 kW: 650 kr/mnd
            (20, 900),  # 15-20 kW: 900 kr/mnd
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
            (2, 118),  # 0-2 kW: 117,89 kr/mnd
            (5, 196),  # 2-5 kW: 196,49 kr/mnd
            (10, 323),  # 5-10 kW: 323,12 kr/mnd
            (15, 575),  # 10-15 kW: 574,63 kr/mnd
            (20, 763),  # 15-20 kW: 763,25 kr/mnd
            (25, 947),  # 20-25 kW: 946,65 kr/mnd
            (50, 1467),  # 25-50 kW: 1467,13 kr/mnd
            (75, 2297),  # 50-75 kW: 2296,76 kr/mnd
            (100, 3126),  # 75-100 kW: 3126,38 kr/mnd
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
            (2, 85),  # 0-2 kW: 85 kr/mnd
            (5, 201),  # 2-5 kW: 201 kr/mnd
            (10, 398),  # 5-10 kW: 398 kr/mnd
            (15, 595),  # 10-15 kW: 595 kr/mnd
            (20, 792),  # 15-20 kW: 792 kr/mnd
            (25, 989),  # 20-25 kW: 989 kr/mnd
            (50, 1972),  # 25-50 kW: 1972 kr/mnd
            (75, 2955),  # 50-75 kW: 2955 kr/mnd
            (100, 3938),  # 75-100 kW: 3938 kr/mnd
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
            (5, 360),  # 0-5 kW: 360 kr/mnd
            (10, 460),  # 5-10 kW: 460 kr/mnd
            (15, 560),  # 10-15 kW: 560 kr/mnd
            (20, 660),  # 15-20 kW: 660 kr/mnd
            (25, 760),  # 20-25 kW: 760 kr/mnd
            (50, 2200),  # 25-50 kW: 2200 kr/mnd
            (75, 3200),  # 50-75 kW: 3200 kr/mnd
            (100, 4200),  # 75-100 kW: 4200 kr/mnd
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
            (2, 238),  # 0-2 kW: 237,5 kr/mnd
            (5, 294),  # 2-5 kW: 293,8 kr/mnd
            (10, 419),  # 5-10 kW: 418,8 kr/mnd
            (15, 663),  # 10-15 kW: 662,5 kr/mnd
            (20, 838),  # 15-20 kW: 837,5 kr/mnd
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
            (2, 225),  # 0-2 kW: 225 kr/mnd
            (5, 225),  # 2-5 kW: 225 kr/mnd
            (10, 349),  # 5-10 kW: 349 kr/mnd
            (15, 491),  # 10-15 kW: 491 kr/mnd
            (20, 633),  # 15-20 kW: 633 kr/mnd
            (25, 776),  # 20-25 kW: 776 kr/mnd
            (50, 1297),  # 25-50 kW: 1297 kr/mnd
            (75, 2008),  # 50-75 kW: 2008 kr/mnd
            (100, 2719),  # 75-100 kW: 2719 kr/mnd
            (150, 3905),  # 100-150 kW: 3905 kr/mnd
            (200, 5326),  # 150-200 kW: 5326 kr/mnd
            (300, 7693),  # 200-300 kW: 7693 kr/mnd
            (400, 10541),  # 300-400 kW: 10541 kr/mnd
            (500, 13383),  # 400-500 kW: 13383 kr/mnd
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
            (2, 310),  # 0-2 kW: 310 kr/mnd
            (4, 440),  # 2-4 kW: 440 kr/mnd
            (6, 530),  # 4-6 kW: 530 kr/mnd
            (8, 610),  # 6-8 kW: 610 kr/mnd
            (10, 680),  # 8-10 kW: 680 kr/mnd
            (15, 750),  # 10-15 kW: 750 kr/mnd
            (20, 890),  # 15-20 kW: 890 kr/mnd
            (25, 1200),  # 20-25 kW: 1200 kr/mnd
            (30, 1400),  # 25-30 kW: 1400 kr/mnd
            (35, 1700),  # 30-35 kW: 1700 kr/mnd
            (40, 1900),  # 35-40 kW: 1900 kr/mnd
            (45, 2100),  # 40-45 kW: 2100 kr/mnd
            (50, 2400),  # 45-50 kW: 2400 kr/mnd
            (75, 3600),  # 50-75 kW: 3600 kr/mnd
            (100, 5300),  # 75-100 kW: 5300 kr/mnd
            (125, 7100),  # 100-125 kW: 7100 kr/mnd
            (150, 8900),  # 125-150 kW: 8900 kr/mnd
            (175, 10700),  # 150-175 kW: 10700 kr/mnd
            (200, 12500),  # 175-200 kW: 12500 kr/mnd
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
            (2, 251),  # 0-2 kW: 251 kr/mnd
            (5, 314),  # 2-5 kW: 314 kr/mnd
            (10, 376),  # 5-10 kW: 376 kr/mnd
            (15, 627),  # 10-15 kW: 627 kr/mnd
            (20, 753),  # 15-20 kW: 753 kr/mnd
            (25, 878),  # 20-25 kW: 878 kr/mnd
            (50, 1254),  # 25-50 kW: 1254 kr/mnd
            (75, 1379),  # 50-75 kW: 1379 kr/mnd
            (100, 1505),  # 75-100 kW: 1505 kr/mnd
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
            (2, 254),  # 0-2 kW: 254 kr/mnd
            (5, 380),  # 2-5 kW: 380 kr/mnd
            (10, 631),  # 5-10 kW: 631 kr/mnd
            (15, 834),  # 10-15 kW: 834 kr/mnd
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
            (2, 275),  # 0-2 kW: 275 kr/mnd
            (5, 343),  # 2-5 kW: 343 kr/mnd
            (10, 411),  # 5-10 kW: 411 kr/mnd
            (15, 686),  # 10-15 kW: 686 kr/mnd
            (20, 824),  # 15-20 kW: 824 kr/mnd
            (25, 960),  # 20-25 kW: 960 kr/mnd
            (50, 1373),  # 25-50 kW: 1373 kr/mnd
            (75, 1510),  # 50-75 kW: 1510 kr/mnd
            (100, 1646),  # 75-100 kW: 1646 kr/mnd
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
            (2, 138),  # 0-2 kW: 137,50 kr/mnd
            (5, 250),  # 2-5 kW: 250 kr/mnd
            (10, 425),  # 5-10 kW: 425 kr/mnd
            (15, 625),  # 10-15 kW: 625 kr/mnd
            (20, 813),  # 15-20 kW: 812,50 kr/mnd
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
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Flat sats: 13,10 øre/kWh (inkl. 4 øre rabatt)
        # + forbruksavgift 7,13 + Enova 1,0 = 21,23 øre/kWh
        "energiledd_dag": 0.2123,  # 21,23 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.2123,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://alut.no/nettleie/",
        "kapasitetstrinn": [
            (2, 292),  # 3500/12
            (5, 350),
            (10, 500),
            (15, 650),
            (20, 800),
            (25, 950),
            (float("inf"), 1200),
        ],
    },
    "area_nett": {
        "name": "Area Nett",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser eks. avgifter: dag 29,89, natt 24,89 øre/kWh
        # + forbruksavgift 7,13 + Enova 1,0 = dag 38,02, natt 33,02 øre/kWh
        "energiledd_dag": 0.3802,  # 38,02 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.3302,  # 33,02 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.area.no",
        "kapasitetstrinn": [
            (2, 250),
            (5, 350),
            (10, 500),
            (15, 650),
            (20, 800),
            (25, 950),
            (float("inf"), 1300),
        ],
    },
    "asker_nett": {
        "name": "Asker Nett",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag": 0.4000,  # 40 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.3000,  # 30 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://askernett.no/prisliste-for-privatkunder-i-2026/",
        "kapasitetstrinn": [
            (2, 215),  # 0-2 kW: 215 kr/mnd
            (5, 270),  # 2-5 kW: 270 kr/mnd
            (10, 395),  # 5-10 kW: 395 kr/mnd
            (15, 825),  # 10-15 kW: 825 kr/mnd
            (20, 1030),  # 15-20 kW: 1030 kr/mnd
            (25, 1300),  # 20-25 kW: 1300 kr/mnd
            (50, 1840),  # 25-50 kW: 1840 kr/mnd
            (75, 2900),  # 50-75 kW: 2900 kr/mnd
            (100, 3890),  # 75-100 kW: 3890 kr/mnd
            (float("inf"), 6250),  # >100 kW: 6250 kr/mnd
        ],
    },
    "barents_nett": {
        "name": "Barents Nett",
        "prisomrade": "NO4",
        "tiltakssone": True,  # Finnmark - fritatt for mva og forbruksavgift
        "supported": True,
        "energiledd_dag": 0.1132,  # Flat sats hele døgnet (2026)
        "energiledd_natt": 0.1132,  # Flat sats hele døgnet (2026)
        "url": "https://www.barents-nett.no/kundeservice/nett-og-nettleie/",
        "kapasitetstrinn": [  # 2026-priser
            {"min": 0, "max": 2, "pris": 517},
            {"min": 2, "max": 5, "pris": 569},
            {"min": 5, "max": 10, "pris": 620},
            {"min": 10, "max": 15, "pris": 673},
            {"min": 15, "max": 20, "pris": 776},
            {"min": 20, "max": 999, "pris": 931},
        ],
    },
    "bindal_kraftnett": {
        "name": "Bindal Kraftnett",
        "prisomrade": "NO3",
        "supported": True,
        # Priser eks. avgifter: dag 26,3, natt 21,3 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 36,46, natt 31,46 øre/kWh eks. mva
        # + 25% mva = dag 45,58, natt 39,33 øre/kWh inkl. mva
        "energiledd_dag": 0.4304,  # 43,04 øre/kWh inkl. avgifter og mva (2025)
        "energiledd_natt": 0.3679,  # 36,79 øre/kWh inkl. avgifter og mva (2025)
        "url": "https://bindalkraftlag.no/tariffer",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "breheim_nett": {
        "name": "Breheim Nett",
        "prisomrade": "NO5",
        "supported": True,
        # Priser inkl. avgifter og mva: dag 28,29, natt 18,29 øre/kWh
        # (tidligere Luster Energiverk)
        "energiledd_dag": 0.2829,  # 28,29 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.1829,  # 18,29 øre/kWh inkl. avgifter (2026)
        "url": "https://www.breheimnett.no/nettleige-for-kundar-under-100-000-kwh-i-arsforbruk2026",
        "kapasitetstrinn": [
            (5, 225),
            (10, 350),
            (15, 500),
            (20, 650),
            (25, 800),
            (50, 1500),
            (75, 2500),
            (100, 3500),
            (float("inf"), 5000),
        ],
    },
    "bomlo_kraftnett": {
        "name": "Bømlo Kraftnett",
        "prisomrade": "NO5",
        "supported": True,
        # Priser eks. avgifter: dag 35,5, natt 29,0 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 45,66, natt 39,16 øre/kWh eks. mva
        # + 25% mva = dag 57,08, natt 48,95 øre/kWh inkl. mva
        "energiledd_dag": 0.5454,  # 54,54 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.4641,  # 46,41 øre/kWh inkl. avgifter (2026)
        "url": "https://nett.finnas-kraftlag.no/nettleige-og-vilkar/category1618.html",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (50, 1500),
            (75, 2200),
            (100, 3000),
            (float("inf"), 4000),
        ],
    },
    "de_nett": {
        "name": "De Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Har sesongpriser - bruker vinterpriser (høyest)
        # Vinter dag: 31,4 øre + avgifter = ca 41,5 øre/kWh inkl. mva
        # Vinter natt: 28,4 øre + avgifter = ca 38,5 øre/kWh inkl. mva
        "energiledd_dag": 0.4150,  # 41,50 øre/kWh inkl. avgifter (2026, vinter)
        "energiledd_natt": 0.3850,  # 38,50 øre/kWh inkl. avgifter (2026, vinter)
        "url": "https://denett.no/priser-tariffer/",
        "kapasitetstrinn": [
            (2, 286),  # 3432/12
            (5, 369),
            (10, 451),
            (15, 622),
            (20, 787),
            (25, 957),
            (50, 1452),
            (75, 2288),
            (100, 3124),
            (float("inf"), 4400),
        ],
    },
    "elmea": {
        "name": "Elmea",
        "prisomrade": "NO4",
        "supported": True,
        # Priser eks mva (Nord-Norge mva-fritak): energiledd + forbruksavgift + Enova
        "energiledd_dag": 0.4781,  # 37,9 + 8,91 + 1 = 47,81 øre/kWh (2026)
        "energiledd_natt": 0.3551,  # 25,6 + 8,91 + 1 = 35,51 øre/kWh (2026)
        "url": "https://www.elmea.no/nettleiepriser/",
        "kapasitetstrinn": [
            (2, 327),
            (5, 489),
            (10, 747),
            (15, 1070),
            (20, 1392),
            (25, 1715),
            (50, 2683),
            (75, 4297),
            (100, 5911),
            (200, 11558),
            (float("inf"), 24468),
        ],
    },
    "enida": {
        "name": "Enida",
        "prisomrade": "NO2",
        "supported": True,
        # Priser eks. avgifter: høylast 27, grunnpris 21 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 37,16, natt 31,16 øre/kWh eks. mva
        # + 25% mva = dag 46,45, natt 38,95 øre/kWh inkl. mva
        "energiledd_dag": 0.4645,  # 46,45 øre/kWh inkl. avgifter (2025)
        "energiledd_natt": 0.3895,  # 38,95 øre/kWh inkl. avgifter (2025)
        "url": "https://enida.no/strompris",
        "kapasitetstrinn": [
            (2, 232),  # 2784/12
            (5, 280),
            (10, 380),
            (15, 500),
            (20, 620),
            (25, 740),
            (float("inf"), 1000),
        ],
    },
    "everket": {
        "name": "Everket",
        "prisomrade": "NO2",
        "supported": True,
        # Everket/Kraftia bruker Midtnett som nettoperatør
        # Priser inkl. forbruksavgift, Enova-avgift og 25% mva
        "energiledd_dag": 0.4674,  # 46,74 øre/kWh inkl. avgifter (2026, dag 06-22)
        "energiledd_natt": 0.4049,  # 40,49 øre/kWh inkl. avgifter (2026, natt 22-06)
        "url": "https://midtnett.no/nettleie-informasjon-og-priser/",
        "kapasitetstrinn": [
            (5, 275),
            (10, 413),
            (15, 625),
            (20, 938),
            (25, 1250),
            (50, 1746),
            (75, 2620),
            (100, 3250),
            (float("inf"), 3750),
        ],
    },
    "fjellnett": {
        "name": "Fjellnett",
        "prisomrade": "NO3",
        "supported": True,
        # Flat sats: 26,29 øre/kWh inkl. alle avgifter og mva
        # Ingen dag/natt-differensiering
        "energiledd_dag": 0.2629,  # 26,29 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2629,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.fjellnett.no/nettleie/nettleiepriser/",
        "kapasitetstrinn": [
            (2, 208),  # Grunnbeløp 2500/12
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "fore": {
        "name": "Føre",
        "prisomrade": "NO2",
        "supported": True,
        # Flat sats: 19,29 øre/kWh eks. mva, 24,11 øre/kWh inkl. mva
        # Kapasitetsbasert modell, ingen dag/natt-differensiering
        "energiledd_dag": 0.2411,  # 24,11 øre/kWh inkl. mva (2026)
        "energiledd_natt": 0.2411,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://foere.net/nettleie/",
        "kapasitetstrinn": [
            (2, 329),  # 328,8 kr/mnd inkl. mva
            (5, 428),  # 427,5 kr/mnd inkl. mva
            (10, 526),  # 526,3 kr/mnd inkl. mva
            (15, 625),  # 625,0 kr/mnd inkl. mva
            (20, 724),
            (25, 823),
            (float("inf"), 1000),
        ],
    },
    "griug": {
        "name": "Griug",
        "prisomrade": "NO1",
        "supported": True,
        # Griug har ikke dag/natt-differensiering, bruker samme sats for begge
        "energiledd_dag": 0.2556,  # 25,56 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.2556,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.griug.no/om-nettleie-og-priser/priser/nettleiepriser-2026/",
        "kapasitetstrinn": [
            (2, 250),
            (5, 380),
            (10, 570),
            (15, 730),
            (20, 920),
            (25, 1115),
            (50, 2085),
            (75, 3060),
            (100, 4110),
            (float("inf"), 8150),
        ],
    },
    "haringnett": {
        "name": "Haringnett",
        "prisomrade": "NO5",
        "supported": True,
        # Priser inkl. avgifter og mva: dag 40,79, natt 30,79 øre/kWh
        "energiledd_dag": 0.4079,  # 40,79 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3079,  # 30,79 øre/kWh inkl. avgifter (2026)
        "url": "https://www.haringnett.no/nettleigeprisar2026",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "havnett": {
        "name": "Havnett",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats: 47,31 øre/kWh inkl. avgifter og mva
        # (Austevoll Kraftlag SA)
        "energiledd_dag": 0.4731,  # 47,31 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.4731,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://havnett.as/priser/nettleigetariff/",
        "kapasitetstrinn": [
            (5, 250),
            (10, 320),
            (15, 563),
            (20, 788),
            (25, 863),
            (float("inf"), 1200),
        ],
    },
    "holand_setskog": {
        "name": "Høland og Setskog Elverk",
        "prisomrade": "NO1",
        "supported": True,
        # Priser eks. avgifter: dag 22,5, natt 17,5 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 32,66, natt 27,66 øre/kWh eks. mva
        # + 25% mva = dag 40,83, natt 34,58 øre/kWh inkl. mva
        "energiledd_dag": 0.3829,  # 38,29 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.3204,  # 32,04 øre/kWh inkl. avgifter og mva (2026)
        "url": "https://hsev.no/nettleie",
        "kapasitetstrinn": [
            (2, 160),  # Estimert basert på lignende nettselskap
            (5, 250),
            (10, 400),
            (15, 600),
            (20, 800),
            (25, 1000),
            (50, 1800),
            (75, 2600),
            (100, 3500),
            (float("inf"), 5000),
        ],
    },
    "indre_hordaland": {
        "name": "Indre Hordaland Kraftnett",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats: 45,86 øre/kWh inkl. avgifter og mva
        "energiledd_dag": 0.4586,  # 45,86 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.4586,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://ihk.no/prisar/nettleige",
        "kapasitetstrinn": [
            (2, 240),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (50, 1800),
            (75, 2700),
            (100, 3600),
            (float("inf"), 7200),
        ],
    },
    "jaren_everk": {
        "name": "Jæren Everk",
        "prisomrade": "NO2",
        "supported": True,
        # Priser inkl. mva: dag 20,00, natt 12,50 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 30,16, natt 22,66 øre/kWh inkl. mva
        "energiledd_dag": 0.3016,  # 30,16 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.2266,  # 22,66 øre/kWh inkl. avgifter og mva (2026)
        "url": "https://jev.no/nettleie-for-kunder-med-forbruk-under-100-000-kwh-2-2-2-2-2-2-2-2",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 800),
            (25, 1000),
            (float("inf"), 1500),
        ],
    },
    "ke_nett": {
        "name": "KE Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Priser eks. avgifter: dag 18,00, natt 8,00 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 28,16, natt 18,16 øre/kWh eks. mva
        # + 25% mva = dag 35,20, natt 22,70 øre/kWh inkl. mva
        "energiledd_dag": 0.3266,  # 32,66 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.2016,  # 20,16 øre/kWh inkl. avgifter og mva (2026)
        "url": "https://ke-nett.no/Nettleiepriser/",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 800),
            (25, 1000),
            (float("inf"), 1500),
        ],
    },
    "klive": {
        "name": "Klive",
        "prisomrade": "NO3",
        "supported": True,
        # Flat sats: 32,20 øre/kWh inkl. mva, forbruksavgift og Enova
        # Kapasitetsbasert modell, ingen dag/natt-differensiering
        "energiledd_dag": 0.3220,  # 32,20 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3220,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://klive.no/har-strom/nettleiepriser/",
        "kapasitetstrinn": [
            (2, 200),  # Estimert basert på kapasitetsmodell
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (50, 1500),
            (float("inf"), 2000),
        ],
    },
    "kystnett": {
        "name": "Kystnett",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Flat sats: 18 øre/kWh eks. avgifter
        # + forbruksavgift 7,13 + Enova 1,0 = 26,13 øre/kWh (ingen mva i NO4)
        "energiledd_dag": 0.2613,  # 26,13 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2613,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://kystnett.no/nettleie",
        "kapasitetstrinn": [
            (2, 200),  # Estimert basert på kapasitetsmodell
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (50, 1500),
            (75, 2200),
            (100, 3000),
            (float("inf"), 4000),
        ],
    },
    "lucerna": {
        "name": "Lucerna",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser: dag 19,32, natt 13,32 øre/kWh (inkl. Enova 1,0)
        # + forbruksavgift 7,13 = dag 26,45, natt 20,45 øre/kWh
        "energiledd_dag": 0.2645,  # 26,45 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.2045,  # 20,45 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.lucerna.no/priser",
        "kapasitetstrinn": [
            (2, 259),
            (5, 350),
            (10, 500),
            (15, 650),
            (20, 800),
            (25, 950),
            (float("inf"), 1300),
        ],
    },
    "lysna": {
        "name": "Lysna",
        "prisomrade": "NO5",
        "supported": True,
        # Priser eks. avgifter: dag 32, natt 24 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 42,16, natt 34,16 øre/kWh eks. mva
        # + 25% mva = dag 52,70, natt 42,70 øre/kWh inkl. mva
        "energiledd_dag": 0.5270,  # 52,70 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.4270,  # 42,70 øre/kWh inkl. avgifter (2026)
        "url": "https://lysna.no/prisar-for-private-kundar-2024",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "meloy_energi": {
        "name": "Meløy Energi",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser: dag 27,40, natt 17,40 øre/kWh
        # + forbruksavgift 7,13 + Enova 1,0 = dag 35,53, natt 25,53 øre/kWh
        "energiledd_dag": 0.3553,  # 35,53 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.2553,  # 25,53 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.meloyenergi.no/ac/nettleie-avregning",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "midtnett": {
        "name": "Midtnett",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag": 0.4674,  # 46,74 øre/kWh inkl. avgifter (fra 1. okt 2025)
        "energiledd_natt": 0.4049,  # 40,49 øre/kWh inkl. avgifter (fra 1. okt 2025)
        "url": "https://midtnett.no/nettleie-informasjon-og-priser/",
        "kapasitetstrinn": [
            (5, 275),
            (10, 413),
            (15, 625),
            (20, 938),
            (25, 1250),
            (50, 1746),
            (75, 2620),
            (100, 3250),
            (float("inf"), 3750),
        ],
    },
    "modalen_kraftlag": {
        "name": "Modalen Kraftlag",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats: 71,16 øre/kWh inkl. avgifter og mva
        # (nett via Mostraum Nett AS)
        "energiledd_dag": 0.7116,  # 71,16 øre/kWh inkl. avgifter (2025)
        "energiledd_natt": 0.7116,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.mostraumnett.no/nettprisar",
        "kapasitetstrinn": [
            (2, 78),
            (5, 200),
            (10, 400),
            (15, 600),
            (20, 800),
            (25, 1000),
            (50, 2000),
            (75, 3500),
            (100, 5000),
            (float("inf"), 6900),
        ],
    },
    "netera": {
        "name": "Netera",
        "prisomrade": "NO3",
        "supported": True,
        # Har sesongpriser - bruker vinterpriser (høyest)
        # Vinter: 36,3 øre/kWh, Sommer: 33,4 øre/kWh (inkl. avgifter og mva)
        "energiledd_dag": 0.3630,  # 36,30 øre/kWh inkl. avgifter (2026, vinter)
        "energiledd_natt": 0.3630,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.netera.no/nettleie/avtaler/privat/",
        "kapasitetstrinn": [
            (10, 167),  # 2000/12
            (63, 333),  # 4000/12
            (float("inf"), 667),  # 8000/12
        ],
    },
    "noranett_andoy": {
        "name": "Noranett Andøy",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Flat sats: 16,4 øre/kWh + forbruksavgift 7,13 + Enova 1,0 = 24,53 øre/kWh
        "energiledd_dag": 0.2453,  # 24,53 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.2453,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.noranett.no/nettleiepriser/nettleiepriser-andoy-fra-1-1-2026-article4140-2415.html",
        "kapasitetstrinn": [
            (2, 310),
            (4, 440),
            (6, 530),
            (8, 610),
            (10, 680),
            (15, 750),
            (20, 890),
            (25, 1200),
            (float("inf"), 1500),
        ],
    },
    "noranett_hadsel": {
        "name": "Noranett Hadsel",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser: dag 14,0, natt 9,0 øre/kWh + forbruksavgift 7,13 + Enova 1,0
        "energiledd_dag": 0.2213,  # 22,13 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.1713,  # 17,13 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.noranett.no/nettleiepriser/nettleiepriser-hadsel-fra-1-1-2026-article4141-2415.html",
        "kapasitetstrinn": [
            (2, 270),
            (4, 380),
            (6, 460),
            (8, 530),
            (10, 590),
            (15, 650),
            (20, 770),
            (25, 1040),
            (float("inf"), 1300),
        ],
    },
    "nordvest_nett": {
        "name": "Nordvest Nett",
        "prisomrade": "NO3",
        "supported": True,
        "energiledd_dag": 0.4270,  # 42,70 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3520,  # 35,20 øre/kWh inkl. avgifter (2026)
        "url": "https://www.nvn.no/nettleige/nettleie-privatkunder",
        "kapasitetstrinn": [
            (2, 158),
            (5, 388),
            (10, 478),
            (15, 726),
            (20, 861),
            (25, 1004),
            (50, 1926),
            (75, 2850),
            (100, 3773),
            (float("inf"), 7420),
        ],
    },
    "norefjell_nett": {
        "name": "Norefjell Nett",
        "prisomrade": "NO1",
        "supported": True,
        # Priser inkl. avgifter og mva: dag 38,33, natt 29,01 øre/kWh
        "energiledd_dag": 0.3833,  # 38,33 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2901,  # 29,01 øre/kWh inkl. avgifter (2026)
        "url": "https://norefjell-nett.no/strompris",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "r_nett": {
        "name": "R-Nett",
        "prisomrade": "NO1",
        "supported": True,
        # Priser eks. avgifter: dag 25,67, natt 16,07 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 35,83, natt 26,23 øre/kWh eks. mva
        # + 25% mva = dag 44,79, natt 32,79 øre/kWh inkl. mva
        "energiledd_dag": 0.4225,  # 42,25 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.3025,  # 30,25 øre/kWh inkl. avgifter og mva (2026)
        "url": "https://r-nett.no/overforingspriser/",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 800),
            (25, 1000),
            (50, 1800),
            (75, 2600),
            (100, 3500),
            (float("inf"), 5000),
        ],
    },
    "rakkestad_energi": {
        "name": "Rakkestad Energi",
        "prisomrade": "NO1",
        "supported": True,
        # Nå del av Elvia - bruker Elvia-priser fra sept 2025
        "energiledd_dag": 0.3640,  # 36,40 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2640,  # 26,40 øre/kWh inkl. avgifter (2026)
        "url": "https://rakkestadenergi.no/nettleiepriser",
        "kapasitetstrinn": [
            (2, 125),
            (5, 190),
            (10, 300),
            (15, 410),
            (20, 520),
            (float("inf"), 655),
        ],
    },
    "rk_nett": {
        "name": "RK Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Flat sats: 20,14 øre/kWh eks. mva, 25,17 øre/kWh inkl. mva
        # + forbruksavgift 8,91 + Enova 1,25 = 35,33 øre/kWh inkl. mva
        "energiledd_dag": 0.3533,  # 35,33 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.3533,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.rauland-nett.no/nettleige",
        "kapasitetstrinn": [
            (2, 213),
            (5, 320),
            (10, 480),
            (15, 640),
            (20, 800),
            (25, 960),
            (float("inf"), 1500),
        ],
    },
    "romsdalsnett": {
        "name": "Romsdalsnett",
        "prisomrade": "NO3",
        "supported": True,
        # Priser inkl. avgifter: dag 38,40, natt 25,90 øre/kWh
        "energiledd_dag": 0.3840,  # 38,40 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2590,  # 25,90 øre/kWh inkl. avgifter (2026)
        "url": "https://www.romsdalsnettas.no/nettleie/",
        "kapasitetstrinn": [
            (2, 290),
            (5, 400),
            (10, 550),
            (15, 700),
            (20, 850),
            (25, 1015),
            (float("inf"), 1500),
        ],
    },
    "s_nett": {
        "name": "S-Nett",
        "prisomrade": "NO3",
        "supported": True,
        # Priser inkl. mva: dag 33,00, natt 26,76 øre/kWh
        "energiledd_dag": 0.3300,  # 33,00 øre/kWh inkl. avgifter (2025)
        "energiledd_natt": 0.2676,  # 26,76 øre/kWh inkl. avgifter (2025)
        "url": "https://snett.no/nettleie-forbruk-under-100-000-kwh",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "stannum": {
        "name": "Stannum",
        "prisomrade": "NO2",
        "supported": True,
        # Priser inkl. avgifter og mva: dag 41,42, natt 37,67 øre/kWh
        "energiledd_dag": 0.4142,  # 41,42 øre/kWh inkl. avgifter (2025)
        "energiledd_natt": 0.3767,  # 37,67 øre/kWh inkl. avgifter (2025)
        "url": "https://stannum.no/nettleiepriser",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "stram": {
        "name": "Stram",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser eks. avgifter: dag 14,11, natt 4,11 øre/kWh
        # + forbruksavgift 7,13 + Enova 1,0 = dag 22,24, natt 12,24 øre/kWh
        "energiledd_dag": 0.2224,  # 22,24 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.1224,  # 12,24 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.stram.no/nettleiepris",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "straumen_nett": {
        "name": "Straumen Nett",
        "prisomrade": "NO3",
        "supported": True,
        # Flat sats: 24,13 øre/kWh eks. avgifter, 33,04 øre/kWh inkl. avgifter og mva
        # Ingen dag/natt-differensiering
        "energiledd_dag": 0.3304,  # 33,04 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3304,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://straumen-nett.no/nettleige/nettleige-private-2026",
        "kapasitetstrinn": [
            (5, 290),
            (10, 334),
            (15, 495),
            (20, 582),
            (25, 873),
            (float("inf"), 1163),
        ],
    },
    "straumnett": {
        "name": "Straumnett",
        "prisomrade": "NO5",
        "supported": True,
        # Priser: dag 26,20, natt 19,95 øre/kWh
        # + forbruksavgift 8,91 + Enova 1,25 = dag 36,36, natt 30,11 øre/kWh eks. mva
        # + 25% mva = dag 45,45, natt 37,64 øre/kWh inkl. mva
        "energiledd_dag": 0.4545,  # 45,45 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3764,  # 37,64 øre/kWh inkl. avgifter (2026)
        "url": "https://straumnett.no/prisar-for-nettleige",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    # Svabo Industrinett (NO4) - Kun industrikunder, ikke relevant for husholdninger
    # "svabo_industrinett": {
    #     "name": "Svabo Industrinett",
    #     "prisomrade": "NO4",
    #     "supported": False,
    #     "energiledd_dag": 0,
    #     "energiledd_natt": 0,
    #     "url": "",
    #     "kapasitetstrinn": [],
    # },
    "sygnir": {
        "name": "Sygnir",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats: 37,73 øre/kWh inkl. forbruksavgift, Enova og mva
        # Ingen dag/natt-differensiering
        "energiledd_dag": 0.3773,  # 37,73 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3773,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.sygnir.no/s/Nettleigeprisar-1-januar-2026.pdf",
        "kapasitetstrinn": [
            (1, 240),
            (2, 288),
            (3, 338),
            (4, 384),
            (5, 431),
            (6, 504),
            (7, 575),
            (8, 648),
            (9, 720),
            (10, 791),
            (12, 938),
            (14, 1081),
            (16, 1225),
            (18, 1369),
            (20, 1519),
            (40, 2713),
            (60, 3913),
            (float("inf"), 5000),
        ],
    },
    "tendranett": {
        "name": "Tendranett",
        "prisomrade": "NO5",
        "supported": True,
        # Priser inkl. forbruksavgift (21,2), Enova (1,25) og mva
        "energiledd_dag": 0.5180,  # 51,8 øre/kWh inkl. avgifter (2025)
        "energiledd_natt": 0.4550,  # 45,5 øre/kWh inkl. avgifter (2025)
        "url": "https://www.tendranett.no/",
        "kapasitetstrinn": [
            (2, 209),
            (5, 272),
            (10, 335),
            (15, 460),
            (20, 586),
            (25, 711),
            (50, 879),
            (75, 1046),
            (100, 1213),
            (float("inf"), 1255),
        ],
    },
    "telemark_nett": {
        "name": "Telemark Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Flat sats: 25,0 øre/kWh eks. mva, 31,25 øre/kWh inkl. mva
        # + forbruksavgift 8,91 + Enova 1,25 = 41,41 øre/kWh inkl. mva
        "energiledd_dag": 0.4141,  # 41,41 øre/kWh inkl. avgifter og mva (2026)
        "energiledd_natt": 0.4141,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.telemark-nett.no/prisar/nettleige-1/",
        "kapasitetstrinn": [
            (5, 284),
            (10, 400),
            (15, 550),
            (20, 700),
            (25, 850),
            (float("inf"), 1200),
        ],
    },
    "uvdal_kraftforsyning": {
        "name": "Uvdal Kraftforsyning",
        "prisomrade": "NO1",
        "supported": True,
        # Priser inkl. avgifter og mva: dag 39,06, natt 29,06 øre/kWh
        "energiledd_dag": 0.3906,  # 39,06 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2906,  # 29,06 øre/kWh inkl. avgifter (2026)
        "url": "https://www.uvdalkraft.no/contact/nett/",
        "kapasitetstrinn": [
            (5, 278),  # 3331/12
            (10, 350),
            (15, 500),
            (20, 650),
            (25, 800),
            (50, 1500),
            (75, 2500),
            (100, 3500),
            (float("inf"), 7833),
        ],
    },
    "vang_energiverk": {
        "name": "Vang Energiverk",
        "prisomrade": "NO1",
        "supported": True,
        # Flat sats: 21,13 øre/kWh eks. mva, 26,41 øre/kWh inkl. mva
        # Ingen dag/natt-differensiering
        "energiledd_dag": 0.2641,  # 26,41 øre/kWh inkl. mva (2026)
        "energiledd_natt": 0.2641,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://vangenergi.no/forbrukarkundar",
        "kapasitetstrinn": [
            (2, 450),  # Fra nettside - kapasitetsbasert
            (5, 550),
            (10, 700),
            (15, 850),
            (20, 1000),
            (25, 1165),
            (float("inf"), 1165),
        ],
    },
    "vestall": {
        "name": "Vestall",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser eks. avgifter: dag 6,00, natt 3,00 øre/kWh
        # + forbruksavgift 7,13 + Enova 1,0 = dag 14,13, natt 11,13 øre/kWh
        "energiledd_dag": 0.1413,  # 14,13 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.1113,  # 11,13 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://vestall.no/nettleiepriser-fra-01-01-2026/",
        "kapasitetstrinn": [
            (2, 150),
            (5, 250),
            (10, 400),
            (15, 550),
            (20, 700),
            (25, 850),
            (float("inf"), 1100),
        ],
    },
    "vestmar_nett": {
        "name": "Vestmar Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Flat sats: 17,10 øre/kWh eks. avgifter (2026)
        # + forbruksavgift 7,13 + Enova 1,00 = 25,23 øre/kWh eks. mva
        # + 25% mva = 31,54 øre/kWh inkl. mva
        "energiledd_dag": 0.3154,  # 31,54 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.3154,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://vestmar-nett.no/wp-content/uploads/2026/01/Tariffer-01.01.2026.pdf",
        "kapasitetstrinn": [
            (5, 291),  # 0-5 kW: 290,90 kr/mnd ekskl. mva
            (10, 515),  # 5-10 kW: 514,60 kr/mnd ekskl. mva
            (15, 745),  # 10-15 kW: 745,00 kr/mnd ekskl. mva
            (20, 970),  # 15-20 kW: 970,00 kr/mnd ekskl. mva
            (25, 1195),  # 20-25 kW: 1195,00 kr/mnd ekskl. mva
            (50, 1870),  # 25-50 kW: 1870,00 kr/mnd ekskl. mva
            (75, 3000),  # 50-75 kW: 3000,00 kr/mnd ekskl. mva
            (100, 4100),  # 75-100 kW: 4100,00 kr/mnd ekskl. mva
            (150, 5800),  # 100-150 kW: 5800,00 kr/mnd ekskl. mva
            (200, 8050),  # 150-200 kW: 8050,00 kr/mnd ekskl. mva
            (float("inf"), 11400),  # 200+ kW: 11400,00 kr/mnd ekskl. mva
        ],
    },
    "vevig": {
        "name": "Vevig",
        "prisomrade": "NO3",
        "supported": True,
        "energiledd_dag": 0.4166,  # 41,66 øre/kWh inkl. avgifter (2026)
        "energiledd_natt": 0.2991,  # 29,91 øre/kWh inkl. avgifter (2026)
        "url": "https://www.vevig.no/nettleie-og-vilkar/nettleie-privat",
        "kapasitetstrinn": [
            (2, 251),
            (5, 326),
            (10, 454),
            (15, 581),
            (20, 710),
            (25, 835),
            (30, 963),
            (float("inf"), 963),  # Næring over 30 kW
        ],
    },
    "viermie": {
        "name": "Viermie",
        "prisomrade": "NO3",
        "supported": True,
        # Priser inkl. mva: dag 28,5, natt 20,5 øre/kWh
        # (tidligere Røros E-verk Nett)
        "energiledd_dag": 0.2850,  # 28,50 øre/kWh inkl. mva (2026)
        "energiledd_natt": 0.2050,  # 20,50 øre/kWh inkl. mva (2026)
        "url": "https://viermie.no/nettleiepriser/priser-for-kunder-med-forbruk-under-100-000-kwh-ar/",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
    "vissi": {
        "name": "Vissi",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 - mva-fritak for husholdninger
        # Priser: dag 30,00, natt 14,00 øre/kWh (inkl. avgifter)
        "energiledd_dag": 0.3000,  # 30,00 øre/kWh inkl. avgifter (2026, NO4)
        "energiledd_natt": 0.1400,  # 14,00 øre/kWh inkl. avgifter (2026, NO4)
        "url": "https://www.vissi.no/priser-og-vilkar/nettleie-privat/",
        "kapasitetstrinn": [
            (2, 200),
            (5, 300),
            (10, 450),
            (15, 600),
            (20, 750),
            (25, 900),
            (float("inf"), 1200),
        ],
    },
}
