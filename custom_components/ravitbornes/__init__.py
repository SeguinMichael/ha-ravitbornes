"""The RavitBornes integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_POSITION_ENTITY
from .coordinator import RavitBornesConfigEntry, RavitBornesCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> bool:
    """Set up RavitBornes from a config entry."""
    coordinator = RavitBornesCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(
        async_track_state_change_event(
            hass, [entry.options[CONF_POSITION_ENTITY]], coordinator.async_position_changed
        )
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> bool:
    """Unload a RavitBornes config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: RavitBornesConfigEntry) -> None:
    """Reload when the vehicle settings change."""
    await hass.config_entries.async_reload(entry.entry_id)
