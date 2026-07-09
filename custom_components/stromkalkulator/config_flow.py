"""Config flow for Nettleie integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    AVGIFTSSONE_OPTIONS,
    AVGIFTSSONE_STANDARD,
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_OPTIONS,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_ENERGY_SENSOR,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_SPOTPRIS_INKL_MVA,
    DEFAULT_DSO,
    DEFAULT_ENERGILEDD_DAG,
    DEFAULT_ENERGILEDD_NATT,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DEFAULT_NAME,
    DOMAIN,
    DSO_LIST,
    resolve_avgiftssone,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

    from .dso import DSOEntry

_LOGGER: logging.Logger = logging.getLogger(__name__)

# Enheter som ikke kan være en spotpris (mangler /-tegnet) eller er valuta uten energi-divisor.
_INVALID_SPOT_UNITS: frozenset[str] = frozenset(
    {"kr", "nok", "eur", "kwh", "mwh", "wh"}
)
# Spotpris er typisk -1 til ~10 NOK/kWh, eller -100 til 1000 øre/kWh, eller -10 til
# ~100 EUR/MWh. Et tall over denne grensen er nesten garantert ikke en spotpris.
_MAX_REASONABLE_SPOT_VALUE: float = 2000.0


def _validate_spot_sensor(state: Any) -> str | None:
    """Sjekk at sensoren ser ut som en pris-sensor og ikke en kr- eller kWh-sensor.

    Returnerer error-nøkkel hvis ugyldig, ellers None. Ment som første-linjes
    forsvar mot at brukere peker mot en kr-totalsensor eller en kWh-måler.
    """
    unit = (state.attributes.get("unit_of_measurement") or "").strip().lower()
    if unit:
        if unit in _INVALID_SPOT_UNITS:
            return "spot_unit_invalid"
        # øre/kWh-sensorer (ofte skrevet "ore" uten ø) tolkes av coordinator som
        # NOK/kWh og gir 100x for lav pris. Verdien alene røper det ikke, siden
        # øre-området (~-100 til 1000) er innenfor den godtatte terskelen.
        if "øre" in unit or "ore" in unit:
            return "spot_unit_invalid"
    try:
        value = float(state.state)
    except (ValueError, TypeError):
        return None
    if abs(value) > _MAX_REASONABLE_SPOT_VALUE:
        return "spot_value_unreasonable"
    return None


def _dso_options() -> list[selector.SelectOptionDict]:
    """Get sorted DSO options with Egendefinert last."""
    return [
        *sorted(
            [
                selector.SelectOptionDict(value=key, label=value["name"])
                for key, value in DSO_LIST.items()
                if value.get("supported", False) and key != "custom"
            ],
            key=lambda x: x["label"],
        ),
        selector.SelectOptionDict(value="custom", label="Egendefinert"),
    ]


def _config_data_schema(current: dict[str, Any]) -> vol.Schema:
    """Bygg konfigurasjons-skjemaet med defaults fra ``current`` (typisk entry.data).

    Delt mellom options-flowen og reconfigure-steget slik at de to inngangene
    alltid viser og validerer de samme feltene.
    """
    avgiftssone_options: list[selector.SelectOptionDict] = [
        selector.SelectOptionDict(value=key, label=label) for key, label in AVGIFTSSONE_OPTIONS.items()
    ]

    return vol.Schema(
        {
            vol.Required(
                CONF_DSO,
                default=current.get(CONF_DSO, DEFAULT_DSO),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=_dso_options(),
                    mode=selector.SelectSelectorMode.DROPDOWN,
                ),
            ),
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
            vol.Required(
                CONF_ENERGILEDD_DAG,
                default=current.get(CONF_ENERGILEDD_DAG, DEFAULT_ENERGILEDD_DAG),
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
                CONF_ENERGILEDD_NATT,
                default=current.get(CONF_ENERGILEDD_NATT, DEFAULT_ENERGILEDD_NATT),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0,
                    max=2,
                    step="any",
                    unit_of_measurement="NOK/kWh",
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


def _apply_dso_derivation(user_input: dict[str, Any], old_dso: str | None) -> None:
    """Re-avled energiledd og avgiftssone ved bytte til et kjent nettselskap.

    Skjemaets energiledd-felter defaulter til forrige DSOs lagrede verdier, så
    uten dette ville et bytte f.eks. gi BKK-energiledd med Elvia-kapasitetstrinn.
    Egendefinert DSO beholder brukerens felter (samme som ved oppsett).
    """
    new_dso = user_input.get(CONF_DSO)
    if new_dso != old_dso and new_dso != "custom" and new_dso in DSO_LIST:
        dso: DSOEntry = DSO_LIST[new_dso]
        user_input[CONF_ENERGILEDD_DAG] = dso["energiledd_dag_eks_mva"]
        user_input[CONF_ENERGILEDD_NATT] = dso["energiledd_natt_eks_mva"]
        user_input[CONF_AVGIFTSSONE] = resolve_avgiftssone(dso)


def _validate_options_input(
    hass: Any,
    user_input: dict[str, Any],
    entry_id: str,
    current_data: dict[str, Any],
) -> dict[str, str]:
    """Valider power-sensor-unikhet og at spot-sensoren ser ut som en pris.

    Delt mellom options-flowen og reconfigure-steget. Returnerer en error-dict
    (tom hvis alt er gyldig).
    """
    errors: dict[str, str] = {}

    new_power = user_input.get(CONF_POWER_SENSOR)
    if new_power and new_power != current_data.get(CONF_POWER_SENSOR):
        new_unique_id = f"{DOMAIN}_{new_power}"
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.entry_id != entry_id and entry.unique_id == new_unique_id:
                errors[CONF_POWER_SENSOR] = "already_configured"
                break

    new_spot = user_input.get(CONF_SPOT_PRICE_SENSOR)
    if new_spot:
        spot_state = hass.states.get(new_spot)
        if spot_state is None:
            errors[CONF_SPOT_PRICE_SENSOR] = "sensor_not_found"
        else:
            spot_error = _validate_spot_sensor(spot_state)
            if spot_error:
                errors[CONF_SPOT_PRICE_SENSOR] = spot_error

    return errors


class NettleieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for Nettleie."""

    # VERSION 3: spotpris_inkl_mva-felt lagt til. Default False (eks. mva, riktig
    # for HA-core nordpool). Eksisterende konfig migreres til True for å bevare
    # gjeldende oppførsel. Se incident 004.
    VERSION: int = 3

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
            # Validate sensors exist
            power_sensor: Any = user_input[CONF_POWER_SENSOR]
            spot_sensor: Any = user_input[CONF_SPOT_PRICE_SENSOR]

            power_state: Any = self.hass.states.get(power_sensor)
            spot_state: Any = self.hass.states.get(spot_sensor)

            if power_state is None:
                errors[CONF_POWER_SENSOR] = "sensor_not_found"
            if spot_state is None:
                errors[CONF_SPOT_PRICE_SENSOR] = "sensor_not_found"
            else:
                spot_error = _validate_spot_sensor(spot_state)
                if spot_error:
                    errors[CONF_SPOT_PRICE_SENSOR] = spot_error

            # Check if this power sensor is already used by another instance
            if not errors:
                unique_id = f"{DOMAIN}_{power_sensor}"
                for entry in self._async_current_entries():
                    if entry.unique_id == unique_id:
                        errors[CONF_POWER_SENSOR] = "already_configured"
                        break

            if not errors:
                self._data.update(user_input)

                # If custom DSO, go to pricing step (includes avgiftssone)
                if self._data.get(CONF_DSO) == "custom":
                    return await self.async_step_pricing()

                # Auto-detect avgiftssone from DSO
                dso: DSOEntry = DSO_LIST[self._data[CONF_DSO]]
                self._data[CONF_AVGIFTSSONE] = resolve_avgiftssone(dso)

                # Lagre eks-mva-verdier; brukeren kan overstyre dem via Options.
                self._data[CONF_ENERGILEDD_DAG] = dso["energiledd_dag_eks_mva"]
                self._data[CONF_ENERGILEDD_NATT] = dso["energiledd_natt_eks_mva"]

                return await self._create_entry()

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

    async def async_step_pricing(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the pricing step for custom grid company."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self._create_entry()

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
                    vol.Required(CONF_ENERGILEDD_DAG, default=DEFAULT_ENERGILEDD_DAG): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=2,
                            step="any",
                            unit_of_measurement="NOK/kWh",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Required(CONF_ENERGILEDD_NATT, default=DEFAULT_ENERGILEDD_NATT): selector.NumberSelector(
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

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        await self.async_set_unique_id(f"{DOMAIN}_{self._data[CONF_POWER_SENSOR]}")
        self._abort_if_unique_id_configured()

        dso_name: str = DSO_LIST[self._data[CONF_DSO]]["name"]
        title: str = f"{DEFAULT_NAME} ({dso_name})"

        return self.async_create_entry(
            title=title,
            data=self._data,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure an existing entry via the standard HA entry menu.

        Reuses the same schema, validation and DSO-derivation as the options
        flow. Unlike the options flow (which writes to entry.data via
        async_update_entry), this persists via async_update_reload_and_abort,
        the idiomatic reconfigure API, and keeps unique_id consistent with the
        stored power sensor.
        """
        entry: config_entries.ConfigEntry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = _validate_options_input(
                self.hass, user_input, entry.entry_id, entry.data
            )
            if not errors:
                _apply_dso_derivation(user_input, entry.data.get(CONF_DSO))
                new_data: dict[str, Any] = {**entry.data, **user_input}
                return self.async_update_reload_and_abort(
                    entry,
                    data=new_data,
                    unique_id=f"{DOMAIN}_{new_data[CONF_POWER_SENSOR]}",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_config_data_schema(entry.data),
            errors=errors,
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
            errors = _validate_options_input(
                self.hass, user_input, self.config_entry.entry_id, current
            )
            if not errors:
                _apply_dso_derivation(user_input, current.get(CONF_DSO))

                new_data: dict[str, Any] = {**current, **user_input}
                update_kwargs: dict[str, Any] = {"data": new_data}
                # Hold unique_id i takt med power-sensoren. Uten dette blir den
                # hengende igjen på gammel sensor og duplikatvernet blokkerer
                # feil entry senere. Se _create_entry for skjemaet.
                new_power = new_data.get(CONF_POWER_SENSOR)
                if new_power and new_power != current.get(CONF_POWER_SENSOR):
                    update_kwargs["unique_id"] = f"{DOMAIN}_{new_power}"

                self.hass.config_entries.async_update_entry(self.config_entry, **update_kwargs)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=_config_data_schema(current),
            errors=errors,
        )
