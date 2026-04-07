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
    AVGIFTSSONE_TILTAKSSONE,
    BOLIGTYPE_BOLIG,
    BOLIGTYPE_OPTIONS,
    CONF_AVGIFTSSONE,
    CONF_BOLIGTYPE,
    CONF_DSO,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_EXPORT_POWER_SENSOR,
    CONF_HAR_NORGESPRIS,
    CONF_KAPASITET_VARSEL_TERSKEL,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    DEFAULT_DSO,
    DEFAULT_ENERGILEDD_DAG,
    DEFAULT_ENERGILEDD_NATT,
    DEFAULT_KAPASITET_VARSEL_TERSKEL,
    DEFAULT_NAME,
    DOMAIN,
    DSO_LIST,
    get_default_avgiftssone,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

    from .dso import DSOEntry

_LOGGER: logging.Logger = logging.getLogger(__name__)


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


class NettleieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg,misc]
    """Handle a config flow for Nettleie."""

    VERSION: int = 1

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
                if dso.get("tiltakssone"):
                    self._data[CONF_AVGIFTSSONE] = AVGIFTSSONE_TILTAKSSONE
                else:
                    self._data[CONF_AVGIFTSSONE] = get_default_avgiftssone(dso["prisomrade"])

                self._data[CONF_ENERGILEDD_DAG] = dso["energiledd_dag"]
                self._data[CONF_ENERGILEDD_NATT] = dso["energiledd_natt"]

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
                            device_class="monetary",
                        ),
                    ),
                    vol.Optional(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            device_class="monetary",
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

    @staticmethod
    @callback  # type: ignore[untyped-decorator]
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> NettleieOptionsFlow:
        """Create the options flow."""
        return NettleieOptionsFlow()


class NettleieOptionsFlow(config_entries.OptionsFlow):  # type: ignore[misc]
    """Handle options flow for Nettleie."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        # Get current values from config entry
        current: dict[str, Any] = self.config_entry.data
        avgiftssone_options: list[selector.SelectOptionDict] = [
            selector.SelectOptionDict(value=key, label=label) for key, label in AVGIFTSSONE_OPTIONS.items()
        ]

        # Build schema with defaults from current config
        options_schema: vol.Schema = vol.Schema(
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
                        device_class="monetary",
                    ),
                ),
                vol.Optional(
                    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
                    description={"suggested_value": current.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor",
                        device_class="monetary",
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

        if user_input is not None:
            # Validate power sensor uniqueness
            new_power = user_input.get(CONF_POWER_SENSOR)
            if new_power and new_power != self.config_entry.data.get(CONF_POWER_SENSOR):
                new_unique_id = f"{DOMAIN}_{new_power}"
                for entry in self.hass.config_entries.async_entries(DOMAIN):
                    if entry.entry_id != self.config_entry.entry_id and entry.unique_id == new_unique_id:
                        errors[CONF_POWER_SENSOR] = "already_configured"
                        break

            if not errors:
                # Update config entry data
                new_data: dict[str, Any] = {**self.config_entry.data, **user_input}
                self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )
