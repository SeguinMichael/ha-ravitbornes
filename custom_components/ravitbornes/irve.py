"""Approximate prices from the French national IRVE open data (data.gouv.fr).

TomTom gives no price. The IRVE static file has a free-text `tarification`
field per charge point. There is no key shared with TomTom, but TomTom uses
the IRVE coordinates for French stations, so stations are matched by position.

Only the position of a shown *station* is sent (a ~30 m box around it), never
the car's position.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
import logging
import re
from typing import Any

import aiohttp

from .cache import TTLCache
from .models import distance_m
from .scoring import RankedStation

_LOGGER = logging.getLogger(__name__)

# Consolidated IRVE file on data.gouv.fr, queried through the tabular API.
# This dataset is announced as replaced by the transport.data.gouv.fr
# consolidation and kept until 2026-12-31: see docs/TODO.md.
IRVE_RESOURCE_ID = "eb76d20a-8501-400e-b336-d85724de5435"
IRVE_URL = f"https://tabular-api.data.gouv.fr/api/resources/{IRVE_RESOURCE_ID}/data/"
# ~30 m around the station (latitude), a bit wider in longitude for France.
BOX_LAT = 0.0003
BOX_LON = 0.0005
MATCH_DISTANCE_M = 30.0
PAGE_SIZE = 50
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
# Tariffs change rarely: one lookup per station and per day at most.
TARIFF_TTL_S = 24 * 3600

_PRICE_PER_KWH = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(?:€|eur(?:os?)?)\s*(?:ttc\s*)?(?:/|par)\s*kwh",
    re.IGNORECASE,
)


def parse_price_per_kwh(text: str | None) -> float | None:
    """First '€/kWh' price found in a free-text tariff, e.g. '0,29€ / kWh' -> 0.29."""
    if not text:
        return None
    match = _PRICE_PER_KWH.search(text)
    return float(match.group(1).replace(",", ".")) if match else None


@dataclass(frozen=True, slots=True)
class IrveStation:
    """One IRVE station (rows are per charge point, grouped here)."""

    station_id: str
    latitude: float
    longitude: float
    # (charge point power in kW, price in €/kWh); 0.0 means free of charge.
    prices: tuple[tuple[float, float], ...]

    def price_for(self, power_kw: float) -> float | None:
        """Price of the charge point whose power is closest to `power_kw`."""
        if not self.prices:
            return None
        return min(self.prices, key=lambda item: abs(item[0] - power_kw))[1]


def parse_irve_rows(rows: list[dict[str, Any]]) -> list[IrveStation]:
    """Group charge point rows by station and keep the readable prices."""
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        latitude = row.get("consolidated_latitude")
        longitude = row.get("consolidated_longitude")
        station_id = row.get("id_station_itinerance") or row.get("id_station_local")
        if latitude is None or longitude is None or not station_id:
            continue
        station = grouped.setdefault(
            station_id, {"lat": float(latitude), "lon": float(longitude), "prices": set()}
        )
        price = 0.0 if row.get("gratuit") is True else parse_price_per_kwh(row.get("tarification"))
        power = row.get("puissance_nominale")
        if price is not None and power is not None:
            station["prices"].add((float(power), price))
    return [
        IrveStation(station_id, value["lat"], value["lon"], tuple(sorted(value["prices"])))
        for station_id, value in grouped.items()
    ]


def nearest_station(
    stations: list[IrveStation], latitude: float, longitude: float
) -> IrveStation | None:
    """The IRVE station at the same place as a TomTom station, if any."""
    candidates = [
        (distance_m(latitude, longitude, s.latitude, s.longitude), s) for s in stations
    ]
    candidates = [item for item in candidates if item[0] <= MATCH_DISTANCE_M]
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


class IrveError(Exception):
    """The IRVE API could not be used (prices are then simply left out)."""


class IrveClient:
    """Minimal client for the IRVE tabular API (no key needed)."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize with Home Assistant's shared HTTP session."""
        self._session = session

    async def station_at(self, latitude: float, longitude: float) -> IrveStation | None:
        """The IRVE station at a given station position, if any."""
        params = {
            "consolidated_latitude__greater": round(latitude - BOX_LAT, 6),
            "consolidated_latitude__less": round(latitude + BOX_LAT, 6),
            "consolidated_longitude__greater": round(longitude - BOX_LON, 6),
            "consolidated_longitude__less": round(longitude + BOX_LON, 6),
            "page_size": PAGE_SIZE,
        }
        try:
            async with self._session.get(
                IRVE_URL, params=params, timeout=REQUEST_TIMEOUT
            ) as response:
                if response.status != 200:
                    raise IrveError(f"Unexpected HTTP status {response.status}")
                payload = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise IrveError(f"Cannot reach the IRVE API ({type(err).__name__})") from None
        _LOGGER.debug("IRVE: %d rows", len(payload.get("data", [])))
        return nearest_station(parse_irve_rows(payload.get("data", [])), latitude, longitude)


class TariffLookup:
    """Adds IRVE prices to the shown stations, with a per-station daily cache."""

    def __init__(self, client: IrveClient, clock: Callable[[], float]) -> None:
        """Initialize with a client and the clock used by the other caches."""
        self._client = client
        # Wrapped in a tuple so that "no IRVE station here" is cached too.
        self._cache: TTLCache[tuple[IrveStation | None]] = TTLCache(TARIFF_TTL_S, clock)

    async def with_prices(self, items: Iterable[RankedStation]) -> list[RankedStation]:
        """Same stations, with `price_per_kwh` when the IRVE has a readable one.

        Prices are optional: any IRVE failure leaves them out, never the station.
        """
        priced = []
        for item in items:
            station = item.station
            irve = None
            if station.country_code == "FR":
                cached = self._cache.get(station.poi_id)
                if cached is None:
                    try:
                        cached = (await self._client.station_at(station.latitude, station.longitude),)
                    except IrveError as err:
                        _LOGGER.debug("No price for a station: %s", err)
                        cached = None
                    if cached is not None:
                        self._cache.set(station.poi_id, cached)
                irve = cached[0] if cached else None
            price = irve.price_for(item.shown_power_kw) if irve else None
            priced.append(replace(item, price_per_kwh=price))
        return priced
