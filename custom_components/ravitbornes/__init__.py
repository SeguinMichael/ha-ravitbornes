"""The RavitBornes integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_POSITION_ENTITIES, CONF_TRIP_ENTITY
from .coordinator import RavitBornesConfigEntry, RavitBornesCoordinator
from .exclusions import Exclusions
from .irve_file import async_remove_local_copy

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> bool:
    """Set up RavitBornes from a config entry."""
    exclusions = Exclusions(hass, entry.entry_id)
    await exclusions.async_load()
    coordinator = RavitBornesCoordinator(hass, entry, exclusions)
    if coordinator.local_irve is not None:
        await coordinator.local_irve.async_start(entry)
    else:
        # Switching away from the local file frees its copy.
        await async_remove_local_copy(hass)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(
        async_track_state_change_event(
            hass, entry.options[CONF_POSITION_ENTITIES], coordinator.async_position_changed
        )
    )
    if trip_entity := entry.options.get(CONF_TRIP_ENTITY):
        entry.async_on_unload(
            async_track_state_change_event(
                hass, [trip_entity], coordinator.async_trip_changed
            )
        )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> bool:
    """Unload a RavitBornes config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> None:
    """Delete the exclusion list and the local IRVE copy when the integration is removed."""
    await Exclusions(hass, entry.entry_id).async_remove_store()
    await async_remove_local_copy(hass)


async def _async_update_listener(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> None:
    """Reload when the settings change."""
    await hass.config_entries.async_reload(entry.entry_id)
