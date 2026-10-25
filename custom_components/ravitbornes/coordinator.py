"""Coordinator: stations around the car and their real-time availability."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_API_KEY,
    STATE_HOME,
    STATE_ON,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    HomeAssistant,
    State,
    callback,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.debounce import Debouncer
from homeassistant.helpers.event import async_call_later
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    TomTomAuthError,
    TomTomClient,
    TomTomConnectionError,
    TomTomError,
    TomTomQuotaError,
    round_position,
)
from .cache import TTLCache
from .const import (
    CONF_CHARGING_ENTITY,
    CONF_CONNECTORS,
    CONF_POSITION_ENTITIES,
    CONF_PROFILE,
    CONF_TARIFFS,
    CONF_TRIP_ENTITY,
    CONNECTORS,
    DEFAULT_TARIFFS,
    DOMAIN,
    TARIFFS_LOCAL,
    TARIFFS_ONLINE,
)
from .exclusions import Exclusions
from .irve import IrveClient, TariffLookup
from .irve_file import LocalIrve
from .models import ConnectorAvailability, Station, dedupe_stations, distance_m
from .scoring import PROFILES, ChargingProfile, RankedStation, rank_stations

_LOGGER = logging.getLogger(__name__)

# The station list barely changes during a trip; TomTom refreshes availability every 3 min.
STATIONS_TTL_S = 6 * 3600
AVAILABILITY_TTL_S = 180
# While the trip entity is on, refresh at TomTom's pace even if the car is stopped.
TRIP_REFRESH = timedelta(seconds=AVAILABILITY_TTL_S)
# "Search for 30 minutes" button: same pace, outside trips and even at home.
MANUAL_SEARCH = timedelta(minutes=30)
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
    """Refreshed when the car moves and, during a trip or a manual search, every 3 minutes.

    Without a trip entity and outside a manual search, there is no timer at all.
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
        self.tariff_source = entry.options.get(CONF_TARIFFS, DEFAULT_TARIFFS)
        self.local_irve: LocalIrve | None = None
        self._tariffs: TariffLookup | None = None
        if self.tariff_source == TARIFFS_ONLINE:
            self._tariffs = TariffLookup(IrveClient(async_get_clientsession(hass)), _timestamp)
        elif self.tariff_source == TARIFFS_LOCAL:
            self.local_irve = LocalIrve(hass, async_get_clientsession(hass), _timestamp)
            self._tariffs = TariffLookup(self.local_irve, _timestamp)
        self._stations: TTLCache[list[Station]] = TTLCache(STATIONS_TTL_S, _timestamp)
        self._availability: TTLCache[list[ConnectorAvailability]] = TTLCache(
            AVAILABILITY_TTL_S, _timestamp
        )
        self._last_position: tuple[float, float] | None = None
        self._search_until: datetime | None = None
        self._cancel_search_end: CALLBACK_TYPE | None = None
        self.update_interval = self._refresh_interval()
        entry.async_on_unload(self._cancel_search_timer)

    @property
    def position_entities(self) -> list[str]:
        """Entities that may provide the car position (phone, car...)."""
        return list(self.config_entry.options[CONF_POSITION_ENTITIES])

    @property
    def trip_entity(self) -> str | None:
        """Optional entity that is on during a trip (e.g. Android Auto connected)."""
        return self.config_entry.options.get(CONF_TRIP_ENTITY)

    @property
    def charging_entity(self) -> str | None:
        """Optional entity that is on while the car charges."""
        return self.config_entry.options.get(CONF_CHARGING_ENTITY)

    @property
    def hiding_allowed(self) -> bool:
        """Without a charging entity, always; otherwise only while charging."""
        if self.charging_entity is None:
            return True
        state = self.hass.states.get(self.charging_entity)
        return state is not None and state.state == STATE_ON

    @property
    def trip_active(self) -> bool:
        """Without a trip entity, every move counts; otherwise only while it is on."""
        if self.trip_entity is None:
            return True
        state = self.hass.states.get(self.trip_entity)
        return state is not None and state.state == STATE_ON

    @property
    def manual_search_active(self) -> bool:
        """Whether a "search for 30 minutes" window is running."""
        return self._search_until is not None and dt_util.utcnow() < self._search_until

    @property
    def lookups_allowed(self) -> bool:
        """Lookups happen during a trip or during a manual search window."""
        return self.manual_search_active or self.trip_active

    def _refresh_interval(self) -> timedelta | None:
        """Timer only during a manual search or while the trip entity is on."""
        if self.manual_search_active or (self.trip_entity is not None and self.trip_active):
            return TRIP_REFRESH
        return None

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
        """Position to search around, or None when nothing should be looked up.

        At home nothing is looked up, unless the user asked for a manual search.
        """
        if not self.lookups_allowed:
            return None
        state = self._freshest_position_state()
        if state is None or (state.state == STATE_HOME and not self.manual_search_active):
            return None
        return float(state.attributes[ATTR_LATITUDE]), float(state.attributes[ATTR_LONGITUDE])

    def station_at(self, index: int) -> RankedStation | None:
        """The station shown in slot `index` (1-based), if any."""
        data = self.data or []
        return data[index - 1] if len(data) >= index else None

    @callback
    def async_position_changed(self, event: Event[EventStateChangedData]) -> None:
        """Refresh when the car has really moved; clear the list once home."""
        if not self.lookups_allowed:
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
        self.update_interval = self._refresh_interval()
        if self.lookups_allowed:
            self._request_refresh()
        else:
            self._clear()

    async def async_start_search(self) -> None:
        """Look up now, then every 3 min for 30 min, even outside a trip or at home.

        Pressing again restarts the 30 minutes.
        """
        self._cancel_search_timer()
        self._search_until = dt_util.utcnow() + MANUAL_SEARCH
        self._cancel_search_end = async_call_later(
            self.hass, MANUAL_SEARCH, self._async_search_ended
        )
        self.update_interval = self._refresh_interval()
        self._last_position = None  # a manual search always refreshes
        await self.async_refresh()

    @callback
    def _async_search_ended(self, _now: datetime) -> None:
        """Back to normal: keep going only if a trip is still on."""
        self._cancel_search_end = None
        self._search_until = None
        self.update_interval = self._refresh_interval()
        if self.current_position() is None:
            self._clear()

    @callback
    def _cancel_search_timer(self) -> None:
        if self._cancel_search_end is not None:
            self._cancel_search_end()
            self._cancel_search_end = None

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
        position = self.current_position()
        if position is None:
            self._last_position = None
            return []
        options = self.config_entry.options
        profile = PROFILES[options[CONF_PROFILE]]
        connector_types = {CONNECTORS[key] for key in options[CONF_CONNECTORS]}

        try:
            stations = await self._stations_around(position, profile, connector_types)
        except TomTomAuthError as err:
            # Asks the user for a new key (reauth flow) instead of failing silently.
            raise ConfigEntryAuthFailed(str(err)) from err
        except TomTomError as err:
            raise UpdateFailed(str(err)) from err
        stations = [s for s in stations if not self.exclusions.is_excluded(s)]
        # Ordering is by distance only, so availability is needed for the shown ones only.
        candidates = rank_stations(stations, {}, *position, connector_types, profile)
        availability = await self._availability_for(candidates)

        self._last_position = position
        ranked = rank_stations(stations, availability, *position, connector_types, profile)
        return await self._tariffs.with_prices(ranked) if self._tariffs else ranked

    async def _stations_around(
        self,
        position: tuple[float, float],
        profile: ChargingProfile,
        connector_types: set[str],
    ) -> list[Station]:
        """Usable stations around the rounded zone, kept for the duration of a trip."""
        zone = round_position(*position)
        key = (zone, profile.key, frozenset(connector_types))
        stations = self._stations.get(key)
        if stations is None:
            stations = dedupe_stations(
                await self._client.nearby_stations(
                    *zone,
                    radius_m=int(profile.max_distance_m) + SEARCH_MARGIN_M,
                    limit=SEARCH_LIMIT,
                    connector_types=connector_types,
                    min_power_kw=profile.min_power_kw,
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
                except TomTomAuthError as err:
                    raise ConfigEntryAuthFailed(str(err)) from err
                except TomTomError as err:
                    raise UpdateFailed(str(err)) from err
                self._availability.set(availability_id, levels)
            found[availability_id] = levels
        return found
