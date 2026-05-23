"""Distribution System Operators (nettselskap) data for Strømkalkulator.

Energileddsatsene lagres som ren nettleie eks. mva og eks. avgifter
(`energiledd_dag_eks_mva`, `energiledd_natt_eks_mva`). Coordinator legger på
forbruksavgift, Enova-avgift og mva basert på avgiftssone. Eksakte
mellomregninger gir mindre avrundingsfeil mot fakturaen enn å lagre
display-avrundede inkl-priser.

Kilder:
- Energileddsatser: nettselskapets prisliste (url-felt)
- Avgifter: skatteetaten.no (FORBRUKSAVGIFT_ALMINNELIG, ENOVA_AVGIFT i const.py)
- DSO-liste: Elhub (https://elhub.no/nettselskaper/)
- Kapasitetstrinn-struktur: NVE (https://www.nve.no/reguleringsmyndigheten/)

NB: BKK er verifisert mot faktura. Øvrige eks_mva-verdier er konvertert fra
tidligere inkl-mva-verdier (formel: inkl/1.25 - 0.0713 - 0.01 for standard-sone)
og arver ~0,5% avrunding fra display-avrundede kilder. Bør re-verifiseres mot
DSO-prisliste ved oppdatering.

Sist oppdatert: Januar 2026 (2026-priser)
"""

from dataclasses import dataclass
from typing import Final, NotRequired, TypedDict

# Type for kapasitetstrinn: tuple of (kW-grense, kr/mnd)
type KapasitetstrinnTuple = tuple[float, int]


# Type for kapasitetstrinn dict format (used by some DSOs like Barents Nett)
class KapasitetstrinnDict(TypedDict):
    """Kapasitetstrinn entry in dict format."""

    min: int
    max: int
    pris: int


class DSOEntry(TypedDict):
    """Type definition for a DSO (Distribution System Operator) entry."""

    name: str
    prisomrade: str
    supported: bool
    energiledd_dag_eks_mva: float  # NOK/kWh, ren nettleie eks. forbruksavgift/Enova/mva
    energiledd_natt_eks_mva: float
    url: str
    kapasitetstrinn: list[KapasitetstrinnTuple | KapasitetstrinnDict]
    tiltakssone: NotRequired[bool]
    helg_som_natt: NotRequired[bool]  # Default True. False = kun klokkeslett styrer dag/natt.
    avgiftssone: NotRequired[str]  # Overstyrer default fra prisomrade (f.eks. Nordland-selskap i NO3)


@dataclass(frozen=True)
class DSOFusjon:
    """Represents a DSO merger: gammel (old key) -> ny (new key)."""

    gammel: str
    ny: str


DSO_MIGRATIONS: Final[list[DSOFusjon]] = [
    DSOFusjon(gammel="skiakernett", ny="vevig"),
]


# Distribution System Operators (DSO) with default values
# Format: {dso_id: {name, prisomrade, supported, energiledd_dag_eks_mva,
#                   energiledd_natt_eks_mva, url, kapasitetstrinn}}
#
# supported: True = har priser, False = mangler priser (trenger bidrag)
# For å legge til priser for et nettselskap:
# 1. Finn nettleiepriser på nettselskapets nettside (url-feltet)
# 2. Sett energiledd_*_eks_mva i NOK/kWh — kun nettleieleddet, eks. mva og
#    eks. forbruksavgift/Enova. Coordinator legger på avgifter og mva basert
#    på avgiftssone.
# 3. Legg til kapasitetstrinn som liste med tupler: (kW-grense, kr/mnd)
# 4. Sett supported til True
DSO_LIST: Final[dict[str, DSOEntry]] = {
    "bkk": {
        "name": "BKK",
        "prisomrade": "NO5",
        "supported": True,
        "energiledd_dag_eks_mva": 0.2877,
        "energiledd_natt_eks_mva": 0.105,
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
        "energiledd_dag_eks_mva": 0.2099,  # 20,99 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1299,  # 12,99 øre/kWh ren energiledd (2026)
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
        # Kilde: tariffblad_1_0_standard-tariff_privat_20260101.pdf (verifisert 2026-05-23)
        "kapasitetstrinn": [
            (2, 125),
            (5, 190),
            (10, 300),
            (15, 410),
            (20, 520),
            (25, 630),
            (50, 1175),
            (75, 1720),
            (100, 2270),
            (float("inf"), 4570),
        ],
    },
    "glitre": {
        "name": "Glitre Nett",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag_eks_mva": 0.24598,  # 24,60 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.12598,  # 12,60 øre/kWh ren energiledd (2026)
        "url": "https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde",
        "helg_som_natt": False,
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
    "norgesnett": {
        "name": "Norgesnett (Glitre Nett)",
        "prisomrade": "NO1",
        "supported": True,
        # Norgesnett er en del av Glitre Nett, men kunder faktureres etter egne tariffer.
        # Kilde: https://norgesnett.no/nettleie-privat/
        "energiledd_dag_eks_mva": 0.20262,  # 20,26 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.13286,  # 13,29 øre/kWh ren energiledd (2026, natt 22-06)
        "url": "https://norgesnett.no/nettleie-privat/",
        "kapasitetstrinn": [
            (2, 118),  # 0-1,99 kW: 117,89 kr/mnd
            (5, 196),  # 2-4,99 kW: 196,49 kr/mnd
            (10, 323),  # 5-9,99 kW: 323,12 kr/mnd
            (15, 575),  # 10-14,99 kW: 574,63 kr/mnd
            (20, 763),  # 15-19,99 kW: 763,25 kr/mnd
            (25, 947),  # 20-24,99 kW: 946,65 kr/mnd
            (50, 1467),  # 25-49,99 kW: 1467,13 kr/mnd
            (75, 2297),  # 50-74,99 kW: 2296,76 kr/mnd
            (100, 3126),  # 75-99,99 kW: 3126,38 kr/mnd
            (float("inf"), 5067),  # >100 kW: 5066,84 kr/mnd
        ],
    },
    "tensio_tn": {
        "name": "Tensio TN",
        "prisomrade": "NO3",
        "supported": True,
        # Tidligere NTE Nett - Nord-Trøndelag
        "energiledd_dag_eks_mva": 0.25902,  # 25,90 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.13006,  # 13,01 øre/kWh ren energiledd (2026, natt 22-06)
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "helg_som_natt": False,
        "kapasitetstrinn": [
            (2, 134),  # 1608/12
            (5, 270),  # 3240/12
            (10, 488),  # 5856/12
            (15, 739),  # 8868/12
            (20, 991),  # 11892/12
            (25, 1243),  # 14916/12
            (50, 2166),  # 25992/12
            (75, 3427),  # 41124/12
            (100, 4687),  # 56244/12
            (150, 6784),  # 81408/12
            (200, 9305),  # 111660/12
            (300, 13500),  # 162000/12
            (400, 18540),  # 222480/12
            (500, 23580),  # 282960/12
            (float("inf"), 28615),  # 343380/12
        ],
    },
    "tensio_ts": {
        "name": "Tensio TS",
        "prisomrade": "NO3",
        "supported": True,
        # Tidligere Trønderenergi Nett - Sør-Trøndelag
        "energiledd_dag_eks_mva": 0.20702,  # 20,70 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.10206,  # 10,21 øre/kWh ren energiledd (2026, natt 22-06)
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "helg_som_natt": False,
        "kapasitetstrinn": [
            (2, 122),  # 1464/12
            (5, 218),  # 2616/12
            (10, 371),  # 4452/12
            (15, 547),  # 6564/12
            (20, 724),  # 8688/12
            (25, 901),  # 10812/12
            (50, 1547),  # 18564/12
            (75, 2429),  # 29148/12
            (100, 3312),  # 39744/12
            (150, 4782),  # 57384/12
            (200, 6545),  # 78540/12
            (300, 9483),  # 113796/12
            (400, 13014),  # 156168/12
            (500, 16539),  # 198468/12
            (float("inf"), 20068),  # 240816/12
        ],
    },
    "lede": {
        "name": "Lede",
        "prisomrade": "NO2",
        "supported": True,
        # Kilde: lede.no/priser/nettleie-privatkunder + kraftsystemet.no/lede (verifisert 2026-05-23).
        # Flat sats - ingen dag/natt-forskjell. 24,42 øre/kWh inkl. alle avgifter = 11,41 eks. mva og avgifter.
        "energiledd_dag_eks_mva": 0.1141,  # 11,41 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1141,  # Flat sats - ingen dag/natt-forskjell
        "url": "https://lede.no/priser/nettleie-privatkunder/",
        "kapasitetstrinn": [
            (5, 269),  # 0-5 kW: 268,75 kr/mnd inkl. mva
            (10, 459),  # 5-10 kW: 458,75 kr/mnd inkl. mva
            (15, 648),  # 10-15 kW: 647,50 kr/mnd inkl. mva
            (20, 838),  # 15-20 kW: 837,50 kr/mnd inkl. mva
            (25, 1028),  # 20-25 kW: 1027,50 kr/mnd inkl. mva
            (50, 1596),  # 25-50 kW: 1596,25 kr/mnd inkl. mva
            (75, 2545),  # 50-75 kW: 30540/12 kr/mnd inkl. mva
            (100, 3493),  # 75-100 kW: 41910/12 kr/mnd inkl. mva
            (150, 4915),  # 100-150 kW: 58980/12 kr/mnd inkl. mva
            (200, 6810),  # 150-200 kW: 81720/12 kr/mnd inkl. mva
            (float("inf"), 9655),  # 200+ kW: 115860/12 kr/mnd inkl. mva
        ],
    },
    "lnett": {
        "name": "Lnett",
        "prisomrade": "NO2",
        "supported": True,
        # Kilde: Lnett tariffhefte 2026 PDF (verifisert 2026-05-23).
        "energiledd_dag_eks_mva": 0.256,  # 25,60 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.136,  # 13,60 øre/kWh ren energiledd (2026)
        "url": "https://www.l-nett.no/nettleie/priser-og-vilkar-privat/",
        "kapasitetstrinn": [
            (2, 150),  # 0-2 kW: 150 kr/mnd inkl. mva
            (5, 250),  # 2-5 kW: 250 kr/mnd inkl. mva
            (10, 400),  # 5-10 kW: 400 kr/mnd inkl. mva
            (15, 650),  # 10-15 kW: 650 kr/mnd inkl. mva
            (20, 900),  # 15-20 kW: 900 kr/mnd inkl. mva
            (25, 1150),  # 20-25 kW: 1150 kr/mnd inkl. mva
            (50, 2150),  # 25-50 kW: 2150 kr/mnd inkl. mva
            (75, 3150),  # 50-75 kW: 3150 kr/mnd inkl. mva
            (100, 4150),  # 75-100 kW: 4150 kr/mnd inkl. mva
            (float("inf"), 7000),  # 100+ kW: 7000 kr/mnd inkl. mva
        ],
    },
    "arva": {
        "name": "Arva",
        "prisomrade": "NO4",
        "supported": True,
        "energiledd_dag_eks_mva": 0.1497,  # 14,97 øre/kWh ren energiledd (2026, nord_norge, dag 06-22)
        "energiledd_natt_eks_mva": 0.0347,  # 3,47 øre/kWh ren energiledd (2026, nord_norge, natt 22-06)
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
        "energiledd_dag_eks_mva": 0.27998,  # 28,00 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.19998,  # 20,00 øre/kWh ren energiledd (2026, natt 22-06)
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
        "energiledd_dag_eks_mva": 0.16502,  # 16,50 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.09998,  # 10,00 øre/kWh ren energiledd (2026, natt 22-06)
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
        # NO4 mva-fritak: coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.235,  # 23,50 øre/kWh ren energiledd (2026, nord_norge, dag 06-22)
        "energiledd_natt_eks_mva": 0.135,  # 13,50 øre/kWh ren energiledd (2026, nord_norge, natt 22-06)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.008,  # 0,80 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.008,  # 0,80 øre/kWh ren energiledd (2026, nord_norge)
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
        # Molde-området (Møre og Romsdal) - HAR 25% mva
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.22638,  # 22,64 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.14638,  # 14,64 øre/kWh ren energiledd (2026, natt 22-06)
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
        "energiledd_dag_eks_mva": 0.21638,  # 21,64 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.15342,  # 15,34 øre/kWh ren energiledd (2026, natt 22-06)
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
        "energiledd_dag_eks_mva": 0.22382,  # 22,38 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.15382,  # 15,38 øre/kWh ren energiledd (2026, natt 22-06)
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
        # Namdal (Trøndelag) - HAR 25% mva (ikke mva-fritak)
        # Har sommer/vinter-priser, bruker vinterpriser (høyest).
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.12702,  # 12,70 øre/kWh ren energiledd (2026, vinter dag)
        "energiledd_natt_eks_mva": 0.02702,  # 2,70 øre/kWh ren energiledd (2026, vinter natt)
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
        "energiledd_dag_eks_mva": 0.2387,
        "energiledd_natt_eks_mva": 0.0787,
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
        # Flat sats inkl. 4 øre rabatt. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.131,  # 13,10 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.131,  # Flat sats - ingen dag/natt-differensiering
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
        "tiltakssone": True,  # Dekker kun Finnmark-kommuner (Nordkapp, Måsøy, Porsanger, Karasjok, Gamvik, Lebesby)
        "supported": True,
        # Tiltakssone: fritak for forbruksavgift og mva, kun Enova 1,0 øre/kWh.
        # Coordinator legger på Enova: dag 29,89 + 1,0 = 30,89 øre, natt 26,89 + 1,0 = 27,89 øre.
        "energiledd_dag_eks_mva": 0.2989,  # 29,89 øre/kWh ren energiledd (2026, tiltakssone)
        "energiledd_natt_eks_mva": 0.2689,  # 26,89 øre/kWh ren energiledd (2026, tiltakssone)
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
        "energiledd_dag_eks_mva": 0.2387,  # 23,87 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.1587,  # 15,87 øre/kWh ren energiledd (2026, natt 22-06)
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
        # Tiltakssone: ren energiledd 11,32 øre + Enova 1,0 = 12,32 øre/kWh sluttpris.
        "energiledd_dag_eks_mva": 0.1132,  # 11,32 øre/kWh ren energiledd (2026, tiltakssone)
        "energiledd_natt_eks_mva": 0.1132,  # Flat sats hele døgnet (2026)
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
        "avgiftssone": "nord_norge",  # Bindal er i Nordland (mva-fritak), men NO3 prisomrade
        "supported": True,
        # Nordland (mva-fritak). Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        # NB: Kun 2025-tariffer tilgjengelig. 2026-priser ikke publisert.
        "energiledd_dag_eks_mva": 0.263,  # 26,30 øre/kWh ren energiledd (2025, nord_norge)
        "energiledd_natt_eks_mva": 0.213,  # 21,30 øre/kWh ren energiledd (2025, nord_norge)
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
        # (tidligere Luster Energiverk)
        "energiledd_dag_eks_mva": 0.14502,  # 14,50 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.06502,  # 6,50 øre/kWh ren energiledd (2026)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.35502,  # 35,50 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.28998,  # 29,00 øre/kWh ren energiledd (2026)
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
        # De Nett PDF 2026 vinter.
        "energiledd_dag_eks_mva": 0.31398,  # 31,40 øre/kWh ren energiledd (2026, vinter)
        "energiledd_natt_eks_mva": 0.28398,  # 28,40 øre/kWh ren energiledd (2026, vinter)
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.379,  # 37,90 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.256,  # 25,60 øre/kWh ren energiledd (2026, nord_norge)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.26998,  # 27,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.20998,  # 21,00 øre/kWh ren energiledd (2026)
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
        # Kilde: Midtnett PDF 2026.
        "energiledd_dag_eks_mva": 0.23862,  # 23,86 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.18862,  # 18,86 øre/kWh ren energiledd (2026, natt 22-06)
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
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.12902,  # 12,90 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.12902,  # Flat sats - ingen dag/natt-differensiering
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
        # Kapasitetsbasert modell, ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.11158,  # 11,16 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.11158,  # Flat sats - ingen dag/natt-differensiering
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
        # Griug har ikke dag/natt-differensiering, bruker samme sats for begge.
        "energiledd_dag_eks_mva": 0.12318,  # 12,32 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.12318,  # Flat sats - ingen dag/natt-differensiering
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
        "energiledd_dag_eks_mva": 0.24502,  # 24,50 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.16502,  # 16,50 øre/kWh ren energiledd (2026)
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
        # (Austevoll Kraftlag SA). Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.29718,  # 29,72 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.29718,  # Flat sats - ingen dag/natt-differensiering
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.22502,  # 22,50 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.17502,  # 17,50 øre/kWh ren energiledd (2026)
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
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.28558,  # 28,56 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.28558,  # Flat sats - ingen dag/natt-differensiering
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.15998,  # 16,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.09998,  # 10,00 øre/kWh ren energiledd (2026)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.17998,  # 18,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.07998,  # 8,00 øre/kWh ren energiledd (2026)
        "url": "https://ke-nett.no/priser-og-vilkar/nettleiepriser/",
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
        # Kapasitetsbasert modell, ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.1763,  # 17,63 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1763,  # Flat sats - ingen dag/natt-differensiering
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.17,  # 17,00 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.17,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://kystnett.no/nettleie",
        "kapasitetstrinn": [
            (5, 493),
            (10, 890),
            (15, 1286),
            (20, 1682),
            (25, 2079),
            (50, 3268),
            (75, 5250),
            (100, 7231),
            (float("inf"), 10204),
        ],
    },
    "lucerna": {
        "name": "Lucerna",
        "prisomrade": "NO4",
        "tiltakssone": True,  # Hammerfest (Finnmark) - fritak for mva og forbruksavgift
        "supported": True,
        # Tiltakssone: ingen forbruksavgift, ingen mva, kun Enova 1,0 øre/kWh.
        # Coordinator legger på Enova: dag 19,32 + 1,0 = 20,32 øre, natt 13,32 + 1,0 = 14,32 øre.
        "energiledd_dag_eks_mva": 0.1932,  # 19,32 øre/kWh ren energiledd (2026, tiltakssone)
        "energiledd_natt_eks_mva": 0.1332,  # 13,32 øre/kWh ren energiledd (2026, tiltakssone)
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
        "energiledd_dag_eks_mva": 0.3203,  # 32,03 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.2403,  # 24,03 øre/kWh ren energiledd (2026)
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.274,  # 27,40 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.174,  # 17,40 øre/kWh ren energiledd (2026, nord_norge)
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
        # Kilde: Midtnett PDF 2026.
        "energiledd_dag_eks_mva": 0.23862,  # 23,86 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.18862,  # 18,86 øre/kWh ren energiledd (2026, natt 22-06)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.38998,  # 39,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.38998,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.mostraumnett.no/nettprisar",
        "kapasitetstrinn": [
            (2, 78),
            (5, 125),
            (10, 208),
            (15, 300),
            (20, 385),
            (25, 470),
            (50, 900),
            (75, 2650),
            (100, 3500),
            (float("inf"), 6900),
        ],
    },
    "netera": {
        "name": "Netera",
        "prisomrade": "NO3",
        "supported": True,
        # Har sesongpriser - bruker vinterpriser (høyest).
        "energiledd_dag_eks_mva": 0.2091,  # 20,91 øre/kWh ren energiledd (2026, vinter)
        "energiledd_natt_eks_mva": 0.2091,  # Flat sats - ingen dag/natt-differensiering
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.164,  # 16,40 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.164,  # Flat sats - ingen dag/natt-differensiering
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.14,  # 14,00 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.09,  # 9,00 øre/kWh ren energiledd (2026, nord_norge)
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
        "energiledd_dag_eks_mva": 0.2603,  # 26,03 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.2003,  # 20,03 øre/kWh ren energiledd (2026)
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
        "energiledd_dag_eks_mva": 0.22534,  # 22,53 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.15078,  # 15,08 øre/kWh ren energiledd (2026)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.2567,  # 25,67 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1607,  # 16,07 øre/kWh ren energiledd (2026)
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
        # Nå del av Elvia - bruker Elvia-priser fra sept 2025.
        "energiledd_dag_eks_mva": 0.2099,  # 20,99 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1299,  # 12,99 øre/kWh ren energiledd (2026)
        # Rakkestad Energi er na del av Elvia
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.20134,  # 20,13 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.20134,  # Flat sats - ingen dag/natt-differensiering
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
        "energiledd_dag_eks_mva": 0.2259,  # 22,59 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1259,  # 12,59 øre/kWh ren energiledd (2026)
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
        "energiledd_dag_eks_mva": 0.1827,  # 18,27 øre/kWh ren energiledd (2025)
        "energiledd_natt_eks_mva": 0.13278,  # 13,28 øre/kWh ren energiledd (2025)
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
        # Stannum PDF 2026. Helg har ingen reduksjon (PDF viser "Reduksjon helg: -").
        "energiledd_dag_eks_mva": 0.28334,  # 28,33 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.25334,  # 25,33 øre/kWh ren energiledd (2026)
        "url": "https://stannum.no/nettleiepriser",
        "helg_som_natt": False,
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.1411,  # 14,11 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.0411,  # 4,11 øre/kWh ren energiledd (2026, nord_norge)
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
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.18302,  # 18,30 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.18302,  # Flat sats - ingen dag/natt-differensiering
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.26198,  # 26,20 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.1995,  # 19,95 øre/kWh ren energiledd (2026)
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
    #     "energiledd_dag_eks_mva": 0,
    #     "energiledd_natt_eks_mva": 0,
    #     "url": "",
    #     "kapasitetstrinn": [],
    # },
    "sygnir": {
        "name": "Sygnir",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.22054,  # 22,05 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.22054,  # Flat sats - ingen dag/natt-differensiering
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
        # Kilde: kraftsystemet 2026.
        "energiledd_dag_eks_mva": 0.2587,  # 25,87 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.2035,  # 20,35 øre/kWh ren energiledd (2026)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.24998,  # 25,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.24998,  # Flat sats - ingen dag/natt-differensiering
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
        "energiledd_dag_eks_mva": 0.23118,  # 23,12 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.15118,  # 15,12 øre/kWh ren energiledd (2026)
        "url": "https://www.uvdalkraft.no/contact/nett/",
        # PDF 2026 inkl. mva
        "kapasitetstrinn": [
            (5, 347),
            (10, 521),
            (15, 764),
            (20, 1458),
            (25, 2153),
            (50, 3194),
            (75, 4930),
            (100, 7014),
            (float("inf"), 9791),
        ],
    },
    "vang_energiverk": {
        "name": "Vang Energiverk",
        "prisomrade": "NO1",
        "supported": True,
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.21134,  # 21,13 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.21134,  # Flat sats - ingen dag/natt-differensiering
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
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.06,  # 6,00 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.03,  # 3,00 øre/kWh ren energiledd (2026, nord_norge)
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
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.17102,  # 17,10 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.17102,  # Flat sats - ingen dag/natt-differensiering
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
        "energiledd_dag_eks_mva": 0.25198,  # 25,20 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.15798,  # 15,80 øre/kWh ren energiledd (2026)
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
        # Kilde: kraftsystemet 2026 (tidligere Røros E-verk Nett).
        "energiledd_dag_eks_mva": 0.22798,  # 22,80 øre/kWh ren energiledd (2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.16398,  # 16,40 øre/kWh ren energiledd (2026, natt 22-06)
        "url": "https://viermie.no/nettleiepriser/priser-for-kunder-med-forbruk-under-100-000-kwh-ar/",
        "kapasitetstrinn": [
            (5, 355),  # 4260/12
            (10, 515),  # 6180/12
            (15, 721),  # 8652/12
            (20, 1001),  # 12012/12
            (25, 1299),  # 15588/12
            (50, 2469),  # 29628/12
            (100, 4528),  # 54336/12
            (200, 8173),  # 98076/12
            (float("inf"), 12578),  # 150936/12
        ],
    },
    "vissi": {
        "name": "Vissi",
        "prisomrade": "NO4",
        "tiltakssone": True,  # Finnmark og Nord-Troms - fritak for mva og forbruksavgift
        "supported": True,
        # Tiltakssonen - ingen mva, ingen forbruksavgift, kun Enova 1,0 øre/kWh.
        # Coordinator legger på Enova: dag 29 + 1 = 30 øre, natt 13 + 1 = 14 øre.
        "energiledd_dag_eks_mva": 0.29,  # 29,00 øre/kWh ren energiledd (2026, tiltakssone)
        "energiledd_natt_eks_mva": 0.13,  # 13,00 øre/kWh ren energiledd (2026, tiltakssone)
        "url": "https://www.vissi.no/priser-og-vilkar/nettleie-privat/",
        "kapasitetstrinn": [
            (5, 350),  # 4200/12
            (10, 600),  # 7200/12
            (15, 813),  # 9750/12
            (20, 1025),  # 12300/12
            (25, 1238),  # 14850/12
            (50, 1938),  # 23250/12
            (75, 2594),  # 31125/12
            (100, 3188),  # 38250/12
            (150, 3813),  # 45750/12
            (200, 4313),  # 51750/12
            (float("inf"), 4938),  # 59250/12
        ],
    },
    "elvenett": {
        "name": "Elvenett",
        "prisomrade": "NO1",
        "supported": True,
        # NB: Natt er 22-05, ikke 22-06.
        "energiledd_dag_eks_mva": 0.19998,  # 20,00 øre/kWh ren energiledd (2025)
        "energiledd_natt_eks_mva": 0.10998,  # 11,00 øre/kWh ren energiledd (2025)
        "url": "https://www.elvenett.no/priser-og-avtaler/",
        "kapasitetstrinn": [
            (2, 194),  # 2325/12
            (5, 275),  # 3300/12
            (10, 380),  # 4560/12
            (15, 496),  # 5955/12
            (20, 638),  # 7650/12
            (25, 803),  # 9630/12
            (50, 1133),  # 13590/12
            (75, 1511),  # 18135/12
            (100, 1894),  # 22725/12
            (float("inf"), 2275),  # 27300/12
        ],
    },
    "etna_nett": {
        "name": "Etna Nett",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag_eks_mva": 0.2455,  # 24,55 øre/kWh ren energiledd (2025)
        "energiledd_natt_eks_mva": 0.1759,  # 17,59 øre/kWh ren energiledd (2025)
        "url": "https://etna.no/om-nettleie",
        "kapasitetstrinn": [
            (2, 319),  # 3829/12
            (5, 479),  # 5744/12
            (10, 624),  # 7484/12
            (15, 769),  # 9226/12
            (20, 1015),  # 12184/12
            (float("inf"), 1269),  # 15230/12
        ],
    },
    "tinfos": {
        "name": "Tinfos",
        "prisomrade": "NO2",
        "supported": True,
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.18998,  # 19,00 øre/kWh ren energiledd (2024)
        "energiledd_natt_eks_mva": 0.18998,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.tinfos.no/tinfos-nett/",
        "kapasitetstrinn": [
            (5, 329),  # 3945/12
            (10, 516),  # 6195/12
            (15, 704),  # 8445/12
            (20, 891),  # 10695/12
            (25, 1079),  # 12945/12
            (50, 1641),  # 19695/12
            (float("inf"), 4688),  # 56250/12
        ],
    },
    "sor_aurdal_energi": {
        "name": "Sør Aurdal Energi",
        "prisomrade": "NO1",
        "supported": True,
        # Har sesongpriser - bruker vinterpriser (høyest).
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.25518,  # 25,52 øre/kWh ren energiledd (vinter)
        "energiledd_natt_eks_mva": 0.25518,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://sae.no/tariffer",
        "kapasitetstrinn": [
            (5, 563),  # 6750/12
            (8, 650),  # 7800/12
            (15, 775),  # 9300/12
            (30, 900),  # 10800/12
            (50, 1013),  # 12150/12
            (float("inf"), 1375),  # 16500/12
        ],
    },
    # Skiakernett (Skjåk) - Fusjonert med Vevig AS fra 01.01.2025
    # Kunder i Skjåk bruker nå Vevig sine tariffer
}
