"""Local IRVE copy: weekly download, local matching, nothing sent about positions."""

from datetime import timedelta
from pathlib import Path
from typing import Any

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes import irve_file
from custom_components.ravitbornes.const import CONF_TARIFFS, DOMAIN
from custom_components.ravitbornes.diagnostics import async_get_config_entry_diagnostics
from custom_components.ravitbornes.irve import IRVE_URL, IrveError
from custom_components.ravitbornes.irve_file import (
    IRVE_FILE_URL,
    PART_FILE,
    STORAGE_KEY,
    read_irve_csv,
)

from .conftest import FIXTURES
from .test_sensor import OPTIONS, STATION_1, STATION_2, _mock_tomtom, _move, _set_position, _unload

CSV = (FIXTURES / "irve_file.csv").read_text(encoding="utf-8")
DAY = timedelta(days=1)


@pytest.fixture(autouse=True)
def config_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Keep the temporary download in a throw-away folder."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path


def test_read_csv() -> None:
    """Stations grouped from the CSV text values, free ones at 0."""
    stations = {s.station_id: s for s in read_irve_csv(FIXTURES / "irve_file.csv")}

    assert stations["FREXAP00000001"].prices == ((22.0, 0.29),)
    assert stations["FREXBP00000002"].prices == ()
    assert stations["FREXCP00000003"].prices == ((11.0, 0.0),)


def test_unexpected_columns_are_refused(tmp_path: Path) -> None:
    """A renamed column must not silently give "no price anywhere"."""
    path = tmp_path / "irve.csv"
    path.write_text(CSV.replace("tarification", "tarif"), encoding="utf-8")

    with pytest.raises(IrveError, match="tarification"):
        read_irve_csv(path)


def _downloads(aioclient_mock: AiohttpClientMocker) -> int:
    return sum(1 for call in aioclient_mock.mock_calls if str(call[1]) == IRVE_FILE_URL)


async def _setup_local(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: "fakekey"},
        options={**OPTIONS, CONF_TARIFFS: "local"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return entry


async def test_local_file_gives_prices_without_sending_positions(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    config_dir: Path,
) -> None:
    """Downloaded once, kept compact, matched locally; only the file URL is requested."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    aioclient_mock.get(IRVE_FILE_URL, text=CSV)
    entry = await _setup_local(hass)
    await _move(hass, 45.1027, 4.2)  # next refresh, once the copy is there

    assert hass.states.get(STATION_1).state.endswith(" · 0.29 €/kWh")
    assert hass.states.get(STATION_2).attributes["price_per_kwh"] is None
    assert _downloads(aioclient_mock) == 1
    irve_calls = [c[1] for c in aioclient_mock.mock_calls if "data.gouv.fr" in c[1].host]
    assert [str(url) for url in irve_calls] == [IRVE_FILE_URL]  # no query, no position
    assert not any(c[1].path.endswith("/data/") for c in aioclient_mock.mock_calls)
    assert not (config_dir / ".storage" / PART_FILE).exists()  # the 120 MB CSV is gone
    assert len(hass_storage[STORAGE_KEY]["data"]["stations"]) == 3

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["tariff_source"] == "local"
    assert diagnostics["local_irve"] == {"loaded": True, "stations": 3, "age_days": 0.0}
    await _unload(hass, entry)


async def test_stored_copy_is_used_and_refreshed_weekly(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Prices right after a restart; a new download only once the copy is a week old."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    aioclient_mock.get(IRVE_FILE_URL, text=CSV)
    entry = await _setup_local(hass)
    await _unload(hass, entry)

    assert await hass.config_entries.async_setup(entry.entry_id)  # restart: from the store
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(STATION_1).attributes["price_per_kwh"] == 0.29
    assert _downloads(aioclient_mock) == 1

    freezer.tick(6 * DAY + timedelta(hours=23))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _downloads(aioclient_mock) == 1

    freezer.tick(2 * timedelta(hours=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _downloads(aioclient_mock) == 2
    await _unload(hass, entry)


async def test_failed_download_keeps_stations_and_retries_later(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No copy: stations without price; a new try after 6 hours, not every hour."""
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    aioclient_mock.get(IRVE_FILE_URL, status=503)
    entry = await _setup_local(hass)

    assert hass.states.get(STATION_1).state.endswith(" · 8/12 free")
    assert "Local IRVE copy not updated" in caplog.text

    freezer.tick(timedelta(hours=5))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _downloads(aioclient_mock) == 1

    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done(wait_background_tasks=True)
    assert _downloads(aioclient_mock) == 2
    await _unload(hass, entry)


async def test_oversized_file_is_refused(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A file far larger than expected is not stored."""
    monkeypatch.setattr(irve_file, "MAX_FILE_BYTES", len(CSV) // 2)
    monkeypatch.setattr(irve_file, "CHUNK_BYTES", 100)
    aioclient_mock.get(IRVE_FILE_URL, text=CSV)
    entry = await _setup_local(hass)

    assert STORAGE_KEY not in hass_storage
    await _unload(hass, entry)


@pytest.mark.parametrize("source", ["off", "online"])
async def test_other_sources_drop_the_local_copy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
    source: str,
) -> None:
    """Leaving the local option frees the stored copy; "off" asks nothing about prices."""
    hass_storage[STORAGE_KEY] = {"version": 1, "data": {"downloaded_at": 0, "stations": []}}
    _set_position(hass, 45.1, 4.2)
    _mock_tomtom(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_API_KEY: "fakekey"}, options={**OPTIONS, CONF_TARIFFS: source}
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert STORAGE_KEY not in hass_storage
    assert _downloads(aioclient_mock) == 0
    online_calls = sum(1 for c in aioclient_mock.mock_calls if str(c[1]).startswith(IRVE_URL))
    assert online_calls == (2 if source == "online" else 0)
    await _unload(hass, entry)


async def test_removing_the_integration_deletes_the_copy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """Nothing is left behind once the integration is removed."""
    aioclient_mock.get(IRVE_FILE_URL, text=CSV)
    entry = await _setup_local(hass)
    assert STORAGE_KEY in hass_storage

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert STORAGE_KEY not in hass_storage


async def test_empty_file_does_not_replace_the_copy(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    hass_storage: dict[str, Any],
) -> None:
    """A file with no station (truncated, emptied upstream) is not stored."""
    aioclient_mock.get(IRVE_FILE_URL, text=CSV.splitlines()[0] + "\n")
    entry = await _setup_local(hass)

    assert STORAGE_KEY not in hass_storage
    await _unload(hass, entry)


async def test_match_across_grid_cells(hass: HomeAssistant) -> None:
    """A station a few metres away, but in the neighbouring grid cell, is found."""
    local = irve_file.LocalIrve(hass, None, lambda: 0.0)
    station = irve_file.IrveStation("FREX1", 45.1, 4.2, ((22.0, 0.29),))
    local._index([station])

    assert await local.station_at(45.09996, 4.19996) is station  # ~5 m, other cell
    assert await local.station_at(45.1006, 4.2) is None  # ~65 m
