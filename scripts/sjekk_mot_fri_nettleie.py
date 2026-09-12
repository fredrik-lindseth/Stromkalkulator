#!/usr/bin/env python3
"""Sammenlign DSO_LIST mot kraftsystemet/fri-nettleie.

Henter alle tariff-YAML-filer fra fri-nettleie (CC-BY-4.0) og sammenligner med
vår dso.py: dag/natt-energiledd (eks. mva og avgifter), fastledd-metode og
fastledd-satser. Rapporterer avvik per nettselskap, merket [X] for energiledd,
[K] for fastledd og [M] for metode.

Hvert nettselskap får ett av tre utfall, og exit-koden er det verste av dem:

    verifisert (0)    alle feltene vi kan sammenligne stemmer
    avvik (1)         minst ett felt spriker mer enn toleransen
    ufullstendig (2)  vi fikk ikke sjekket det vi skulle: ingen match i
                      fri-nettleie, 404, nettverksfeil, ingen aktiv tariff,
                      manglende energiledd, eller en fastledd-metode ingen
                      kilde har kartlagt

Ufullstendig slår avvik i exit-koden. En kjøring som ikke vet hva den ikke
sjekket, har ingen rett til å si «alt i orden», og workflowen lukker bare
pris-drift-issues på 0 fra en ukjørt-filtrert kjøring. Begge listene står i
rapporten og i `--json-ut`, så ingenting forsvinner av at 2 vinner.

Alle fem fastledd-metodene sammenlignes, hver på sin akse: kW-trinn for
TRE_DØGNMAX_MND, MND_MAX og UKJENT, sikringstrinn for OV_TREFASE og en lineær
sats for FEM_VEKTET_ÅR. Uten det ville de fem nettselskapene som avviker fra
NVE-modellen stått uten drift-vakt, som er nøyaktig den halvdekningen incident
006 handler om.

Bruk:
    python scripts/sjekk_mot_fri_nettleie.py
    python scripts/sjekk_mot_fri_nettleie.py --dato 2026-07-01  # sesongprising
    python scripts/sjekk_mot_fri_nettleie.py --bare-avvik
    python scripts/sjekk_mot_fri_nettleie.py --dso bkk,tensio_tn
    python scripts/sjekk_mot_fri_nettleie.py --json-ut resultat.json

Data fra https://github.com/kraftsystemet/fri-nettleie/ (CC-BY-4.0).

Senere utvidelse: dette scriptet er strukturert slik at samme mapper og parser
kan generere const.py-data direkte. Se `match_dso()` og `hent_satser_aktiv_dato()`.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

# Last dso.py og const.py som en syntetisk pakke, slik at const.py sin relative
# import av dso løser seg. Går utenom __init__.py, som krever homeassistant.
import importlib  # noqa: E402
import types  # noqa: E402

_pkg = types.ModuleType("_sk")
_pkg.__path__ = [str(REPO_ROOT / "custom_components" / "stromkalkulator")]  # type: ignore[attr-defined]
sys.modules["_sk"] = _pkg
_dso_mod = importlib.import_module("_sk.dso")
DSO_LIST = _dso_mod.DSO_LIST
FASTLEDD_FEM_VEKTET_AR = _dso_mod.FASTLEDD_FEM_VEKTET_AR
FASTLEDD_OV_TREFASE = _dso_mod.FASTLEDD_OV_TREFASE
FASTLEDD_TRINNBASERTE = _dso_mod.FASTLEDD_TRINNBASERTE
FASTLEDD_UKJENT = _dso_mod.FASTLEDD_UKJENT
hent_fastledd_metode = _dso_mod.hent_fastledd_metode
_const = importlib.import_module("_sk.const")
resolve_avgiftssone = _const.resolve_avgiftssone
get_mva_sats = _const.get_mva_sats

GITHUB_API = "https://api.github.com/repos/kraftsystemet/fri-nettleie/contents/tariffer"
RAW_BASE = "https://raw.githubusercontent.com/kraftsystemet/fri-nettleie/main/tariffer"
TOLERANSE = 0.001  # NOK/kWh, 0,1 øre
# Fastledd lagres avrundet til hele kroner per måned, og fri-nettleie oppgir
# årspris. 1 krone slack dekker avrundingen uten å skjule ekte prisendringer.
TOLERANSE_FASTLEDD = 1.0  # kr/mnd


class Utfall(IntEnum):
    """Utfall per nettselskap. Verdien er exit-koden utfallet gir alene."""

    VERIFISERT = 0
    AVVIK = 1
    UFULLSTENDIG = 2


# Feltnavn. Feltet er nøkkelen et unntak dempes på, så et nytt avvik i et annet
# felt hos samme nettselskap slipper gjennom selv om ett felt er kjent.
FELT_DAG = "dag"
FELT_NATT = "natt"
FELT_FASTLEDD = "fastledd"
FELT_METODE = "metode"
FELT_MATCH = "match"
FELT_HENTING = "henting"
FELT_TARIFF = "tariff"
FELT_ENERGILEDD = "energiledd"
FELT_FASTLEDD_METODE_UKJENT = "fastledd_metode_ukjent"


@dataclass(frozen=True)
class Unntak:
    """Ett kjent, akseptert funn hos ett nettselskap, med utløpsdato.

    `signatur` er den nøyaktige formen funnet har i dag. Endrer tallene seg,
    matcher ikke signaturen lenger, og funnet rapporteres som nytt. Det er
    forskjellen fra den gamle listen, som dempet alt hos et nettselskap på
    ubestemt tid: et injisert energiledd på 100 kr/kWh hos Fjellnett ble grønt.

    `gyldig_til` er eksklusiv. Etter den datoen dempes ingenting, og et unntak
    som ikke lenger treffer noe funn melder seg selv som ufullstendig, så listen
    ikke kan gro seg full av oppføringer ingen rydder.
    """

    felt: str
    signatur: str
    gyldig_til: date
    grunn: str


# Kjente, aksepterte funn. Her hører to slag hjemme: avvik der vi bevisst følger
# nettselskapets egen prisside framfor fri-nettleie, og hull i dekningen der
# fri-nettleie ikke har data å sammenligne med. Begge er ting en kjøring ellers
# ville ropt om hver uke, og begge er ting et menneske har tatt stilling til på
# en dato. Derfor har begge en utløpsdato: stillheten er lånt, ikke gitt.
KJENTE_AVVIK: dict[str, tuple[Unntak, ...]] = {
    "telemark_nett": (
        Unntak(
            felt=FELT_MATCH,
            signatur="ingen match i fri-nettleie",
            gyldig_til=date(2027, 3, 1),
            grunn=(
                "fri-nettleie hadde telemark.yml da kapasitetstrinnene ble hentet 2026-07-28, "
                "men filen er borte fra tariffer/ (og ligger ikke i tariffer/old/) per "
                "2026-09-12. Satsene står på telemark-nett.no sin egen prisside. Sjekk ved "
                "fornyelse om selskapet er fusjonert inn i et annet nettselskap; er det "
                "tilfellet, hører det hjemme i DSO_MIGRATIONS, ikke her."
            ),
        ),
    ),
    "tinfos": (
        Unntak(
            felt=FELT_FASTLEDD_METODE_UKJENT,
            signatur="fastledd-metode ikke kartlagt",
            gyldig_til=date(2027, 3, 1),
            grunn=(
                "Verken tinfos.no eller fri-nettleie sier hvilken kW-verdi kapasitetstrinnet "
                "slås opp med (døgnmaks, månedsmaks, snitt av tre). Prisene sammenlignes "
                "likevel som kW-trinn. Fornyes ved å spørre nettselskapet, eller ved å lese "
                "det av en ekte faktura."
            ),
        ),
    ),
}


# Mapping mellom våre DSO-IDer og fri-nettleie sine filnavn. Hvis vår ID kan
# utledes direkte (med "-" → "_") trenger vi ikke oppføring her.
EKSPLISITT_MAPPING: dict[str, str] = {
    "tensio_tn": "tensio-tn",
    "tensio_ts": "tensio-ts",
    "de_nett": "denett",
    "asker_nett": "asker",
    "bindal_kraftnett": "bindalkraftlag",
    "bomlo_kraftnett": "bomlokraftnett",
    "barents_nett": "barentsnett",
    "ke_nett": "kenett",
    "holand_setskog": "holandogsetskogelverk",
    "indre_hordaland": "indrehordalandkraftnett",
    "jaren_everk": "jaereneverk",
    "modalen_kraftlag": "mostraum",
    "meloy_energi": "meloy",
    "noranett_andoy": "noranett-andoy",
    "noranett_hadsel": "noranett-hadsel",
    "nordvest_nett": "nordvest",
    "norefjell_nett": "norefjell",
    "r_nett": "rnett",
    "rk_nett": "rknett",
    "rakkestad_energi": "elvia",
    "fore": "foere",
    "foie": "foie",
    # fri-nettleie dropper "nett"/selskapsledd i slug; auto-utleding tar ikke dette.
    "etna_nett": "etna",
    "breheim_nett": "breheim",
    "straumen_nett": "straumen",
    "telemark_nett": "telemark",
    "vestmar_nett": "vestmar",
    "vang_energiverk": "vang",
    "uvdal_kraftforsyning": "uvdal",
    # Area Nett er tre prisområder hos oss og hos fri-nettleie. Den utfasede
    # area_nett bruker område 2 som interim, så den sjekkes mot samme fil og
    # feller exit-koden hvis de kommer ut av takt.
    "area_nett_omrade1": "area-nettinord",
    "area_nett_omrade2": "area-luostejok",
    "area_nett_omrade3": "area-lega",
    "area_nett": "area-luostejok",
}


@dataclass
class Funn:
    """Ett funn hos ett nettselskap: enten et avvik eller en manglende kontroll."""

    dso_id: str
    felt: str
    signatur: str
    tekst: str
    utfall: Utfall
    dempet_til: date | None = None

    @property
    def teller(self) -> bool:
        """Skal funnet påvirke exit-koden?"""
        return self.dempet_til is None


@dataclass
class Resultat:
    """Samlet utfall for ett nettselskap."""

    dso_id: str
    slug: str | None
    funn: list[Funn]

    @property
    def utfall(self) -> Utfall:
        return max((f.utfall for f in self.funn if f.teller), default=Utfall.VERIFISERT)

    @property
    def dempet(self) -> bool:
        """Grønn, men bare fordi et unntak demper noe. Ikke det samme som verifisert."""
        return self.utfall is Utfall.VERIFISERT and bool(self.funn)


def gh_get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def hent_yaml(slug: str) -> dict[str, Any] | None:
    try:
        with urllib.request.urlopen(f"{RAW_BASE}/{slug}.yml", timeout=30) as r:
            return yaml.safe_load(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def list_remote_dsoer() -> list[str]:
    items = gh_get_json(GITHUB_API)
    return sorted(i["name"].removesuffix(".yml") for i in items if i["name"].endswith(".yml"))


def match_dso(var_id: str, remote_slugs: set[str]) -> str | None:
    """Map vår DSO-ID til fri-nettleie slug. None hvis ingen match."""
    if var_id in EKSPLISITT_MAPPING:
        slug = EKSPLISITT_MAPPING[var_id]
        return slug if slug in remote_slugs else None
    kandidater = [var_id, var_id.replace("_", "-"), var_id.replace("_", "")]
    for k in kandidater:
        if k in remote_slugs:
            return k
    return None


def aktiv_tariff(data: dict[str, Any], paa: date, kundegruppe: str = "husholdning") -> dict[str, Any] | None:
    """Finn tariffen som er gyldig på en gitt dato for en kundegruppe."""
    for t in data.get("tariffer", []):
        if kundegruppe not in t.get("kundegrupper", []):
            continue
        if date.fromisoformat(t["gyldig_fra"]) > paa:
            continue
        if "gyldig_til" in t and date.fromisoformat(t["gyldig_til"]) <= paa:
            continue
        return t
    return None


MAANED_MAP = {
    "januar": 1,
    "februar": 2,
    "mars": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "desember": 12,
}


def unntak_matcher_dato(unntak: dict[str, Any], paa: date) -> bool:
    maaneder = unntak.get("måneder")
    if maaneder is None:
        return True
    return paa.month in {MAANED_MAP[m] for m in maaneder if m in MAANED_MAP}


def hent_satser_aktiv_dato(tariff: dict[str, Any], paa: date) -> tuple[float, float] | None:
    """Returner (dag, natt) energiledd i NOK/kWh for gitt dato. None hvis ukjent.

    grunnpris er typisk laveste sats (ofte natt-pris, men ved sesongprising kan
    den være sommer-natt mens vinter-natt ligger som unntak). Vi behandler
    grunnpris som default for både dag og natt, og lar unntak overstyre.
    """
    el = tariff.get("energiledd")
    if not el:
        return None
    grunn = el["grunnpris"] / 100
    dag = grunn
    natt = grunn
    aktuelle = [u for u in el.get("unntak") or [] if unntak_matcher_dato(u, paa)]
    # Unntak uten `timer` gjelder hele døgnet (typisk en sesongpris, f.eks. Sør
    # Aurdals "Vinter"). De setter grunnlinjen først, så tidsstyrte unntak kan
    # overstyre dag eller natt oppå den.
    for unntak in sorted(aktuelle, key=lambda u: "timer" in u):
        navn = unntak.get("navn", "").lower()
        timer = unntak.get("timer", "")
        pris = unntak["pris"] / 100
        if not timer:
            dag = natt = pris
            continue
        er_natt = "natt" in navn or timer.startswith("22-") or "22-5" in timer or "22-6" in timer
        er_dag = any(s in navn for s in ("dag", "høylast")) or "6-21" in timer or "6-22" in timer
        if er_natt:
            natt = pris
        elif er_dag:
            dag = pris
    return dag, natt


def vaare_trinn(entry: dict[str, Any]) -> list[tuple[float, int]]:
    """Normaliser kapasitetstrinn til (øvre kW-grense, kr/mnd inkl. mva).

    Noen DSO-er lagrer trinn som dict ({min, max, pris}) i stedet for tupler.
    """
    raw = entry["kapasitetstrinn"]
    if raw and isinstance(raw[0], dict):
        return [(float(t["max"]), int(t["pris"])) for t in raw]
    return [(float(g), int(p)) for g, p in raw]


def deres_metode(tariff: dict[str, Any]) -> str:
    """Fastledd-metoden fri-nettleie oppgir. Tom streng hvis den mangler."""
    return str((tariff.get("fastledd") or {}).get("metode", ""))


def kr_mnd(aar_eks_mva: float, mva_faktor: float) -> int:
    """kr/år eks. mva -> kr/mnd inkl. mva, slik dso.py lagrer det.

    Halve kroner rundes opp. Innebygd round() gjør bankers rounding og ville
    gitt 232 der vi lagrer 233.
    """
    return int(Decimal(aar_eks_mva / 12 * mva_faktor).quantize(Decimal(1), ROUND_HALF_UP))


def deres_trinn(tariff: dict[str, Any], mva_faktor: float) -> list[tuple[float, int]] | None:
    """Konverter fri-nettleies fastledd til vårt kW-trinn-format.

    De oppgir (nedre kW-grense, kr/år eks. mva); vi lagrer (øvre kW-grense,
    kr/mnd inkl. mva). Øvre grense for trinn i er nedre grense for trinn i+1,
    og siste trinn er uendelig.

    Returnerer None for OV_TREFASE (tersklene er ampere) og FEM_VEKTET_ÅR (ingen
    trinn, bare en lineær sats). De har egne sammenligninger under. UKJENT
    sammenlignes som kW-trinn: metoden er ukjent, men prisene er like fullt
    verdt en drift-vakt.
    """
    metode = deres_metode(tariff)
    if metode not in FASTLEDD_TRINNBASERTE:
        return None
    terskler = (tariff.get("fastledd") or {}).get("terskler")
    if not terskler:
        return None
    ut: list[tuple[float, int]] = []
    for i, t in enumerate(terskler):
        neste = terskler[i + 1]["terskel"] if i + 1 < len(terskler) else float("inf")
        ut.append((float(neste), kr_mnd(t["pris"], mva_faktor)))
    return ut


def sammenlign_sikringstrinn(entry: dict[str, Any], tariff: dict[str, Any], mva_faktor: float) -> str | None:
    """Sammenlign sikringsbaserte fastledd-satser. None hvis likt.

    Vi kan ha flere rader enn fri-nettleie: de koder bare én spenningskolonne,
    mens vi gjengir hele prislisten (f.eks. Netera, som har egne rader for 230 V
    og 400 V). Derfor sammenlignes settet av distinkte priser, ikke rekkefølgen.
    """
    terskler = (tariff.get("fastledd") or {}).get("terskler") or []
    deres = sorted({kr_mnd(t["pris"], mva_faktor) for t in terskler})
    vaare = sorted({int(t["kr_mnd"]) for t in entry.get("fastledd_sikringstrinn", [])})
    if not deres:
        return "fri-nettleie mangler terskler"
    if len(vaare) != len(deres) or any(
        abs(v - d) > TOLERANSE_FASTLEDD for v, d in zip(vaare, deres, strict=True)
    ):
        return f"sikringstrinn {vaare} vs {deres} kr/mnd"
    return None


def sammenlign_lineaer(entry: dict[str, Any], tariff: dict[str, Any]) -> str | None:
    """Sjekk vår lineære sats mot fri-nettleies punktvise terskler. None hvis likt.

    fri-nettleie koder et lineært fastledd som tabellen nettselskapet publiserer,
    altså funksjonen samplet på hele kW. Da skal `pris(n) = grunnbeløp + sats * n`
    treffe hver terskel, og et avvik betyr at grunnbeløpet eller satsen har endret
    seg. Sammenlignes i kr/år eks. mva, som er enheten begge sider lagrer.
    """
    lineaer = entry.get("fastledd_lineaer")
    if not lineaer:
        return "mangler fastledd_lineaer"
    terskler = (tariff.get("fastledd") or {}).get("terskler") or []
    if not terskler:
        return "fri-nettleie mangler terskler"
    grunn = float(lineaer["grunnbelop_aar_eks_mva"])
    sats = float(lineaer["sats_kw_aar_eks_mva"])
    for t in terskler:
        forventet = grunn + sats * float(t["terskel"])
        # 12 kr/år er 1 kr/mnd, samme slack som trinnsammenligningen.
        if abs(forventet - float(t["pris"])) > TOLERANSE_FASTLEDD * 12:
            return (
                f"{t['terskel']:g} kW: {grunn:g}+{sats:g}*{t['terskel']:g} = "
                f"{forventet:g} vs {t['pris']:g} kr/år eks. mva"
            )
    return None


def sammenlign_fastledd(vaare: list[tuple[float, int]], deres: list[tuple[float, int]]) -> str | None:
    """Returner en beskrivelse av første fastledd-avvik, eller None hvis likt.

    Vi kollapser gjerne de øverste trinnene til ett `inf`-trinn der DSO-en selv
    ikke publiserer dem for privatkunder. Det sammenlignes derfor kun så langt
    vår liste rekker, og kun prisene, ikke antall trinn.
    """
    for i, (vaar_grense, vaar_pris) in enumerate(vaare):
        if i >= len(deres):
            return f"trinn {i + 1}: vi har et trinn fri-nettleie ikke har"
        deres_grense, deres_pris = deres[i]
        if abs(vaar_pris - deres_pris) > TOLERANSE_FASTLEDD:
            return f"trinn {i + 1}: {vaar_pris} vs {deres_pris} kr/mnd"
        # Siste trinn hos oss kan være en kollaps av flere av deres trinn.
        siste = i == len(vaare) - 1
        if not siste and vaar_grense != deres_grense:
            return f"trinn {i + 1}: grense {vaar_grense:g} vs {deres_grense:g} kW"
    return None


def energiledd_for_dato(entry: dict[str, Any], paa: date) -> tuple[float, float]:
    """Våre dag/natt-satser for datoen, med sesongperiode hvis den finnes."""
    dag = float(entry["energiledd_dag_eks_mva"])
    natt = float(entry["energiledd_natt_eks_mva"])
    mm_dd = paa.strftime("%m-%d")
    for p in entry.get("energiledd_perioder", []):
        fra, til = p["fra"], p["til"]
        if (fra <= til and fra <= mm_dd <= til) or (fra > til and (mm_dd >= fra or mm_dd <= til)):
            return float(p["dag_eks_mva"]), float(p["natt_eks_mva"])
    return dag, natt


def _ufullstendig(var_id: str, slug: str | None, felt: str, signatur: str, melding: str) -> Resultat:
    """Ett nettselskap vi ikke fikk kontrollert, med grunnen skrevet ut."""
    prefiks = f"{var_id:20s} ({slug:25s})" if slug else f"{var_id:20s} {'':27s}"
    return Resultat(
        var_id, slug, [Funn(var_id, felt, signatur, f"[?] {prefiks}  {melding}", Utfall.UFULLSTENDIG)]
    )


def kontroller_dso(var_id: str, entry: dict[str, Any], remote_slugs: set[str], paa: date) -> Resultat:
    """Kontroller ett nettselskap og returner alle funn, dempet eller ei.

    Manglende energiledd stopper ikke fastledd-sjekken. De to er uavhengige
    kontroller, og å droppe den andre fordi den første manglet var nettopp
    halvdekningen incident 006 handler om.
    """
    slug = match_dso(var_id, remote_slugs)
    if slug is None:
        return _ufullstendig(
            var_id,
            None,
            FELT_MATCH,
            "ingen match i fri-nettleie",
            "ingen match i fri-nettleie, kan ikke kontrolleres",
        )

    try:
        data = hent_yaml(slug)
    except OSError as feil:  # urllib.error.URLError arver OSError
        return _ufullstendig(var_id, slug, FELT_HENTING, "henting feilet", f"henting feilet: {feil}")
    if data is None:
        return _ufullstendig(
            var_id, slug, FELT_HENTING, "404 fra fri-nettleie", f"404: {slug}.yml finnes ikke lenger"
        )

    tariff = aktiv_tariff(data, paa)
    if tariff is None:
        return _ufullstendig(
            var_id,
            slug,
            FELT_TARIFF,
            "ingen aktiv tariff for husholdning",
            f"ingen aktiv tariff for husholdning på {paa}",
        )

    funn: list[Funn] = []
    prefiks = f"{var_id:20s} ({slug:25s})"

    satser = hent_satser_aktiv_dato(tariff, paa)
    if satser is None:
        funn.append(
            Funn(
                var_id,
                FELT_ENERGILEDD,
                "mangler energiledd i tariff",
                f"[?] {prefiks}  mangler energiledd i tariff, energiledd ikke kontrollert",
                Utfall.UFULLSTENDIG,
            )
        )
    else:
        dag_deres, natt_deres = satser
        dag_var, natt_var = energiledd_for_dato(entry, paa)
        if abs(dag_var - dag_deres) > TOLERANSE or abs(natt_var - natt_deres) > TOLERANSE:
            tekst = (
                f"[X] {prefiks}  "
                f"dag {dag_var * 100:>6.2f} vs {dag_deres * 100:>6.2f}  "
                f"natt {natt_var * 100:>6.2f} vs {natt_deres * 100:>6.2f}"
            )
            # Ett funn per felt: dag og natt dempes hver for seg, så et unntak
            # for nattsatsen ikke skjuler at dagsatsen har løpt fra oss.
            for felt, var, deres in ((FELT_DAG, dag_var, dag_deres), (FELT_NATT, natt_var, natt_deres)):
                if abs(var - deres) > TOLERANSE:
                    funn.append(
                        Funn(
                            var_id,
                            felt,
                            f"{var * 100:.2f} vs {deres * 100:.2f} øre",
                            tekst,
                            Utfall.AVVIK,
                        )
                    )

    mva_faktor = 1 + get_mva_sats(resolve_avgiftssone(entry))

    # Metoden er en sats på lik linje med prisene: bytter nettselskapet
    # modell, blir beløpet feil uansett hvor riktige trinnene er.
    var_metode = hent_fastledd_metode(entry)
    their_metode = deres_metode(tariff)
    if their_metode and var_metode != their_metode:
        funn.append(
            Funn(
                var_id,
                FELT_METODE,
                f"{var_metode} vs {their_metode}",
                f"[M] {prefiks}  fastledd-metode {var_metode} vs {their_metode}",
                Utfall.AVVIK,
            )
        )

    if var_metode == FASTLEDD_OV_TREFASE:
        fastledd_avvik = sammenlign_sikringstrinn(entry, tariff, mva_faktor)
    elif var_metode == FASTLEDD_FEM_VEKTET_AR:
        fastledd_avvik = sammenlign_lineaer(entry, tariff)
    else:
        deres_kap = deres_trinn(tariff, mva_faktor)
        if deres_kap is None:
            fastledd_avvik = f"fri-nettleie har metode {their_metode or 'ukjent'} uten kW-trinn"
        else:
            fastledd_avvik = sammenlign_fastledd(vaare_trinn(entry), deres_kap)

    if fastledd_avvik:
        funn.append(
            Funn(
                var_id,
                FELT_FASTLEDD,
                fastledd_avvik,
                f"[K] {prefiks}  fastledd {fastledd_avvik}",
                Utfall.AVVIK,
            )
        )

    if var_metode == FASTLEDD_UKJENT:
        # Prisene er sjekket, men ingen av kildene vet hvilken kW-verdi de slås
        # opp med. Da er kontrollen ufullstendig, ikke verifisert, og det står
        # den som til noen enten finner metoden eller fornyer unntaket.
        funn.append(
            Funn(
                var_id,
                FELT_FASTLEDD_METODE_UKJENT,
                "fastledd-metode ikke kartlagt",
                f"[?] {prefiks}  fastledd-metode ikke kartlagt hos nettselskapet",
                Utfall.UFULLSTENDIG,
            )
        )

    return Resultat(var_id, slug, funn)


@dataclass
class UnntakStatus:
    """Hvordan unntakslisten kom ut av en kjøring."""

    brukte: list[tuple[str, Unntak]]
    ubrukte: list[tuple[str, Unntak]]
    utlopte: list[tuple[str, Unntak]]


def anvend_unntak(resultater: list[Resultat], i_dag: date) -> UnntakStatus:
    """Demp funn som har et gyldig unntak, og gjør status på listen.

    Et unntak demper kun funn med samme felt *og* samme signatur. Endrer tallene
    seg, er det et nytt funn og skal ropes om. Etter `gyldig_til` demper unntaket
    ingenting: treffer det fortsatt et funn, teller funnet igjen; treffer det
    ingenting, melder unntaket seg selv som ufullstendig så listen kan ryddes.
    """
    brukte: list[tuple[str, Unntak]] = []
    ubrukte: list[tuple[str, Unntak]] = []
    utlopte: list[tuple[str, Unntak]] = []

    per_dso = {r.dso_id: r for r in resultater}

    for dso_id, unntak_liste in sorted(KJENTE_AVVIK.items()):
        resultat = per_dso.get(dso_id)
        if resultat is None:
            # Utenfor filteret: vi vet ingenting om denne, verken brukt eller ubrukt.
            continue
        for unntak in unntak_liste:
            treff = [f for f in resultat.funn if f.felt == unntak.felt and f.signatur == unntak.signatur]
            utlopt = i_dag >= unntak.gyldig_til
            if utlopt:
                utlopte.append((dso_id, unntak))
            if treff and not utlopt:
                for f in treff:
                    f.dempet_til = unntak.gyldig_til
                brukte.append((dso_id, unntak))
            elif not treff and not utlopt:
                ubrukte.append((dso_id, unntak))
            elif not treff and utlopt:
                resultat.funn.append(
                    Funn(
                        dso_id,
                        f"unntak_{unntak.felt}",
                        "utløpt unntak uten funn",
                        f"[U] {dso_id:20s} {'':27s}  unntak for {unntak.felt} utløp "
                        f"{unntak.gyldig_til} og treffer ingenting. Fjern oppføringen i "
                        "KJENTE_AVVIK.",
                        Utfall.UFULLSTENDIG,
                    )
                )
    return UnntakStatus(brukte, ubrukte, utlopte)


def kontroller_alle(
    remote_slugs: set[str], paa: date, filter_ids: set[str] | None, i_dag: date
) -> tuple[list[Resultat], UnntakStatus]:
    resultater = [
        kontroller_dso(var_id, entry, remote_slugs, paa)
        for var_id, entry in sorted(DSO_LIST.items())
        if var_id != "custom" and (not filter_ids or var_id in filter_ids)
    ]
    return resultater, anvend_unntak(resultater, i_dag)


def skriv_rapport(resultater: list[Resultat], status: UnntakStatus, bare_avvik: bool) -> None:
    """Skriv linjene per nettselskap og sammendraget."""
    for r in resultater:
        skrevet: set[str] = set()
        for f in r.funn:
            # dag og natt deler én linje; skriv den bare én gang.
            linje = f"[D] {f.tekst[4:]}  (dempet til {f.dempet_til})" if f.dempet_til else f.tekst
            if linje not in skrevet:
                print(linje)
                skrevet.add(linje)
        if not r.funn and not bare_avvik:
            print(f"[OK] {r.dso_id:20s} ({r.slug or '':25s})")

    avvik = sorted({r.dso_id for r in resultater if r.utfall is Utfall.AVVIK})
    ufullstendige = sorted({r.dso_id for r in resultater if r.utfall is Utfall.UFULLSTENDIG})
    verifiserte = [r for r in resultater if r.utfall is Utfall.VERIFISERT and not r.dempet]
    dempede = sorted(r.dso_id for r in resultater if r.dempet)

    print()
    print(
        f"# Sammendrag: {len(verifiserte)} verifisert, {len(avvik)} med avvik, "
        f"{len(ufullstendige)} ufullstendig, {len(dempede)} dempet av unntak"
    )
    if avvik:
        print(f"# Avvik ({len(avvik)}): {', '.join(avvik)}")
    if ufullstendige:
        print(f"# Ufullstendig ({len(ufullstendige)}): {', '.join(ufullstendige)}")
    if status.brukte:
        print(f"# {len(status.brukte)} dempet av et gyldig unntak:")
        for dso_id, unntak in status.brukte:
            print(f"#   {dso_id} [{unntak.felt}] til {unntak.gyldig_til}: {unntak.grunn}")
    if status.ubrukte:
        print(f"# {len(status.ubrukte)} unntak treffer ingenting og kan trolig fjernes:")
        for dso_id, unntak in status.ubrukte:
            print(f"#   {dso_id} [{unntak.felt}] (gyldig til {unntak.gyldig_til})")
    if status.utlopte:
        print(f"# {len(status.utlopte)} utløpt(e) unntak, må fornyes eller fjernes:")
        for dso_id, unntak in status.utlopte:
            print(f"#   {dso_id} [{unntak.felt}] utløp {unntak.gyldig_til}")


def exit_kode(resultater: list[Resultat]) -> Utfall:
    return max((r.utfall for r in resultater), default=Utfall.VERIFISERT)


def json_sammendrag(
    resultater: list[Resultat], status: UnntakStatus, paa: date, fullstendig: bool
) -> dict[str, Any]:
    kode = exit_kode(resultater)
    return {
        "dato": paa.isoformat(),
        "fullstendig": fullstendig,
        "status": kode.name.lower(),
        "exit": int(kode),
        "kontrollert": len(resultater),
        "verifisert": sorted(r.dso_id for r in resultater if r.utfall is Utfall.VERIFISERT and not r.dempet),
        "dempet_dsoer": sorted(r.dso_id for r in resultater if r.dempet),
        "avvik": sorted({r.dso_id for r in resultater if r.utfall is Utfall.AVVIK}),
        "ufullstendig": sorted({r.dso_id for r in resultater if r.utfall is Utfall.UFULLSTENDIG}),
        "dempet": [
            {"dso": dso_id, "felt": u.felt, "gyldig_til": u.gyldig_til.isoformat()}
            for dso_id, u in status.brukte
        ],
        "ubrukte_unntak": [{"dso": dso_id, "felt": u.felt} for dso_id, u in status.ubrukte],
        "utlopte_unntak": [
            {"dso": dso_id, "felt": u.felt, "gyldig_til": u.gyldig_til.isoformat()}
            for dso_id, u in status.utlopte
        ],
    }


def parse_filter(raw: str) -> set[str]:
    """Valider --dso mot DSO_LIST. Kaster ValueError med melding ved ukjent ID."""
    ids = {d.strip() for d in raw.split(",") if d.strip()}
    if not ids:
        raise ValueError("--dso er tom. Dropp flagget for å sjekke alle nettselskap.")
    ukjente = sorted(i for i in ids if i not in DSO_LIST)
    if ukjente:
        raise ValueError(
            f"ukjent DSO-ID i --dso: {', '.join(ukjente)}. "
            "IDene er nøklene i DSO_LIST i custom_components/stromkalkulator/dso.py."
        )
    if ids == {"custom"}:
        raise ValueError("custom er brukerdefinerte satser og har ingen fasit i fri-nettleie.")
    return ids


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--dato",
        type=date.fromisoformat,
        default=date.today(),
        help="Dato å sammenligne for (YYYY-MM-DD), default: i dag",
    )
    p.add_argument("--bare-avvik", action="store_true", help="Skriv bare ut avvik, ikke OK-rader")
    p.add_argument("--dso", help="Komma-separert liste over DSO-IDer å sjekke")
    p.add_argument("--json-ut", help="Skriv maskinlesbart sammendrag til denne filen")
    args = p.parse_args(argv)

    filter_ids: set[str] | None = None
    if args.dso:
        try:
            filter_ids = parse_filter(args.dso)
        except ValueError as feil:
            print(f"[!] {feil}", file=sys.stderr)
            return int(Utfall.UFULLSTENDIG)

    print(f"# Sammenligning mot fri-nettleie for {args.dato}")
    print(f"# Toleranse: {TOLERANSE * 100:.2f} øre/kWh")
    if filter_ids:
        print(f"# Delvis kjøring: kun {', '.join(sorted(filter_ids))}")
    print()
    try:
        remote = set(list_remote_dsoer())
    except OSError as feil:  # urllib.error.URLError arver OSError
        print(f"[!] fikk ikke listet tariffer hos fri-nettleie: {feil}", file=sys.stderr)
        return int(Utfall.UFULLSTENDIG)
    print(f"# {len(remote)} DSO-er tilgjengelig i fri-nettleie")
    print()

    resultater, status = kontroller_alle(remote, args.dato, filter_ids, date.today())
    skriv_rapport(resultater, status, args.bare_avvik)

    if args.json_ut:
        sammendrag = json_sammendrag(resultater, status, args.dato, fullstendig=filter_ids is None)
        Path(args.json_ut).write_text(json.dumps(sammendrag, indent=2, ensure_ascii=False) + "\n")

    return int(exit_kode(resultater))


if __name__ == "__main__":
    sys.exit(main())
