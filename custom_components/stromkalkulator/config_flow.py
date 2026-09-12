"""Config flow for Nettleie integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .const import (
    AVGIFTSSONE_OPTIONS,
    AVGIFTSSONE_STANDARD,
    BOLIGTYPE_BOLIG,
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
    CONF_TARIFFMODUS,
    DEFAULT_DSO,
    DEFAULT_ENERGI_FROSSEN_TIMER,
    DEFAULT_ENERGILEDD_DAG,
    DEFAULT_ENERGILEDD_NATT,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DEFAULT_NAME,
    DOMAIN,
    DSO_EGENDEFINERT,
    DSO_LIST,
    INPUT_ROLLE_EFFEKT,
    INPUT_ROLLE_EKSPORT,
    INPUT_ROLLE_ENERGI,
    INPUT_ROLLE_LEVERANDORPRIS,
    INPUT_ROLLE_SPOTPRIS,
    MAX_ENERGI_FROSSEN_TIMER,
    MIN_ENERGI_FROSSEN_TIMER,
    TARIFFMODUS_CATALOG,
    TARIFFMODUS_MANUAL,
    compute_energiledd_inkl_mva,
    resolve_avgiftssone,
)
from .dso import FASTLEDD_OV_TREFASE, finn_sikringstrinn, hent_fastledd_metode
from .inputadapter import (
    GRUNN_FEIL_DIMENSJON,
    GRUNN_FEIL_VALUTA,
    GRUNN_FINNES_IKKE,
    GRUNN_IKKE_KUMULATIV,
    GRUNN_UKJENT_ENHET,
    GRUNN_URIMELIG_VERDI,
    Ugyldig,
    Utilgjengelig,
    les_input,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

    from .dso import DSOEntry

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Feilnøkkel per `Ugyldig`-grunn fra adapteren. Grunnene som ikke står her er
# de som ikke skal stoppe et oppsett: at sensoren akkurat nå leverer noe
# uleselig sier ingenting om at valget er feil, og en spotpris-sensor er ofte
# `unknown` i minuttene rett etter en omstart.
_FEILNOKKEL_PER_GRUNN: dict[str, str] = {
    GRUNN_UKJENT_ENHET: "enhet_ukjent",
    GRUNN_FEIL_DIMENSJON: "enhet_feil_dimensjon",
    GRUNN_FEIL_VALUTA: "enhet_feil_valuta",
    GRUNN_IKKE_KUMULATIV: "energi_ikke_kumulativ",
    GRUNN_URIMELIG_VERDI: "spot_value_unreasonable",
}

# Config-feltet hver rolle valideres gjennom.
_ROLLE_PER_FELT: dict[str, str] = {
    CONF_POWER_SENSOR: INPUT_ROLLE_EFFEKT,
    CONF_SPOT_PRICE_SENSOR: INPUT_ROLLE_SPOTPRIS,
    CONF_ENERGY_SENSOR: INPUT_ROLLE_ENERGI,
    CONF_EXPORT_POWER_SENSOR: INPUT_ROLLE_EKSPORT,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR: INPUT_ROLLE_LEVERANDORPRIS,
}


def _valider_sensorfelt(hass: Any, user_input: dict[str, Any], *, paakrevd: set[str]) -> dict[str, str]:
    """Valider alle fem sensorrollene gjennom adapteren.

    Samme kode i oppsett, options og reconfigure, og samme kode som runtime
    bruker. Før sto det en halv vakt bare på spotprisen, og den avviste
    øre/kWh den kunne regnet om mens den slapp EUR gjennom til å bli lest som
    kroner.
    """
    errors: dict[str, str] = {}
    naa = dt_util.now()

    for felt, rolle in _ROLLE_PER_FELT.items():
        entity_id = user_input.get(felt)
        if not entity_id:
            if felt in paakrevd:
                errors[felt] = "sensor_not_found"
            continue
        resultat = les_input(hass, entity_id, rolle, naa=naa)
        if isinstance(resultat, Utilgjengelig) and resultat.grunn == GRUNN_FINNES_IKKE:
            errors[felt] = "sensor_not_found"
        elif isinstance(resultat, Ugyldig):
            feilnokkel = _FEILNOKKEL_PER_GRUNN.get(resultat.grunn)
            if feilnokkel:
                errors[felt] = feilnokkel

    return errors


def _dso_options() -> list[selector.SelectOptionDict]:
    """Get sorted DSO options with Egendefinert last."""
    return [
        *sorted(
            [
                selector.SelectOptionDict(value=key, label=value["name"])
                for key, value in DSO_LIST.items()
                if value.get("supported", False) and key != DSO_EGENDEFINERT
            ],
            key=lambda x: x["label"],
        ),
        selector.SelectOptionDict(value=DSO_EGENDEFINERT, label="Egendefinert"),
    ]


def _bruker_sikringstrinn(dso_id: str | None) -> bool:
    """Om nettselskapet fakturerer fastledd etter sikringsstørrelse."""
    dso = DSO_LIST.get(dso_id or "")
    # `is not None` og ikke `bool(dso)`: sistnevnte smalner ikke typen for mypy.
    return dso is not None and hent_fastledd_metode(dso) == FASTLEDD_OV_TREFASE


def _sikringstrinn_selector(dso_id: str) -> selector.SelectSelector:
    """Nedtrekk med nettselskapets egne fastledd-rader, ordrett fra prislisten.

    Vi ber ikke om ampere som et tall, fordi satsen hos flere nettselskap også
    avhenger av systemspenning (3x230 V IT mot 3x400 V TN). Å utlede raden fra
    et amperetall alene ville vært en tolkning vi ikke har grunnlag for.
    """
    trinn = DSO_LIST[dso_id].get("fastledd_sikringstrinn", [])
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[selector.SelectOptionDict(value=t["id"], label=t["label"]) for t in trinn],
            mode=selector.SelectSelectorMode.LIST,
        ),
    )


def _config_data_schema(current: dict[str, Any]) -> vol.Schema:
    """Bygg konfigurasjons-skjemaet med defaults fra ``current`` (typisk entry.data).

    Delt mellom options-flowen og reconfigure-steget slik at de to inngangene
    alltid viser og validerer de samme feltene.
    """
    avgiftssone_options: list[selector.SelectOptionDict] = [
        selector.SelectOptionDict(value=key, label=label) for key, label in AVGIFTSSONE_OPTIONS.items()
    ]

    felter: dict[Any, Any] = {
        vol.Required(
            CONF_DSO,
            default=current.get(CONF_DSO, DEFAULT_DSO),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=_dso_options(),
                mode=selector.SelectSelectorMode.DROPDOWN,
            ),
        ),
    }

    # Sikringsstørrelse vises kun for nettselskap som fakturerer etter den.
    # Bytter brukeren til et slikt nettselskap i denne submiten, finnes ikke
    # feltet ennå; da tømmes valget og et repair-varsel ber om at
    # innstillingene åpnes på nytt (se __init__.py).
    dso_id: str = current.get(CONF_DSO, DEFAULT_DSO)
    if _bruker_sikringstrinn(dso_id):
        lagret = finn_sikringstrinn(DSO_LIST[dso_id], current.get(CONF_SIKRINGSTRINN))
        nokkel = (
            vol.Required(CONF_SIKRINGSTRINN, default=lagret[1]["id"])
            if lagret
            else vol.Required(CONF_SIKRINGSTRINN)
        )
        felter[nokkel] = _sikringstrinn_selector(dso_id)

    felter.update(
        {
            vol.Required(
                CONF_BOLIGTYPE,
                default=current.get(CONF_BOLIGTYPE, BOLIGTYPE_BOLIG),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=key, label=label)
                        for key, label in BOLIGTYPE_OPTIONS.items()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Required(
                CONF_AVGIFTSSONE,
                default=current.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=avgiftssone_options,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
            vol.Optional(
                CONF_HAR_NORGESPRIS,
                default=current.get(CONF_HAR_NORGESPRIS, False),
            ): selector.BooleanSelector(),
            vol.Required(
                CONF_POWER_SENSOR,
                default=current.get(CONF_POWER_SENSOR),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                ),
            ),
            vol.Required(
                CONF_SPOT_PRICE_SENSOR,
                default=current.get(CONF_SPOT_PRICE_SENSOR),
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                ),
            ),
            vol.Optional(
                CONF_SPOTPRIS_INKL_MVA,
                default=current.get(CONF_SPOTPRIS_INKL_MVA, False),
            ): selector.BooleanSelector(),
            vol.Optional(
                CONF_ENERGY_SENSOR,
                description={"suggested_value": current.get(CONF_ENERGY_SENSOR)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="energy",
                ),
            ),
            vol.Optional(
                CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
                description={"suggested_value": current.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                ),
            ),
            vol.Optional(
                CONF_EXPORT_POWER_SENSOR,
                description={"suggested_value": current.get(CONF_EXPORT_POWER_SENSOR)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor",
                    device_class="power",
                ),
            ),
            # Energiledd er et overstyringsfelt, ikke et påkrevd tall med
            # forrige verdi som default (kontrakt §6). Var det påkrevd, ville
            # hver eneste lagring i innstillingene fryst katalogens sats på
            # entryet, og det var nettopp den mekanismen som gjorde at en
            # tariffendring aldri nådde fram. Tomt felt betyr «følg katalogen».
            # Egendefinert har ingen katalog og beholder derfor sitt tall.
            **_energiledd_felt(current, dso_id == DSO_EGENDEFINERT),
            vol.Optional(
                CONF_ENERGI_FROSSEN_TIMER,
                default=current.get(CONF_ENERGI_FROSSEN_TIMER, DEFAULT_ENERGI_FROSSEN_TIMER),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=MIN_ENERGI_FROSSEN_TIMER,
                    max=MAX_ENERGI_FROSSEN_TIMER,
                    step=1,
                    unit_of_measurement="t",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
            vol.Optional(
                CONF_KAPASITET_VARSEL_TERSKEL,
                default=current.get(CONF_KAPASITET_VARSEL_TERSKEL, DEFAULT_KAPASITET_VARSEL_TERSKEL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=20,
                    step=0.5,
                    unit_of_measurement="kW",
                    mode=selector.NumberSelectorMode.BOX,
                ),
            ),
        }
    )

    return vol.Schema(felter)


def _energiledd_sats_selector() -> selector.NumberSelector:
    """Tallfeltet for et energiledd, i NOK/kWh eks. mva og avgifter."""
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=2,
            step="any",
            unit_of_measurement="NOK/kWh",
            mode=selector.NumberSelectorMode.BOX,
        ),
    )


def _energiledd_felt(current: dict[str, Any], egendefinert: bool) -> dict[Any, Any]:
    """Energiledd-feltene, som overstyring eller som påkrevd tall.

    `suggested_value` og ikke `default`: et default fyller feltet på nytt hver
    gang skjemaet åpnes, og da kan overstyringen aldri fjernes igjen. Et
    suggested_value er brukerens eget tall når det finnes, og tomt ellers.
    """
    if egendefinert:
        return {
            vol.Required(
                CONF_ENERGILEDD_DAG,
                default=current.get(CONF_ENERGILEDD_DAG, DEFAULT_ENERGILEDD_DAG),
            ): _energiledd_sats_selector(),
            vol.Required(
                CONF_ENERGILEDD_NATT,
                default=current.get(CONF_ENERGILEDD_NATT, DEFAULT_ENERGILEDD_NATT),
            ): _energiledd_sats_selector(),
        }
    return {
        vol.Optional(
            CONF_ENERGILEDD_DAG,
            description={"suggested_value": current.get(CONF_ENERGILEDD_DAG)},
        ): _energiledd_sats_selector(),
        vol.Optional(
            CONF_ENERGILEDD_NATT,
            description={"suggested_value": current.get(CONF_ENERGILEDD_NATT)},
        ): _energiledd_sats_selector(),
    }


def _ore(verdi: float) -> str:
    """Sats i NOK/kWh vist som øre med norsk desimalkomma."""
    return f"{verdi * 100:.2f}".replace(".", ",")


def _tariffhint(current: dict[str, Any]) -> dict[str, str]:
    """Plassholderne som forteller hva nettselskapets prisliste fører nå.

    Katalogtallene vises inkl. forbruksavgift, Enova og mva, fordi det er
    tallet brukeren kjenner igjen fra fakturaen. Selve feltene tas imot eks.
    avgifter, og det står i teksten over dem.
    """
    dso_id: str = current.get(CONF_DSO, DEFAULT_DSO)
    dso = DSO_LIST.get(dso_id)
    sone: str = current.get(CONF_AVGIFTSSONE, AVGIFTSSONE_STANDARD)
    if dso is None or dso_id == DSO_EGENDEFINERT:
        # Egendefinert har ingen prisliste å lese fra. Strekene står der
        # framfor et plausibelt tall (incident 006), og setningen etter i
        # teksten forklarer hvorfor de er tomme.
        return {"dso": "Egendefinert", "katalog_dag": "-", "katalog_natt": "-"}
    return {
        "dso": dso["name"],
        "katalog_dag": _ore(compute_energiledd_inkl_mva(dso["energiledd_dag_eks_mva"], sone)),
        "katalog_natt": _ore(compute_energiledd_inkl_mva(dso["energiledd_natt_eks_mva"], sone)),
    }


# Valgfrie entitetsfelt som skal kunne tømmes igjen. Home Assistant utelater et
# tømt `vol.Optional`-felt fra user_input, så et rett `{**current, **user_input}`
# gjeninnfører bindingen brukeren nettopp fjernet. Det er grunnen til at ingen
# har fått fjernet en valgfri sensor de en gang valgte.
_TOMBARE_FELT: tuple[str, ...] = (
    CONF_ENERGY_SENSOR,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
)


def _ny_entry_data(current: dict[str, Any], user_input: dict[str, Any]) -> dict[str, Any]:
    """Slå skjemaet sammen med det som alt står på entryet.

    Tre ting skjer her som en rett sammenslåing ikke gjør: tømte valgfrie
    entitetsfelt fjernes, tariffmodusen settes ut fra om energiledd-feltet er
    fylt ut, og et bytte av nettselskap tar med seg avgiftssone og sikringstrinn.
    """
    ny: dict[str, Any] = {**current, **user_input}

    for felt in _TOMBARE_FELT:
        if not user_input.get(felt):
            ny.pop(felt, None)

    _sett_tariffmodus(ny, user_input, gammel_dso=current.get(CONF_DSO))
    return ny


def _sett_tariffmodus(ny: dict[str, Any], user_input: dict[str, Any], *, gammel_dso: str | None) -> None:
    """Avgjør hvor satsene skal komme fra etter denne lagringen (kontrakt §6).

    Tomt energiledd-felt betyr `catalog`, utfylt betyr `manual`. Det gjelder
    også den som står i `legacy_unconfirmed`: åpner de innstillingene og lagrer
    uten å røre feltet, er svaret «følg katalogen».
    """
    ny_dso = ny.get(CONF_DSO, DEFAULT_DSO)

    if ny_dso == DSO_EGENDEFINERT:
        # Ingen katalog å falle tilbake på, så satsene er alltid brukerens.
        ny[CONF_TARIFFMODUS] = TARIFFMODUS_MANUAL
        return

    if ny_dso != gammel_dso:
        # Et energiledd hører til ett nettselskaps prisliste. Overlever det et
        # bytte, får brukeren BKKs sats med Elvias kapasitetstrinn.
        ny[CONF_TARIFFMODUS] = TARIFFMODUS_CATALOG
        ny.pop(CONF_ENERGILEDD_DAG, None)
        ny.pop(CONF_ENERGILEDD_NATT, None)
        return

    overstyrt = False
    for felt in (CONF_ENERGILEDD_DAG, CONF_ENERGILEDD_NATT):
        if user_input.get(felt) is None:
            ny.pop(felt, None)
        else:
            overstyrt = True
    ny[CONF_TARIFFMODUS] = TARIFFMODUS_MANUAL if overstyrt else TARIFFMODUS_CATALOG


def _apply_dso_derivation(user_input: dict[str, Any], current: dict[str, Any]) -> None:
    """Ta med avgiftssone og satser over til det nye nettselskapet.

    Energileddet re-avledes ikke lenger her: et kjent nettselskap får
    `catalog`-modus av `_sett_tariffmodus`, og da er katalogen satsen. Det som
    trengs her er avgiftssonen, og at Egendefinert får med seg et tall å starte
    fra, siden det er brukerens eget felt og ingen katalog finnes.
    """
    old_dso = current.get(CONF_DSO)
    new_dso = user_input.get(CONF_DSO)
    if new_dso == old_dso:
        return

    if new_dso != DSO_EGENDEFINERT and new_dso in DSO_LIST:
        dso: DSOEntry = DSO_LIST[new_dso]
        user_input[CONF_AVGIFTSSONE] = resolve_avgiftssone(dso)

    if new_dso == DSO_EGENDEFINERT:
        # Bytter man til Egendefinert nå, står satsene med rettet merking i
        # skjemaet, så varselet om den gamle «inkl. avgifter»-teksten er ikke
        # relevant.
        user_input[CONF_EGENDEFINERT_SATSER_BEKREFTET] = True
        # Skjemaet ble tegnet for det gamle nettselskapet, så energiledd-feltet
        # kan stå tomt fordi katalogen gjaldt. Egendefinert har ingen katalog,
        # og et tomt felt ville gitt en sats fra ingensteds. Vi starter der
        # anlegget faktisk lå, og brukeren retter tallet mot sin egen prisliste.
        forrige = DSO_LIST.get(old_dso or "")
        for felt, katalognokkel in (
            (CONF_ENERGILEDD_DAG, "energiledd_dag_eks_mva"),
            (CONF_ENERGILEDD_NATT, "energiledd_natt_eks_mva"),
        ):
            if user_input.get(felt) is not None:
                continue
            arvet = current.get(felt)
            if arvet is None and forrige is not None:
                arvet = forrige[katalognokkel]  # type: ignore[literal-required]
            if arvet is not None:
                user_input[felt] = arvet

    # Et sikringstrinn hører til ett nettselskaps prisliste. Overlever id-en et
    # bytte, ville den enten peke i tomme luften eller, verre, treffe en rad med
    # samme id og helt annen pris. Tømmes med vilje, også ved bytte til
    # Egendefinert, som ikke har sikringstrinn i det hele tatt.
    ny_dso: DSOEntry | dict[str, Any] = DSO_LIST.get(new_dso or "", {})
    if finn_sikringstrinn(ny_dso, user_input.get(CONF_SIKRINGSTRINN)) is None:
        user_input[CONF_SIKRINGSTRINN] = None


def _validate_options_input(
    hass: Any,
    user_input: dict[str, Any],
    entry_id: str,
    current_data: dict[str, Any],
) -> dict[str, str]:
    """Valider alle fem sensorrollene og at power-sensoren ikke er i bruk.

    Delt mellom options-flowen og reconfigure-steget. Returnerer en error-dict
    (tom hvis alt er gyldig).
    """
    errors: dict[str, str] = _valider_sensorfelt(
        hass, user_input, paakrevd={CONF_POWER_SENSOR, CONF_SPOT_PRICE_SENSOR}
    )

    new_power = user_input.get(CONF_POWER_SENSOR)
    if new_power and new_power != current_data.get(CONF_POWER_SENSOR):
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id != entry_id and entry.data.get(CONF_POWER_SENSOR) == new_power:
                errors[CONF_POWER_SENSOR] = "already_configured"
                break

    return errors


class NettleieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Nettleie."""

    # VERSION 3: spotpris_inkl_mva-felt lagt til. Default False (eks. mva, riktig
    # for HA-core nordpool). Eksisterende konfig migreres også til False; den
    # gamle koden antok inkl. mva, men det var feil. Se incident 004.
    # VERSION 4: entry unique_id gikk fra "{DOMAIN}_{power_sensor}" til entry_id.
    # Det gamle skjemaet brakk ved rename av power-sensoren og bandt
    # duplikatvernet til sensornavnet. entry_id er stabilt og kollisjonsfritt;
    # duplikatvernet er nå en eksplisitt sjekk mot eksisterende entries' data.
    # VERSION 5: `tariffmodus` sier hvor energiledd-satsen kommer fra. Før vant
    # en sats lagret på entryet over dso.py, og oppsettet lagret katalogens sats
    # på alle, så en tariffendring nådde aldri fram. Se kontrakt §6 og §7.
    VERSION: int = 5

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step - select DSO and avgiftssone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DSO, default=DEFAULT_DSO): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_dso_options(),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(CONF_BOLIGTYPE, default=BOLIGTYPE_BOLIG): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=label)
                                for key, label in BOLIGTYPE_OPTIONS.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(CONF_HAR_NORGESPRIS, default=False): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def async_step_sensors(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the sensors step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            power_sensor: Any = user_input[CONF_POWER_SENSOR]

            # Samme validering som options, reconfigure og runtime: en enhet vi
            # ikke kan regne om skal stoppes her, ikke oppdages som et tusen
            # ganger feil tall en måned senere.
            errors = _valider_sensorfelt(
                self.hass, user_input, paakrevd={CONF_POWER_SENSOR, CONF_SPOT_PRICE_SENSOR}
            )

            # Duplikatvern: samme power-sensor skal ikke kunne legges til to
            # ganger. Sammenlign mot eksisterende entries' data, ikke unique_id
            # (som nå er entry_id og dermed alltid unik).
            if not errors:
                for entry in self._async_current_entries():
                    if entry.data.get(CONF_POWER_SENSOR) == power_sensor:
                        errors[CONF_POWER_SENSOR] = "already_configured"
                        break

            if not errors:
                self._data.update(user_input)

                # If custom DSO, go to pricing step (includes avgiftssone)
                if self._data.get(CONF_DSO) == DSO_EGENDEFINERT:
                    return await self.async_step_pricing()

                # Auto-detect avgiftssone from DSO
                dso: DSOEntry = DSO_LIST[self._data[CONF_DSO]]
                self._data[CONF_AVGIFTSSONE] = resolve_avgiftssone(dso)

                # Ingen sats lagres på entryet. Katalogen i dso.py gjelder
                # løpende, så en tariffendring når fram uten at brukeren må
                # gjøre noe. Det er hele poenget med kontrakt §6: før lagret
                # dette steget katalogens sats, og da frøs den for godt.
                self._data[CONF_TARIFFMODUS] = TARIFFMODUS_CATALOG

                # Sikringsbasert fastledd kan ikke måles, og et gjettet trinn
                # ville gitt et plausibelt men feil beløp. Spør nå, i oppsettet,
                # så nye brukere aldri havner i "ikke valgt"-tilstanden.
                if _bruker_sikringstrinn(self._data[CONF_DSO]):
                    return await self.async_step_sikring()

                return self._create_entry()

        return self.async_show_form(
            step_id="sensors",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_POWER_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="power",
                        ),
                    ),
                    vol.Required(CONF_SPOT_PRICE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                        ),
                    ),
                    vol.Optional(CONF_SPOTPRIS_INKL_MVA, default=False): selector.BooleanSelector(),
                    vol.Optional(CONF_ENERGY_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="energy",
                        ),
                    ),
                    vol.Optional(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                        ),
                    ),
                    vol.Optional(CONF_EXPORT_POWER_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="power",
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_sikring(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Velg fastledd-rad for nettselskap som fakturerer etter sikringsstørrelse."""
        dso_id: str = self._data[CONF_DSO]

        if user_input is not None:
            self._data.update(user_input)
            return self._create_entry()

        return self.async_show_form(
            step_id="sikring",
            data_schema=vol.Schema({vol.Required(CONF_SIKRINGSTRINN): _sikringstrinn_selector(dso_id)}),
            description_placeholders={"dso": DSO_LIST[dso_id]["name"]},
        )

    async def async_step_pricing(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the pricing step for custom grid company."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            # Teksten over feltet er rettet, så den som taster nå har fått
            # riktig beskjed og skal ikke møte varselet om feilmerkingen
            # (incident 007).
            self._data[CONF_EGENDEFINERT_SATSER_BEKREFTET] = True
            # Egendefinert har ingen katalog å falle tilbake på; tallene her er
            # brukerens egne og skal aldri overskrives av dso.py.
            self._data[CONF_TARIFFMODUS] = TARIFFMODUS_MANUAL
            return self._create_entry()

        return self.async_show_form(
            step_id="pricing",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_AVGIFTSSONE, default=AVGIFTSSONE_STANDARD): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=label)
                                for key, label in AVGIFTSSONE_OPTIONS.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        CONF_ENERGILEDD_DAG, default=DEFAULT_ENERGILEDD_DAG
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=2,
                            step="any",
                            unit_of_measurement="NOK/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(
                        CONF_ENERGILEDD_NATT, default=DEFAULT_ENERGILEDD_NATT
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=2,
                            step="any",
                            unit_of_measurement="NOK/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    def _create_entry(self) -> FlowResult:
        """Create the config entry.

        Setter ikke unique_id her: config-flowen kjenner ikke entry_id før
        entryet er opprettet. async_setup_entry setter unique_id = entry_id ved
        første oppstart. Duplikatvern mot samme power-sensor gjøres i
        async_step_sensors (eksplisitt data-sjekk), ikke via unique_id.
        """
        dso_name: str = DSO_LIST[self._data[CONF_DSO]]["name"]
        title: str = f"{DEFAULT_NAME} ({dso_name})"

        return self.async_create_entry(
            title=title,
            data=self._data,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Reconfigure an existing entry via the standard HA entry menu.

        Reuses the same schema, validation and DSO-derivation as the options
        flow. Unlike the options flow (which writes to entry.data via
        async_update_entry), this persists via async_update_reload_and_abort,
        the idiomatic reconfigure API. unique_id is entry_id and stays put
        regardless of which power sensor is chosen.
        """
        entry: config_entries.ConfigEntry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_options_input(self.hass, user_input, entry.entry_id, entry.data)
            if not errors:
                _apply_dso_derivation(user_input, dict(entry.data))
                new_data: dict[str, Any] = _ny_entry_data(dict(entry.data), user_input)
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_config_data_schema(entry.data),
            errors=errors,
            description_placeholders=_tariffhint(dict(entry.data)),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NettleieOptionsFlow:
        """Create the options flow."""
        return NettleieOptionsFlow()


class NettleieOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Nettleie."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        current: dict[str, Any] = self.config_entry.data

        if user_input is not None:
            errors = _validate_options_input(self.hass, user_input, self.config_entry.entry_id, current)
            if not errors:
                _apply_dso_derivation(user_input, dict(current))

                new_data: dict[str, Any] = _ny_entry_data(dict(current), user_input)
                # unique_id er entry_id (stabil) og skal ikke røres når power-
                # sensoren endres. Duplikatvern håndteres av
                # _validate_options_input over.
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_config_data_schema(current),
            errors=errors,
            description_placeholders=_tariffhint(dict(current)),
        )
