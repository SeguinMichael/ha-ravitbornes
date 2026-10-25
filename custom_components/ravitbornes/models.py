"""Data models and parsing for TomTom EV charging responses."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Any

# Two results closer than this are treated as the same charging park.
DUPLICATE_DISTANCE_M = 25.0


@dataclass(frozen=True, slots=True)
class ConnectorGroup:
    """Connectors of one kind at a station (TomTom lists one entry per plug)."""

    connector_type: str
    power_kw: float
    current_type: str | None
    count: int


@dataclass(frozen=True, slots=True)
class Station:
    """A charging station returned by the Search API."""

    poi_id: str
    name: str
    latitude: float
    longitude: float
    connectors: tuple[ConnectorGroup, ...]
    availability_id: str | None
    address: str = ""
    street: str = ""

    @property
    def max_power_kw(self) -> float:
        """Highest rated power among the station's connectors."""
        return max((group.power_kw for group in self.connectors), default=0.0)


@dataclass(frozen=True, slots=True)
class ConnectorAvailability:
    """Real-time availability for one connector type at one power level."""

    connector_type: str
    power_kw: float
    available: int
    occupied: int
    reserved: int
    unknown: int
    out_of_service: int

    @property
    def total(self) -> int:
        """Number of connectors of this kind."""
        return (
            self.available
            + self.occupied
            + self.reserved
            + self.unknown
            + self.out_of_service
        )


def parse_stations(payload: dict[str, Any]) -> list[Station]:
    """Build stations from a nearbySearch response, aggregating identical plugs."""
    stations = []
    for result in payload.get("results", []):
        position = result.get("position") or {}
        if "lat" not in position or "lon" not in position:
            continue
        plugs = Counter(
            (
                connector.get("connectorType", "Unknown"),
                float(connector.get("ratedPowerKW", 0)),
                connector.get("currentType"),
            )
            for connector in (result.get("chargingPark") or {}).get("connectors", [])
        )
        stations.append(
            Station(
                poi_id=result.get("id", ""),
                name=(result.get("poi") or {}).get("name", ""),
                latitude=position["lat"],
                longitude=position["lon"],
                connectors=tuple(
                    ConnectorGroup(ctype, power, current, count)
                    for (ctype, power, current), count in plugs.items()
                ),
                availability_id=(
                    (result.get("dataSources") or {})
                    .get("chargingAvailability", {})
                    .get("id")
                ),
                address=(result.get("address") or {}).get("freeformAddress", ""),
                # TomTom pads some street names with spaces.
                street=" ".join(((result.get("address") or {}).get("streetName") or "").split()),
            )
        )
    return stations


def parse_availability(payload: dict[str, Any]) -> list[ConnectorAvailability]:
    """Build per-connector, per-power-level availability from a chargingAvailability response."""
    levels = []
    for connector in payload.get("connectors", []):
        connector_type = connector.get("type", "Unknown")
        for level in (connector.get("availability") or {}).get("perPowerLevel", []):
            levels.append(
                ConnectorAvailability(
                    connector_type=connector_type,
                    power_kw=float(level.get("powerKW", 0)),
                    available=level.get("available", 0),
                    occupied=level.get("occupied", 0),
                    reserved=level.get("reserved", 0),
                    unknown=level.get("unknown", 0),
                    out_of_service=level.get("outOfService", 0),
                )
            )
    return levels


def distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres (haversine)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def dedupe_stations(stations: list[Station]) -> list[Station]:
    """Merge results at the same location, preferring the one with availability data.

    TomTom sometimes returns the same charging park twice (e.g. once per address),
    only one of them carrying an availability id.
    """
    kept: list[Station] = []
    for station in stations:
        for index, other in enumerate(kept):
            if (
                distance_m(
                    station.latitude, station.longitude, other.latitude, other.longitude
                )
                <= DUPLICATE_DISTANCE_M
            ):
                if other.availability_id is None and station.availability_id:
                    kept[index] = station
                break
        else:
            kept.append(station)
    return kept
