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
    CONF_AVGIFTSSONE,
    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
    CONF_ENERGILEDD_DAG,
    CONF_ENERGILEDD_NATT,
    CONF_POWER_SENSOR,
    CONF_SPOT_PRICE_SENSOR,
    CONF_TSO,
    DEFAULT_ENERGILEDD_DAG,
    DEFAULT_ENERGILEDD_NATT,
    DEFAULT_NAME,
    DEFAULT_TSO,
    DOMAIN,
    TSO_LIST,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_LOGGER = logging.getLogger(__name__)


def _get_tso_options() -> dict[str, str]:
    """Get TSO options for selector (only supported ones)."""
    return {key: value["name"] for key, value in TSO_LIST.items() if value.get("supported", False)}


class NettleieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nettleie."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - select TSO and avgiftssone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_sensors()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TSO, default=DEFAULT_TSO
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=value["name"])
                                for key, value in TSO_LIST.items()
                                if value.get("supported", False)
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        CONF_AVGIFTSSONE, default=AVGIFTSSONE_STANDARD
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(value=key, label=label)
                                for key, label in AVGIFTSSONE_OPTIONS.items()
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the sensors step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate sensors exist
            power_sensor = user_input[CONF_POWER_SENSOR]
            spot_sensor = user_input[CONF_SPOT_PRICE_SENSOR]

            power_state = self.hass.states.get(power_sensor)
            spot_state = self.hass.states.get(spot_sensor)

            if power_state is None:
                errors[CONF_POWER_SENSOR] = "sensor_not_found"
            if spot_state is None:
                errors[CONF_SPOT_PRICE_SENSOR] = "sensor_not_found"

            if not errors:
                self._data.update(user_input)

                # If custom TSO, go to pricing step
                if self._data.get(CONF_TSO) == "custom":
                    return await self.async_step_pricing()

                # Otherwise, use defaults from TSO
                tso = TSO_LIST[self._data[CONF_TSO]]
                self._data[CONF_ENERGILEDD_DAG] = tso["energiledd_dag"]
                self._data[CONF_ENERGILEDD_NATT] = tso["energiledd_natt"]

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
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                    vol.Optional(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor"),
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_pricing(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the pricing step for custom grid company."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self._create_entry()

        return self.async_show_form(
            step_id="pricing",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ENERGILEDD_DAG, default=DEFAULT_ENERGILEDD_DAG
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0,
                            max=2,
                            step=0.0001,
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
                            step=0.0001,
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

        tso_name = TSO_LIST[self._data[CONF_TSO]]["name"]
        title = f"{DEFAULT_NAME} ({tso_name})"

        return self.async_create_entry(
            title=title,
            data=self._data,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return NettleieOptionsFlow()


class NettleieOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Nettleie."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update config entry data
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        # Get current values from config entry
        current = self.config_entry.data
        tso_options = [
            selector.SelectOptionDict(value=key, label=value["name"])
            for key, value in TSO_LIST.items()
            if value.get("supported", False)
        ]
        avgiftssone_options = [
            selector.SelectOptionDict(value=key, label=label)
            for key, label in AVGIFTSSONE_OPTIONS.items()
        ]

        # Build schema with defaults from current config
        options_schema = vol.Schema(
            {
                vol.Required(
                    CONF_TSO,
                    default=current.get(CONF_TSO, DEFAULT_TSO),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=tso_options,
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
                vol.Required(
                    CONF_POWER_SENSOR,
                    default=current.get(CONF_POWER_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Required(
                    CONF_SPOT_PRICE_SENSOR,
                    default=current.get(CONF_SPOT_PRICE_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Optional(
                    CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR,
                    description={"suggested_value": current.get(CONF_ELECTRICITY_PROVIDER_PRICE_SENSOR)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor"),
                ),
                vol.Required(
                    CONF_ENERGILEDD_DAG,
                    default=current.get(CONF_ENERGILEDD_DAG, DEFAULT_ENERGILEDD_DAG),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=2,
                    ),
                ),
                vol.Required(
                    CONF_ENERGILEDD_NATT,
                    default=current.get(CONF_ENERGILEDD_NATT, DEFAULT_ENERGILEDD_NATT),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0,
                        max=2,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
