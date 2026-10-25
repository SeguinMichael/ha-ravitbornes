"""Tests for the TomTom client: privacy guarantees and error mapping."""

import logging

import aiohttp
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.api import (
    BASE_URL,
    TomTomAuthError,
    TomTomClient,
    TomTomConnectionError,
    TomTomQuotaError,
)

from .conftest import load_json_fixture

API_KEY = "fakekey-fakekey-fakekey"  # low entropy: not flagged by gitleaks
NEARBY_URL = f"{BASE_URL}/nearbySearch/.json"
AVAILABILITY_URL = f"{BASE_URL}/chargingAvailability.json"


async def test_position_is_rounded_before_the_call(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """TomTom receives a coarse area, never the exact position."""
    aioclient_mock.get(NEARBY_URL, json=load_json_fixture("nearby_search.json"))
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    stations = await client.nearby_stations(45.123456, 4.987654, radius_m=5000)

    assert len(stations) == 4
    _, url, _, _ = aioclient_mock.mock_calls[0]
    assert url.query["lat"] == "45.12"
    assert url.query["lon"] == "4.99"
    assert url.query["categorySet"] == "7309"


async def test_charging_availability(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The availability id is passed through and the response parsed."""
    aioclient_mock.get(
        AVAILABILITY_URL, json=load_json_fixture("charging_availability.json")
    )
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    levels = await client.charging_availability("00000000-0000-4000-8000-000000000001")

    assert sum(level.available for level in levels) == 9
    _, url, _, _ = aioclient_mock.mock_calls[0]
    assert url.query["chargingAvailability"] == "00000000-0000-4000-8000-000000000001"


@pytest.mark.parametrize(
    ("status", "error"),
    [
        (401, TomTomAuthError),
        (403, TomTomAuthError),
        (429, TomTomQuotaError),
        (500, TomTomConnectionError),
    ],
)
async def test_http_errors_are_mapped(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    error: type[Exception],
) -> None:
    """HTTP failures become typed errors."""
    aioclient_mock.get(NEARBY_URL, status=status)
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    with pytest.raises(error):
        await client.validate_key()


async def test_api_key_never_leaks(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The key appears neither in logs nor in raised errors, success or failure."""
    caplog.set_level(logging.DEBUG, logger="custom_components.ravitbornes")
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    aioclient_mock.get(NEARBY_URL, json=load_json_fixture("nearby_search.json"))
    await client.nearby_stations(45.1, 4.2, radius_m=5000)

    aioclient_mock.clear_requests()
    aioclient_mock.get(NEARBY_URL, exc=aiohttp.ClientError(f"boom {NEARBY_URL}?key={API_KEY}"))
    with pytest.raises(TomTomConnectionError) as excinfo:
        await client.validate_key()

    assert API_KEY not in caplog.text
    assert API_KEY not in str(excinfo.value)
    # The original aiohttp error (which may embed the URL) is not chained.
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__
    assert "nearbySearch" in caplog.text  # calls are still journaled


async def test_timeout_is_a_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A timeout is reported as a connection problem."""
    aioclient_mock.get(NEARBY_URL, exc=TimeoutError())
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    with pytest.raises(TomTomConnectionError):
        await client.validate_key()


async def test_connector_and_power_filters_are_sent_to_tomtom(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """TomTom filters server-side, so the result limit is spent on usable stations."""
    aioclient_mock.get(NEARBY_URL, json=load_json_fixture("nearby_search.json"))
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    await client.nearby_stations(
        45.1,
        4.2,
        radius_m=6000,
        connector_types={"IEC62196Type2CCS", "Chademo"},
        min_power_kw=50.0,
    )

    _, url, _, _ = aioclient_mock.mock_calls[0]
    assert url.query["connectorSet"] == "Chademo,IEC62196Type2CCS"
    assert url.query["minPowerKW"] == "50.0"


async def test_no_power_filter_when_profile_has_no_floor(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    aioclient_mock.get(NEARBY_URL, json=load_json_fixture("nearby_search.json"))
    client = TomTomClient(async_get_clientsession(hass), API_KEY)

    await client.nearby_stations(45.1, 4.2, radius_m=3000, connector_types={"IEC62196Type2Outlet"})

    _, url, _, _ = aioclient_mock.mock_calls[0]
    assert url.query["connectorSet"] == "IEC62196Type2Outlet"
    assert "minPowerKW" not in url.query
