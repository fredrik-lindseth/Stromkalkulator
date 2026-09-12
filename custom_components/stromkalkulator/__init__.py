"""Nettleie integration for Home Assistant."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import dt as dt_util

from .const import (
    AVGIFTSSONE_NORD_NORGE,
    AVGIFTSSONE_STANDARD,
    CONF_AVGIFTSSONE,
    CONF_DSO,
    CONF_EGENDEFINERT_SATSER_BEKREFTET,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_HAR_NORGESPRIS,
    CONF_SIKRINGSTRINN,
    CONF_SPOTPRIS_INKL_MVA,
    CONF_TARIFFMODUS,
    DEFAULT_DSO,
    DOMAIN,
    DSO_EGENDEFINERT,
    EGENDEFINERT_ISSUE_PREFIX,
    ENOVA_AVGIFT,
    NORGESPRIS_SLUTT_AAR,
    SATSER_GJELDER_AAR,
    TARIFF_ISSUE_PREFIX,
    TARIFFMODUS_CATALOG,
    TARIFFMODUS_LEGACY,
    TARIFFMODUS_MANUAL,
    compute_energiledd_inkl_mva,
    energiledd_avviker,
    get_forbruksavgift,
    get_mva_sats,
    har_lagret_energiledd,
    les_tariffmodus,
    resolve_avgiftssone,
)
from .coordinator import NettleieCoordinator
from .dso import (
    DSO_LIST,
    DSO_MIGRATIONS,
    FASTLEDD_OV_TREFASE,
    DSOFusjon,
    finn_sikringstrinn,
    hent_fastledd_metode,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

_LOGGER: logging.Logger = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]

type StromkalkulatorConfigEntry = ConfigEntry[NettleieCoordinator]

_MIGRATION_INDEX: dict[str, DSOFusjon] = {m.gammel: m for m in DSO_MIGRATIONS}

# Issue-id-er som gjelder ett anlegg er suffikset med entry_id (incident 001:
# entry_id er nøkkelen, aldri DSO-id eller brukervalg). HA lager entry_id som en
# ULID (26 tegn, versaler og siffer); entries fra før ULID-skiftet har 32 tegn
# heksadesimalt. Mønsteret treffer derfor bare ekte entry-suffikser, og lar
# domenevide issues som satser_utdatert og dso_migration_<gammel>_<ny> stå.
_ENTRY_ID_SUFFIX = re.compile(r"_([0-9A-Z]{26}|[0-9a-f]{32})$")


def _migrate_storage_file_sync(storage_dir: str, old_dso: str, new_dso: str) -> None:
    """Rename storage file from old DSO key to new DSO key (sync, runs in executor).

    NOTE: Since v0.55.0, storage files are keyed by entry_id, not DSO.
    This function only handles transitional migration for users upgrading
    from <=v0.54 who also have a DSO merger. The coordinator's
    _load_stored_data handles the DSO→entry_id migration separately.
    """
    old_path = Path(storage_dir) / f"{DOMAIN}_{old_dso}"
    new_path = Path(storage_dir) / f"{DOMAIN}_{new_dso}"

    if not old_path.exists():
        _LOGGER.debug("No storage file to migrate: %s", old_path)
        return

    if new_path.exists():
        _LOGGER.warning(
            "Storage file already exists for %s, skipping migration from %s",
            new_dso,
            old_dso,
        )
        return

    try:
        old_path.rename(new_path)
    except OSError as err:
        _LOGGER.warning("Failed to migrate storage file %s: %s", old_path.name, err)
        return
    _LOGGER.info("Migrated storage file: %s -> %s", old_path.name, new_path.name)


async def _migrate_storage_file(hass: HomeAssistant, storage_dir: str, old_dso: str, new_dso: str) -> None:
    """Migrate storage file in executor to avoid blocking the event loop."""
    await hass.async_add_executor_job(_migrate_storage_file_sync, storage_dir, old_dso, new_dso)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entries to current schema.

    v1 -> v2: Energiledd-overrides lagret som inkl-mva-verdier konverteres til
    eks-mva. Reverserer formelen `inkl = (eks + forbruksavgift + Enova) * (1+mva)`
    basert på avgiftssonen som er lagret på entry-en.

    v2 -> v3: Setter `spotpris_inkl_mva = False` for eksisterende konfig. Den
    gamle koden antok inkl. mva fra spotpris-sensoren, men HA-core nordpool
    leverer eks. mva. Nye konfigurasjoner får samme default. Se incident 004.

    v3 -> v4: Setter entry unique_id = entry_id. Tidligere var den utledet fra
    power-sensorens entity_id ("{DOMAIN}_{power_sensor}"), som brakk ved rename
    og bandt duplikatvernet til sensornavnet. entry_id er stabilt og
    kollisjonsfritt. Endringen er på entry-nivå: entitetene har egne unique_id-er
    i entity-registeret (utledet fra entry_id, ikke entry.unique_id), så de
    beholdes uendret.

    v4 -> v5: Setter `tariffmodus` på hver entry, se kontrakt §7. Fram til nå
    vant en sats lagret på entryet over `dso.py`, og oppsettsflyten lagret
    katalogens sats på hvert eneste oppsett. En tariffendring i katalogen nådde
    derfor aldri fram til en bruker som allerede hadde satt opp anlegget sitt.
    Migreringen rører kun `entry.data`, aldri lagringsfilen med måledata, og
    aldri entry_id eller entitetenes unique-id-er: ingen akkumulator går tapt.
    """
    # Nedgraderingsvern: en entry med høyere versjon enn koden kjenner kommer
    # fra en nyere installasjon som er rullet tilbake. Ikke last den med et
    # ukjent skjema. Gjeldende versjon er 5 (config_flow VERSION).
    if entry.version > 5:
        return False

    if entry.version == 1:
        new_data = {**entry.data}
        sone = entry.data.get(CONF_AVGIFTSSONE) or resolve_avgiftssone(
            DSO_LIST.get(entry.data.get(CONF_DSO, DEFAULT_DSO), {})
        )
        forbruksavgift = get_forbruksavgift(sone)
        mva_sats = get_mva_sats(sone)

        def inkl_to_eks(value: object) -> float | None:
            try:
                v = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            return v / (1 + mva_sats) - forbruksavgift - ENOVA_AVGIFT

        for key in (CONF_ENERGILEDD_DAG, CONF_ENERGILEDD_NATT):
            raw = entry.data.get(key)
            if raw is None:
                continue
            converted = inkl_to_eks(raw)
            if converted is None or converted <= 0:
                # Sannsynlig feil/korrupt verdi; la coordinator falle tilbake
                # til DSO-default ved å fjerne overstyringen.
                new_data.pop(key, None)
                continue
            new_data[key] = round(converted, 5)

        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrerte config entry %s fra v1 til v2 (energiledd inkl→eks mva, avgiftssone=%s)",
            entry.entry_id,
            sone,
        )

    if entry.version == 2:
        # Auto-fix incident 004: HA-core nordpool leverer eks. mva. Sett False
        # for alle eksisterende konfig (riktig for ~alle brukere). Repair-issue
        # informerer om endringen i tilfelle brukeren har en custom-sensor som
        # inkluderer mva (egendefinert template, eldre custom_components/nordpool
        # med VAT=true). Trigges kun for Sør-Norge der mva-håndteringen utgjør
        # en forskjell.
        new_data = {**entry.data, CONF_SPOTPRIS_INKL_MVA: False}
        hass.config_entries.async_update_entry(entry, data=new_data, version=3)
        sone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
        if sone == AVGIFTSSONE_STANDARD:
            ir.async_create_issue(
                hass,
                DOMAIN,
                f"spotpris_mva_check_{entry.entry_id}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="spotpris_mva_check",
            )
        _LOGGER.info(
            "Migrerte config entry %s fra v2 til v3 (spotpris_inkl_mva=False, sone=%s)",
            entry.entry_id,
            sone,
        )

    if entry.version == 3:
        # Bytt til stabil, kollisjonsfri unique_id. Rører kun entry-nivå;
        # entitetene ligger i entity-registeret koblet via config_entry_id og
        # beholdes uendret (se docstring).
        hass.config_entries.async_update_entry(entry, unique_id=entry.entry_id, version=4)
        _LOGGER.info(
            "Migrerte config entry %s fra v3 til v4 (unique_id -> entry_id)",
            entry.entry_id,
        )

    if entry.version == 4:
        new_data = {**entry.data}
        modus = _avled_tariffmodus(new_data)
        new_data[CONF_TARIFFMODUS] = modus
        if modus == TARIFFMODUS_CATALOG:
            # Katalogen gjelder, og da skal det ikke ligge igjen et tall som
            # ser ut som en regel. Ble det stående, ville entryet drifte fra
            # katalogen på nytt ved neste prisendring, og vi ville vært tilbake
            # der vi startet. Brukeren merker ingenting: tallet er enten det
            # samme som katalogens, eller det gjaldt ikke fra før.
            new_data.pop(CONF_ENERGILEDD_DAG, None)
            new_data.pop(CONF_ENERGILEDD_NATT, None)
        hass.config_entries.async_update_entry(entry, data=new_data, version=5)
        _LOGGER.info(
            "Migrerte config entry %s fra v4 til v5 (tariffmodus=%s)",
            entry.entry_id,
            modus,
        )

    return True


def _avled_tariffmodus(data: dict[str, object]) -> str:
    """Hvilken tariffmodus en v4-entry skal ha, etter tabellen i kontrakt §7.

    Hovedregelen er at tall-likhet ikke er brukerintensjon. At en lagret sats
    tilfeldigvis er lik katalogens betyr ikke at brukeren valgte den, og at den
    er ulik betyr ikke at brukeren skrev den: oppsettsflyten lagret katalogens
    sats på alle. Derfor blir ingen `manual` her uten at nettselskapet er
    Egendefinert; de som avviker får `legacy_unconfirmed` og et valg.
    """
    dso_id = data.get(CONF_DSO, DEFAULT_DSO)
    dso = DSO_LIST.get(str(dso_id))

    # Egendefinert har ingen katalog å falle tilbake på, og det samme gjelder
    # et nettselskap som ikke finnes i listen i det hele tatt (håndredigert
    # .storage). Satsen på entryet er alt de har.
    if dso_id == DSO_EGENDEFINERT or dso is None:
        return TARIFFMODUS_MANUAL

    if not har_lagret_energiledd(data):
        return TARIFFMODUS_CATALOG

    # Sesongperioder styrte allerede over den lagrede satsen, så tallene endrer
    # seg ikke av at den forsvinner.
    if dso.get("energiledd_perioder"):
        return TARIFFMODUS_CATALOG

    # Et nettselskap som er fusjonert inn i et annet, eller som ikke lenger
    # vedlikeholdes: den lagrede satsen hører til selskapet de forlater.
    # `dso_migration`-varselet forteller allerede hva som skjedde, og et
    # tariffvarsel i tillegg ville vært to varsler om samme flytting.
    if str(dso_id) in _MIGRATION_INDEX or not dso.get("supported", False):
        return TARIFFMODUS_CATALOG

    sone = data.get(CONF_AVGIFTSSONE) or resolve_avgiftssone(dso)
    if energiledd_avviker(data, dso, str(sone)):
        return TARIFFMODUS_LEGACY
    return TARIFFMODUS_CATALOG


def _issues_for_entry(hass: HomeAssistant, entry_id: str) -> list[str]:
    """Hent våre issue-id-er som er suffikset med denne entry-en."""
    registry = ir.async_get(hass)
    suffix = f"_{entry_id}"
    return [
        issue_id
        for issue_domain, issue_id in list(registry.issues)
        if issue_domain == DOMAIN and issue_id.endswith(suffix)
    ]


def _rydd_issues_for_entry(hass: HomeAssistant, entry_id: str) -> None:
    """Slett alle repair-issues som hører til en entry."""
    for issue_id in _issues_for_entry(hass, entry_id):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        _LOGGER.debug("Fjernet repair-issue %s for slettet entry %s", issue_id, entry_id)


def _rydd_foreldrelose_issues(hass: HomeAssistant) -> None:
    """Slett anleggs-issues som peker på en entry som ikke finnes lenger.

    Issues opprettet av eldre versjoner ble aldri fjernet når brukeren slettet
    anlegget, så de ble liggende og maste om noe som ikke fantes. Ryddingen
    kjøres ved hver setup og rører kun issues i vårt eget domene med et gyldig
    entry_id-suffiks.
    """
    registry = ir.async_get(hass)
    kjente = {oppforing.entry_id for oppforing in hass.config_entries.async_entries(DOMAIN)}

    for issue_domain, issue_id in list(registry.issues):
        if issue_domain != DOMAIN:
            continue
        treff = _ENTRY_ID_SUFFIX.search(issue_id)
        if treff is None or treff.group(1) in kjente:
            continue
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        _LOGGER.info(
            "Fjernet foreldreløs repair-issue %s (entry %s finnes ikke)",
            issue_id,
            treff.group(1),
        )


async def async_setup_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Set up Nettleie from a config entry."""
    # Nye entries opprettes uten unique_id (config-flowen kjenner ikke entry_id
    # før entryet finnes). Sett den til entry_id her: stabil og kollisjonsfri.
    # Migrerte entries (v3->v4) har den allerede, så guarden hopper over dem.
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=entry.entry_id)

    _rydd_foreldrelose_issues(hass)

    # Check for DSO migration (merger)
    dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
    migration = _MIGRATION_INDEX.get(dso_id)

    if migration is not None:
        new_dso = DSO_LIST.get(migration.ny)
        if new_dso is None:
            _LOGGER.error("DSO migration target %s not found in DSO_LIST", migration.ny)
            return False
        new_name = new_dso["name"]

        _LOGGER.info(
            "Migrerer nettselskap: %s → %s (%s)",
            migration.gammel,
            migration.ny,
            new_name,
        )

        # Migrate storage file FIRST (before updating config entry)
        storage_dir = hass.config.path(".storage")
        await _migrate_storage_file(hass, storage_dir, migration.gammel, migration.ny)

        # Update config entry with new DSO key
        new_data = {**entry.data, CONF_DSO: migration.ny}
        hass.config_entries.async_update_entry(entry, data=new_data)

        # Create repair issue
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"dso_migration_{migration.gammel}_{migration.ny}",
            is_fixable=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="tso_migrated",
            translation_placeholders={
                "old_name": migration.gammel,
                "new_name": new_name,
            },
        )

    # Migrer avgiftssone for NO3-DSO-er (incident 003)
    # NO3 ble feil mappet til nord_norge (mva-fritak), men de fleste NO3-selskap
    # er i Trøndelag/Møre og Romsdal som betaler 25% mva.
    current_avgiftssone = entry.data.get(CONF_AVGIFTSSONE)
    if current_avgiftssone == AVGIFTSSONE_NORD_NORGE:
        resolved_dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
        current_dso = DSO_LIST.get(resolved_dso_id)
        if current_dso and current_dso["prisomrade"] == "NO3":
            dso_avgiftssone = current_dso.get("avgiftssone")
            if dso_avgiftssone != AVGIFTSSONE_NORD_NORGE:
                new_data = {**entry.data, CONF_AVGIFTSSONE: AVGIFTSSONE_STANDARD}
                hass.config_entries.async_update_entry(entry, data=new_data)
                _LOGGER.info(
                    "Migrerte avgiftssone for %s fra nord_norge til standard (NO3, mva-pliktig)",
                    current_dso["name"],
                )

    coordinator: NettleieCoordinator = NettleieCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    _check_stale_rates(hass, entry)
    _check_sikringstrinn(hass, entry)
    _check_delt_dso(hass, entry)
    _check_egendefinerte_satser(hass, entry)
    _check_tariffmodus(hass, entry)

    return True


def _ore(verdi: object) -> str:
    """Formater en NOK/kWh-sats som øre med norsk desimalkomma."""
    try:
        tall = float(verdi)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "?"
    return f"{tall * 100:.2f}".replace(".", ",")


def _check_egendefinerte_satser(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Be brukere med egendefinert nettselskap sjekke energiledd-satsen.

    Til og med 1.16.0 var feltet merket «inkl. avgifter» på norsk og «incl.
    taxes» på engelsk, mens koden regner satsen som ren nettleie eks. mva og
    legger forbruksavgift, Enova og mva på selv. Fulgte du teksten, telles
    avgiftene to ganger. Vi kan ikke se hva den enkelte tastet, bare at teksten
    var villedende, så varselet ber om en sjekk framfor å påstå en feil.

    Bekreftelsen lagres på entryet (repairs.py), ellers ville varselet kommet
    tilbake ved hver omstart. Nye oppsett etter rettingen får flagget satt med en
    gang i config-flowen og ser aldri varselet.
    """
    issue_id = f"{EGENDEFINERT_ISSUE_PREFIX}{entry.entry_id}"
    bruker_egendefinert = entry.data.get(CONF_DSO) == DSO_EGENDEFINERT
    if not bruker_egendefinert or entry.data.get(CONF_EGENDEFINERT_SATSER_BEKREFTET):
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    sone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="egendefinert_energiledd",
        translation_placeholders={
            "avgifter": _ore(get_forbruksavgift(sone) + ENOVA_AVGIFT),
            "dag": _ore(entry.data.get(CONF_ENERGILEDD_DAG)),
            "natt": _ore(entry.data.get(CONF_ENERGILEDD_NATT)),
        },
    )


def _check_tariffmodus(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Be brukeren velge når entryets lagrede sats ikke er den katalogen fører.

    Varselet reises kun der satsene faktisk spriker (kontrakt §8). Den som
    allerede ligger riktig skal ikke merke at modusen finnes, og et varsel hos
    alle ville vært en falsk positiv hos de fleste.

    Sjekken kjøres på nytt ved hver oppstart, ikke bare i migreringen. Blir
    katalogen oppdatert til det entryet alt har lagret, forsvinner varselet av
    seg selv, og da er det ingenting å velge mellom.

    Så lenge varselet står ubesvart regner entryet med katalogen. Å la brukeren
    bli stående på en utdatert sats mens vi venter på svar ville vært å
    videreføre nettopp feilen dette retter.
    """
    issue_id = f"{TARIFF_ISSUE_PREFIX}{entry.entry_id}"
    dso = DSO_LIST.get(entry.data.get(CONF_DSO, DEFAULT_DSO))
    sone = entry.data.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)

    uavklart = (
        les_tariffmodus(entry.data) == TARIFFMODUS_LEGACY
        and dso is not None
        and not dso.get("energiledd_perioder")
        and energiledd_avviker(entry.data, dso, sone)
    )
    if not uavklart or dso is None:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    def inkl(verdi: object) -> str:
        try:
            return _ore(compute_energiledd_inkl_mva(float(verdi), sone))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return "?"

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key="tariff_ubekreftet",
        data={"entry_id": entry.entry_id},
        translation_placeholders={
            "dso": dso["name"],
            "lagret_dag": inkl(entry.data.get(CONF_ENERGILEDD_DAG, dso["energiledd_dag_eks_mva"])),
            "lagret_natt": inkl(entry.data.get(CONF_ENERGILEDD_NATT, dso["energiledd_natt_eks_mva"])),
            "katalog_dag": inkl(dso["energiledd_dag_eks_mva"]),
            "katalog_natt": inkl(dso["energiledd_natt_eks_mva"]),
        },
    )


def _check_delt_dso(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Varsle hvis nettselskapet er delt i flere prisområder.

    Area Nett har tre områder med ulik pris, og hvilket som gjelder avgjøres av
    adressen. En fusjon kan migreres automatisk (DSO_MIGRATIONS), men en splitt
    kan ikke: bare brukeren vet hvor anlegget står. Vi regner videre med det
    midterste området i mellomtiden, så sensorene ikke blir utilgjengelige, og
    varselet forteller at valget må tas.
    """
    issue_id = f"dso_delt_{entry.entry_id}"
    dso_id = entry.data.get(CONF_DSO, DEFAULT_DSO)
    dso = DSO_LIST.get(dso_id)
    delt_i = dso.get("delt_i") if dso else None
    if dso is not None and delt_i:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="dso_delt",
            translation_placeholders={
                "dso": dso["name"],
                "omrader": ", ".join(DSO_LIST[nytt]["name"] for nytt in delt_i if nytt in DSO_LIST),
            },
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def _check_sikringstrinn(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Varsle hvis et sikringsbasert fastledd står uten gyldig valg.

    Alut og Netera fakturerer fastledd etter overbelastningsvernets størrelse,
    som ikke kan leses av en effektsensor. Nye oppsett spør om det i
    config-flowen, men to grupper kan havne uten valg: brukere som hadde et av
    nettselskapene fra før feltet fantes, og brukere som bytter til et av dem i
    innstillingene (der feltet først dukker opp neste gang skjemaet åpnes).
    Kapasitetsledd-sensoren står som Ukjent i mellomtiden, framfor å vise et
    plausibelt gjettet beløp.
    """
    issue_id = f"sikringstrinn_mangler_{entry.entry_id}"
    dso = DSO_LIST.get(entry.data.get(CONF_DSO, DEFAULT_DSO))
    mangler = (
        dso is not None
        and hent_fastledd_metode(dso) == FASTLEDD_OV_TREFASE
        and finn_sikringstrinn(dso, entry.data.get(CONF_SIKRINGSTRINN)) is None
    )
    if mangler and dso is not None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="sikringstrinn_mangler",
            translation_placeholders={"dso": dso["name"]},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, issue_id)


def _check_stale_rates(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Varsle via Repairs hvis satsene kan være utdaterte eller Norgespris har opphørt.

    Satsene i const.py og dso.py er verifisert for et bestemt år. Ruller kalenderen
    over uten at satsene er oppdatert, regner integrasjonen videre på fjorårets tall,
    stikk i strid med presisjonsløftet. Varselet er informativt (ikke fiksbart): det
    ber brukeren se etter en oppdatering. Fjernes automatisk når satsene er oppdatert.
    """
    current_year = dt_util.now().year

    if current_year > SATSER_GJELDER_AAR:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "satser_utdatert",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="satser_utdatert",
            translation_placeholders={"aar": str(SATSER_GJELDER_AAR)},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "satser_utdatert")

    if entry.data.get(CONF_HAR_NORGESPRIS) and current_year > NORGESPRIS_SLUTT_AAR:
        ir.async_create_issue(
            hass,
            DOMAIN,
            "norgespris_utlopt",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="norgespris_utlopt",
            translation_placeholders={"aar": str(NORGESPRIS_SLUTT_AAR)},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, "norgespris_utlopt")


async def _async_update_options(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Reload integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok: bool = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: StromkalkulatorConfigEntry) -> None:
    """Rydd opp etter en slettet entry.

    Repair-issuene våre er suffikset med entry_id. Uten denne ryddingen blir de
    liggende i issue-registeret og varsler om et anlegg som ikke finnes lenger.
    """
    _rydd_issues_for_entry(hass, entry.entry_id)
