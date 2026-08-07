"""Distribution System Operators (nettselskap) data for Strømkalkulator.

Energileddsatsene lagres som ren nettleie eks. mva og eks. avgifter
(`energiledd_dag_eks_mva`, `energiledd_natt_eks_mva`). Coordinator legger på
forbruksavgift, Enova-avgift og mva basert på avgiftssone. Eksakte
mellomregninger gir mindre avrundingsfeil mot fakturaen enn å lagre
display-avrundede inkl-priser.

Kilder:
- Energileddsatser: nettselskapets prisliste (url-felt)
- Referanse/fasit: kraftsystemet/fri-nettleie (CC-BY-4.0,
  https://github.com/kraftsystemet/fri-nettleie). Satsene kryssjekkes mot
  fri-nettleie med scripts/sjekk_mot_fri_nettleie.py.
- Avgifter: skatteetaten.no (FORBRUKSAVGIFT_ALMINNELIG, ENOVA_AVGIFT i const.py)
- DSO-liste: Elhub (https://elhub.no/nettselskaper/)
- Kapasitetstrinn-struktur: NVE (https://www.nve.no/reguleringsmyndigheten/)

NB: BKK er verifisert mot faktura. Øvrige eks_mva-verdier er konvertert fra
tidligere inkl-mva-verdier (formel: inkl/1.25 - 0.0713 - 0.01 for standard-sone)
og arver ~0,5% avrunding fra display-avrundede kilder. Bør re-verifiseres mot
DSO-prisliste ved oppdatering.

Sist oppdatert: Juli 2026 (Elvia og Nettselskapet hevet priser 01.07.2026)
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, NotRequired, TypedDict

# Type for kapasitetstrinn: tuple of (kW-grense, kr/mnd)
type KapasitetstrinnTuple = tuple[float, int]

# === FASTLEDD-METODER ===
# Hvordan nettselskapet bestemmer fastleddet (kapasitetsleddet). Navnene er
# fri-nettleies (feltet `fastledd.metode` i tariff-YAML-en), slik at
# scripts/sjekk_mot_fri_nettleie.py kan sammenligne dem direkte og fange at et
# nettselskap bytter modell. Se docs/beregninger.md#kapasitetsledd.
#
# Snitt av de tre høyeste døgnmaksene i måneden. NVE-modellen, og den de aller
# fleste bruker. Default når `fastledd_metode` ikke er satt.
FASTLEDD_TRE_DOGNMAX_MND: Final[str] = "TRE_DØGNMAX_MND"
# Månedens enkeltstående høyeste time. Ellers samme trinn-tabell.
FASTLEDD_MND_MAX: Final[str] = "MND_MAX"
# Fastledd etter sikringsstørrelse (overbelastningsvern), ikke målt effekt.
# Kan ikke utledes fra effektsensoren og krever et brukervalg.
FASTLEDD_OV_TREFASE: Final[str] = "OV_TREFASE"
# Grunnbeløp + sats per kW, der kW er snittet av de fem høyeste sesongvektede
# ukestoppene over løpende tolv måneder. Ingen trinn.
FASTLEDD_FEM_VEKTET_AR: Final[str] = "FEM_VEKTET_ÅR"
# Nettselskapet publiserer ikke metoden. Vi regner som NVE-modellen og sier
# tydelig at beløpet er uverifisert, framfor å gjette på en annen modell.
FASTLEDD_UKJENT: Final[str] = "UKJENT"

FASTLEDD_METODER: Final[frozenset[str]] = frozenset(
    {
        FASTLEDD_TRE_DOGNMAX_MND,
        FASTLEDD_MND_MAX,
        FASTLEDD_OV_TREFASE,
        FASTLEDD_FEM_VEKTET_AR,
        FASTLEDD_UKJENT,
    }
)

# Metoder som slår opp i `kapasitetstrinn` med en målt kW-verdi.
FASTLEDD_TRINNBASERTE: Final[frozenset[str]] = frozenset(
    {FASTLEDD_TRE_DOGNMAX_MND, FASTLEDD_MND_MAX, FASTLEDD_UKJENT}
)


class FastleddSikringstrinn(TypedDict):
    """Ett fastledd-trinn for sikringsbasert fastledd (OV_TREFASE).

    Brukeren velger raden selv, så `label` skal gjengi raden ordrett slik
    nettselskapet skriver den i prislisten. Da slipper vi å tolke ampere mot
    systemspenning på brukerens vegne, en tolkning vi ikke har grunnlag for.
    `id` er nøkkelen som lagres i config og må aldri endres etter at den er
    sluppet i en release.

    `kr_mnd` er inkl. mva for nettselskapets egen avgiftssone, samme
    konvensjon som `kapasitetstrinn`.
    """

    id: str
    label: str
    kr_mnd: int


class FastleddLineaer(TypedDict):
    """Fastledd som grunnbeløp + sats per kW, uten trinn (FEM_VEKTET_ÅR).

    Lagres eks. mva i kr/år, som nettselskapet publiserer det. En lineær sats
    kan ikke forhåndsavrundes til kr/mnd inkl. mva uten å miste presisjon, så
    coordinator ganger opp med mva-faktoren for brukerens avgiftssone.
    """

    grunnbelop_aar_eks_mva: float
    sats_kw_aar_eks_mva: float


# Type for kapasitetstrinn dict format (used by some DSOs like Barents Nett)
class KapasitetstrinnDict(TypedDict):
    """Kapasitetstrinn entry in dict format."""

    min: int
    max: int
    pris: int


class EnergileddPeriode(TypedDict):
    """En sesongperiode med egne energileddsatser.

    Format: fra/til som "MM-DD" (begge inkludert). Krysser perioden nyttår
    (fra > til), tolkes det som "fra fra-dato til årsslutt, og fra årets
    start til til-dato". Satser er eks. mva og avgifter, som hovedfeltene
    i DSOEntry. Coordinator legger på forbruksavgift, Enova og mva basert
    på avgiftssone.

    Brukes av nettselskaper som bytter pris mellom sommer og vinter
    (Nettselskapet, De Nett, Sør Aurdal Energi). Disse publiserer nye
    priser uten varsel, så satsene må oppdateres manuelt når DSO-en
    endrer prislisten. Krever bekreftelse fra DSO-prisliste.
    """

    fra: str
    til: str
    dag_eks_mva: float
    natt_eks_mva: float


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
    terskel_inkludert: NotRequired[bool]  # Default True. False = eksakt grensetreff hører til lavere trinn.
    avgiftssone: NotRequired[str]  # Overstyrer default fra prisomrade (f.eks. Nordland-selskap i NO3)
    # DSO-spesifikke ekstra "helligdager" i tillegg til HELLIGDAGER_FASTE.
    # Format: MM-DD. Brukes for nettselskaper som tar lavtariff på dager som
    # ikke er offisielle helligdager (julaften, nyttårsaften, etc).
    # Krever bekreftelse fra ekte faktura før det legges til.
    helligdager_ekstra: NotRequired[list[str]]
    # Sesongprising. Hvis satt, overstyrer energiledd_dag/natt_eks_mva for
    # dager som ligger innenfor en periode. Periodene må dekke hele året
    # uten overlapp; ellers faller coordinator tilbake til
    # energiledd_*_eks_mva for ukjente datoer.
    energiledd_perioder: NotRequired[list[EnergileddPeriode]]
    # Nettselskapet har flere prisområder og er delt i egne oppføringer.
    # Verdien er DSO-IDene brukeren kan velge mellom. Oppføringen beholdes med
    # `supported: False` så eksisterende config-entries ikke knekker, og
    # `_check_delt_dso` ber brukeren velge riktig område. Motsatt av
    # DSO_MIGRATIONS: en fusjon kan migreres automatisk, en splitt kan ikke,
    # fordi bare brukeren vet hvilket område adressen ligger i.
    delt_i: NotRequired[list[str]]
    # Hvordan fastleddet bestemmes. Default FASTLEDD_TRE_DOGNMAX_MND (NVE).
    # Krever kilde på lik linje med satser: en feil metode gir feil beløp
    # uansett hvor riktige trinnprisene er.
    fastledd_metode: NotRequired[str]
    # Kun OV_TREFASE: radene brukeren kan velge mellom.
    fastledd_sikringstrinn: NotRequired[list[FastleddSikringstrinn]]
    # Kun FEM_VEKTET_ÅR: grunnbeløp og sats per kW.
    fastledd_lineaer: NotRequired[FastleddLineaer]
    # Kun FEM_VEKTET_ÅR: vektfaktor per måned (1-12) som effektene skaleres med
    # før de fem høyeste plukkes ut.
    fastledd_sesongfaktor: NotRequired[dict[int, float]]


@dataclass(frozen=True)
class DSOFusjon:
    """Represents a DSO merger: gammel (old key) -> ny (new key)."""

    gammel: str
    ny: str


DSO_MIGRATIONS: Final[list[DSOFusjon]] = [
    DSOFusjon(gammel="skiakernett", ny="vevig"),
]


def hent_fastledd_metode(entry: Mapping[str, Any]) -> str:
    """Fastledd-metoden for et nettselskap, med NVE-modellen som default.

    Oppføringer uten `fastledd_metode` skal oppføre seg som før, så defaulten
    må aldri endres uten at hvert nettselskap får metoden sin eksplisitt satt.
    """
    return str(entry.get("fastledd_metode", FASTLEDD_TRE_DOGNMAX_MND))


def finn_sikringstrinn(
    entry: Mapping[str, Any], trinn_id: str | None
) -> tuple[int, FastleddSikringstrinn] | None:
    """Finn valgt sikringstrinn som (1-basert radnummer, trinn).

    None hvis brukeren ikke har valgt, eller hvis den lagrede id-en ikke finnes
    hos dette nettselskapet (typisk etter et DSO-bytte). Begge tilfellene skal
    behandles som "ikke satt", aldri som trinn 1.
    """
    if not trinn_id:
        return None
    trinnliste: list[FastleddSikringstrinn] = list(entry.get("fastledd_sikringstrinn", []))
    for nummer, trinn in enumerate(trinnliste, 1):
        if trinn["id"] == trinn_id:
            return nummer, trinn
    return None


def grunnlag_i_lavere_trinn(
    grunnlag_kw: float, terskel: float, terskel_inkludert: bool
) -> bool:
    """Om effektgrunnlaget hører til trinnet under denne terskelen.

    De fleste nettselskap legger eksakt grensetreff i trinnet over, altså `<`.
    De med `terskel_inkludert: False` skriver trinnene som "til og med", og
    bruker `<=`.
    """
    if terskel_inkludert:
        return grunnlag_kw < terskel
    return grunnlag_kw <= terskel


def finn_kapasitetstrinn(
    trinn: list[KapasitetstrinnTuple], grunnlag_kw: float, terskel_inkludert: bool = True
) -> tuple[int, int, str]:
    """Slå opp fastledd for et effektgrunnlag: (kr/mnd, trinnummer, beskrivelse).

    Én definisjon av grenseoppslaget, brukt av både coordinator og tester. En
    lokal kopi i testene brukte `<=` for alle nettselskap og bekreftet dermed
    motsatt oppførsel av produksjonskoden ved eksakt grensetreff.
    """
    for i, (terskel, pris) in enumerate(trinn, 1):
        if grunnlag_i_lavere_trinn(grunnlag_kw, terskel, terskel_inkludert):
            forrige = trinn[i - 2][0] if i > 1 else 0.0
            if terskel == float("inf"):
                return pris, i, f">{forrige:.0f} kW"
            return pris, i, f"{forrige:.0f}-{terskel:.0f} kW"
    siste = len(trinn)
    forrige = trinn[-2][0] if siste > 1 else 0.0
    return trinn[-1][1], siste, f">{forrige:.0f} kW"


def finn_aktiv_periode(
    perioder: list[EnergileddPeriode], mm_dd: str
) -> EnergileddPeriode | None:
    """Finn perioden som dekker `mm_dd` ("MM-DD"). None hvis ingen treffer.

    Krysser en periode nyttår (fra > til), tolkes det som union av
    [fra, 12-31] og [01-01, til].
    """
    for periode in perioder:
        fra, til = periode["fra"], periode["til"]
        if fra <= til:
            if fra <= mm_dd <= til:
                return periode
        elif mm_dd >= fra or mm_dd <= til:
            return periode
    return None


# Distribution System Operators (DSO) with default values
# Format: {dso_id: {name, prisomrade, supported, energiledd_dag_eks_mva,
#                   energiledd_natt_eks_mva, url, kapasitetstrinn}}
#
# supported: True = har priser, False = mangler priser (trenger bidrag)
# For å legge til priser for et nettselskap:
# 1. Finn nettleiepriser på nettselskapets nettside (url-feltet)
# 2. Sett energiledd_*_eks_mva i NOK/kWh: kun nettleieleddet, eks. mva og
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
        # Verifisert mot BKK-fakturaer okt 2025 til apr 2026: hele 24.12 og 31.12
        # behandles som lavtariff (helg-tariff).
        "helligdager_ekstra": ["12-24", "12-31"],
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
        "energiledd_dag_eks_mva": 0.2899,  # 28,99 øre/kWh ren energiledd (per 01.07.2026, elvia.no 46,40 inkl.)
        "energiledd_natt_eks_mva": 0.1699,  # 16,99 øre/kWh ren energiledd (per 01.07.2026, elvia.no 31,40 inkl.)
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
        # Kilde: tariffblad_1_0_standard-tariff_privat_20260701.pdf (verifisert 2026-07-28)
        "kapasitetstrinn": [
            (2, 150),
            (5, 250),
            (10, 420),
            (15, 585),
            (20, 755),
            (25, 925),
            (50, 1760),
            (75, 2600),
            (100, 3440),
            (float("inf"), 6800),
        ],
    },
    "glitre": {
        "name": "Glitre Nett",
        "prisomrade": "NO1",
        "supported": True,
        "energiledd_dag_eks_mva": 0.256,  # 25,60 øre/kWh ren energiledd (per 01.07.2026)
        "energiledd_natt_eks_mva": 0.136,  # 13,60 øre/kWh ren energiledd (per 01.07.2026)
        "url": "https://www.glitrenett.no/kunde/nettleie-og-priser/nettleiepriser-privatkunde",
        "helg_som_natt": False,
        # Kilde: glitrenett.no per 01.07.2026 (verifisert 2026-07-28). Energileddet
        # sto stille, kun kapasitetsleddet ble hevet.
        "kapasitetstrinn": [
            (2, 160),
            (5, 233),  # 232,50 kr/mnd
            (10, 390),
            (15, 730),
            (20, 965),
            (25, 1210),
            (50, 1885),
            (75, 2990),
            (100, 3990),
            (float("inf"), 6665),
        ],
    },
    "norgesnett": {
        "name": "Norgesnett (Glitre Nett)",
        "prisomrade": "NO1",
        "supported": True,
        # Norgesnett er en del av Glitre Nett, men kunder faktureres etter egne tariffer.
        # Kilde: norgesnett.no, tabellen "Nettleiepriser privat 1. juli 2026,
        # kapasitetstariff" (per 01.07.2026, verifisert 2026-08-07). Publiserte
        # energiledd er inkl. alt: 42,16 (dag) og 27,16 (natt) øre/kWh.
        # Dag/natt-klokkeslettene under er fra tidligere kilde, ikke verifisert nå.
        "energiledd_dag_eks_mva": 0.25598,  # 25,60 øre/kWh ren energiledd (dag 06-22)
        "energiledd_natt_eks_mva": 0.13598,  # 13,60 øre/kWh ren energiledd (natt 22-06)
        "url": "https://norgesnett.no/kunde/nettleie-privat/",
        "kapasitetstrinn": [
            (2, 140),  # 0-1,99 kW
            (5, 233),  # 2-4,99 kW: 232,50 kr/mnd
            (10, 390),  # 5-9,99 kW
            (15, 695),  # 10-14,99 kW
            (20, 935),  # 15-19,99 kW
            (25, 1145),  # 20-24,99 kW
            (50, 1813),  # 25-49,99 kW: 1812,50 kr/mnd
            (75, 2813),  # 50-74,99 kW: 2812,50 kr/mnd
            (100, 3813),  # 75-99,99 kW: 3812,50 kr/mnd
            (float("inf"), 6113),  # >100 kW: 6112,50 kr/mnd
        ],
    },
    "tensio_tn": {
        "name": "Tensio TN",
        "prisomrade": "NO3",
        "supported": True,
        # Tidligere NTE Nett - Nord-Trøndelag
        "energiledd_dag_eks_mva": 0.27198,  # 27,20 øre/kWh ren energiledd (per 01.07.2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.13702,  # 13,70 øre/kWh ren energiledd (per 01.07.2026, natt 22-06)
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "helg_som_natt": False,
        # Kapasitetstrinn: fri-nettleie tensio-tn.yml, tariff gyldig fra 2026-07-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 141),
            (5, 284),
            (10, 512),
            (15, 776),
            (20, 1041),
            (25, 1305),
            (50, 2274),
            (75, 3598),
            (100, 4921),
            (150, 7123),
            (200, 9770),
            (300, 14175),
            (400, 19467),
            (500, 24759),
            (float("inf"), 30046),
        ],
    },
    "tensio_ts": {
        "name": "Tensio TS",
        "prisomrade": "NO3",
        "supported": True,
        # Tidligere Trønderenergi Nett - Sør-Trøndelag
        "energiledd_dag_eks_mva": 0.22102,  # 22,10 øre/kWh ren energiledd (per 01.07.2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.10902,  # 10,90 øre/kWh ren energiledd (per 01.07.2026, natt 22-06)
        "url": "https://www.tensio.no/no/kunde/nettleie/nettleiepriser-for-privat",
        "helg_som_natt": False,
        # Kapasitetstrinn: fri-nettleie tensio-ts.yml, tariff gyldig fra 2026-07-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 131),
            (5, 233),
            (10, 397),
            (15, 585),
            (20, 775),
            (25, 964),
            (50, 1655),
            (75, 2599),
            (100, 3544),
            (150, 5117),
            (200, 7003),
            (300, 10147),
            (400, 13925),
            (500, 17697),
            (float("inf"), 21473),
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
        # Korrigert 2026-05-25: tidligere tall trakk forbruksavgift+Enova dobbelt.
        # NO4 har ikke mva, så "u/ avgifter" hos kraftsystemet = ren netteierandel.
        #
        # Åpent spørsmål (2026-07-28): en tidligere kommentar her påsto sesong-
        # prising vinter 1.9-30.4 og sommer 1.5-31.8, uten kilde på sommersatsen,
        # og uten `energiledd_perioder`. Vi brukte altså vintersatsen hele året
        # på en påstand ingen hadde verifisert. fri-nettleie har ingen sesong for
        # Arva i det hele tatt, og satsene under matcher dem eksakt. arva.no
        # rendrer prisene med JavaScript, så de er ikke lesbare uten nettleser,
        # og fri-nettleies arva.yml er sist oppdatert 2024-10-22. Påstanden om
        # sesong er derfor fjernet framfor å bli implementert på gjetning. Se
        # begrensninger.md punkt 10.
        "energiledd_dag_eks_mva": 0.231,  # 23,10 øre/kWh ren energiledd
        "energiledd_natt_eks_mva": 0.116,  # 11,60 øre/kWh ren energiledd
        "url": "https://arva.no/ny-nettleie/Priser",
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
        # Verifisert 2026-05-30 mot fri-nettleie (NVE-referansedata): mellom.no
        # publiserer energiledd inkl. mva, men eks. forbruksavgift/Enova (de kommer
        # i tillegg). 37,21/29,34 inkl. mva ÷1,25 = 29,77/23,47 ren netteierandel.
        "energiledd_dag_eks_mva": 0.2977,  # 29,77 øre/kWh ren energiledd (2026, dag)
        "energiledd_natt_eks_mva": 0.2347,  # 23,47 øre/kWh ren energiledd (2026, natt)
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
        "energiledd_dag_eks_mva": 0.22808,  # 22,81 øre/kWh ren energiledd (per 01.07.2026, dag 06-22)
        "energiledd_natt_eks_mva": 0.14808,  # 14,81 øre/kWh ren energiledd (per 01.07.2026, natt 22-06)
        "url": "https://www.linja.no/nettleige",
        # Kapasitetstrinn: fri-nettleie linja.yml, tariff gyldig fra 2026-07-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 299),
            (5, 373),
            (10, 448),
            (15, 745),
            (20, 895),
            (25, 1044),
            (50, 1491),
            (75, 1640),
            (100, 1790),
            (float("inf"), 2236),
        ],
    },
    "nettselskapet": {
        "name": "Nettselskapet",
        "prisomrade": "NO3",
        "supported": True,
        # Namdal (Trøndelag) - HAR 25% mva (ikke mva-fritak)
        # Sesongpriser, verifisert 2026-07-28 mot nettselskapet.as og fri-nettleie:
        # vinter (nov-apr) 12,7/2,7, sommer (mai-okt) 11,6/1,6. Base = vinter (fallback).
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.127,  # 12,70 øre/kWh ren energiledd (vinter dag)
        "energiledd_natt_eks_mva": 0.027,  # 2,70 øre/kWh ren energiledd (vinter natt)
        "energiledd_perioder": [
            {"fra": "11-01", "til": "04-30", "dag_eks_mva": 0.127, "natt_eks_mva": 0.027},
            {"fra": "05-01", "til": "10-31", "dag_eks_mva": 0.116, "natt_eks_mva": 0.016},
        ],
        # Prislisten skiller kun på klokkeslett (dag 06-22, natt 22-06), ingen
        # helgetariff. Bekreftet av kunde i GitHub-issue #11.
        "helg_som_natt": False,
        "url": "https://nettselskapet.as/strompris",
        # Kilde: nettselskapet.as/strompris per 01.07.2026 (verifisert 2026-07-28)
        "kapasitetstrinn": [
            (2, 163),  # 0-2 kW: 162,50 kr/mnd
            (5, 300),  # 2-5 kW: 300 kr/mnd
            (10, 513),  # 5-10 kW: 512,50 kr/mnd
            (15, 763),  # 10-15 kW: 762,50 kr/mnd
            (20, 988),  # 15-20 kW: 987,50 kr/mnd
            (25, 1238),  # 20-25 kW: 1237,50 kr/mnd
            (50, 2125),  # 25-50 kW: 2125 kr/mnd
            (float("inf"), 3325),  # 50-75 kW: 3325 kr/mnd
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
        # Alut leverer til Alta, Loppa og Kvænangen (alut.no/om-alut/, verifisert
        # 2026-07-28). Alta og Loppa er Finnmark, Kvænangen er en av Nord-Troms-
        # kommunene, så hele området ligger i tiltakssonen med fritak for både
        # forbruksavgift og mva. Uten dette la vi på 7,13 øre/kWh som ikke skal
        # betales, altså 54% for høyt energiledd.
        "tiltakssone": True,
        "supported": True,
        # Korrigert 2026-05-25: Alut publiserer 13,10 inkl. Enova (vanlig norsk konvensjon).
        # Ren netteierandel: 13,10 - 1,00 = 12,10. Tidligere lagret 13,10 dobbelt-tellet Enova.
        # At prislisten deres viser 13,10 og ikke 20,23 bekrefter tiltakssonen:
        # 12,10 + Enova 1,00 uten forbruksavgift. Gyldig fra 01.07.2025.
        "energiledd_dag_eks_mva": 0.121,  # 12,10 øre/kWh ren energiledd
        "energiledd_natt_eks_mva": 0.121,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://alut.no/nettleie/",
        # Fastleddet følger overbelastningsvernet, ikke målt effekt.
        # Kilde: alut.no/nettleie/ tabell "Nettleie for 2026", kundegruppe
        # "Husholdning og hytter": inntil 3 x 125 A 3 500 kr/år, over 3 x 125 A
        # 4 500 kr/år. Kryssjekket mot fri-nettleie alut.yml (tariff 2025-07-01,
        # metode OV_TREFASE, terskel 0 -> 3500 og 125 -> 4500 kr/år eks. mva).
        # NO4-husholdninger har mva-fritak, så kr/mnd = kr/år / 12.
        "fastledd_metode": FASTLEDD_OV_TREFASE,
        "fastledd_sikringstrinn": [
            {"id": "inntil_3x125a", "label": "Inntil 3 x 125 A", "kr_mnd": 292},
            {"id": "over_3x125a", "label": "Over 3 x 125 A", "kr_mnd": 375},
        ],
        "kapasitetstrinn": [],
    },
    # =========================================================================
    # Area Nett har tre prisområder med hver sin tariff. Kilde for alle tre:
    # area.no "Nettleietariffer 2026 inkl enovavgift"
    # (getfile.php/132156-1766066155/Filer/20251218_Tariffer%202026.pdf,
    # verifisert 2026-07-28), kryssjekket mot fri-nettleie area-nettinord.yml,
    # area-luostejok.yml og area-lega.yml. Prisbladet er oppgitt inkl. Enova,
    # og hele området ligger i tiltakssonen uten mva og forbruksavgift, så ren
    # energiledd = publisert sats minus 1,00 øre. Alle tolv sesong- og
    # døgnkombinasjonene stemmer med fri-nettleie.
    # =========================================================================
    "area_nett_omrade1": {
        "name": "Area Nett Område 1 (Nordkapp, Måsøy)",
        "prisomrade": "NO4",
        "tiltakssone": True,
        "supported": True,
        # Nordkapp, Måsøy, vestsiden av Porsangerfjorden, samt Kokelv og
        # Refsnes i Hammerfest.
        "energiledd_dag_eks_mva": 0.2989,  # vinter dag (30,89 publisert)
        "energiledd_natt_eks_mva": 0.2689,  # vinter natt (27,89 publisert)
        "energiledd_perioder": [
            {"fra": "01-01", "til": "03-31", "dag_eks_mva": 0.2989, "natt_eks_mva": 0.2689},
            {"fra": "04-01", "til": "12-31", "dag_eks_mva": 0.2689, "natt_eks_mva": 0.2489},
        ],
        "url": "https://www.area.no/kunde-og-nettleie/priser-og-nettleie/",
        "kapasitetstrinn": [
            (2, 525),
            (5, 551),
            (10, 604),
            (15, 840),
            (20, 945),
            (25, 1103),
            (float("inf"), 1365),
        ],
    },
    "area_nett_omrade2": {
        "name": "Area Nett Område 2 (Karasjok, Porsanger)",
        "prisomrade": "NO4",
        "tiltakssone": True,
        "supported": True,
        # Karasjok og Porsanger, unntatt vestsiden av Porsangerfjorden.
        "energiledd_dag_eks_mva": 0.2989,
        "energiledd_natt_eks_mva": 0.2689,
        "energiledd_perioder": [
            {"fra": "01-01", "til": "03-31", "dag_eks_mva": 0.2989, "natt_eks_mva": 0.2689},
            {"fra": "04-01", "til": "12-31", "dag_eks_mva": 0.2689, "natt_eks_mva": 0.2489},
        ],
        "url": "https://www.area.no/kunde-og-nettleie/priser-og-nettleie/",
        "kapasitetstrinn": [
            (2, 390),
            (5, 527),
            (10, 585),
            (15, 840),
            (20, 945),
            (25, 1102),
            (float("inf"), 1365),
        ],
    },
    "area_nett_omrade3": {
        "name": "Area Nett Område 3 (Gamvik, Lebesby)",
        "prisomrade": "NO4",
        "tiltakssone": True,
        "supported": True,
        "energiledd_dag_eks_mva": 0.269,  # vinter dag (27,90 publisert)
        "energiledd_natt_eks_mva": 0.239,  # vinter natt (24,90 publisert)
        "energiledd_perioder": [
            {"fra": "01-01", "til": "03-31", "dag_eks_mva": 0.269, "natt_eks_mva": 0.239},
            {"fra": "04-01", "til": "12-31", "dag_eks_mva": 0.239, "natt_eks_mva": 0.219},
        ],
        "url": "https://www.area.no/kunde-og-nettleie/priser-og-nettleie/",
        "kapasitetstrinn": [
            (2, 358),
            (5, 465),
            (10, 572),
            (15, 840),
            (20, 945),
            (25, 1102),
            (float("inf"), 1365),
        ],
    },
    "area_nett": {
        "name": "Area Nett (velg område)",
        "prisomrade": "NO4",
        "tiltakssone": True,
        # Utfaset: én oppføring kan ikke dekke tre prisområder med ulik pris.
        # Skjult for nye oppsett, og `delt_i` gir eksisterende brukere et
        # repair-varsel som ber dem velge område.
        "supported": False,
        "delt_i": ["area_nett_omrade1", "area_nett_omrade2", "area_nett_omrade3"],
        # Interim inntil brukeren velger: område 2, det midterste av de tre.
        # Tidligere lå her 250/350/500/... kr/mnd, tall som ikke finnes i noen
        # av områdene og som bommet med 108 til 275 kr/mnd for alle. Område 2
        # er feil for to av tre, men nærmere for alle enn det som sto her.
        "energiledd_dag_eks_mva": 0.2989,
        "energiledd_natt_eks_mva": 0.2689,
        "energiledd_perioder": [
            {"fra": "01-01", "til": "03-31", "dag_eks_mva": 0.2989, "natt_eks_mva": 0.2689},
            {"fra": "04-01", "til": "12-31", "dag_eks_mva": 0.2689, "natt_eks_mva": 0.2489},
        ],
        "url": "https://www.area.no/kunde-og-nettleie/priser-og-nettleie/",
        "kapasitetstrinn": [
            (2, 390),
            (5, 527),
            (10, 585),
            (15, 840),
            (20, 945),
            (25, 1102),
            (float("inf"), 1365),
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
        "terskel_inkludert": False,
        "name": "Bindal Kraftnett",
        "prisomrade": "NO3",
        "avgiftssone": "nord_norge",  # Bindal er i Nordland (mva-fritak), men NO3 prisomrade
        "supported": True,
        # Nordland (mva-fritak). Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        # NB: Kun 2025-tariffer tilgjengelig. 2026-priser ikke publisert.
        "energiledd_dag_eks_mva": 0.263,  # 26,30 øre/kWh ren energiledd (2025, nord_norge)
        "energiledd_natt_eks_mva": 0.213,  # 21,30 øre/kWh ren energiledd (2025, nord_norge)
        "url": "https://bindalkraftlag.no/tariffer",
        # Kapasitetstrinn: fri-nettleie bindalkraftlag.yml, tariff gyldig fra 2025-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 264),
            (10, 395),
            (15, 580),
            (20, 738),
            (25, 896),
            (30, 1055),
            (50, 1318),
            (75, 2109),
            (100, 3164),
            (float("inf"), 3954),
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
        # Kapasitetstrinn: fri-nettleie breheim.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 225),
            (10, 450),
            (15, 675),
            (20, 900),
            (25, 1138),
            (50, 2263),
            (75, 3400),
            (100, 4538),
            (150, 6800),
            (200, 9075),
            (float("inf"), 13613),
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
        # Kapasitetstrinn: fri-nettleie bomlokraftnett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 210),
            (5, 300),
            (10, 400),
            (15, 525),
            (20, 700),
            (25, 875),
            (50, 2000),
            (75, 3000),
            (100, 4000),
            (float("inf"), 5000),
        ],
    },
    "de_nett": {
        "name": "De Nett",
        "prisomrade": "NO2",
        "supported": True,
        # Verifisert mot offisiell PDF 2026 (denett.no/uploads/Nettleietariffer-fra-01.01.2026...).
        # Vinter (okt-mars): dag 31,40 / natt 28,40 øre/kWh ren energiledd.
        # Sommer (apr-sep): dag 26,60 / natt 23,60 øre/kWh ren energiledd.
        # PDF-en oppgir base + "Reduksjon energiledd natt" 3,00 øre/kWh (eks. mva).
        "energiledd_dag_eks_mva": 0.314,
        "energiledd_natt_eks_mva": 0.284,
        "energiledd_perioder": [
            {"fra": "10-01", "til": "03-31", "dag_eks_mva": 0.314, "natt_eks_mva": 0.284},
            {"fra": "04-01", "til": "09-30", "dag_eks_mva": 0.266, "natt_eks_mva": 0.236},
        ],
        "url": "https://denett.no/priser-tariffer/",
        # Kapasitetstrinn: fri-nettleie denett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 358),
            (5, 461),
            (10, 564),
            (15, 778),
            (20, 984),
            (25, 1196),
            (50, 1815),
            (75, 2860),
            (100, 3905),
            (150, 5500),
            (200, 7563),
            (float("inf"), 10690),
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
        # Kapasitetstrinn: fri-nettleie enida.yml, tariff gyldig fra 2025-08-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 290),
            (5, 350),
            (10, 475),
            (15, 569),
            (20, 679),
            (25, 790),
            (50, 1250),
            (75, 1875),
            (100, 2500),
            (float("inf"), 5000),
        ],
    },
    "everket": {
        "name": "Everket",
        "prisomrade": "NO1",
        "supported": True,
        # Korrigert 2026-05-25: feil prisomrade (sto NO2, Everket er Notodden = NO1).
        # Også feil tall: tidligere kopiert fra Midtnett. Riktig flat 19,20 fra 01.10.2025.
        # Kilde: PDF 251001-Nettleie-Everket. "Energiledd eks. mva" + avgifter legges på separat.
        "energiledd_dag_eks_mva": 0.192,
        "energiledd_natt_eks_mva": 0.192,
        "url": "https://everket-notodden.no/",
        # Kapasitetstrinn: fri-nettleie everket.yml, tariff gyldig fra 2025-10-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 310),
            (5, 380),
            (10, 480),
            (15, 630),
            (20, 780),
            (25, 1000),
            (50, 1350),
            (75, 1850),
            (100, 2500),
            (150, 3400),
            (200, 4500),
            (float("inf"), 6000),
        ],
    },
    "fjellnett": {
        "name": "Fjellnett",
        "prisomrade": "NO3",
        "supported": True,
        # Kilde: fjellnett.no/nettleie/nettleiepriser/ "Privatkunder fra
        # 1.7.2026". Siden oppgir selv eks-avgift-tallene: energiledd 14,80
        # øre/kWh, grunnbeløp 2 000 kr/år, fastledd effekt 589 kr/kW/år.
        # fri-nettleie fjellnett.yml ligger én tariff bak (1.1.2026: 12,90
        # øre og 534 kr/kW), se KJENTE_AVVIK i scripts/sjekk_mot_fri_nettleie.py.
        "energiledd_dag_eks_mva": 0.148,  # 14,80 øre/kWh ren energiledd (01.07.2026)
        "energiledd_natt_eks_mva": 0.148,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.fjellnett.no/nettleie/nettleiepriser/",
        # Fjellnett har ingen trinn: fastleddet er grunnbeløp + sats per kW, der
        # kW er snittet av de fem høyeste sesongvektede ukestoppene over
        # løpende tolv måneder. Sesongfaktorene står i samme tabell på siden.
        "fastledd_metode": FASTLEDD_FEM_VEKTET_AR,
        "fastledd_lineaer": {
            "grunnbelop_aar_eks_mva": 2000,
            "sats_kw_aar_eks_mva": 589,
        },
        "fastledd_sesongfaktor": {
            1: 1.00,
            2: 1.00,
            3: 0.85,
            4: 0.50,
            5: 0.30,
            6: 0.25,
            7: 0.25,
            8: 0.25,
            9: 0.30,
            10: 0.45,
            11: 0.70,
            12: 0.95,
        },
        "kapasitetstrinn": [],
    },
    "fore": {
        "terskel_inkludert": False,
        "name": "Føre",
        "prisomrade": "NO2",
        "supported": True,
        # Korrigert 2026-05-25: tidligere 11,16 hadde trukket avgifter dobbelt.
        # Riktig flat 19,29 ren energiledd. Føre publiserer "Energiledd eks. mva" + avgifter separat.
        # Kapasitetsbasert modell, ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.1929,
        "energiledd_natt_eks_mva": 0.1929,
        "url": "https://foere.net/nettleie/",
        # Kapasitetstrinn: fri-nettleie foere.yml, tariff gyldig fra 2025-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 329),
            (5, 428),
            (10, 526),
            (15, 625),
            (20, 724),
            (25, 1381),
            (50, 2039),
            (75, 2696),
            (100, 3354),
            (150, 4011),
            (200, 4669),
            (float("inf"), 5326),
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
        # Kapasitetstrinn: fri-nettleie haringnett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 275),
            (5, 375),
            (10, 575),
            (15, 875),
            (20, 1050),
            (25, 1250),
            (50, 2500),
            (75, 3750),
            (100, 5000),
            (float("inf"), 7500),
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
        # Kapasitetstrinn: fri-nettleie havnett.yml, tariff gyldig fra 2024-08-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 250),
            (10, 320),
            (15, 563),
            (20, 788),
            (float("inf"), 863),
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
        # Kapasitetstrinn: fri-nettleie holandogsetskogelverk.yml, tariff gyldig fra 2025-07-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 200),
            (5, 240),
            (10, 350),
            (15, 440),
            (20, 590),
            (25, 690),
            (50, 1450),
            (75, 2200),
            (100, 3000),
            (float("inf"), 5900),
        ],
    },
    "indre_hordaland": {
        "name": "Indre Hordaland Kraftnett",
        "prisomrade": "NO5",
        "supported": True,
        # Flat sats - ingen dag/natt-differensiering.
        "energiledd_dag_eks_mva": 0.29,  # 29,00 øre/kWh ren energiledd (per 01.06.2026)
        "energiledd_natt_eks_mva": 0.29,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://ihk.no/prisar/nettleige",
        # Kapasitetstrinn: fri-nettleie indrehordalandkraftnett.yml, tariff gyldig fra 2026-06-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 265),
            (5, 340),
            (10, 465),
            (15, 725),
            (20, 1000),
            (25, 1250),
            (50, 2000),
            (75, 3250),
            (100, 4500),
            (float("inf"), 7500),
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
        # Kapasitetstrinn: fri-nettleie jaereneverk.yml, tariff gyldig fra 2025-09-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 198),
            (5, 319),
            (10, 510),
            (15, 750),
            (20, 991),
            (25, 1231),
            (50, 1951),
            (75, 3153),
            (100, 4354),
            (150, 6156),
            (200, 8555),
            (float("inf"), 10954),
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
        # Kapasitetstrinn: fri-nettleie kenett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 250),
            (10, 375),
            (15, 563),
            (20, 838),
            (25, 1013),
            (50, 2063),
            (75, 2625),
            (100, 3500),
            (float("inf"), 6738),
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
        # Kapasitetstrinn: fri-nettleie klive.yml, tariff gyldig fra 2024-11-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 481),
            (10, 597),
            (15, 792),
            (20, 1057),
            (25, 1321),
            (50, 2642),
            (75, 3963),
            (100, 5284),
            (150, 7926),
            (200, 10568),
            (300, 15852),
            (500, 26419),
            (float("inf"), 36987),
        ],
    },
    "kystnett": {
        "name": "Kystnett",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.18,  # 18,00 øre/kWh ren energiledd (nord_norge)
        "energiledd_natt_eks_mva": 0.18,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://kystnett.no/nettleie",
        # Kapasitetstrinn: fri-nettleie kystnett.yml, tariff gyldig fra 2024-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 493),
            (10, 890),
            (15, 1286),
            (20, 1682),
            (25, 2079),
            (50, 3268),
            (75, 5250),
            (100, 7231),
            (150, 10204),
            (float("inf"), 14168),
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
        # Kapasitetstrinn: fri-nettleie lucerna.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 259),
            (5, 311),
            (10, 376),
            (15, 415),
            (20, 519),
            (25, 584),
            (50, 649),
            (75, 713),
            (float("inf"), 778),
        ],
    },
    "lysna": {
        "name": "Lysna",
        "prisomrade": "NO5",
        "supported": True,
        "energiledd_dag_eks_mva": 0.3203,  # 32,03 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.2403,  # 24,03 øre/kWh ren energiledd (2026)
        "url": "https://lysna.no/prisar-for-private-kundar-2024",
        # Kapasitetstrinn: fri-nettleie lysna.yml, tariff gyldig fra 2024-02-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 388),
            (5, 494),
            (10, 596),
            (15, 725),
            (20, 856),
            (float("inf"), 981),
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
        # Kapasitetstrinn: fri-nettleie meloy.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 305),
            (5, 366),
            (10, 396),
            (15, 427),
            (20, 457),
            (25, 533),
            (50, 579),
            (75, 640),
            (100, 701),
            (float("inf"), 762),
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
        # Korrigert 2026-05-25: Netera fjernet sesongprising i 2026. Flat 20,0 hele året.
        # Tidligere 2025-tariff (20,91) hadde Høylast vinter 20,9 / lavlast 18,6.
        "energiledd_dag_eks_mva": 0.20,  # 20,0 øre/kWh ren energiledd (2026, flat)
        "energiledd_natt_eks_mva": 0.20,
        "url": "https://www.netera.no/nettleie/avtaler/privat/",
        # Fastleddet følger sikringsstørrelse, og satsen avhenger av
        # systemspenningen (3x230 V IT eller 3x400 V TN). Derfor er radene
        # gjengitt ordrett fra prislisten i stedet for å bli utledet fra ampere.
        # Kilde: netera.no/nettleie/avtaler/privat/ prisliste gyldig fra
        # 01.01.2026 ("Alle priser er inkl. mva"): 0-10 A 230 V 2 000 kr/år,
        # 11-63 A 230 V 4 000, 63-125 A 230 V 8 000, 0-40 A 400 V 4 000,
        # 40-80 A 400 V 8 000. Kryssjekket mot fri-nettleie netera.yml (tariff
        # 2026-01-01, metode OV_TREFASE, 1600/3200/6400 kr/år eks. mva).
        "fastledd_metode": FASTLEDD_OV_TREFASE,
        "fastledd_sikringstrinn": [
            {"id": "230v_0_10", "label": "0-10 A (230 V)", "kr_mnd": 167},
            {"id": "230v_11_63", "label": "11-63 A (230 V)", "kr_mnd": 333},
            {"id": "230v_63_125", "label": "63-125 A (230 V)", "kr_mnd": 667},
            {"id": "400v_0_40", "label": "0-40 A (400 V)", "kr_mnd": 333},
            {"id": "400v_40_80", "label": "40-80 A (400 V)", "kr_mnd": 667},
        ],
        "kapasitetstrinn": [],
    },
    "noranett_andoy": {
        "name": "Noranett Andøy",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.164,  # 16,40 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.164,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://www.noranett.no/nettleiepriser/nettleiepriser-andoy-fra-1-1-2026-article4140-2415.html",
        # Kapasitetstrinn: fri-nettleie noranett-andoy.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 310),
            (4, 410),
            (6, 520),
            (8, 630),
            (10, 730),
            (15, 920),
            (20, 1180),
            (25, 1450),
            (30, 1700),
            (35, 1980),
            (40, 2260),
            (45, 2540),
            (50, 2830),
            (75, 3600),
            (100, 4950),
            (125, 6340),
            (150, 7730),
            (175, 9120),
            (200, 10520),
            (float("inf"), 11910),
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
        # Kapasitetstrinn: fri-nettleie noranett-hadsel.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 270),
            (4, 350),
            (6, 420),
            (8, 490),
            (10, 560),
            (15, 650),
            (20, 820),
            (25, 980),
            (30, 1170),
            (35, 1330),
            (40, 1490),
            (45, 1650),
            (50, 1820),
            (75, 2280),
            (100, 3090),
            (125, 3940),
            (150, 4810),
            (175, 5690),
            (200, 6560),
            (float("inf"), 7430),
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
        # Kapasitetstrinn: fri-nettleie norefjell.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 243),
            (5, 315),
            (10, 435),
            (15, 653),
            (20, 846),
            (25, 1040),
            (50, 1694),
            (75, 2540),
            (100, 3386),
            (float("inf"), 4838),
        ],
    },
    "r_nett": {
        "name": "R-Nett",
        "prisomrade": "NO1",
        "supported": True,
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.2647,  # 26,47 øre/kWh ren energiledd (per 01.06.2026)
        "energiledd_natt_eks_mva": 0.1687,  # 16,87 øre/kWh ren energiledd (per 01.06.2026)
        "url": "https://r-nett.no/overforingspriser/",
        # Kapasitetstrinn: fri-nettleie rnett.yml, tariff gyldig fra 2026-06-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 343),
            (10, 514),
            (15, 754),
            (20, 1439),
            (25, 2124),
            (50, 3152),
            (75, 4866),
            (100, 6921),
            (float("inf"), 9663),
        ],
    },
    "rakkestad_energi": {
        "name": "Rakkestad Energi",
        "prisomrade": "NO1",
        "supported": True,
        # Nå del av Elvia - bruker Elvia-priser fra sept 2025.
        "energiledd_dag_eks_mva": 0.2899,  # 28,99 øre/kWh ren energiledd (Elvia-priser, jf. fri-nettleie #248, per 01.07.2026)
        "energiledd_natt_eks_mva": 0.1699,  # 16,99 øre/kWh ren energiledd (per 01.07.2026)
        # Rakkestad Energi er na del av Elvia
        "url": "https://www.elvia.no/nettleie/alt-om-nettleiepriser/nettleie-pris/",
        # Samme trinn som Elvia (tariffblad_1_0_standard-tariff_privat_20260701.pdf)
        "kapasitetstrinn": [
            (2, 150),
            (5, 250),
            (10, 420),
            (15, 585),
            (20, 755),
            (25, 925),
            (50, 1760),
            (75, 2600),
            (100, 3440),
            (float("inf"), 6800),
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
        # Kapasitetstrinn: fri-nettleie rknett.yml, tariff gyldig fra 2025-10-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 266),
            (5, 346),
            (10, 480),
            (15, 614),
            (20, 748),
            (25, 880),
            (50, 1548),
            (75, 2214),
            (100, 2881),
            (150, 4215),
            (200, 5549),
            (float("inf"), 8004),
        ],
    },
    "romsdalsnett": {
        "name": "Romsdalsnett",
        "prisomrade": "NO3",
        "supported": True,
        # Verifisert 2026-05-30 mot fri-nettleie (NVE-referansedata): publisert
        # eks. forbruksavgift/Enova, ikke trekk dem fra. Natt = grunnpris.
        "energiledd_dag_eks_mva": 0.3072,  # 30,72 øre/kWh ren energiledd (2026, dag)
        "energiledd_natt_eks_mva": 0.2072,  # 20,72 øre/kWh ren energiledd (2026, natt)
        "url": "https://www.romsdalsnettas.no/nettleie/",
        # Kapasitetstrinn: fri-nettleie romsdalsnett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 290),
            (5, 363),
            (10, 435),
            (15, 725),
            (20, 1015),
            (25, 1160),
            (50, 1594),
            (75, 2174),
            (100, 2464),
            (float("inf"), 2899),
        ],
    },
    "s_nett": {
        "name": "S-Nett",
        "prisomrade": "NO3",
        "supported": True,
        # Verifisert 2026-05-30 mot fri-nettleie (NVE-referansedata): snett.no
        # oppgir eks. mva, og forbruksavgift/Enova kommer i tillegg. Ikke trekk dem fra.
        "energiledd_dag_eks_mva": 0.264,  # 26,40 øre/kWh ren energiledd (2026, dag)
        "energiledd_natt_eks_mva": 0.2141,  # 21,41 øre/kWh ren energiledd (2026, natt)
        "url": "https://snett.no/nettleie-forbruk-under-100-000-kwh",
        # Kapasitetstrinn: fri-nettleie snett.yml, tariff gyldig fra 2025-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 263),
            (5, 364),
            (10, 526),
            (15, 728),
            (20, 930),
            (25, 1133),
            (50, 1740),
            (75, 2751),
            (100, 3763),
            (150, 5281),
            (200, 7304),
            (float("inf"), 10340),
        ],
    },
    "stannum": {
        "name": "Stannum",
        "prisomrade": "NO2",
        "supported": True,
        # Verifisert 2026-05-30 mot fri-nettleie (Stannum PDF 01.10.25): prisen falt
        # 2025-10-01 fra 28,33/25,33 til 25,01/22,01. Helg har ingen reduksjon.
        "energiledd_dag_eks_mva": 0.2501,  # 25,01 øre/kWh ren energiledd (fra 01.10.2025)
        "energiledd_natt_eks_mva": 0.2201,  # 22,01 øre/kWh ren energiledd (fra 01.10.2025)
        "url": "https://stannum.no/nettleiepriser",
        "helg_som_natt": False,
        # Kapasitetstrinn: fri-nettleie stannum.yml, tariff gyldig fra 2025-10-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 316),
            (5, 379),
            (10, 411),
            (15, 474),
            (20, 537),
            (25, 553),
            (50, 600),
            (75, 664),
            (100, 727),
            (float("inf"), 790),
        ],
    },
    "stram": {
        "terskel_inkludert": False,
        "name": "Stram",
        "prisomrade": "NO4",
        "supported": True,
        # NO4 mva-fritak. Coordinator legger på forbruksavgift 7,13 + Enova 1,0.
        "energiledd_dag_eks_mva": 0.1411,  # 14,11 øre/kWh ren energiledd (2026, nord_norge)
        "energiledd_natt_eks_mva": 0.0411,  # 4,11 øre/kWh ren energiledd (2026, nord_norge)
        "url": "https://www.stram.no/nettleiepris",
        # Kapasitetstrinn: fri-nettleie stram.yml, tariff gyldig fra 2024-10-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 110),
            (5, 330),
            (10, 441),
            (15, 551),
            (20, 661),
            (25, 771),
            (50, 1982),
            (75, 3194),
            (100, 4405),
            (float("inf"), 6828),
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
        # Verifisert 2026-05-30 mot fri-nettleie (NVE-referansedata): straumnett.no
        # oppgir energiledd inkl. mva, men forbruksavgift/Enova kommer i tillegg.
        # Tidligere trakk vi feilaktig fra 8,13 øre (forbruksavgift+Enova).
        # 2026: grunnpris 15,96 (natt) / høylast 20,96 (dag), eks. avgifter.
        # Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + 25% mva.
        "energiledd_dag_eks_mva": 0.2096,  # 20,96 øre/kWh ren energiledd (2026, dag)
        "energiledd_natt_eks_mva": 0.1596,  # 15,96 øre/kWh ren energiledd (2026, natt)
        "url": "https://straumnett.no/prisar-for-nettleige",
        # Kapasitetstrinn: fri-nettleie straumnett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 438),
            (5, 526),
            (10, 570),
            (15, 614),
            (20, 658),
            (25, 766),
            (50, 833),
            (75, 920),
            (100, 1008),
            (float("inf"), 1095),
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
        # Kapasitetstrinn: fri-nettleie sygnir.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
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
            (float("inf"), 3913),
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
        # Kapasitetstrinn: fri-nettleie tendranett.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 230),
            (5, 299),
            (10, 368),
            (15, 506),
            (20, 644),
            (25, 782),
            (50, 966),
            (75, 1151),
            (100, 1335),
            (float("inf"), 1381),
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
        # Kapasitetstrinn: fri-nettleie telemark.yml, tariff gyldig fra 2025-03-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 355),
            (10, 453),
            (15, 846),
            (20, 1139),
            (25, 1403),
            (50, 2425),
            (75, 3815),
            (float("inf"), 5319),
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
        # Verifisert 2026-05-30 mot fri-nettleie + vangenergi.no: nettsiden oppgir
        # 21,13 øre/kWh eks. mva INKL. forbruksavgift+Enova. Ren netteierandel =
        # 21,13 - 8,13 = 13,00. Coordinator legger på forbruksavgift 7,13 + Enova 1,0 + mva.
        "energiledd_dag_eks_mva": 0.13,  # 13,00 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.13,  # Flat sats - ingen dag/natt-differensiering
        "url": "https://vangenergi.no/forbrukarkundar",
        # Kapasitetstrinn: fri-nettleie vang.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 563),
            (5, 688),
            (8, 819),
            (12, 950),
            (18, 1106),
            (25, 1269),
            (float("inf"), 1456),
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
        # Kapasitetstrinn: fri-nettleie vestall.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 306),
            (5, 457),
            (10, 763),
            (15, 1078),
            (20, 1394),
            (25, 1696),
            (50, 2630),
            (75, 2970),
            (100, 4062),
            (float("inf"), 5879),
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
        # Kapasitetstrinn: fri-nettleie vestmar.yml, tariff gyldig fra 2026-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 364),
            (10, 643),
            (15, 931),
            (20, 1213),
            (25, 1495),
            (50, 2338),
            (75, 3750),
            (100, 5125),
            (150, 7250),
            (200, 10063),
            (float("inf"), 14250),
        ],
    },
    "vevig": {
        "name": "Vevig",
        "prisomrade": "NO3",
        "supported": True,
        "energiledd_dag_eks_mva": 0.25198,  # 25,20 øre/kWh ren energiledd (2026)
        "energiledd_natt_eks_mva": 0.15798,  # 15,80 øre/kWh ren energiledd (2026)
        "url": "https://www.vevig.no/nettleie-og-vilkar/nettleie-privat",
        # Kapasitetstrinn: fri-nettleie vevig.yml, tariff gyldig fra 2025-07-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 251),
            (5, 326),
            (10, 454),
            (15, 581),
            (20, 710),
            (25, 835),
            (30, 963),
            (40, 1218),
            (50, 1556),
            (75, 2104),
            (100, 2739),
            (125, 3371),
            (150, 4008),
            (200, 5275),
            (300, 7301),
            (400, 10206),
            (float("inf"), 20488),
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
        # Kapasitetstrinn: fri-nettleie vissi.yml, tariff gyldig fra 2025-01-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (5, 280),
            (10, 480),
            (15, 650),
            (20, 820),
            (25, 990),
            (50, 1550),
            (75, 2075),
            (100, 2550),
            (150, 3050),
            (200, 3450),
            (float("inf"), 3950),
        ],
    },
    "elvenett": {
        "name": "Elvenett",
        "prisomrade": "NO1",
        "supported": True,
        # Dag-vinduet 06-22 er globalt (DAY_RATE_START_HOUR/END_HOUR), så en
        # tidligere kommentar her om at natten slutter 05:00 hadde ingen virkning.
        # fri-nettleie oppgir høylast 6-21 for Elvenett, altså dag fra 06 som hos
        # de andre, så det var ikke noe å implementere. Fjernet 2026-07-28.
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
        # Verifisert 2026-05-30 mot fri-nettleie (Etna-Nett tariff 1. mai 2026):
        # prisen steg 2026-05-01 fra 24,55/17,59 til 25,55/18,59.
        "energiledd_dag_eks_mva": 0.2555,  # 25,55 øre/kWh ren energiledd (2026, fra 01.05)
        "energiledd_natt_eks_mva": 0.1859,  # 18,59 øre/kWh ren energiledd (2026, fra 01.05)
        "url": "https://etna.no/om-nettleie",
        # Kapasitetstrinn: fri-nettleie etna.yml, tariff gyldig fra 2026-05-01 (hentet 2026-07-28)
        "kapasitetstrinn": [
            (2, 350),
            (5, 525),
            (10, 623),
            (15, 769),
            (20, 1015),
            (float("inf"), 1269),
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
        # Tinfos publiserer ikke tariffen sin, og fri-nettleie har en åpen TODO
        # på det (tinfos.yml: "Tinfos publiserer ikke tariffer på sine sider.
        # Har sendt epost til post@tinfos.no", sist_oppdatert 2024-11-24). Vi vet
        # altså ikke hvilken kW-verdi trinnene slås opp med, og regner som
        # NVE-modellen. Beløpet er derfor uverifisert, og sensoren sier det.
        # Trinnprisene under er fri-nettleies kr/år eks. mva delt på 12 med 25 % mva.
        "fastledd_metode": FASTLEDD_UKJENT,
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
        # Korrigert 2026-05-25: lagt på sesongprising (verifisert mot SAE PDF 2026).
        # Vinter (okt-mar) 25,52 / sommer (apr-sep) 21,52. Flat sats, ingen dag/natt.
        "energiledd_dag_eks_mva": 0.2552,
        "energiledd_natt_eks_mva": 0.2552,
        "energiledd_perioder": [
            {"fra": "10-01", "til": "03-31", "dag_eks_mva": 0.2552, "natt_eks_mva": 0.2552},
            {"fra": "04-01", "til": "09-30", "dag_eks_mva": 0.2152, "natt_eks_mva": 0.2152},
        ],
        "url": "https://sae.no/tariffer",
        # Fastleddet bestemmes av månedens enkeltstående høyeste time, ikke
        # snittet av tre døgnmakser. Kilde: sae.no/uploads/Kundeinformasjon/
        # 2026_01_Kundeinformasjon_tariffer.pdf, gyldig fra 01.01.2026:
        # "Fastledd fastsettes på bakgrunn av den timen i måneden du har høyest
        # gjennomsnittlig forbruk (månedsmaksimal)". Samme PDF gir trinnene som
        # kr/mnd inkl. mva, og skriver dem som "fra [kW] - til og med [kW]", så
        # eksakt grensetreff hører til det lavere trinnet (terskel_inkludert
        # False). Kryssjekket mot fri-nettleie soraurdalenergi.yml (MND_MAX).
        "fastledd_metode": FASTLEDD_MND_MAX,
        "terskel_inkludert": False,
        "kapasitetstrinn": [
            (5, 563),  # 562,50 kr/mnd inkl. mva (450,00 eks.)
            (8, 650),  # 650,00 (520,00)
            (15, 775),  # 775,00 (620,00)
            (30, 900),  # 900,00 (720,00)
            (50, 1013),  # 1 012,50 (810,00)
            (float("inf"), 1375),  # 1 375,00 (1 100,00)
        ],
    },
    # Skiakernett (Skjåk) - Fusjonert med Vevig AS fra 01.01.2025
    # Kunder i Skjåk bruker nå Vevig sine tariffer
}
