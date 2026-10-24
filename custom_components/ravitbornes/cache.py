"""Small in-memory cache with a time-to-live, scoped to the running integration."""

from __future__ import annotations

from collections.abc import Callable, Hashable
import time


class TTLCache[V]:
    """Values expire ttl_s seconds after being set. Nothing is persisted."""

    def __init__(self, ttl_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        """Initialize the cache; the clock is injectable for tests."""
        self._ttl = ttl_s
        self._clock = clock
        self._items: dict[Hashable, tuple[float, V]] = {}

    def get(self, key: Hashable) -> V | None:
        """Return the value, or None if missing or expired."""
        item = self._items.get(key)
        if item is None:
            return None
        expires, value = item
        if self._clock() >= expires:
            del self._items[key]
            return None
        return value

    def set(self, key: Hashable, value: V) -> None:
        """Store a value and drop expired ones, so memory stays bounded."""
        now = self._clock()
        for expired in [k for k, (exp, _) in self._items.items() if exp <= now]:
            del self._items[expired]
        self._items[key] = (now + self._ttl, value)

    def __len__(self) -> int:
        """Number of stored entries (expired ones included until the next set)."""
        return len(self._items)
