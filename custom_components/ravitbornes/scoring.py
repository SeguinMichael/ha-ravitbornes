"""Filtering and ranking of charging stations (score v1).

Decision 2026-10-24: stations are ordered by distance only; the charging
profile acts as a filter. A station with no compatible connector free right
now is kept in place and flagged as unavailable (to be shown greyed).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum

from .models import ConnectorAvailability, ConnectorGroup, Station, distance_m

# Android Auto shows at most 6 rows while driving.
DEFAULT_LIMIT = 6


class AvailabilityStatus(StrEnum):
    """Availability of a station's compatible connectors."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"  # all compatible connectors busy or out of service
    UNKNOWN = "unknown"  # TomTom has no availability data for them


@dataclass(frozen=True, slots=True)
class ChargingProfile:
    """Filtering preset for one charging situation."""

    key: str
    dc_only: bool
    min_power_kw: float
    max_distance_m: float


HIGHWAY = ChargingProfile("highway", dc_only=True, min_power_kw=50.0, max_distance_m=5000.0)
VISIT = ChargingProfile("visit", dc_only=False, min_power_kw=0.0, max_distance_m=2000.0)
PROFILES = {profile.key: profile for profile in (HIGHWAY, VISIT)}


@dataclass(frozen=True, slots=True)
class RankedStation:
    """A station that passed the filters, with what the display needs."""

    station: Station
    distance_m: float
    power_kw: float
    available: int | None
    total: int | None
    status: AvailabilityStatus


def compatible_groups(
    station: Station, connector_types: Collection[str], profile: ChargingProfile
) -> list[ConnectorGroup]:
    """Connector groups the vehicle can use under this profile."""
    return [
        group
        for group in station.connectors
        if group.connector_type in connector_types
        and group.power_kw >= profile.min_power_kw
        and (not profile.dc_only or group.current_type == "DC")
    ]


def _availability(
    groups: list[ConnectorGroup], levels: list[ConnectorAvailability] | None
) -> tuple[int | None, int | None, AvailabilityStatus]:
    """Count free connectors among the compatible ones only."""
    if levels is None:
        return None, None, AvailabilityStatus.UNKNOWN
    keys = {(group.connector_type, group.power_kw) for group in groups}
    matching = [level for level in levels if (level.connector_type, level.power_kw) in keys]
    total = sum(level.total for level in matching)
    if total == 0:
        # Availability exists but not for these connectors: no evidence either way.
        return None, None, AvailabilityStatus.UNKNOWN
    available = sum(level.available for level in matching)
    status = AvailabilityStatus.AVAILABLE if available else AvailabilityStatus.UNAVAILABLE
    return available, total, status


def rank_stations(
    stations: Iterable[Station],
    availability: Mapping[str, list[ConnectorAvailability]],
    latitude: float,
    longitude: float,
    connector_types: Collection[str],
    profile: ChargingProfile,
    limit: int = DEFAULT_LIMIT,
) -> list[RankedStation]:
    """Keep stations usable under the profile and order them by distance.

    The exact position is only used here, locally; it is never sent out.
    `availability` maps a station's availability id to its connector levels.
    """
    ranked = []
    for station in stations:
        groups = compatible_groups(station, connector_types, profile)
        if not groups:
            continue
        distance = distance_m(latitude, longitude, station.latitude, station.longitude)
        if distance > profile.max_distance_m:
            continue
        levels = (
            availability.get(station.availability_id)
            if station.availability_id
            else None
        )
        available, total, status = _availability(groups, levels)
        ranked.append(
            RankedStation(
                station=station,
                distance_m=distance,
                power_kw=max(group.power_kw for group in groups),
                available=available,
                total=total,
                status=status,
            )
        )
    ranked.sort(key=lambda item: item.distance_m)
    return ranked[:limit]
