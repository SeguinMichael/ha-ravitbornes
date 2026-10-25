"""Sensors: the nearest usable charging stations, one sensor per slot.

Each sensor carries the station position in its latitude / longitude
attributes, so the companion app can navigate to it from Android Auto.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import STATION_SLOTS
from .coordinator import RavitBornesConfigEntry, RavitBornesCoordinator
from .display import format_station
from .entity import device_info
from .scoring import RankedStation

# Data comes from the coordinator: no parallel update limit needed.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavitBornesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create one sensor per station slot."""
    coordinator = entry.runtime_data
    async_add_entities(
        StationSensor(coordinator, index) for index in range(1, STATION_SLOTS + 1)
    )


class StationSensor(CoordinatorEntity[RavitBornesCoordinator], SensorEntity):
    """The n-th nearest usable station; unknown when there are fewer stations."""

    _attr_has_entity_name = True
    _attr_translation_key = "station"

    def __init__(self, coordinator: RavitBornesCoordinator, index: int) -> None:
        """Initialize the sensor for slot `index` (1-based)."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._index = index
        self._attr_unique_id = f"{entry_id}_station_{index}"
        self._attr_translation_placeholders = {"index": str(index)}
        self._attr_device_info = device_info(entry_id)

    @property
    def _item(self) -> RankedStation | None:
        return self.coordinator.station_at(self._index)

    @property
    def native_value(self) -> str | None:
        """Short text shown in the car."""
        item = self._item
        return None if item is None else format_station(item, self.hass.config.language)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Station position (for navigation) and raw figures."""
        item = self._item
        if item is None:
            return None
        return {
            ATTR_LATITUDE: item.station.latitude,
            ATTR_LONGITUDE: item.station.longitude,
            "station": item.station.name,
            "distance_km": round(item.distance_m / 1000, 1),
            "power_kw": item.power_kw,
            "available": item.available,
            "total": item.total,
            "status": item.status.value,
        }
