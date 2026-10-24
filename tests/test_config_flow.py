"""Tests for the RavitBornes config flow."""

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravitbornes.const import DOMAIN

FAKE_KEY = "test-api-key-not-real"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    """The user step shows a form, then stores the API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: FAKE_KEY}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RavitBornes"
    assert result["data"] == {CONF_API_KEY: FAKE_KEY}


async def test_single_instance(hass: HomeAssistant) -> None:
    """A second setup is refused."""
    MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: FAKE_KEY}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
