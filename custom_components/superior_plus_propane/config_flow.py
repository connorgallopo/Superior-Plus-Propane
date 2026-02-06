"""Adds config flow for Superior Plus Propane."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from slugify import slugify

from .api import (
    SuperiorPlusPropaneApiClientAuthenticationError,
    SuperiorPlusPropaneApiClientCommunicationError,
    SuperiorPlusPropaneApiClientError,
    create_api_client,
)
from .const import (
    CONF_ADAPTIVE_THRESHOLDS,
    CONF_INCLUDE_UNMONITORED,
    CONF_MAX_THRESHOLD,
    CONF_MIN_THRESHOLD,
    CONF_REGION,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    LOGGER,
)
from .region import get_region_config


class SuperiorPlusPropaneFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Superior Plus Propane."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the flow."""
        self._region: str = "us"

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Region selection."""
        if user_input is not None:
            self._region = user_input.get(CONF_REGION, "us")
            return await self.async_step_credentials()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_REGION, default="us"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value="us", label="United States"
                                ),
                                selector.SelectOptionDict(value="ca", label="Canada"),
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
        )

    async def async_step_credentials(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Credentials and options."""
        region_config = get_region_config(self._region)
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                await self._test_credentials(
                    region=self._region,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except SuperiorPlusPropaneApiClientAuthenticationError as exc:
                LOGGER.warning(exc)
                errors["base"] = "auth"
            except SuperiorPlusPropaneApiClientCommunicationError as exc:
                LOGGER.error(exc)
                errors["base"] = "connection"
            except SuperiorPlusPropaneApiClientError as exc:
                LOGGER.exception(exc)
                errors["base"] = "unknown"
            else:
                min_val = user_input.get(CONF_MIN_THRESHOLD)
                max_val = user_input.get(CONF_MAX_THRESHOLD)
                if min_val is not None and max_val is not None and min_val >= max_val:
                    errors["base"] = "invalid_thresholds"
                else:
                    await self.async_set_unique_id(slugify(user_input[CONF_USERNAME]))
                    self._abort_if_unique_id_configured()

                    title = (
                        f"Superior Plus Propane ({user_input[CONF_USERNAME]})"
                        if self._region == "us"
                        else f"Superior Propane ({user_input[CONF_USERNAME]})"
                    )

                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_REGION: self._region,
                            CONF_USERNAME: user_input[CONF_USERNAME],
                            CONF_PASSWORD: user_input[CONF_PASSWORD],
                            CONF_UPDATE_INTERVAL: user_input.get(
                                CONF_UPDATE_INTERVAL,
                                region_config.default_update_interval,
                            ),
                            CONF_INCLUDE_UNMONITORED: user_input.get(
                                CONF_INCLUDE_UNMONITORED, False
                            ),
                            CONF_ADAPTIVE_THRESHOLDS: user_input.get(
                                CONF_ADAPTIVE_THRESHOLDS, True
                            ),
                            CONF_MIN_THRESHOLD: user_input.get(
                                CONF_MIN_THRESHOLD,
                                region_config.default_min_threshold,
                            ),
                            CONF_MAX_THRESHOLD: user_input.get(
                                CONF_MAX_THRESHOLD,
                                region_config.default_max_threshold,
                            ),
                        },
                    )

        volume_unit = region_config.volume_unit

        return self.async_show_form(
            step_id="credentials",
            data_schema=vol.Schema(
                {
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
                        default=region_config.default_update_interval,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=300,
                            max=86400,
                            step=300,
                            unit_of_measurement="seconds",
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_INCLUDE_UNMONITORED,
                        default=False,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_ADAPTIVE_THRESHOLDS,
                        default=True,
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        CONF_MIN_THRESHOLD,
                        default=region_config.default_min_threshold,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.01,
                            max=5.0,
                            step=0.01,
                            unit_of_measurement=volume_unit,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                    vol.Optional(
                        CONF_MAX_THRESHOLD,
                        default=region_config.default_max_threshold,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1.0,
                            max=100.0,
                            step=1.0,
                            unit_of_measurement=volume_unit,
                            mode=selector.NumberSelectorMode.BOX,
                        ),
                    ),
                },
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication trigger."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle re-authentication credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            reauth_entry = self._get_reauth_entry()
            region = reauth_entry.data.get(CONF_REGION, "us")
            try:
                await self._test_credentials(
                    region=region,
                    username=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                )
            except SuperiorPlusPropaneApiClientAuthenticationError:
                errors["base"] = "auth"
            except SuperiorPlusPropaneApiClientCommunicationError:
                errors["base"] = "connection"
            except SuperiorPlusPropaneApiClientError as exc:
                LOGGER.exception(exc)
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.EMAIL,
                        ),
                    ),
                    vol.Required(CONF_PASSWORD): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(
        self, region: str, username: str, password: str
    ) -> None:
        """Validate credentials using the appropriate API client."""
        region_config = get_region_config(region)
        client = create_api_client(
            region=region,
            username=username,
            password=password,
            session=async_create_clientsession(self.hass),
            region_config=region_config,
        )
        try:
            if not await client.async_test_connection():
                msg = "Connection test failed"
                raise SuperiorPlusPropaneApiClientAuthenticationError(msg)
        finally:
            await client.async_close()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,  # noqa: ARG004
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return SuperiorPlusPropaneOptionsFlowHandler()


class SuperiorPlusPropaneOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Superior Plus Propane."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            min_threshold = user_input.get(CONF_MIN_THRESHOLD)
            max_threshold = user_input.get(CONF_MAX_THRESHOLD)
            if (
                min_threshold is not None
                and max_threshold is not None
                and min_threshold >= max_threshold
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "invalid_thresholds"},
                )

            data = dict(self.config_entry.data)
            data.update(user_input)
            self.hass.config_entries.async_update_entry(self.config_entry, data=data)
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(),
        )

    def _get_options_schema(self) -> vol.Schema:
        """Get the options schema with current values."""
        region = self.config_entry.data.get(CONF_REGION, "us")
        region_config = get_region_config(region)
        volume_unit = region_config.volume_unit

        current_interval = self.config_entry.data.get(
            CONF_UPDATE_INTERVAL, region_config.default_update_interval
        )
        current_adaptive = self.config_entry.data.get(CONF_ADAPTIVE_THRESHOLDS, True)
        current_include_unmonitored = self.config_entry.data.get(
            CONF_INCLUDE_UNMONITORED, False
        )
        current_min = self.config_entry.data.get(
            CONF_MIN_THRESHOLD, region_config.default_min_threshold
        )
        current_max = self.config_entry.data.get(
            CONF_MAX_THRESHOLD, region_config.default_max_threshold
        )

        return vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=current_interval,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=300,
                        max=86400,
                        step=300,
                        unit_of_measurement="seconds",
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_INCLUDE_UNMONITORED,
                    default=current_include_unmonitored,
                ): selector.BooleanSelector(),
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
                        "suffix": ("Only used when adaptive thresholds are disabled"),
                    },
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.01,
                        max=5.0,
                        step=0.01,
                        unit_of_measurement=volume_unit,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
                vol.Optional(
                    CONF_MAX_THRESHOLD,
                    default=current_max,
                    description={
                        "suggested_value": current_max,
                        "suffix": ("Only used when adaptive thresholds are disabled"),
                    },
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=1.0,
                        max=100.0,
                        step=1.0,
                        unit_of_measurement=volume_unit,
                        mode=selector.NumberSelectorMode.BOX,
                    ),
                ),
            }
        )
