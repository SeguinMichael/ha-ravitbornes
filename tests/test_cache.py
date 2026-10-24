"""Tests for the in-memory TTL cache."""

from custom_components.ravitbornes.cache import TTLCache


class FakeClock:
    """Manually advanced monotonic clock."""

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_value_expires_after_ttl() -> None:
    clock = FakeClock()
    cache: TTLCache[str] = TTLCache(180, clock=clock)

    cache.set("a", "value")
    clock.now += 179
    assert cache.get("a") == "value"
    clock.now += 1
    assert cache.get("a") is None


def test_missing_key() -> None:
    assert TTLCache(60).get("nope") is None


def test_expired_entries_are_dropped_on_set() -> None:
    """Memory stays bounded over a long trip."""
    clock = FakeClock()
    cache: TTLCache[int] = TTLCache(10, clock=clock)
    for index in range(5):
        cache.set(index, index)
    clock.now += 11
    cache.set("new", 1)

    assert len(cache) == 1
