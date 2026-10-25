"""Diagnostics must be safe to paste into a public bug report."""

from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.api import BASE_URL
from custom_components.ravitbornes.const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITIES,
    CONF_PROFILE,
    DOMAIN,
)
from custom_components.ravitbornes.diagnostics import async_get_config_entry_diagnostics

from .conftest import load_json_fixture

API_KEY = "fakekey-diagnostics"
TRACKER = "device_tracker.someones_phone"


async def test_diagnostics_contain_no_key_and_no_position(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The API key, the tracker id and coordinates are absent."""
    hass.states.async_set(TRACKER, "not_home", {ATTR_LATITUDE: 45.1, ATTR_LONGITUDE: 4.2})
    aioclient_mock.get(
        f"{BASE_URL}/chargingAvailability.json",
        json=load_json_fixture("charging_availability.json"),
    )
    aioclient_mock.get(
        f"{BASE_URL}/nearbySearch/.json", json=load_json_fixture("nearby_search.json")
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: API_KEY},
        options={
            CONF_POSITION_ENTITIES: [TRACKER],
            CONF_CONNECTORS: ["type2_outlet"],
            CONF_PROFILE: "visit",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    text = str(diagnostics)

    assert API_KEY not in text
    assert TRACKER not in text
    assert "45.1" not in text and "4.2" not in text
    assert diagnostics["stations"] == 2
    assert diagnostics["options"][CONF_CONNECTORS] == ["type2_outlet"]

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
