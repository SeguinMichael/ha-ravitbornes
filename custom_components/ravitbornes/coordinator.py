"""Coordinator: stations around the car and their real-time availability."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    STATE_HOME,
    STATE_ON,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    TomTomClient,
    TomTomConnectionError,
    TomTomError,
    TomTomQuotaError,
    round_position,
)
from .cache import TTLCache
from .const import (
    CONF_CONNECTORS,
    CONF_POSITION_ENTITIES,
    CONF_PROFILE,
    CONF_TRIP_ENTITY,
    CONNECTORS,
    DOMAIN,
)
from .exclusions import Exclusions
from .models import ConnectorAvailability, Station, dedupe_stations, distance_m
from .scoring import PROFILES, ChargingProfile, RankedStation, rank_stations

_LOGGER = logging.getLogger(__name__)

# The station list barely changes during a trip; TomTom refreshes availability every 3 min.
STATIONS_TTL_S = 6 * 3600
AVAILABILITY_TTL_S = 180
# While the trip entity is on, refresh at TomTom's pace even if the car is stopped.
TRIP_REFRESH = timedelta(seconds=AVAILABILITY_TTL_S)
# Ignore GPS jitter: refresh only once the car has moved this far.
MIN_MOVE_M = 200
# The search is centred on the rounded zone, which can be ~700 m away from the car.
SEARCH_MARGIN_M = 1000
SEARCH_LIMIT = 50
REFRESH_COOLDOWN_S = 60

type RavitBornesConfigEntry = ConfigEntry[RavitBornesCoordinator]


def _timestamp() -> float:
    """Wall-clock seconds, as used by Home Assistant (and frozen in tests)."""
    return dt_util.utcnow().timestamp()


class RavitBornesCoordinator(DataUpdateCoordinator[list[RankedStation]]):
    """Refreshed when the car moves and, during a trip, every 3 minutes.

    Without a trip entity, there is no timer at all: no polling outside trips.
    """

    config_entry: RavitBornesConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: RavitBornesConfigEntry, exclusions: Exclusions
    ) -> None:
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
        self.exclusions = exclusions
        self._client = TomTomClient(
            async_get_clientsession(hass), entry.data[CONF_API_KEY]
        )
        self._stations: TTLCache[list[Station]] = TTLCache(STATIONS_TTL_S, _timestamp)
        self._availability: TTLCache[list[ConnectorAvailability]] = TTLCache(
            AVAILABILITY_TTL_S, _timestamp
        )
        self._last_position: tuple[float, float] | None = None
        self.update_interval = TRIP_REFRESH if self.trip_active else None

    @property
    def position_entities(self) -> list[str]:
        """Entities that may provide the car position (phone, car...)."""
        return list(self.config_entry.options[CONF_POSITION_ENTITIES])

    @property
    def trip_entity(self) -> str | None:
        """Optional entity that is on during a trip (e.g. Android Auto connected)."""
        return self.config_entry.options.get(CONF_TRIP_ENTITY)

    @property
    def trip_active(self) -> bool:
        """Without a trip entity, every move counts; otherwise only while it is on."""
        if self.trip_entity is None:
            return True
        state = self.hass.states.get(self.trip_entity)
        return state is not None and state.state == STATE_ON

    def _freshest_position_state(self) -> State | None:
        """Among the position sources with coordinates, the most recently reported."""
        states = [
            state
            for entity_id in self.position_entities
            if (state := self.hass.states.get(entity_id)) is not None
            and state.attributes.get(ATTR_LATITUDE) is not None
            and state.attributes.get(ATTR_LONGITUDE) is not None
        ]
        return max(states, key=lambda state: state.last_reported, default=None)

    def current_position(self) -> tuple[float, float] | None:
        """Car position, or None when unknown or at home (nothing is looked up then)."""
        state = self._freshest_position_state()
        if state is None or state.state == STATE_HOME:
            return None
        return float(state.attributes[ATTR_LATITUDE]), float(state.attributes[ATTR_LONGITUDE])

    def station_at(self, index: int) -> RankedStation | None:
        """The station shown in slot `index` (1-based), if any."""
        data = self.data or []
        return data[index - 1] if len(data) >= index else None

    @callback
    def async_position_changed(self, event: Event[EventStateChangedData]) -> None:
        """Refresh when the car has really moved; clear the list once home."""
        if not self.trip_active:
            return
        position = self.current_position()
        if position is None:
            self._clear()
            return
        if (
            self._last_position is not None
            and distance_m(*self._last_position, *position) < MIN_MOVE_M
        ):
            return
        self._request_refresh()

    @callback
    def async_trip_changed(self, event: Event[EventStateChangedData]) -> None:
        """Start refreshing at trip start (every 3 min); stop and clear at trip end."""
        if self.trip_active:
            self.update_interval = TRIP_REFRESH
            self._request_refresh()
        else:
            self.update_interval = None
            self._clear()

    async def async_exclude(self, station: Station) -> None:
        """Hide a station and show the next one right away (from the caches)."""
        await self.exclusions.async_add(station)
        await self.async_refresh()

    async def async_keep_excluded(self, poi_ids: list[str]) -> None:
        """Show again the hidden stations not in `poi_ids`, and refresh the list."""
        await self.exclusions.async_keep_only(poi_ids)
        await self.async_refresh()

    @callback
    def _request_refresh(self) -> None:
        self.config_entry.async_create_background_task(
            self.hass, self.async_request_refresh(), name=f"{DOMAIN} refresh"
        )

    @callback
    def _clear(self) -> None:
        self._last_position = None
        if self.data:
            self.async_set_updated_data([])

    async def _async_update_data(self) -> list[RankedStation]:
        """Search stations (cached per zone), then fetch availability of the shown ones."""
        position = self.current_position() if self.trip_active else None
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
        stations = [s for s in stations if not self.exclusions.is_excluded(s)]
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
