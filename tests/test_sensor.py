"""End-to-end tests: car position -> TomTom -> station sensors."""

import logging

import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.api import BASE_URL
from custom_components.ravitbornes.const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITY,
    CONF_PROFILE,
    DOMAIN,
)

from .conftest import load_json_fixture

TRACKER = "device_tracker.test_phone"
NEARBY_URL = f"{BASE_URL}/nearbySearch/.json"
AVAILABILITY_URL = f"{BASE_URL}/chargingAvailability.json"
PARK_A = "00000000-0000-4000-8000-000000000001"
SLOW = "00000000-0000-4000-8000-000000000004"
OPTIONS = {
    CONF_POSITION_ENTITY: TRACKER,
    CONF_CONNECTORS: ["type2_outlet"],
    CONF_PROFILE: "visit",
}
STATION_1 = "sensor.ravitbornes_station_1"
STATION_2 = "sensor.ravitbornes_station_2"
STATION_3 = "sensor.ravitbornes_station_3"


def _set_position(hass: HomeAssistant, lat: float, lon: float, state: str = "not_home") -> None:
    hass.states.async_set(TRACKER, state, {ATTR_LATITUDE: lat, ATTR_LONGITUDE: lon})


def _mock_tomtom(aioclient_mock: AiohttpClientMocker, slow_status: int = 200) -> None:
    aioclient_mock.get(
        AVAILABILITY_URL,
        params={"chargingAvailability": PARK_A},
        json=load_json_fixture("charging_availability.json"),
    )
    aioclient_mock.get(
        AVAILABILITY_URL,
        params={"chargingAvailability": SLOW},
        status=slow_status,
        json=load_json_fixture("charging_availability_full.json"),
    )
    aioclient_mock.get(NEARBY_URL, json=load_json_fixture("nearby_search.json"))


def _calls(aioclient_mock: AiohttpClientMocker, path_end: str) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if call[1].path.endswith(path_end))


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "fakekey"}, options=OPTIONS)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _move(hass: HomeAssistant, lat: float, lon: float, state: str = "not_home") -> None:
    _set_position(hass, lat, lon, state)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Unload so the refresh debouncer timer does not linger."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


async def test_sensors_show_nearest_stations(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Nearest compatible stations first, with position for navigation."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)

    first = hass.states.get(STATION_1)
    assert first.state == "Example Recharge · 22 kW · 0 km · 8/12 free"
    assert first.attributes[ATTR_LATITUDE] == 45.1
    assert first.attributes[ATTR_LONGITUDE] == 4.2
    assert first.attributes["status"] == "available"

    second = hass.states.get(STATION_2)
    assert second.state == "Example Slow · 7 kW · 0.9 km · full"
    assert second.attributes["status"] == "unavailable"

    assert hass.states.get(STATION_3).state == STATE_UNKNOWN
    # One search; availability only for the two shown stations (the DC one is filtered out).
    assert _calls(aioclient_mock, "nearbySearch/.json") == 1
    assert _calls(aioclient_mock, "chargingAvailability.json") == 2
    await _unload(hass, entry)


async def test_small_moves_are_ignored_and_cache_saves_calls(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """GPS jitter triggers nothing; a real move in the same zone reuses the caches."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)

    await _move(hass, 45.1009, 4.2)  # ~100 m
    assert hass.states.get(STATION_1).state.endswith("· 0 km · 8/12 free")

    await _move(hass, 45.1027, 4.2)  # ~300 m, same rounded zone
    assert " · 0.3 km · " in hass.states.get(STATION_1).state
    assert _calls(aioclient_mock, "nearbySearch/.json") == 1
    assert _calls(aioclient_mock, "chargingAvailability.json") == 2
    await _unload(hass, entry)


async def test_new_zone_triggers_a_new_search(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Driving into another zone searches again."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)

    await _move(hass, 45.13, 4.25)  # ~4 km away: no compatible station within 2 km

    assert _calls(aioclient_mock, "nearbySearch/.json") == 2
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_nothing_is_looked_up_at_home(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """At home: no call to TomTom, and the list is cleared when coming back."""
    _set_position(hass, 45.1, 4.2, state="home")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)
    assert aioclient_mock.call_count == 0
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN

    await _move(hass, 45.1, 4.2)  # leaving home
    assert hass.states.get(STATION_1).state != STATE_UNKNOWN

    await _move(hass, 45.1, 4.2, state="home")
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_quota_on_availability_keeps_partial_results(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A 429 on availability degrades to "unknown" instead of failing everything."""
    caplog.set_level(logging.WARNING)
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock, slow_status=429)
    entry = await _setup(hass)

    assert hass.states.get(STATION_1).attributes["status"] == "available"
    second = hass.states.get(STATION_2)
    assert second.attributes["status"] == "unknown"
    assert second.state.endswith("· availability ?")
    assert "quota" in caplog.text
    await _unload(hass, entry)


async def test_rejected_key_retries_setup(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """If TomTom rejects the key, setup is retried later instead of crashing."""
    _set_position(hass, 45.1, 4.2)
    aioclient_mock.get(NEARBY_URL, status=403)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "fakekey"}, options=OPTIONS)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
