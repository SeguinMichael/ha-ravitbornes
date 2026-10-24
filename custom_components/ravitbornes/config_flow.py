"""Config flow for the RavitBornes integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
        if user_input is not None:
            # The key is not validated against TomTom yet (see docs/WIP.md, chantier 3).
            return self.async_create_entry(
                title="RavitBornes",
                data={CONF_API_KEY: user_input[CONF_API_KEY]},
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)
