"""IRVE prices: parsing, matching to TomTom stations, lookups and cache."""

from dataclasses import replace

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.ravitbornes.irve import (
    IRVE_URL,
    TARIFF_TTL_S,
    IrveClient,
    IrveStation,
    TariffLookup,
    nearest_station,
    parse_irve_rows,
    parse_price_per_kwh,
)
from custom_components.ravitbornes.models import Station
from custom_components.ravitbornes.scoring import AvailabilityStatus, RankedStation

from .conftest import load_json_fixture
from .test_sensor import (
    STATION_1,
    STATION_2,
    _calls,
    _mock_tomtom,
    _move,
    _set_position,
    _setup,
    _unload,
)

STORE_ID = "FREXAP00000001"
PARK_ID = "FREXBP00000002"


@pytest.mark.parametrize(
    ("text", "price"),
    [
        ("0,29€ / kWh", 0.29),
        ("0.45 € TTC/kWh", 0.45),
        ("Recharge : 0,59 euros par kWh, stationnement offert", 0.59),
        ("0,35 EUR/kWh + 0,05 €/min après 2 h", 0.35),
        ("2 € la session", None),
        ("0,05 €/min", None),
        ("Tarification disponible sur l'application", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_price_per_kwh(text: str | None, price: float | None) -> None:
    """Only a readable €/kWh price is kept, never a per-minute or per-session one."""
    assert parse_price_per_kwh(text) == price


def test_rows_are_grouped_by_station() -> None:
    """Charge point rows become one station, with the prices it has."""
    stations = {s.station_id: s for s in parse_irve_rows(load_json_fixture("irve_tabular.json")["data"])}

    assert set(stations) == {STORE_ID, PARK_ID}
    assert stations[STORE_ID].prices == ((22.0, 0.29),)
    assert (stations[STORE_ID].latitude, stations[STORE_ID].longitude) == (45.1, 4.2)
    assert stations[PARK_ID].prices == ()  # tariff left empty in the IRVE
    assert stations[PARK_ID].price_for(7.4) is None


def test_free_charge_points_cost_nothing() -> None:
    """`gratuit` wins over the free-text tariff."""
    row = load_json_fixture("irve_tabular.json")["data"][0] | {"gratuit": True}

    assert parse_irve_rows([row])[0].prices == ((22.0, 0.0),)


def test_rows_without_position_or_id_are_ignored() -> None:
    """Incomplete rows are skipped rather than guessed."""
    row = load_json_fixture("irve_tabular.json")["data"][0]
    rows = [row | {"consolidated_latitude": None}, row | {"id_station_itinerance": None, "id_station_local": None}]

    assert parse_irve_rows(rows) == []


def test_price_of_the_closest_power() -> None:
    """A station with several powers gives the price of the one shown."""
    station = IrveStation("FREX1", 45.1, 4.2, ((22.0, 0.35), (50.0, 0.49), (150.0, 0.59)))

    assert station.price_for(22) == 0.35
    assert station.price_for(60) == 0.49
    assert station.price_for(300) == 0.59


def test_nearest_station_within_30_m_only() -> None:
    """Stations are matched by position; one 50 m away is another station."""
    near = IrveStation("NEAR", 45.10018, 4.2, ())  # ~20 m
    far = IrveStation("FAR", 45.10045, 4.2, ())  # ~50 m

    assert nearest_station([far, near], 45.1, 4.2) is near
    assert nearest_station([far], 45.1, 4.2) is None


def _ranked(country_code: str = "FR", poi_id: str = "poi-1") -> RankedStation:
    station = Station(
        poi_id=poi_id,
        name="Example Recharge",
        latitude=45.1,
        longitude=4.2,
        connectors=(),
        availability_id=None,
        country_code=country_code,
    )
    return RankedStation(station, 10.0, 22.0, 1, 2, AvailabilityStatus.AVAILABLE)


class _Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


async def test_prices_are_cached_for_a_day(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """One IRVE lookup per station per day, "no IRVE station" included."""
    aioclient_mock.get(IRVE_URL, json=load_json_fixture("irve_tabular.json"))
    clock = _Clock()
    lookup = TariffLookup(IrveClient(async_get_clientsession(hass)), clock)

    first = await lookup.with_prices([_ranked()])
    assert first[0].price_per_kwh == 0.29
    clock.now += 23 * 3600
    await lookup.with_prices([_ranked()])
    assert aioclient_mock.call_count == 1

    clock.now += TARIFF_TTL_S
    await lookup.with_prices([_ranked()])
    assert aioclient_mock.call_count == 2


async def test_no_lookup_outside_france(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The IRVE covers France only: other stations are not looked up."""
    lookup = TariffLookup(IrveClient(async_get_clientsession(hass)), _Clock())

    result = await lookup.with_prices([_ranked(country_code="BE")])

    assert result[0].price_per_kwh is None
    assert aioclient_mock.call_count == 0


@pytest.mark.parametrize("failure", [{"status": 503}, {"exc": TimeoutError()}, {"text": "not json"}])
async def test_irve_failure_only_drops_the_price(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, failure: dict
) -> None:
    """The station stays, without price, and the failure is not cached."""
    aioclient_mock.get(IRVE_URL, **failure)
    lookup = TariffLookup(IrveClient(async_get_clientsession(hass)), _Clock())

    result = await lookup.with_prices([_ranked()])
    assert result == [replace(_ranked(), price_per_kwh=None)]

    await lookup.with_prices([_ranked()])
    assert aioclient_mock.call_count == 2  # retried at the next refresh


async def test_price_shown_and_only_the_station_position_is_sent(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The price is shown; the IRVE query is a small box around the station, not the car."""
    car = (45.1027, 4.2)  # ~300 m from the first station
    _set_position(hass, *car)
    _mock_tomtom(aioclient_mock, irve=load_json_fixture("irve_tabular.json"))
    entry = await _setup(hass)

    assert hass.states.get(STATION_1).state.endswith(" · 8/12 free · 0.29 €/kWh")
    assert hass.states.get(STATION_1).attributes["price_per_kwh"] == 0.29
    assert hass.states.get(STATION_2).attributes["price_per_kwh"] is None  # empty tariff

    queries = [c[1].query for c in aioclient_mock.mock_calls if str(c[1]).startswith(IRVE_URL)]
    assert len(queries) == 2  # the two shown stations
    for query in queries:
        lat_min = float(query["consolidated_latitude__greater"])
        lat_max = float(query["consolidated_latitude__less"])
        lon_min = float(query["consolidated_longitude__greater"])
        lon_max = float(query["consolidated_longitude__less"])
        assert lat_max - lat_min < 0.001 and lon_max - lon_min < 0.002
        assert not (lat_min <= car[0] <= lat_max)
    centres = sorted(
        (round((float(q["consolidated_latitude__greater"]) + float(q["consolidated_latitude__less"])) / 2, 4),
         round((float(q["consolidated_longitude__greater"]) + float(q["consolidated_longitude__less"])) / 2, 4))
        for q in queries
    )
    assert centres == [(45.092, 4.203), (45.1, 4.2)]

    await _move(hass, 45.105, 4.2)  # new refresh: prices come from the cache
    assert _calls(aioclient_mock, "/data/") == 2
    await _unload(hass, entry)
