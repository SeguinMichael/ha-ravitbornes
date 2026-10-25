"""Tests for the RavitBornes config and options flows."""

import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.api import BASE_URL
from custom_components.ravitbornes.const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITIES,
    CONF_PROFILE,
    CONF_TARIFFS,
    DOMAIN,
)

FAKE_KEY = "test-api-key-not-real"
NEARBY_URL = f"{BASE_URL}/nearbySearch/.json"
SETTINGS = {
    CONF_POSITION_ENTITIES: ["device_tracker.test_phone"],
    CONF_CONNECTORS: ["ccs2", "type2_outlet"],
    CONF_PROFILE: "highway",
}


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Key step (validated), then settings step; key in data, settings in options."""
    aioclient_mock.get(NEARBY_URL, json={"summary": {}, "results": []})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: FAKE_KEY}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"
    assert aioclient_mock.call_count == 1

    result = await hass.config_entries.flow.async_configure(result["flow_id"], SETTINGS)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "RavitBornes"
    assert result["data"] == {CONF_API_KEY: FAKE_KEY}
    # Prices default to the light online lookup (decision 2026-10-25).
    assert result["options"] == {**SETTINGS, CONF_TARIFFS: "online"}


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


async def test_settings_need_a_connector(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Without any connector nothing could ever match: refused."""
    aioclient_mock.get(NEARBY_URL, json={"summary": {}, "results": []})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: FAKE_KEY}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SETTINGS, CONF_CONNECTORS: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_CONNECTORS: "no_connector"}


async def test_single_instance(hass: HomeAssistant) -> None:
    """A second setup is refused."""
    MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: FAKE_KEY}).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_options_flow_changes_settings(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Settings can be changed later; the entry reloads with them."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: FAKE_KEY}, options=SETTINGS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    new_settings = {**SETTINGS, CONF_PROFILE: "visit", CONF_TARIFFS: "off"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], new_settings
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == new_settings
    assert aioclient_mock.call_count == 0  # no position known yet: no lookup

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_reauth_replaces_the_key(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected new key is refused; a valid one replaces the stored key."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "revoked-key"}, options={**SETTINGS, CONF_TARIFFS: "off"}
    )
    entry.add_to_hass(hass)
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    aioclient_mock.get(NEARBY_URL, status=403)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "still-wrong"}
    )
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(NEARBY_URL, json={"summary": {}, "results": []})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: FAKE_KEY}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {CONF_API_KEY: FAKE_KEY}
    assert entry.options == {**SETTINGS, CONF_TARIFFS: "off"}  # settings kept

