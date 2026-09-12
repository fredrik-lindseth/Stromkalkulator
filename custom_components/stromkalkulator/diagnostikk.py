"""Bygger diagnostikk-snapshotet for en config entry.

`diagnostics.py` er bare HAs inngang hit, slik at selve skjemaet kan testes
uten HAs diagnostics-plattform.

Fire regler holder filen ærlig:

1. **Allowlist på nøklene.** Ingenting havner i dumpen fordi det tilfeldigvis
   ligger i `entry.data` eller `coordinator.data`. Hvert felt står oppført her,
   og `tests/test_diagnostics.py` feller oss hvis coordinatoren får en ny nøkkel
   som verken er tatt med eller uttrykkelig utelatt. Det gjelder også radene i
   `input_problemer`: de var en denylist («alt utenom entity_id»), og en
   denylist lekker av konstruksjon, siden den må kjenne alt som er farlig på
   forhånd.
2. **Allowlist på strengverdiene.** En allowlistet nøkkel sier ingenting om hva
   som ligger under den. Tall og bool bærer verken navn eller adresse, men en
   streng bærer det den blir matet. Derfor går hver streng gjennom `tekstvakt`
   og må enten stå i et kjent vokabular (DSO-navn, avgiftssone, fastledd-metode)
   eller treffe et kjent format (ISO-dato, `0-2 kW`, `juni 2026`). Alt annet
   byttes med en markør.
3. **Aliaser.** Brukeren limer dumpen inn i en offentlig GitHub-issue. Entity-
   id-er, entry-id og entry-tittel er navn brukeren har valgt, og de røper
   både hvem det er og hvor de bor. De byttes med tellere som er stabile
   innenfor én eksport, så relasjonene mellom rollene består (samme sensor i
   to roller får samme alias), men navnet er borte.
4. **Kun JSON-primitiver.** Alt går gjennom `rens()`, så `json.dumps` lykkes
   uten `default`-hook. `coordinator.data` inneholder dataklasser
   (`DailyMaxEntry`), og de ville sprengt en rå dump.

Skjemaet er versjonert med `DIAGNOSTICS_SCHEMA_VERSION`. Endrer du feltene,
bump den, slik at en dump fra en gammel versjon kan leses for det den er.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from homeassistant.const import __version__ as HA_VERSION
from homeassistant.loader import async_get_integration

from .const import (
    AVGIFTSSONE_OPTIONS,
    BOLIGTYPE_OPTIONS,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_EGENDEFINERT_SATSER_BEKREFTET,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGI_FROSSEN_TIMER,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SIKRINGSTRINN,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DOMAIN,
    INPUT_ROLLE_EFFEKT,
    INPUT_ROLLE_EKSPORT,
    INPUT_ROLLE_ENERGI,
    INPUT_ROLLE_LEVERANDORPRIS,
    INPUT_ROLLE_SPOTPRIS,
    INPUT_UTFALL_GRACE_MINUTTER,
    VAKTHOLD_FROSSEN,
    VAKTHOLD_SPOT_UTLOPT,
    VAKTHOLD_UTFALL,
)
from .dso import DSO_LIST, FASTLEDD_METODER

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

DIAGNOSTICS_SCHEMA_VERSION: int = 1

# Valgene brukeren har tatt, uten entity-id-ene. Disse er trygge å vise rått:
# de sier hva integrasjonen regnet med, ikke hvem som regnet.
VALG_ALLOWLIST: tuple[str, ...] = (
    CONF_DSO,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_HAR_NORGESPRIS,
    CONF_SPOTPRIS_INKL_MVA,
    CONF_SIKRINGSTRINN,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_ENERGI_FROSSEN_TIMER,
    CONF_EGENDEFINERT_SATSER_BEKREFTET,
)

# Inputrollene. Selve entity-id-en aliaseres; her står bare koblingen fra
# rolle til konfignøkkel. D2 utvider hver rolle med tilgjengelighet, enhet og
# kvalitet når K1 eksponerer dem.
ROLLE_TIL_CONF: dict[str, str] = {
    INPUT_ROLLE_EFFEKT: CONF_POWER_SENSOR,
    INPUT_ROLLE_ENERGI: CONF_ENERGY_SENSOR,
    INPUT_ROLLE_SPOTPRIS: CONF_SPOT_PRICE_SENSOR,
    INPUT_ROLLE_EKSPORT: CONF_EXPORT_POWER_SENSOR,
    INPUT_ROLLE_LEVERANDORPRIS: CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
}

# Nøklene fra coordinator.data som forklarer beregningen.
BEREGNING_ALLOWLIST: tuple[str, ...] = (
    "energiledd",
    "energiledd_dag",
    "energiledd_natt",
    "energiledd_perioder",
    "aktiv_energiledd_periode",
    "kapasitetsledd",
    "kapasitetstrinn_nummer",
    "kapasitetstrinn_intervall",
    "kapasitetsledd_per_kwh",
    "fastledd_metode",
    "fastledd_grunnlag_kw",
    "fastledd_mangler_sikringsvalg",
    "spot_price",
    "spot_price_valid",
    "stromstotte",
    "stromstotte_terskel",
    "spotpris_etter_stotte",
    "norgespris",
    "strompris_norgespris",
    "total_pris_norgespris",
    "kroner_spart_per_kwh",
    "total_price",
    "total_price_uten_stotte",
    "total_price_inkl_avgifter",
    "strompris_per_kwh",
    "strompris_per_kwh_etter_stotte",
    "forbruksavgift_inkl_mva",
    "enova_inkl_mva",
    "offentlige_avgifter",
    "electricity_company_price",
    "electricity_company_total",
    "current_power_kw",
    "avg_top_3_kw",
    "top_3_days",
    "is_day_rate",
    "har_norgespris",
    "avgiftssone",
    "boligtype",
    "current_month",
    "current_date",
    "monthly_consumption_dag_kwh",
    "monthly_consumption_natt_kwh",
    "monthly_consumption_total_kwh",
    "previous_month_consumption_dag_kwh",
    "previous_month_consumption_natt_kwh",
    "previous_month_consumption_total_kwh",
    "previous_month_top_3",
    "previous_month_avg_top_3_kw",
    "previous_month_name",
    "previous_month_kapasitetsledd",
    "previous_month_kapasitetstrinn",
    "previous_month_energiledd_dag",
    "previous_month_energiledd_natt",
    "stromstotte_tak_naadd",
    "norgespris_over_tak",
    "stromstotte_gjenstaaende_kwh",
    "margin_neste_trinn_kw",
    "neste_trinn_pris",
    "kapasitet_varsel",
    "maaledata_problem",
    "leverandorpris_gyldig",
    "monthly_norgespris_diff_kr",
    "previous_month_norgespris_diff_kr",
    "monthly_norgespris_compensation_kr",
    "previous_month_norgespris_compensation_kr",
    "daily_cost_kr",
    "monthly_accumulated_cost_kr",
    "monthly_accumulated_cost_strom_kr",
    "monthly_accumulated_cost_energiledd_kr",
    "monthly_accumulated_cost_kapasitetsledd_kr",
    "eksport_konfigurert",
    "monthly_export_kwh",
    "monthly_export_revenue_kr",
    "monthly_cost_kr",
    "monthly_net_cost_kr",
    "previous_month_export_kwh",
    "previous_month_export_revenue_kr",
    "previous_month_cost_kr",
    "previous_month_net_cost_kr",
)

# Nøkler i coordinator.data som med vilje ikke ligger under "beregning".
# Står her for at vakten i testene skal kunne kreve at hver nøkkel er
# behandlet, ikke bare glemt.
BEREGNING_UTELATT: dict[str, str] = {
    "input_problemer": "aliaseres og vises under vakthold",
    "dso": "står i dso-seksjonen",
    "sist_energi_okning": "står i vakthold-seksjonen",
    "energi_frossen_terskel_timer": "står i vakthold-seksjonen",
}

# Feltene på én rad i coordinator.data["input_problemer"]. Dette var en
# denylist («alt utenom entity_id»), og da gikk hvert nytt felt noen la på
# raden rett ut i dumpen. Allowlist her og `PROBLEM_UTELATT` under, slik at
# testen kan kreve at hvert felt _vakthold_problem lager er behandlet.
PROBLEM_ALLOWLIST: tuple[str, ...] = ("type", "input", "siden", "minutter", "timer")

PROBLEM_UTELATT: dict[str, str] = {
    "entity_id": "aliaseres til entitet_alias, samme alias som rollen fikk",
}

# HA-domenet på en entity-id beholdes i aliaset fordi «sensor» mot
# «input_number» forteller leseren hva slags kilde det er. Bare disse tre er
# nåbare i config-flowens EntitySelector; alt annet er håndredigert .storage,
# og da er domenedelen like gjerne et navn. Da forsvinner den også.
ENTITET_DOMENER: frozenset[str] = frozenset({"sensor", "number", "input_number"})

# Månedsnavnene coordinatoren setter i previous_month_name. Kopien er vaktet:
# tests/test_diagnostics.py sammenligner den med det coordinatoren faktisk
# produserer for alle tolv månedene.
MAANEDSNAVN: tuple[str, ...] = (
    "januar",
    "februar",
    "mars",
    "april",
    "mai",
    "juni",
    "juli",
    "august",
    "september",
    "oktober",
    "november",
    "desember",
)

# Tilstandene og kildene på et config entry. HA definerer dem, men de er få og
# faste, og et entry som melder noe annet skal ikke få skrive fritt i dumpen.
ENTRY_TILSTANDER: frozenset[str] = frozenset(
    {
        "loaded",
        "not_loaded",
        "setup_error",
        "setup_retry",
        "setup_in_progress",
        "migration_error",
        "failed_unload",
    }
)
ENTRY_KILDER: frozenset[str] = frozenset(
    {"user", "import", "reconfigure", "discovery", "reauth", "hassio", "ignore", "system"}
)

# Nøkler som står inne i verdiene, ikke på dem: energiledd-periodene og
# dagsmaks-postene er dicter coordinatoren bygger selv.
NESTEDE_NOKLER: frozenset[str] = frozenset({"fra", "til", "dag", "natt", "kw", "hour"})

TEKST_MARKOR = "<tekst utelatt>"
NOKKEL_MARKOR = "<nøkkel utelatt>"

# Hver streng i dumpen må stå her eller treffe et format under. DSO-navnene er
# nettselskap, ikke personer, og sier hvilken prisliste som gjelder.
TEKST_VOKABULAR: frozenset[str] = frozenset(
    {"", "ukjent", "loader", "manifest_fil", DOMAIN}
    | set(DSO_LIST)
    | {str(oppforing["name"]) for oppforing in DSO_LIST.values() if oppforing.get("name")}
    | set(FASTLEDD_METODER)
    | set(AVGIFTSSONE_OPTIONS)
    | set(BOLIGTYPE_OPTIONS)
    | set(MAANEDSNAVN)
    | set(ENTRY_TILSTANDER)
    | set(ENTRY_KILDER)
    | set(NESTEDE_NOKLER)
    | set(ROLLE_TIL_CONF)
    | set(VALG_ALLOWLIST)
    | set(BEREGNING_ALLOWLIST)
    | set(PROBLEM_ALLOWLIST)
    | {VAKTHOLD_UTFALL, VAKTHOLD_FROSSEN, VAKTHOLD_SPOT_UTLOPT}
)

# Strengene som ikke er et fast ord, men et format koden selv lager.
TEKST_FORMATER: tuple[re.Pattern[str], ...] = (
    # ISO-dato og -tidspunkt, med eller uten sone.
    re.compile(r"\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?"),
    re.compile(r"\d{4}-\d{2}"),  # fakturamåned
    re.compile(r"\d{2}-\d{2}"),  # sesonggrense (MM-DD)
    re.compile(r"\d{2}-\d{2} til \d{2}-\d{2}"),  # aktiv energiledd-periode
    re.compile(r">?\d+(-\d+)? kW"),  # kapasitetstrinn-intervall
    re.compile(r"(?:" + "|".join(MAANEDSNAVN) + r") \d{4}"),  # previous_month_name
    re.compile(r"\d+\.\d+\.\d+[0-9A-Za-z.+-]*"),  # versjonsstreng
    re.compile(r"<utelatt: \w+>"),  # rens() sin markør for ukjent type
)


def tekstvakt(tekst: str) -> bool:
    """Om en streng er kjent nok til å stå i en dump som limes inn offentlig."""
    return tekst in TEKST_VOKABULAR or any(m.fullmatch(tekst) for m in TEKST_FORMATER)


# Hva som aldri er med, og hvorfor. Følger dumpen, så den som leser den vet at
# hullene er med vilje og slipper å be om «hele» dumpen.
UTELATT_MED_VILJE: tuple[str, ...] = (
    "entity-id-er, entry-id og entry-tittel i klartekst (aliasert)",
    "rå entry.data og entry.options (kun allowlisten over)",
    "sensorattributter og states fra andre integrasjoner",
    "vertsstier, konfigkatalog og filnavn",
    "full forbrukshistorikk (snapshotet forklarer én oppdatering)",
)


def rens(verdi: Any) -> Any:
    """Gjør en verdi om til JSON-primitiver.

    `json.dumps(rens(x), allow_nan=False)` skal alltid gå. Ikke-endelige
    floats (NaN, inf) blir None, siden JSON ikke har dem, og ukjente typer blir
    en markørstreng framfor å ryke i serialiseringen.
    """
    if verdi is None or isinstance(verdi, (bool, int, str)):
        return verdi
    if isinstance(verdi, float):
        return verdi if math.isfinite(verdi) else None
    if isinstance(verdi, (datetime, date)):
        return verdi.isoformat()
    if is_dataclass(verdi) and not isinstance(verdi, type):
        return rens(asdict(verdi))
    if isinstance(verdi, dict):
        return {str(nokkel): rens(v) for nokkel, v in verdi.items()}
    if isinstance(verdi, (list, tuple)):
        return [rens(v) for v in verdi]
    if isinstance(verdi, (set, frozenset)):
        return sorted(str(v) for v in verdi)
    return f"<utelatt: {type(verdi).__name__}>"


def _filtrer_tekst(verdi: Any) -> Any:
    """Bytt ut hver ukjent streng, i nøkler og verdier, med en markør."""
    if isinstance(verdi, str):
        return verdi if tekstvakt(verdi) else TEKST_MARKOR
    if isinstance(verdi, dict):
        return {(n if tekstvakt(n) else NOKKEL_MARKOR): _filtrer_tekst(v) for n, v in verdi.items()}
    if isinstance(verdi, list):
        return [_filtrer_tekst(v) for v in verdi]
    return verdi


def rens_trygg(verdi: Any) -> Any:
    """`rens()` pluss tekstvakten.

    Brukes på alt som kommer fra `entry.data`, `entry.options` eller
    `coordinator.data`. Feltene diagnostikken lager selv (aliaser, domenenavn,
    listen over det som er utelatt) går utenom: de er ikke data noen kan plante
    i.
    """
    return _filtrer_tekst(rens(verdi))


class Aliaser:
    """Bytter brukervalgte navn med tellere som er stabile i én eksport.

    Samme verdi gir samme alias hele dumpen igjennom, så man ser at
    effektsensoren og energisensoren er den samme entiteten, eller at et
    vaktholdsproblem gjelder rollen man tror.

    Aliasene er tellere uten innhold, ikke hasher av navnet. `sensor.alias_1`
    er den første entiteten dumpen nevner, og ingenting mer. To dumper fra samme
    bruker får derfor de samme aliasene, men et alias kan ikke knytte dem
    sammen, for det er utledet av rekkefølgen i dumpen og ikke av brukeren. En
    salt per dump ville gjort aliasene ulike uten å skjule noe mer, og samtidig
    ødelagt det de er til for: å sammenligne to dumper fra samme oppsett.
    """

    def __init__(self) -> None:
        self._kjente: dict[tuple[str, str], str] = {}
        self._tellere: dict[str, int] = {}

    def alias(self, verdi: Any, sort: str) -> str | None:
        """Returner aliaset for `verdi`. None inn gir None ut."""
        if verdi is None:
            return None
        tekst = str(verdi)
        nokkel = (sort, tekst)
        if nokkel in self._kjente:
            return self._kjente[nokkel]
        self._tellere[sort] = self._tellere.get(sort, 0) + 1
        nummer = self._tellere[sort]
        domene = tekst.split(".", 1)[0] if "." in tekst else ""
        if sort == "entitet" and domene in ENTITET_DOMENER:
            # Behold HA-domenet. «sensor» røper ingenting og forteller leseren
            # at det faktisk er en sensor og ikke en input_number. Er domenet
            # ukjent, er det ikke et domene: da står det et navn der.
            alias = f"{domene}.alias_{nummer}"
        else:
            alias = f"{sort}_{nummer}"
        self._kjente[nokkel] = alias
        return alias


async def _versjoner(hass: HomeAssistant) -> dict[str, Any]:
    """Versjonen som faktisk kjører, versjonen som ligger på disk, og HA-en.

    `manifest.json` bumpes ved release, så filen på disk kan påstå en versjon
    den ikke er lastet fra: oppdaterer HACS filene uten at HA startes på nytt,
    kjører fortsatt den gamle koden. `async_get_integration` gir manifestet
    slik det ble lest ved lasting, altså koden som faktisk kjører, mens vi
    leser filen på disk ved siden av. Spriker de to, er det nettopp da
    diagnostikken trengs, og da sier `versjon_avvik` fra.
    """
    kjorende: str | None = None
    kilde = "ukjent"
    try:
        integration = await async_get_integration(hass, DOMAIN)
    except Exception:  # loaderen skal aldri kunne felle hele dumpen
        integration = None
    if integration is not None:
        rå = getattr(integration, "version", None)
        if rå is not None:
            kjorende = str(rå)
            kilde = "loader"

    paa_disk: str | None = None
    try:
        manifest = json.loads((Path(__file__).parent / "manifest.json").read_text(encoding="utf-8"))
        verdi = manifest.get("version")
        paa_disk = str(verdi) if verdi is not None else None
    except (OSError, ValueError):
        paa_disk = None

    if kjorende is None and paa_disk is not None:
        kjorende = paa_disk
        kilde = "manifest_fil"

    return {
        # Versjonsstrengene er våre egne, men manifest.json på disk er en fil
        # HACS eller en bruker kan ha rørt, så de går samme vei som resten.
        "version": rens_trygg(kjorende),
        "version_kilde": kilde,
        "manifest_version_paa_disk": rens_trygg(paa_disk),
        "versjon_avvik": bool(kjorende and paa_disk and kjorende != paa_disk),
        "ha_version": rens_trygg(HA_VERSION) if isinstance(HA_VERSION, str) else None,
    }


def _config_entry_seksjon(entry: ConfigEntry, aliaser: Aliaser) -> dict[str, Any]:
    """Entryets identitet (aliasert), skjemaversjon og de valgte verdiene."""
    data = dict(getattr(entry, "data", {}) or {})
    options = dict(getattr(entry, "options", {}) or {})
    tilstand = getattr(entry, "state", None)
    return {
        "alias": aliaser.alias(getattr(entry, "entry_id", None), "entry"),
        "tittel_alias": aliaser.alias(getattr(entry, "title", None), "tittel"),
        # Skjemaversjonen på selve entryet, ikke releaseversjonen. De to ble
        # forvekslet før, og da fortalte dumpen aldri hvilken kode som kjørte.
        "version": rens_trygg(getattr(entry, "version", None)),
        "minor_version": rens_trygg(getattr(entry, "minor_version", None)),
        "source": rens_trygg(getattr(entry, "source", None)),
        "state": rens_trygg(getattr(tilstand, "value", tilstand)),
        "valg": {nokkel: rens_trygg(data.get(nokkel)) for nokkel in VALG_ALLOWLIST},
        "options_overstyrer": sorted(n for n in options if n in VALG_ALLOWLIST),
    }


def _input_roller_seksjon(entry: ConfigEntry, aliaser: Aliaser) -> dict[str, Any]:
    """Hvilke roller som er satt opp, med aliaserte entity-id-er."""
    data = dict(getattr(entry, "data", {}) or {})
    roller: dict[str, Any] = {}
    for rolle, conf in ROLLE_TIL_CONF.items():
        entity_id = data.get(conf) or None
        roller[rolle] = {
            "konfigurert": entity_id is not None,
            "entitet_alias": aliaser.alias(entity_id, "entitet"),
        }
    return roller


def _dso_seksjon(coordinator: Any) -> dict[str, Any]:
    """Tariffgrunnlaget. D2 utvider med tarifforigin fra K2."""
    dso = getattr(coordinator, "dso", {}) or {}
    return {
        "id": rens_trygg(getattr(coordinator, "_dso_id", None)),
        "name": rens_trygg(dso.get("name") if isinstance(dso, dict) else None),
        "energiledd_dag_eks_mva": rens_trygg(getattr(coordinator, "energiledd_dag_eks_mva", None)),
        "energiledd_natt_eks_mva": rens_trygg(getattr(coordinator, "energiledd_natt_eks_mva", None)),
        "energiledd_dag_inkl_mva": rens_trygg(getattr(coordinator, "energiledd_dag", None)),
        "energiledd_natt_inkl_mva": rens_trygg(getattr(coordinator, "energiledd_natt", None)),
        "kapasitetstrinn_count": len(getattr(coordinator, "kapasitetstrinn", []) or []),
        # Metoden er halve svaret på «hvorfor stemmer ikke fastleddet».
        # Uten den i diagnostikken må man gjette fra DSO-id-en.
        "fastledd_metode": rens_trygg(getattr(coordinator, "fastledd_metode", None)),
        "ukesmaks_count": len(getattr(coordinator, "_weekly_max_power", {}) or {}),
    }


def _vakthold_seksjon(coordinator: Any, aliaser: Aliaser) -> dict[str, Any]:
    """Vaktholdet er det første man vil se når noen melder at tallene stoppet.

    Hvilken input som svikter, hvor lenge, og hvilke varsler som står ute nå.
    Problemradene bærer entity-id-en fra coordinatoren, så den aliaseres her
    med samme alias som rollen fikk over. Resten av raden plukkes felt for felt
    fra `PROBLEM_ALLOWLIST`, ikke kopieres med `entity_id` strøket: et nytt felt
    på raden skal kreve en beslutning, ikke bare dukke opp i dumpen.
    """
    data = getattr(coordinator, "data", None) or {}
    problemer = []
    for problem in data.get("input_problemer", []) or []:
        if not isinstance(problem, dict):
            continue
        rad = {n: rens_trygg(problem.get(n)) for n in PROBLEM_ALLOWLIST}
        rad["entitet_alias"] = aliaser.alias(problem.get("entity_id"), "entitet")
        problemer.append(rad)

    sist_gyldig = getattr(coordinator, "_input_sist_gyldig", {}) or {}
    sist_okning = getattr(coordinator, "_last_energy_increase", None)
    return {
        "grace_minutter": INPUT_UTFALL_GRACE_MINUTTER,
        "frossen_terskel_timer": rens_trygg(getattr(coordinator, "energi_frossen_terskel_timer", None)),
        "sist_energi_okning": rens_trygg(sist_okning),
        "input_sist_gyldig": rens_trygg(dict(sist_gyldig)),
        "aktive_issues": rens_trygg(
            sorted(str(n) for n in getattr(coordinator, "_vakthold_issues", set()) or set())
        ),
        "input_problemer": problemer,
    }


def _beregning_seksjon(coordinator: Any) -> dict[str, Any]:
    """Allowlisten fra coordinator.data, renset til JSON-primitiver."""
    data = getattr(coordinator, "data", None) or {}
    return {nokkel: rens_trygg(data.get(nokkel)) for nokkel in BEREGNING_ALLOWLIST}


async def bygg_diagnostikk(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Bygg hele snapshotet for et config entry.

    Virker også når entryet ikke er lastet: da finnes ikke `runtime_data`, og
    seksjonene som kommer fra coordinatoren står som None. Det er nettopp når
    oppsettet feiler at noen ber om en dump, så den skal ikke kreve at
    oppsettet virket.
    """
    aliaser = Aliaser()
    coordinator = getattr(entry, "runtime_data", None)
    lastet = coordinator is not None and hasattr(coordinator, "data")

    return {
        "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "integration": {"domain": DOMAIN, **await _versjoner(hass)},
        "config_entry": _config_entry_seksjon(entry, aliaser),
        "input_roller": _input_roller_seksjon(entry, aliaser),
        "lastet": lastet,
        "dso": _dso_seksjon(coordinator) if lastet else None,
        "vakthold": _vakthold_seksjon(coordinator, aliaser) if lastet else None,
        "beregning": _beregning_seksjon(coordinator) if lastet else None,
        "utelatt_med_vilje": list(UTELATT_MED_VILJE),
    }
