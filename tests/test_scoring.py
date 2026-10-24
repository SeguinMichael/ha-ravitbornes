"""Tests for station filtering and ranking (score v1)."""

from custom_components.ravitbornes.models import (
    ConnectorAvailability,
    dedupe_stations,
    parse_availability,
    parse_stations,
)
from custom_components.ravitbornes.scoring import (
    HIGHWAY,
    VISIT,
    AvailabilityStatus,
    rank_stations,
)

from .conftest import load_json_fixture

TYPE2 = {"IEC62196Type2Outlet"}
CCS = {"IEC62196Type2CCS"}
PARK_A = "00000000-0000-4000-8000-000000000001"
FAST = "00000000-0000-4000-8000-000000000003"
SLOW = "00000000-0000-4000-8000-000000000004"
ORIGIN = (45.1, 4.2)  # position of park A in the fixture


def _stations():
    """Park A, fast DC station (~2.7 km), slow AC station (~0.9 km)."""
    return dedupe_stations(parse_stations(load_json_fixture("nearby_search.json")))


def _level(ctype, power, available=0, occupied=0, out_of_service=0):
    return ConnectorAvailability(ctype, power, available, occupied, 0, 0, out_of_service)


def test_visit_orders_by_distance_and_filters_by_profile() -> None:
    """Type 2 car on visit: DC-only station and far stations are left out."""
    availability = {PARK_A: parse_availability(load_json_fixture("charging_availability.json"))}

    ranked = rank_stations(_stations(), availability, *ORIGIN, TYPE2, VISIT)

    assert [r.station.poi_id for r in ranked] == ["poi-example-park-a", "poi-example-slow"]
    park = ranked[0]
    assert park.status is AvailabilityStatus.AVAILABLE
    assert (park.available, park.total) == (8, 12)  # household plug not counted
    assert park.power_kw == 22.0
    assert 800 < ranked[1].distance_m < 1000


def test_station_without_free_compatible_connector_is_kept_but_unavailable() -> None:
    """A full station stays at its distance rank, flagged unavailable (greyed)."""
    availability = {
        # Only the household plug is free: useless for a Type 2 car.
        PARK_A: [
            _level("StandardHouseholdCountrySpecific", 2.0, available=1),
            _level("IEC62196Type2Outlet", 22.0, occupied=10, out_of_service=2),
        ],
        SLOW: [_level("IEC62196Type2Outlet", 7.0, available=1)],
    }

    ranked = rank_stations(_stations(), availability, *ORIGIN, TYPE2, VISIT)

    assert [r.status for r in ranked] == [
        AvailabilityStatus.UNAVAILABLE,
        AvailabilityStatus.AVAILABLE,
    ]
    assert ranked[0].available == 0


def test_missing_availability_is_unknown_not_unavailable() -> None:
    """No availability data must not grey a station out."""
    ranked = rank_stations(_stations(), {}, *ORIGIN, TYPE2, VISIT)

    assert {r.status for r in ranked} == {AvailabilityStatus.UNKNOWN}
    assert all(r.available is None for r in ranked)


def test_highway_keeps_only_compatible_dc() -> None:
    """CCS car on highway: only the CCS connectors of the fast station count."""
    availability = {
        FAST: [
            _level("IEC62196Type2CCS", 150.0, occupied=2),
            _level("Chademo", 50.0, available=1),
        ]
    }

    ranked = rank_stations(_stations(), availability, *ORIGIN, CCS, HIGHWAY)

    assert [r.station.poi_id for r in ranked] == ["poi-example-fast"]
    fast = ranked[0]
    assert fast.power_kw == 150.0
    assert fast.status is AvailabilityStatus.UNAVAILABLE  # the free plug is CHAdeMO


def test_highway_excludes_ac_even_if_connector_matches() -> None:
    """The highway profile is DC only."""
    assert rank_stations(_stations(), {}, *ORIGIN, TYPE2, HIGHWAY) == []


def test_limit() -> None:
    """At most `limit` stations, the nearest first."""
    ranked = rank_stations(_stations(), {}, *ORIGIN, TYPE2, VISIT, limit=1)

    assert [r.station.poi_id for r in ranked] == ["poi-example-park-a"]
