""""Hide station" only while charging, when a charging entity is configured."""

from typing import Any

import pytest

from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import async_get_platforms
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.const import CONF_CHARGING_ENTITY, DOMAIN

from .test_sensor import STATION_1, _mock_tomtom, _set_position, _unload
from .test_trip_and_exclusions import BUTTON_1, _settle, _setup

CHARGING = "binary_sensor.test_car_charging"


def _button(hass: HomeAssistant, entity_id: str) -> Any:
    platform = next(p for p in async_get_platforms(hass, DOMAIN) if p.domain == "button")
    return platform.entities[entity_id]


async def test_hide_only_while_charging(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Greyed out while driving, usable as soon as charging starts."""
    hass.states.async_set(CHARGING, STATE_OFF)
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_CHARGING_ENTITY: CHARGING})
    assert hass.states.get(BUTTON_1).state == STATE_UNAVAILABLE

    with pytest.raises(HomeAssistantError):
        await _button(hass, BUTTON_1).async_press()  # e.g. a script calling it anyway
    assert hass.states.get(STATION_1).state.startswith("Example Recharge")

    hass.states.async_set(CHARGING, STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get(BUTTON_1).state != STATE_UNAVAILABLE

    await hass.services.async_call("button", "press", {ATTR_ENTITY_ID: BUTTON_1}, blocking=True)
    await _settle(hass)
    assert hass.states.get(STATION_1).state.startswith("Example Slow")
    await _unload(hass, entry)


async def test_without_charging_entity_hiding_is_always_possible(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The guard is opt-in: no charging entity, no restriction."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)

    assert hass.states.get(BUTTON_1).state != STATE_UNAVAILABLE
    await _unload(hass, entry)
