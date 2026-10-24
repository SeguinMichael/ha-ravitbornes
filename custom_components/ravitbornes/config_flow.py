"""Config flow for the RavitBornes integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import TomTomAuthError, TomTomClient, TomTomError, TomTomQuotaError
from .const import DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class RavitBornesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the setup flow: ask for the user's own TomTom API key."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
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
                return self.async_create_entry(
                    title="RavitBornes",
                    data={CONF_API_KEY: user_input[CONF_API_KEY]},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )
