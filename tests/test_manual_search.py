"""The "Search stations (30 min)" button, and no timer outside trips."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.const import CONF_TRIP_ENTITY

from .test_sensor import STATION_1, _calls, _mock_tomtom, _set_position, _unload
from .test_trip_and_exclusions import AA, AVAILABILITY, NEARBY, _settle, _setup

SEARCH_BUTTON = "button.ravitbornes_search_stations_30_min"


async def _press_search(hass: HomeAssistant) -> None:
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: SEARCH_BUTTON}, blocking=True
    )
    await _settle(hass)


async def _wait(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: float) -> None:
    freezer.tick(timedelta(minutes=minutes))
    async_fire_time_changed(hass)
    await _settle(hass)


def _counts(aioclient_mock: AiohttpClientMocker) -> tuple[int, int]:
    return _calls(aioclient_mock, NEARBY), _calls(aioclient_mock, AVAILABILITY)


async def test_no_timer_without_trip_entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Regression: without a trip entity, a stopped car must not poll TomTom."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)
    assert _counts(aioclient_mock) == (1, 2)

    await _wait(hass, freezer, 30)

    assert _counts(aioclient_mock) == (1, 2)
    await _unload(hass, entry)


async def test_search_button_works_at_home_and_outside_a_trip(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Trip off and at home: the button still searches, every 3 min, for 30 min."""
    _set_position(hass, 45.1, 4.2, state="home")
    hass.states.async_set(AA, "off")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})
    assert aioclient_mock.call_count == 0

    await _press_search(hass)
    assert hass.states.get(STATION_1).attributes["status"] == "available"
    assert _counts(aioclient_mock) == (1, 2)

    await _wait(hass, freezer, 181 / 60)
    assert _counts(aioclient_mock) == (1, 4)  # availability refreshed while stopped

    await _wait(hass, freezer, 28)
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN  # window over: cleared
    calls = aioclient_mock.call_count
    await _wait(hass, freezer, 30)
    assert aioclient_mock.call_count == calls
    await _unload(hass, entry)


async def test_search_button_without_trip_entity(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Without a trip entity too, the button overrides the home rule for 30 min."""
    _set_position(hass, 45.1, 4.2, state="home")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)
    assert aioclient_mock.call_count == 0

    await _press_search(hass)
    assert hass.states.get(STATION_1).state != STATE_UNKNOWN

    await _wait(hass, freezer, 31)
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_list_is_cleared_as_soon_as_the_window_ends(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """At the 30-min deadline the list goes away at once, not at the next 3-min tick."""
    _set_position(hass, 45.1, 4.2)
    hass.states.async_set(AA, "off")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})
    await _press_search(hass)

    await _wait(hass, freezer, 29)  # last refresh now: next one due at ~32 min
    assert hass.states.get(STATION_1).state != STATE_UNKNOWN
    await _wait(hass, freezer, 1.5)  # 30.5 min: deadline passed, no refresh due yet

    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_pressing_again_restarts_the_30_minutes(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second press extends the window instead of ending at the first deadline."""
    _set_position(hass, 45.1, 4.2)
    hass.states.async_set(AA, "off")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})

    await _press_search(hass)
    await _wait(hass, freezer, 20)
    await _press_search(hass)

    await _wait(hass, freezer, 15)  # 35 min after the first press
    assert hass.states.get(STATION_1).state != STATE_UNKNOWN

    await _wait(hass, freezer, 20)  # 35 min after the second press
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_trip_end_does_not_cut_a_manual_search(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Android Auto disconnecting during a manual search keeps the list."""
    _set_position(hass, 45.1, 4.2)
    hass.states.async_set(AA, "on")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})
    await _press_search(hass)

    hass.states.async_set(AA, "off")
    await _settle(hass)

    assert hass.states.get(STATION_1).state != STATE_UNKNOWN
    await _unload(hass, entry)
