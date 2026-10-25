"""Shared entity helpers."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN


def device_info(entry_id: str) -> DeviceInfo:
    """All RavitBornes entities belong to one service device."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="RavitBornes",
        entry_type=DeviceEntryType.SERVICE,
    )
