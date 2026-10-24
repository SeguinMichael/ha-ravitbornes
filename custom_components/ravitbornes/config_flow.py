"""Config flow for the RavitBornes integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import TomTomAuthError, TomTomClient, TomTomError, TomTomQuotaError
from .const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITY,
    CONF_PROFILE,
    CONNECTORS,
    DEFAULT_CONNECTORS,
    DEFAULT_PROFILE,
    DOMAIN,
)
from .scoring import PROFILES

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


def _settings_schema(defaults: Mapping[str, Any]) -> vol.Schema:
    """Vehicle and position settings, shared by the config and options flows."""
    return vol.Schema(
        {
            vol.Required(
                CONF_POSITION_ENTITY,
                description={"suggested_value": defaults.get(CONF_POSITION_ENTITY)},
            ): EntitySelector(EntitySelectorConfig(domain=["device_tracker", "person"])),
            vol.Required(
                CONF_CONNECTORS,
                default=list(defaults.get(CONF_CONNECTORS, DEFAULT_CONNECTORS)),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=list(CONNECTORS),
                    multiple=True,
                    translation_key=CONF_CONNECTORS,
                )
            ),
            vol.Required(
                CONF_PROFILE, default=defaults.get(CONF_PROFILE, DEFAULT_PROFILE)
            ): SelectSelector(
                SelectSelectorConfig(options=list(PROFILES), translation_key=CONF_PROFILE)
            ),
        }
    )


def _validate_settings(user_input: Mapping[str, Any]) -> dict[str, str]:
    """At least one connector is needed, otherwise nothing can ever match."""
    if not user_input.get(CONF_CONNECTORS):
        return {CONF_CONNECTORS: "no_connector"}
    return {}


class RavitBornesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Ask for the user's own TomTom API key, then for the vehicle settings."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._api_key = ""

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> RavitBornesOptionsFlow:
        """Vehicle settings can be changed later."""
        return RavitBornesOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the API key step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = TomTomClient(
                async_get_clientsession(self.hass), user_input[CONF_API_KEY]
            )
            try:
                await client.validate_key()
            except TomTomAuthError:
                errors["base"] = "invalid_auth"
            except TomTomQuotaError:
                errors["base"] = "quota_exceeded"
            except TomTomError:
                errors["base"] = "cannot_connect"
            else:
                self._api_key = user_input[CONF_API_KEY]
                return await self.async_step_settings()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the vehicle and position step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_settings(user_input)
            if not errors:
                return self.async_create_entry(
                    title="RavitBornes",
                    data={CONF_API_KEY: self._api_key},
                    options=user_input,
                )

        return self.async_show_form(
            step_id="settings",
            data_schema=_settings_schema(user_input or {}),
            errors=errors,
        )


class RavitBornesOptionsFlow(OptionsFlow):
    """Change the vehicle and position settings."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the settings form, prefilled with the current options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_settings(user_input)
            if not errors:
                return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_settings_schema(user_input or self.config_entry.options),
            errors=errors,
        )
