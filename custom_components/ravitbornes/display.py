"""Short texts for the car display (Android Auto rows have little room)."""

from __future__ import annotations

import re
import unicodedata

from .models import Station
from .scoring import AvailabilityStatus, RankedStation

# Longer network names are replaced by their initials (decision 2026-10-25).
MAX_NETWORK_LENGTH = 20
MAX_STREET_LENGTH = 30
_STOPWORDS = {"de", "des", "du", "d", "la", "le", "les", "l", "et", "of", "the", "and"}

# Free-form sensor states cannot use Home Assistant translations.
_WORDS = {
    "en": {"free": "free", "free_one": "free", "full": "full", "unknown": "availability ?"},
    "fr": {"free": "libres", "free_one": "libre", "full": "complet", "unknown": "dispo ?"},
}


def _language(language: str) -> str:
    return "fr" if language.lower().startswith("fr") else "en"


def _number(value: float, language: str) -> str:
    text = f"{value:g}"
    return text.replace(".", ",") if language == "fr" else text


def network_name(name: str) -> str:
    """Short network name: kept if short, otherwise its initials.

    'Syndicat Départemental Des Énergies De Seine-Et-Marne' -> 'SDESM'.
    """
    if len(name) <= MAX_NETWORK_LENGTH:
        return name
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = [w for w in re.split(r"[\s\-'’]+", plain) if w and w.lower() not in _STOPWORDS]
    initials = "".join(word[0] for word in words).upper()
    return initials if len(initials) >= 2 else name[:MAX_NETWORK_LENGTH]


def station_label(station: Station) -> str:
    """'Network (street)', e.g. 'IONITY (A77, Aire du Jardin des Arbres)'."""
    network = network_name(station.name) or "?"
    street = station.street
    if len(street) > MAX_STREET_LENGTH:
        street = street[: MAX_STREET_LENGTH - 1].rstrip() + "…"
    return f"{network} ({street})" if street else network


def format_station(item: RankedStation, language: str) -> str:
    """One-line summary, e.g. 'IONITY (A6, Rest Area) · 150 kW · 1.2 km · 3/6 free'.

    When only slower connectors are free, the free power comes first:
    '… · 50 kW free (max 350) · 0.1 km · 1/5' (decision 2026-10-25).
    A station with no compatible connector free reads "full": this is the
    text form of the greyed row until the Android Auto test says otherwise.
    """
    lang = _language(language)
    words = _WORDS[lang]
    name = station_label(item.station)
    power = _number(item.power_kw, lang)
    distance = _number(round(item.distance_m / 1000, 1), lang)
    if (
        item.status is AvailabilityStatus.AVAILABLE
        and item.free_power_kw is not None
        and item.free_power_kw < item.power_kw
    ):
        free_power = _number(item.free_power_kw, lang)
        return (
            f"{name} · {free_power} kW {words['free_one']} (max {power}) · "
            f"{distance} km · {item.available}/{item.total}"
        )
    if item.status is AvailabilityStatus.AVAILABLE:
        availability = f"{item.available}/{item.total} {words['free']}"
    elif item.status is AvailabilityStatus.UNAVAILABLE:
        availability = words["full"]
    else:
        availability = words["unknown"]
    return f"{name} · {power} kW · {distance} km · {availability}"
