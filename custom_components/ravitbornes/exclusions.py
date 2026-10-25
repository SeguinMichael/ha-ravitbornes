"""Stations the user chose to hide, kept on the Home Assistant host only."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import asdict, dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN
from .models import DUPLICATE_DISTANCE_M, Station, distance_m

STORAGE_VERSION = 1


@dataclass(frozen=True, slots=True)
class ExcludedStation:
    """What is kept about a hidden station: enough to recognize it again."""

    poi_id: str
    name: str
    address: str
    latitude: float
    longitude: float

    def matches(self, station: Station) -> bool:
        """Same TomTom id, or same place (ids can change and duplicates exist)."""
        return (
            station.poi_id == self.poi_id
            or distance_m(self.latitude, self.longitude, station.latitude, station.longitude)
            <= DUPLICATE_DISTANCE_M
        )


class Exclusions:
    """Persistent list of hidden stations (in `.storage`, never sent anywhere)."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store for one config entry."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.excluded"
        )
        self._items: dict[str, ExcludedStation] = {}

    async def async_load(self) -> None:
        """Load the list saved by a previous run."""
        data = await self._store.async_load() or {}
        self._items = {
            item["poi_id"]: ExcludedStation(**item) for item in data.get("stations", [])
        }

    @property
    def items(self) -> list[ExcludedStation]:
        """Hidden stations, sorted by name."""
        return sorted(self._items.values(), key=lambda item: (item.name, item.address))

    def is_excluded(self, station: Station) -> bool:
        """Whether a search result is one of the hidden stations."""
        return any(item.matches(station) for item in self._items.values())

    async def async_add(self, station: Station) -> None:
        """Hide a station."""
        self._items[station.poi_id] = ExcludedStation(
            station.poi_id, station.name, station.address, station.latitude, station.longitude
        )
        await self._async_save()

    async def async_keep_only(self, poi_ids: Collection[str]) -> None:
        """Show again every hidden station not listed in `poi_ids`."""
        self._items = {key: item for key, item in self._items.items() if key in poi_ids}
        await self._async_save()

    async def async_remove_store(self) -> None:
        """Delete the saved list (when the integration is removed)."""
        await self._store.async_remove()

    async def _async_save(self) -> None:
        await self._store.async_save(
            {"stations": [asdict(item) for item in self._items.values()]}
        )
