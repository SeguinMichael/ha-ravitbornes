"""Buttons reachable from Android Auto.

- "Search stations (30 min)": look up now and every 3 min for 30 min, even
  outside a trip or at home.
- "Hide station N": hide the station shown in a slot (bad experience, crowded,
  hard to reach...). In practice pressed while charging; gating it on the
  car's charging state is in docs/TODO.md.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import STATION_SLOTS
from .coordinator import RavitBornesConfigEntry, RavitBornesCoordinator
from .entity import device_info

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavitBornesConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the search button and one hide button per station slot."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            SearchStationsButton(coordinator),
            *(
                ExcludeStationButton(coordinator, index)
                for index in range(1, STATION_SLOTS + 1)
            ),
        ]
    )


class SearchStationsButton(CoordinatorEntity[RavitBornesCoordinator], ButtonEntity):
    """Start (or restart) a 30-minute search window."""

    _attr_has_entity_name = True
    _attr_translation_key = "search_stations"

    def __init__(self, coordinator: RavitBornesCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_search"
        self._attr_device_info = device_info(entry_id)

    @property
    def available(self) -> bool:
        """Always pressable, also to retry after a failed update."""
        return True

    async def async_press(self) -> None:
        """Search now and keep refreshing for 30 minutes."""
        await self.coordinator.async_start_search()


class ExcludeStationButton(CoordinatorEntity[RavitBornesCoordinator], ButtonEntity):
    """Hide the station currently shown in slot `index`."""

    _attr_has_entity_name = True
    _attr_translation_key = "exclude_station"

    def __init__(self, coordinator: RavitBornesCoordinator, index: int) -> None:
        """Initialize the button for slot `index` (1-based)."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._index = index
        self._attr_unique_id = f"{entry_id}_exclude_{index}"
        self._attr_translation_placeholders = {"index": str(index)}
        self._attr_device_info = device_info(entry_id)

    @property
    def available(self) -> bool:
        """Only when a station is shown in this slot."""
        return super().available and self.coordinator.station_at(self._index) is not None

    async def async_press(self) -> None:
        """Hide the station and refresh the list."""
        item = self.coordinator.station_at(self._index)
        if item is not None:
            await self.coordinator.async_exclude(item.station)
