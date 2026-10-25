"""Diagnostics: shareable in a bug report, so no API key and no position."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .const import CONF_POSITION_ENTITIES, CONF_TRIP_ENTITY
from .coordinator import RavitBornesConfigEntry

# Entity ids often contain a person's or phone's name.
TO_REDACT = {CONF_API_KEY, CONF_POSITION_ENTITIES, CONF_TRIP_ENTITY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RavitBornesConfigEntry
) -> dict[str, Any]:
    """Return redacted settings and a summary without any coordinates."""
    coordinator = entry.runtime_data
    stations = coordinator.data or []
    return {
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "options": async_redact_data(dict(entry.options), TO_REDACT),
        "last_update_success": coordinator.last_update_success,
        "trip_active": coordinator.trip_active,
        "stations": len(stations),
        "statuses": sorted(item.status.value for item in stations),
        # Which stations a user hides says something about their habits: count only.
        "excluded_stations": len(coordinator.exclusions.items),
    }
