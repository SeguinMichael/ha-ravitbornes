"""Coordinator: stations around the car and their real-time availability."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, CONF_API_KEY, STATE_HOME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    TomTomClient,
    TomTomConnectionError,
    TomTomError,
    TomTomQuotaError,
    round_position,
)
from .cache import TTLCache
from .const import CONF_CONNECTORS, CONF_POSITION_ENTITY, CONF_PROFILE, CONNECTORS, DOMAIN
from .models import ConnectorAvailability, Station, dedupe_stations, distance_m
from .scoring import PROFILES, ChargingProfile, RankedStation, rank_stations

_LOGGER = logging.getLogger(__name__)

# The station list barely changes during a trip; TomTom refreshes availability every 3 min.
STATIONS_TTL_S = 6 * 3600
AVAILABILITY_TTL_S = 180
# Ignore GPS jitter: refresh only once the car has moved this far.
MIN_MOVE_M = 200
# The search is centred on the rounded zone, which can be ~700 m away from the car.
SEARCH_MARGIN_M = 1000
SEARCH_LIMIT = 50
REFRESH_COOLDOWN_S = 60

type RavitBornesConfigEntry = ConfigEntry[RavitBornesCoordinator]


class RavitBornesCoordinator(DataUpdateCoordinator[list[RankedStation]]):
    """Refreshed when the car moves, never on a timer: no polling outside trips."""

    config_entry: RavitBornesConfigEntry

    def __init__(self, hass: HomeAssistant, entry: RavitBornesConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            request_refresh_debouncer=Debouncer(
                hass, _LOGGER, cooldown=REFRESH_COOLDOWN_S, immediate=True
            ),
        )
        self._client = TomTomClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._stations: TTLCache[list[Station]] = TTLCache(STATIONS_TTL_S)
        self._availability: TTLCache[list[ConnectorAvailability]] = TTLCache(
            AVAILABILITY_TTL_S
        )
        self._last_position: tuple[float, float] | None = None

    @property
    def position_entity(self) -> str:
        """Entity providing the car position."""
        return self.config_entry.options[CONF_POSITION_ENTITY]

    def current_position(self) -> tuple[float, float] | None:
        """Car position, or None when unknown or at home (nothing is looked up then)."""
        state = self.hass.states.get(self.position_entity)
        if state is None or state.state == STATE_HOME:
            return None
        latitude = state.attributes.get(ATTR_LATITUDE)
        longitude = state.attributes.get(ATTR_LONGITUDE)
        if latitude is None or longitude is None:
            return None
        return float(latitude), float(longitude)

    @callback
    def async_position_changed(self, event: Event[EventStateChangedData]) -> None:
        """Refresh when the car has really moved; clear the list once home."""
        position = self.current_position()
        if position is None:
            self._last_position = None
            if self.data:
                self.async_set_updated_data([])
            return
        if (
            self._last_position is not None
            and distance_m(*self._last_position, *position) < MIN_MOVE_M
        ):
            return
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), name=f"{DOMAIN} refresh"
        )

    async def _async_update_data(self) -> list[RankedStation]:
        """Search stations (cached per zone), then fetch availability of the best ones."""
        position = self.current_position()
        if position is None:
            self._last_position = None
            return []
        options = self.config_entry.options
        profile = PROFILES[options[CONF_PROFILE]]
        connector_types = {CONNECTORS[key] for key in options[CONF_CONNECTORS]}

        try:
            stations = await self._stations_around(position, profile)
        except TomTomError as err:
            raise UpdateFailed(str(err)) from err
        # Ordering is by distance only, so availability is needed for the shown ones only.
        candidates = rank_stations(stations, {}, *position, connector_types, profile)
        availability = await self._availability_for(candidates)

        self._last_position = position
        return rank_stations(stations, availability, *position, connector_types, profile)

    async def _stations_around(
        self, position: tuple[float, float], profile: ChargingProfile
    ) -> list[Station]:
        """Stations around the rounded zone, kept for the duration of a trip."""
        zone = round_position(*position)
        key = (zone, profile.key)
        stations = self._stations.get(key)
        if stations is None:
            stations = dedupe_stations(
                await self._client.nearby_stations(
                    *zone,
                    radius_m=int(profile.max_distance_m) + SEARCH_MARGIN_M,
                    limit=SEARCH_LIMIT,
                )
            )
            self._stations.set(key, stations)
        return stations

    async def _availability_for(
        self, candidates: list[RankedStation]
    ) -> dict[str, list[ConnectorAvailability]]:
        """Availability of the shown stations; degrade to "unknown" on quota or network errors."""
        found: dict[str, list[ConnectorAvailability]] = {}
        for item in candidates:
            availability_id = item.station.availability_id
            if availability_id is None:
                continue
            levels = self._availability.get(availability_id)
            if levels is None:
                try:
                    levels = await self._client.charging_availability(availability_id)
                except (TomTomQuotaError, TomTomConnectionError) as err:
                    _LOGGER.warning("Availability partly missing: %s", err)
                    break
                except TomTomError as err:
                    raise UpdateFailed(str(err)) from err
                self._availability.set(availability_id, levels)
            found[availability_id] = levels
        return found
