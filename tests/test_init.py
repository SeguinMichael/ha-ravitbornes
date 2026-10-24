"""Tests for setting up and unloading RavitBornes."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravitbornes.const import DOMAIN


async def test_setup_and_unload(hass: HomeAssistant) -> None:
    """The entry loads and unloads cleanly."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-api-key-not-real"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
