"""Async client for the TomTom Search API (EV charging stations)."""

from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp

from .models import ConnectorAvailability, Station, parse_availability, parse_stations

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://api.tomtom.com/search/2"
EV_STATION_CATEGORY = 7309
# 2 decimals ≈ 1 km: TomTom receives an area, never the exact position.
COORD_DECIMALS = 2
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


class TomTomError(Exception):
    """Base error for TomTom calls. Messages never contain the API key."""


class TomTomAuthError(TomTomError):
    """The API key was rejected."""


class TomTomQuotaError(TomTomError):
    """The free quota or the request rate limit is exhausted (HTTP 429)."""


class TomTomConnectionError(TomTomError):
    """TomTom could not be reached or answered unexpectedly."""


def round_position(latitude: float, longitude: float) -> tuple[float, float]:
    """Coarsen a position before sending it to an external API."""
    return round(latitude, COORD_DECIMALS), round(longitude, COORD_DECIMALS)


class TomTomClient:
    """Minimal TomTom client: stations around a point and their availability."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        """Initialize the client with Home Assistant's shared HTTP session."""
        self._session = session
        self._api_key = api_key

    async def nearby_stations(
        self, latitude: float, longitude: float, radius_m: int, limit: int = 20
    ) -> list[Station]:
        """Return charging stations within radius_m of a (rounded) position."""
        lat, lon = round_position(latitude, longitude)
        payload = await self._get(
            "nearbySearch/.json",
            {
                "lat": lat,
                "lon": lon,
                "radius": radius_m,
                "limit": limit,
                "categorySet": EV_STATION_CATEGORY,
            },
        )
        return parse_stations(payload)

    async def charging_availability(
        self, availability_id: str
    ) -> list[ConnectorAvailability]:
        """Return real-time availability for a station's availability id."""
        payload = await self._get(
            "chargingAvailability.json", {"chargingAvailability": availability_id}
        )
        return parse_availability(payload)

    async def validate_key(self) -> None:
        """Check the API key with a minimal search (costs one Search request)."""
        await self._get(
            "nearbySearch/.json",
            {
                "lat": 0,
                "lon": 0,
                "radius": 1,
                "limit": 1,
                "categorySet": EV_STATION_CATEGORY,
            },
        )

    async def _get(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """GET an endpoint. Only the endpoint name is ever logged, never the URL."""
        start = time.monotonic()
        payload: dict[str, Any] = {}
        try:
            async with self._session.get(
                f"{BASE_URL}/{endpoint}",
                params={**params, "key": self._api_key},
                timeout=REQUEST_TIMEOUT,
            ) as response:
                status = response.status
                if status == 200:
                    payload = await response.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            # aiohttp errors may embed the request URL, which carries the key:
            # do not chain them.
            _LOGGER.debug("TomTom %s: %s", endpoint, type(err).__name__)
            raise TomTomConnectionError(
                f"Cannot reach TomTom ({type(err).__name__})"
            ) from None

        _LOGGER.debug(
            "TomTom %s: HTTP %s in %d ms",
            endpoint,
            status,
            (time.monotonic() - start) * 1000,
        )
        if status in (401, 403):
            raise TomTomAuthError("TomTom rejected the API key")
        if status == 429:
            raise TomTomQuotaError("TomTom quota or rate limit reached")
        if status != 200:
            raise TomTomConnectionError(f"Unexpected HTTP status {status}")
        return payload
