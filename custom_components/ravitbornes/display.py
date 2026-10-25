"""Short texts for the car display (Android Auto rows have little room)."""

from __future__ import annotations

from .scoring import AvailabilityStatus, RankedStation

MAX_NAME_LENGTH = 40

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


def format_station(item: RankedStation, language: str) -> str:
    """One-line summary, e.g. 'Ionity · 150 kW · 1.2 km · 3/6 free'.

    When only slower connectors are free, the free power comes first:
    'Ionity · 50 kW free (max 350) · 0.1 km · 1/5' (decision 2026-10-25).
    A station with no compatible connector free reads "full": this is the
    text form of the greyed row until the Android Auto test says otherwise.
    """
    lang = _language(language)
    words = _WORDS[lang]
    name = item.station.name[:MAX_NAME_LENGTH] or "?"
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
