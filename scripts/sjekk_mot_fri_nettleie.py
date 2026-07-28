#!/usr/bin/env python3
"""Sammenlign DSO_LIST mot kraftsystemet/fri-nettleie.

Henter alle tariff-YAML-filer fra fri-nettleie (CC-BY-4.0) og sammenligner med
vår dso.py: dag/natt-energiledd (eks. mva og avgifter), fastledd-metode og
fastledd-satser. Rapporterer avvik per nettselskap, merket [X] for energiledd,
[K] for fastledd og [M] for metode.

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

Data fra https://github.com/kraftsystemet/fri-nettleie/ (CC-BY-4.0).

Senere utvidelse: dette scriptet er strukturert slik at samme mapper og parser
kan generere const.py-data direkte. Se `match_dso()` og `hent_satser_aktiv_dato()`.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
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

# Kjente, bevisste avvik mot fri-nettleie: DSO-er der vi følger nettselskapets
# egen prisside framfor fri-nettleie fordi de spriker. Rapporteres, men teller
# ikke som drift (exit-kode). Fjern når fri-nettleie er oppdatert.
KJENTE_AVVIK: dict[str, str] = {
    "area_nett_omrade1": (
        "Vi følger Areas eget prisblad for 2026, som har 11 340, 13 224 og "
        "16 380 kr/år i de tre øverste trinnene. fri-nettleie area-nettinord.yml "
        "har 12 140, 14 030 og 17 180, identisk med sin egen 2025-tariff, så "
        "filen ser ut til å ha blitt forlenget uten oppdatering. Område 2 og 3 "
        "stemmer. Fjern når area-nettinord.yml er rettet."
    ),
    "fjellnett": (
        "Vi følger fjellnett.no sin egen prisliste fra 01.07.2026 (energiledd "
        "14,80 øre, fastledd 2000 + 589 kr/kW/år eks. mva). fri-nettleie har "
        "fortsatt 01.01.2026-tariffen (12,90 øre, 2000 + 534). Fjern når "
        "fjellnett.yml er oppdatert."
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
class Avvik:
    """Ett avvik for ett DSO."""

    dso_id: str
    felt: str
    var: float | None
    deres: float | None
    delta: float | None = None


def gh_get_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=30) as r:
        import json
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
    "januar": 1, "februar": 2, "mars": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
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


def sammenlign_sikringstrinn(
    entry: dict[str, Any], tariff: dict[str, Any], mva_faktor: float
) -> str | None:
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


def sammenlign_fastledd(
    vaare: list[tuple[float, int]], deres: list[tuple[float, int]]
) -> str | None:
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


def sammenlign(remote_slugs: set[str], paa: date, bare_avvik: bool, filter_ids: set[str] | None) -> list[Avvik]:
    avvik: list[Avvik] = []
    for var_id, entry in sorted(DSO_LIST.items()):
        if filter_ids and var_id not in filter_ids:
            continue
        if var_id == "custom":
            continue
        slug = match_dso(var_id, remote_slugs)
        if slug is None:
            if not bare_avvik:
                print(f"[?] {var_id}: ingen match i fri-nettleie")
            avvik.append(Avvik(var_id, "match", None, None))
            continue
        data = hent_yaml(slug)
        if data is None:
            avvik.append(Avvik(var_id, "fetch", None, None))
            continue
        tariff = aktiv_tariff(data, paa)
        if tariff is None:
            print(f"[!] {var_id} ({slug}): ingen aktiv tariff for husholdning på {paa}")
            continue
        satser = hent_satser_aktiv_dato(tariff, paa)
        if satser is None:
            print(f"[!] {var_id} ({slug}): mangler energiledd i tariff")
            continue
        dag_deres, natt_deres = satser
        dag_var = float(entry["energiledd_dag_eks_mva"])
        natt_var = float(entry["energiledd_natt_eks_mva"])

        # Hvis vi har perioder, bruk den som matcher datoen
        perioder = entry.get("energiledd_perioder", [])
        for p in perioder:
            fra, til = p["fra"], p["til"]
            mm_dd = paa.strftime("%m-%d")
            if (fra <= til and fra <= mm_dd <= til) or (fra > til and (mm_dd >= fra or mm_dd <= til)):
                dag_var = float(p["dag_eks_mva"])
                natt_var = float(p["natt_eks_mva"])
                break

        d_dag = dag_var - dag_deres
        d_natt = natt_var - natt_deres
        avvikende = abs(d_dag) > TOLERANSE or abs(d_natt) > TOLERANSE
        if avvikende:
            avvik.append(Avvik(var_id, "dag", dag_var, dag_deres, d_dag))
            avvik.append(Avvik(var_id, "natt", natt_var, natt_deres, d_natt))
            print(
                f"[X] {var_id:20s} ({slug:25s})  "
                f"dag {dag_var * 100:>6.2f} vs {dag_deres * 100:>6.2f}  "
                f"natt {natt_var * 100:>6.2f} vs {natt_deres * 100:>6.2f}"
            )

        mva_faktor = 1 + get_mva_sats(resolve_avgiftssone(entry))

        # Metoden er en sats på lik linje med prisene: bytter nettselskapet
        # modell, blir beløpet feil uansett hvor riktige trinnene er.
        var_metode = hent_fastledd_metode(entry)
        their_metode = deres_metode(tariff)
        if their_metode and var_metode != their_metode:
            avvik.append(Avvik(var_id, "metode", None, None))
            print(
                f"[M] {var_id:20s} ({slug:25s})  fastledd-metode {var_metode} vs {their_metode}"
            )
            avvikende = True

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
            avvik.append(Avvik(var_id, "fastledd", None, None))
            print(f"[K] {var_id:20s} ({slug:25s})  fastledd {fastledd_avvik}")
            avvikende = True

        if var_metode == FASTLEDD_UKJENT:
            # Prisene er sjekket, men ingen av kildene vet hvilken kW-verdi de
            # slås opp med. Sagt høyt hver kjøring, ikke skjult i en kommentar.
            print(f"[?] {var_id:20s} ({slug:25s})  fastledd-metode ikke kartlagt hos nettselskapet")

        if not avvikende and not bare_avvik:
            print(f"[OK] {var_id:20s} ({slug:25s})")
    return avvik


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dato", type=date.fromisoformat, default=date.today(),
                   help="Dato å sammenligne for (YYYY-MM-DD), default: i dag")
    p.add_argument("--bare-avvik", action="store_true",
                   help="Skriv bare ut avvik, ikke OK-rader")
    p.add_argument("--dso", help="Komma-separert liste over DSO-IDer å sjekke")
    args = p.parse_args()

    filter_ids = set(args.dso.split(",")) if args.dso else None

    print(f"# Sammenligning mot fri-nettleie for {args.dato}")
    print(f"# Toleranse: {TOLERANSE * 100:.2f} øre/kWh")
    print()
    remote = set(list_remote_dsoer())
    print(f"# {len(remote)} DSO-er tilgjengelig i fri-nettleie")
    print()
    avvik = sammenlign(remote, args.dato, args.bare_avvik, filter_ids)

    pris_avvik = [a for a in avvik if a.felt in ("dag", "natt")]
    ekte_avvik = [a for a in pris_avvik if a.dso_id not in KJENTE_AVVIK]
    # Kjente avvik listes uansett hvilket felt de gjelder. Ellers ble et kjent
    # fastledd-avvik filtrert vekk fra exit-koden og samtidig usynlig i
    # sammendraget, altså et unntak ingen ser at de har.
    kjente = sorted(
        {a.dso_id for a in avvik if a.felt in ("dag", "natt", "fastledd") and a.dso_id in KJENTE_AVVIK}
    )
    fastledd_avvik = [a for a in avvik if a.felt == "fastledd" and a.dso_id not in KJENTE_AVVIK]
    metode_avvik = [a for a in avvik if a.felt == "metode" and a.dso_id not in KJENTE_AVVIK]
    umatchet = sorted(a.dso_id for a in avvik if a.felt == "match")
    fetch_feil = sorted(a.dso_id for a in avvik if a.felt == "fetch")
    print()
    print(f"# Sammendrag: {len(ekte_avvik) // 2} DSO-er med uventet energiledd-avvik over toleranse")
    print(f"# {len(fastledd_avvik)} DSO-er med fastledd-avvik over toleranse")
    if metode_avvik:
        print(
            f"# {len(metode_avvik)} DSO-er der fastledd-metoden ikke stemmer: "
            f"{', '.join(sorted(a.dso_id for a in metode_avvik))}"
        )
    if kjente:
        print(f"# {len(kjente)} kjent(e) avvik (følger nettselskapets egen side, ikke drift): {', '.join(kjente)}")
        for dso_id in kjente:
            print(f"#   {dso_id}: {KJENTE_AVVIK[dso_id]}")
    # Umatchede DSO-er kan ikke auto-sjekkes og må verifiseres manuelt mot kilde.
    # De skjules ellers i --bare-avvik, og det er nettopp der drift sniker seg inn.
    if umatchet:
        print(f"# {len(umatchet)} uten match i fri-nettleie (sjekk manuelt): {', '.join(umatchet)}")
    if fetch_feil:
        print(f"# {len(fetch_feil)} feilet henting: {', '.join(fetch_feil)}")
    return 1 if ekte_avvik or fastledd_avvik or metode_avvik else 0


if __name__ == "__main__":
    sys.exit(main())
