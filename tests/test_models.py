"""Tests for parsing TomTom responses."""

from custom_components.ravitbornes.models import (
    ConnectorGroup,
    dedupe_stations,
    distance_m,
    parse_availability,
    parse_stations,
)

from .conftest import load_json_fixture


def test_parse_stations_aggregates_plugs() -> None:
    """One ConnectorGroup per (type, power, current), with a plug count."""
    stations = parse_stations(load_json_fixture("nearby_search.json"))

    assert len(stations) == 4
    park = stations[0]
    assert park.name == "Example Recharge"
    assert (park.latitude, park.longitude) == (45.1, 4.2)
    assert park.availability_id == "00000000-0000-4000-8000-000000000001"
    assert set(park.connectors) == {
        ConnectorGroup("IEC62196Type2Outlet", 22.0, "AC3", 3),
        ConnectorGroup("StandardHouseholdCountrySpecific", 2.0, "AC1", 1),
    }
    assert park.max_power_kw == 22.0
    assert park.address == "1 Example Street, 00000 Exampleville"


def test_parse_stations_keeps_dc_and_missing_availability() -> None:
    """DC current type is kept; a result without dataSources has no availability id."""
    stations = parse_stations(load_json_fixture("nearby_search.json"))

    assert stations[1].availability_id is None
    fast = stations[2]
    assert fast.max_power_kw == 150.0
    assert {group.current_type for group in fast.connectors} == {"DC"}


def test_parse_stations_skips_results_without_position() -> None:
    """A malformed result is ignored rather than crashing the parse."""
    assert parse_stations({"results": [{"id": "x", "poi": {"name": "No position"}}]}) == []
    assert parse_stations({}) == []


def test_dedupe_keeps_the_entry_with_availability() -> None:
    """Two results ~12 m apart are one park; the one with an availability id wins."""
    stations = parse_stations(load_json_fixture("nearby_search.json"))
    assert distance_m(45.1, 4.2, 45.1001, 4.20005) < 25

    # Order should not matter: put the duplicate without availability first.
    deduped = dedupe_stations([stations[1], stations[0], stations[2], stations[3]])

    assert [s.poi_id for s in deduped] == [
        "poi-example-park-a",
        "poi-example-fast",
        "poi-example-slow",
    ]


def test_parse_availability() -> None:
    """Counts are read per connector type and power level."""
    levels = parse_availability(load_json_fixture("charging_availability.json"))

    type2 = next(level for level in levels if level.connector_type == "IEC62196Type2Outlet")
    assert type2.power_kw == 22.0
    assert (type2.available, type2.occupied, type2.out_of_service) == (8, 2, 2)
    assert type2.total == 12
    assert len(levels) == 2
