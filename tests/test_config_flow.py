"""Tests for the RavitBornes config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.api import BASE_URL
from custom_components.ravitbornes.const import DOMAIN

FAKE_KEY = "test-api-key-not-real"
NEARBY_URL = f"{BASE_URL}/nearbySearch/.json"


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The user step shows a form, validates the key, then stores it."""
    aioclient_mock.get(NEARBY_URL, json={"summary": {}, "results": []})

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
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("status", "error"),
    [(403, "invalid_auth"), (429, "quota_exceeded"), (503, "cannot_connect")],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: str,
) -> None:
    """A rejected key or an unavailable API keeps the form open with an error."""
    aioclient_mock.get(NEARBY_URL, status=status)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: FAKE_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


async def test_single_instance(hass: HomeAssistant) -> None:
    """A second setup is refused."""
    MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: FAKE_KEY}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"
