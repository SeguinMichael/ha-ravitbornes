"""Tests for the texts shown in the car."""

from dataclasses import replace

from custom_components.ravitbornes.display import format_station, network_name, station_label
from custom_components.ravitbornes.models import ConnectorGroup, Station
from custom_components.ravitbornes.scoring import AvailabilityStatus, RankedStation

STATION = Station(
    poi_id="poi",
    name="Example Fast Charge",
    latitude=45.1,
    longitude=4.2,
    connectors=(ConnectorGroup("IEC62196Type2CCS", 150.0, "DC", 6),),
    availability_id="id",
)


def _ranked(status, available=None, total=None, distance_m=1234.0, power_kw=150.0):
    return RankedStation(STATION, distance_m, power_kw, available, total, status)


def test_available_english_and_french() -> None:
    item = _ranked(AvailabilityStatus.AVAILABLE, available=3, total=6)

    assert format_station(item, "en") == "Example Fast Charge · 150 kW · 1.2 km · 3/6 free"
    assert format_station(item, "fr") == "Example Fast Charge · 150 kW · 1,2 km · 3/6 libres"


def test_unavailable_reads_full() -> None:
    """Text form of the greyed row."""
    item = _ranked(AvailabilityStatus.UNAVAILABLE, available=0, total=6)

    assert format_station(item, "en").endswith("· full")
    assert format_station(item, "fr-FR").endswith("· complet")


def test_unknown_availability() -> None:
    assert format_station(_ranked(AvailabilityStatus.UNKNOWN), "fr").endswith("· dispo ?")


def test_decimal_separator() -> None:
    item = _ranked(AvailabilityStatus.UNKNOWN, distance_m=0.0, power_kw=7.4)

    assert " · 7,4 kW · 0 km · " in format_station(item, "fr")
    assert " · 7.4 kW · 0 km · " in format_station(item, "en")


def test_long_single_word_names_are_truncated() -> None:
    station = replace(STATION, name="X" * 100)
    item = RankedStation(station, 0.0, 150.0, None, None, AvailabilityStatus.UNKNOWN)

    assert format_station(item, "en").startswith("X" * 20 + " · ")


def test_label_is_network_then_street() -> None:
    """Decision 2026-10-25: 'Network (street)'; long network names become initials."""
    public = replace(
        STATION,
        name="Syndicat Départemental Des Énergies De Seine-Et-Marne",
        street="Place Notre Dame",
    )
    assert station_label(public) == "SDESM (Place Notre Dame)"
    assert station_label(replace(STATION, name="IONITY", street="A00, Example Rest Area")) == (
        "IONITY (A00, Example Rest Area)"
    )
    assert station_label(STATION) == "Example Fast Charge"  # no street known


def test_long_streets_are_shortened() -> None:
    label = station_label(replace(STATION, name="Izivia", street="A" * 50))

    assert label == "Izivia (" + "A" * 29 + "…)"


def test_network_name_initials() -> None:
    assert network_name("TotalEnergies") == "TotalEnergies"
    assert network_name("Compagnie Nationale du Rhône Recharge") == "CNRR"


def test_only_slower_connectors_free() -> None:
    """Decision 2026-10-25: show the free power first, the max in brackets."""
    item = RankedStation(
        STATION, 141.0, 350.0, 1, 5, AvailabilityStatus.AVAILABLE, free_power_kw=50.0
    )

    assert format_station(item, "fr") == "Example Fast Charge · 50 kW libre (max 350) · 0,1 km · 1/5"
    assert format_station(item, "en") == "Example Fast Charge · 50 kW free (max 350) · 0.1 km · 1/5"


def test_best_power_free_keeps_the_short_form() -> None:
    item = RankedStation(
        STATION, 141.0, 350.0, 2, 5, AvailabilityStatus.AVAILABLE, free_power_kw=350.0
    )

    assert format_station(item, "fr") == "Example Fast Charge · 350 kW · 0,1 km · 2/5 libres"
