"""Local copy of the IRVE file: downloaded once a week, matched on the HA server.

Option "Local file" (decision 2026-10-25): only the public file is downloaded,
nothing about the car or the shown stations is sent. The ~120 MB CSV is
streamed to disk, read in the executor, and only what prices need is kept
(in the HA store, a few MB); the CSV itself is deleted right away.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
import csv
from datetime import datetime, timedelta
import logging
import math
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import STORAGE_DIR, Store

from .const import DOMAIN
from .irve import IRVE_RESOURCE_ID, IrveError, IrveStation, nearest_station, parse_irve_rows

_LOGGER = logging.getLogger(__name__)

IRVE_FILE_URL = f"https://www.data.gouv.fr/api/1/datasets/r/{IRVE_RESOURCE_ID}"
REFRESH_AFTER_S = 7 * 24 * 3600
# After a failed download, wait before trying again (the file is large).
RETRY_AFTER_S = 6 * 3600
CHECK_INTERVAL = timedelta(hours=1)
# The file is ~120 MB (2026-10): refuse anything absurdly larger.
MAX_FILE_BYTES = 500 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
DOWNLOAD_TIMEOUT = aiohttp.ClientTimeout(total=1800, sock_read=120)
# Lookup grid: 0.001° is ~110 m in latitude, ~75 m in longitude in France,
# more than the 30 m matching distance, so the 3 x 3 neighbouring cells suffice.
CELL_DEG = 0.001
STORAGE_KEY = f"{DOMAIN}.irve"
STORAGE_VERSION = 1
PART_FILE = f"{DOMAIN}.irve.csv.part"
REQUIRED_COLUMNS = {
    "id_station_itinerance",
    "consolidated_latitude",
    "consolidated_longitude",
    "puissance_nominale",
    "tarification",
    "gratuit",
}


def _float(value: str | None) -> float | None:
    try:
        return float(value) if value else None
    except ValueError:
        return None


def _csv_rows(reader: Iterable[dict[str, str]]) -> Iterator[dict[str, Any]]:
    """CSV values are text: convert them like the JSON values of the online API."""
    for row in reader:
        yield {
            "id_station_itinerance": row.get("id_station_itinerance"),
            "id_station_local": row.get("id_station_local"),
            "consolidated_latitude": _float(row.get("consolidated_latitude")),
            "consolidated_longitude": _float(row.get("consolidated_longitude")),
            "puissance_nominale": _float(row.get("puissance_nominale")),
            "tarification": row.get("tarification") or None,
            "gratuit": (row.get("gratuit") or "").strip().lower() in {"true", "1"},
        }


def read_irve_csv(path: Path) -> list[IrveStation]:
    """Stations of an IRVE CSV file (blocking: run it in the executor)."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise IrveError(f"Unexpected IRVE file columns, missing: {sorted(missing)}")
        return parse_irve_rows(_csv_rows(reader))


def _open_part_file(path: Path) -> Any:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("wb")


def _cell(latitude: float, longitude: float) -> tuple[int, int]:
    return math.floor(latitude / CELL_DEG), math.floor(longitude / CELL_DEG)


class LocalIrve:
    """IRVE stations from the weekly local copy, looked up without any network call."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        clock: Callable[[], float],
    ) -> None:
        """Initialize; call async_start() to load the copy and schedule refreshes."""
        self._hass = hass
        self._session = session
        self._clock = clock
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._grid: dict[tuple[int, int], list[IrveStation]] | None = None
        self._count = 0
        self._downloaded_at: float | None = None
        self._last_attempt: float | None = None
        self._entry: ConfigEntry | None = None
        self._refreshing = False

    async def async_start(self, entry: ConfigEntry) -> None:
        """Load the stored copy, then download a new one when it is a week old."""
        self._entry = entry
        if data := await self._store.async_load():
            self._downloaded_at = data["downloaded_at"]
            self._index(
                IrveStation(station_id, lat, lon, tuple(tuple(p) for p in prices))
                for station_id, lat, lon, prices in data["stations"]
            )
        entry.async_on_unload(
            async_track_time_interval(self._hass, self._async_check, CHECK_INTERVAL)
        )
        self._async_check()

    @property
    def status(self) -> dict[str, Any]:
        """Summary for the diagnostics (no position)."""
        age = None if self._downloaded_at is None else self._clock() - self._downloaded_at
        return {
            "loaded": self._grid is not None,
            "stations": self._count,
            "age_days": None if age is None else round(age / 86400, 1),
        }

    @callback
    def _async_check(self, _now: datetime | None = None) -> None:
        """Start a download in the background when the copy is missing or old."""
        now = self._clock()
        if self._refreshing or self._entry is None:
            return
        if self._downloaded_at is not None and now - self._downloaded_at < REFRESH_AFTER_S:
            return
        if self._last_attempt is not None and now - self._last_attempt < RETRY_AFTER_S:
            return
        self._refreshing = True
        self._entry.async_create_background_task(
            self._hass, self.async_refresh(), name=f"{DOMAIN} IRVE download"
        )

    async def async_refresh(self) -> None:
        """Download, read and store a new copy; keep the previous one on failure."""
        self._last_attempt = self._clock()
        path = Path(self._hass.config.path(STORAGE_DIR, PART_FILE))
        try:
            await self._download(path)
            stations = await self._hass.async_add_executor_job(read_irve_csv, path)
            if not stations:
                raise IrveError("The IRVE file has no station")
            await self._store.async_save(
                {
                    "downloaded_at": self._last_attempt,
                    "stations": [
                        [s.station_id, s.latitude, s.longitude, [list(p) for p in s.prices]]
                        for s in stations
                    ],
                }
            )
            self._downloaded_at = self._last_attempt
            self._index(stations)
            _LOGGER.debug("IRVE file: %d stations", self._count)
        except IrveError as err:
            _LOGGER.warning("Local IRVE copy not updated: %s", err)
        finally:
            self._refreshing = False
            await self._hass.async_add_executor_job(path.unlink, True)

    async def _download(self, path: Path) -> None:
        size = 0
        try:
            async with self._session.get(IRVE_FILE_URL, timeout=DOWNLOAD_TIMEOUT) as response:
                if response.status != 200:
                    raise IrveError(f"Unexpected HTTP status {response.status}")
                file = await self._hass.async_add_executor_job(_open_part_file, path)
                try:
                    async for chunk in response.content.iter_chunked(CHUNK_BYTES):
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise IrveError("The IRVE file is unexpectedly large")
                        await self._hass.async_add_executor_job(file.write, chunk)
                finally:
                    await self._hass.async_add_executor_job(file.close)
        except (aiohttp.ClientError, TimeoutError, OSError) as err:
            raise IrveError(f"Cannot download the IRVE file ({type(err).__name__})") from None

    def _index(self, stations: Iterable[IrveStation]) -> None:
        grid: dict[tuple[int, int], list[IrveStation]] = {}
        count = 0
        for station in stations:
            grid.setdefault(_cell(station.latitude, station.longitude), []).append(station)
            count += 1
        self._grid, self._count = grid, count

    async def station_at(self, latitude: float, longitude: float) -> IrveStation | None:
        """The IRVE station at a station position, from the local copy only."""
        if self._grid is None:
            raise IrveError("The local IRVE copy is not downloaded yet")
        row, col = _cell(latitude, longitude)
        candidates = [
            station
            for d_row in (-1, 0, 1)
            for d_col in (-1, 0, 1)
            for station in self._grid.get((row + d_row, col + d_col), ())
        ]
        return nearest_station(candidates, latitude, longitude)


async def async_remove_local_copy(hass: HomeAssistant) -> None:
    """Delete the stored copy (option changed or integration removed)."""
    await Store(hass, STORAGE_VERSION, STORAGE_KEY).async_remove()
