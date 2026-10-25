"""Buttons: hide the station shown in a slot (bad experience, crowded, hard to reach...).

They are reachable from Android Auto; in practice they are meant to be pressed
while charging. Gating them on the car's charging state is in docs/TODO.md.
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
    """Create one exclude button per station slot."""
    coordinator = entry.runtime_data
    async_add_entities(
        ExcludeStationButton(coordinator, index) for index in range(1, STATION_SLOTS + 1)
    )


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
