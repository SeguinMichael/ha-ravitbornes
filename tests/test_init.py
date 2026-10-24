"""Tests for setting up and unloading RavitBornes."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITY,
    CONF_PROFILE,
    DOMAIN,
    STATION_SLOTS,
)


async def test_setup_and_unload(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The entry loads (no position yet: no call) and unloads cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "test-api-key-not-real"},
        options={
            CONF_POSITION_ENTITY: "device_tracker.not_there_yet",
            CONF_CONNECTORS: ["ccs2"],
            CONF_PROFILE: "highway",
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert aioclient_mock.call_count == 0
    assert len(hass.states.async_entity_ids("sensor")) == STATION_SLOTS

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
