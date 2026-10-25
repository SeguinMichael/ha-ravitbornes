"""Trip-driven refresh, freshest position source, and hidden stations."""

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.const import (
    CONF_EXCLUDED,
    CONF_POSITION_ENTITIES,
    CONF_TRIP_ENTITY,
    DOMAIN,
)

from .test_sensor import (
    OPTIONS,
    STATION_1,
    STATION_2,
    TRACKER,
    _calls,
    _mock_tomtom,
    _set_position,
    _unload,
)

AA = "binary_sensor.test_phone_android_auto"
CAR = "device_tracker.test_car"
BUTTON_1 = "button.ravitbornes_hide_station_1"
AVAILABILITY = "chargingAvailability.json"
NEARBY = "nearbySearch/.json"


async def _setup(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "fakekey"}, options={**OPTIONS, **options}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _settle(hass: HomeAssistant) -> None:
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_trip_refreshes_every_3_minutes_even_when_stopped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Android Auto off: no call. On: lookup, then availability every 3 min without moving."""
    _set_position(hass, 45.1, 4.2)
    hass.states.async_set(AA, "off")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})
    assert aioclient_mock.call_count == 0

    hass.states.async_set(AA, "on")
    await _settle(hass)
    assert hass.states.get(STATION_1).attributes["status"] == "available"
    assert (_calls(aioclient_mock, NEARBY), _calls(aioclient_mock, AVAILABILITY)) == (1, 2)

    freezer.tick(timedelta(seconds=181))
    async_fire_time_changed(hass)
    await _settle(hass)
    # Same place: the station list comes from the cache, availability is fetched again.
    assert (_calls(aioclient_mock, NEARBY), _calls(aioclient_mock, AVAILABILITY)) == (1, 4)

    hass.states.async_set(AA, "off")
    await _settle(hass)
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    freezer.tick(timedelta(seconds=600))
    async_fire_time_changed(hass)
    await _settle(hass)
    assert _calls(aioclient_mock, AVAILABILITY) == 4  # nothing more after the trip
    await _unload(hass, entry)


async def test_moves_are_ignored_outside_a_trip(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """With a trip entity configured, moving while it is off looks nothing up."""
    _set_position(hass, 45.1, 4.2)
    hass.states.async_set(AA, "off")
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_TRIP_ENTITY: AA})

    _set_position(hass, 45.13, 4.25)
    await _settle(hass)

    assert aioclient_mock.call_count == 0
    await _unload(hass, entry)


async def test_freshest_position_source_wins(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Car tracker updated after the phone: the car's position is used."""
    hass.states.async_set(CAR, "not_home", {ATTR_LATITUDE: 45.13, ATTR_LONGITUDE: 4.25})
    freezer.tick(timedelta(seconds=30))
    _set_position(hass, 45.1, 4.2)  # phone, more recent
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass, **{CONF_POSITION_ENTITIES: [CAR, TRACKER]})
    assert hass.states.get(STATION_1).state.startswith("Example Recharge · 22 kW · 0 km")

    freezer.tick(timedelta(seconds=30))
    # The car has moved and reports a new position: it becomes the freshest source.
    hass.states.async_set(CAR, "not_home", {ATTR_LATITUDE: 45.131, ATTR_LONGITUDE: 4.25})
    await _settle(hass)
    # The car is now the freshest source, ~4 km away from any compatible station.
    assert hass.states.get(STATION_1).state == STATE_UNKNOWN
    await _unload(hass, entry)


async def test_hide_button_persists_and_shows_next_station(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Hiding slot 1 promotes slot 2, without any new TomTom call, and survives a reload."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)
    calls_before = aioclient_mock.call_count

    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: BUTTON_1}, blocking=True
    )
    await _settle(hass)

    assert hass.states.get(STATION_1).state.startswith("Example Slow")
    assert hass.states.get(STATION_2).state == STATE_UNKNOWN
    assert aioclient_mock.call_count == calls_before
    stored = hass_storage[f"{DOMAIN}.{entry.entry_id}.excluded"]["data"]["stations"]
    assert [s["poi_id"] for s in stored] == ["poi-example-park-a"]
    assert stored[0]["address"] == "1 Example Street, 00000 Exampleville"

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(STATION_1).state.startswith("Example Slow")
    await _unload(hass, entry)


async def test_hidden_station_is_recognized_by_position(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """If TomTom changes the id, the station is still hidden by its position."""
    hass_storage[f"{DOMAIN}.test_entry.excluded"] = {
        "version": 1,
        "key": f"{DOMAIN}.test_entry.excluded",
        "data": {
            "stations": [
                {
                    "poi_id": "old-id",
                    "name": "Example Recharge",
                    "address": "",
                    "latitude": 45.10005,
                    "longitude": 4.2,
                }
            ]
        },
    }
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN, entry_id="test_entry", data={CONF_API_KEY: "fakekey"}, options=OPTIONS
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(STATION_1).state.startswith("Example Slow")
    await _unload(hass, entry)


async def test_hide_button_unavailable_on_empty_slot(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Nothing to hide in an empty slot."""
    _set_position(hass, 45.1, 4.2, state="home")
    entry = await _setup(hass)

    assert hass.states.get(BUTTON_1).state == STATE_UNAVAILABLE
    await _unload(hass, entry)


async def test_options_show_hidden_stations_again(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Unticking a hidden station in the options shows it again."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = await _setup(hass)
    await hass.services.async_call(
        "button", "press", {ATTR_ENTITY_ID: BUTTON_1}, blocking=True
    )
    await _settle(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert CONF_EXCLUDED in result["data_schema"].schema

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**OPTIONS, CONF_EXCLUDED: []}
    )
    await _settle(hass)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert CONF_EXCLUDED not in entry.options
    assert hass_storage[f"{DOMAIN}.{entry.entry_id}.excluded"]["data"]["stations"] == []
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get(STATION_1).state.startswith("Example Recharge")
    await _unload(hass, entry)
