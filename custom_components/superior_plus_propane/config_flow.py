"""Adds config flow for Superior Plus Propane."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    SuperiorPlusPropaneApiClient,
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientCommunicationError,
    SuperiorPlusPropaneApiClientError,
)
from .const import (
    CONF_ADAPTIVE_THRESHOLDS,
    CONF_MAX_THRESHOLD,
    CONF_MIN_THRESHOLD,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DEFAULT_MAX_CONSUMPTION_GALLONS,
    DEFAULT_MIN_CONSUMPTION_GALLONS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
)


class SuperiorPlusPropaneFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Superior Plus Propane."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    region=user_input.get(CONF_REGION, "US"),
                )
            except SuperiorPlusPropaneApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except SuperiorPlusPropaneApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except SuperiorPlusPropaneApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(slugify(user_input[CONF_USERNAME]))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Superior Plus Propane ({user_input[CONF_USERNAME]})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_REGION,
                        default=(user_input or {}).get(CONF_REGION, "US"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["US", "CA"],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        CONF_USERNAME,
                        default=(user_input or {}).get(CONF_USERNAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=DEFAULT_UPDATE_INTERVAL,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=300,  # Minimum 5 minutes
                            max=86400,  # Maximum 24 hours
                            step=300,  # 5 minute steps
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_ADAPTIVE_THRESHOLDS,
                        default=True,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_MIN_THRESHOLD,
                        default=DEFAULT_MIN_CONSUMPTION_GALLONS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=5.0,
                            step=0.01,
                            unit_of_measurement="gallons",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_THRESHOLD,
                        default=DEFAULT_MAX_CONSUMPTION_GALLONS,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.0,
                            max=100.0,
                            step=1.0,
                            unit_of_measurement="gallons",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(
        self, username: str, password: str, region: str = "US"
    ) -> None:
        """Validate credentials."""
        client = SuperiorPlusPropaneApiClient(
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
            region=region,
        )
        await client.async_test_connection()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SuperiorPlusPropaneOptionsFlowHandler(config_entry)


class SuperiorPlusPropaneOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Superior Plus Propane."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Validate threshold values
            min_threshold = user_input.get(CONF_MIN_THRESHOLD)
            max_threshold = user_input.get(CONF_MAX_THRESHOLD)
            if min_threshold is not None and max_threshold is not None:
                if min_threshold >= max_threshold:
                    return self.async_show_form(
                        step_id="init",
                        data_schema=self._get_options_schema(),
                        errors={"base": "invalid_thresholds"},
                    )

            # Update config entry with new options - these settings need a reload to take effect
            data = dict(self.config_entry.data)
            data.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=data
            )
            # Reload the config entry to apply new settings
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self) -> vol.Schema:
        """Get the options schema with current values."""
        current_interval = self.config_entry.data.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        )
        current_adaptive = self.config_entry.data.get(
            CONF_ADAPTIVE_THRESHOLDS, True
        )
        current_min = self.config_entry.data.get(
            CONF_MIN_THRESHOLD, DEFAULT_MIN_CONSUMPTION_GALLONS
        )
        current_max = self.config_entry.data.get(
            CONF_MAX_THRESHOLD, DEFAULT_MAX_CONSUMPTION_GALLONS
        )

        return vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=current_interval,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=300,  # Minimum 5 minutes
                            max=86400,  # Maximum 24 hours
                            step=300,  # 5 minute steps
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_ADAPTIVE_THRESHOLDS,
                        default=current_adaptive,
                        description={"suggested_value": current_adaptive},
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_MIN_THRESHOLD,
                        default=current_min,
                        description={
                            "suggested_value": current_min,
                            "suffix": "Only used when adaptive thresholds are disabled",
                        },
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=5.0,
                            step=0.01,
                            unit_of_measurement="gallons",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_THRESHOLD,
                        default=current_max,
                        description={
                            "suggested_value": current_max,
                            "suffix": "Only used when adaptive thresholds are disabled",
                        },
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.0,
                            max=100.0,
                            step=1.0,
                            unit_of_measurement="gallons",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                }
            )
