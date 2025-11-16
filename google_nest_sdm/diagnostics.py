"""Diagnostics for debugging."""

from __future__ import annotations

import time
from collections import Counter
from collections.abc import Mapping
from contextlib import contextmanager
from typing import Any, Generator, TypeVar, cast

__all__ = [
    "get_diagnostics",
]


class Diagnostics:
    """Information for the library."""

    def __init__(self) -> None:
        """Initialize Diagnostics."""
        self._counter: Counter = Counter()
        self._subkeys: dict[str, Diagnostics] = {}

    def increment(self, key: str, count: int = 1) -> None:
        """Increment a counter for the specified key/event."""
        self._counter.update(Counter({key: count}))

    def elapsed(self, key_prefix: str, elapsed_ms: int = 1) -> None:
        """Track a latency event for the specified key/event prefix."""
        self.increment(f"{key_prefix}_count", 1)
        self.increment(f"{key_prefix}_sum", elapsed_ms)

    def as_dict(self) -> Mapping[str, Any]:
        """Return diagnostics as a debug dictionary."""
        data: dict[str, Any] = {k: self._counter[k] for k in self._counter}
        for k, d in self._subkeys.items():
            v = d.as_dict()
            if not v:
                continue
            data[k] = v
        return data

    def subkey(self, key: str) -> Diagnostics:
        """Return sub-Diagnositics object with the specified subkey."""
        if key not in self._subkeys:
            self._subkeys[key] = Diagnostics()
        return self._subkeys[key]

    @contextmanager
    def timer(self, key_prefix: str) -> Generator[None, None, None]:
        """A context manager that records the timing of operations as a diagnostic."""
        start = time.perf_counter()
        try:
            yield
        finally:
            end = time.perf_counter()
            ms = int((end - start) * 1000)
            self.elapsed(key_prefix, ms)

    def reset(self) -> None:
        """Clear all diagnostics, for testing."""
        self._counter = Counter()
        for d in self._subkeys.values():
            d.reset()


SUBSCRIBER_DIAGNOSTICS = Diagnostics()
DEVICE_MANAGER_DIAGNOSTICS = Diagnostics()
EVENT_DIAGNOSTICS = Diagnostics()
EVENT_MEDIA_DIAGNOSTICS = Diagnostics()
STREAMING_MANAGER_DIAGNOSTICS = Diagnostics()

MAP = {
    "subscriber": SUBSCRIBER_DIAGNOSTICS,
    "device_manager": DEVICE_MANAGER_DIAGNOSTICS,
    "event": EVENT_DIAGNOSTICS,
    "event_media": EVENT_MEDIA_DIAGNOSTICS,
    "streaming_manager": STREAMING_MANAGER_DIAGNOSTICS,
}


def reset() -> None:
    """Clear all diagnostics, for testing."""
    for diagnostics in MAP.values():
        diagnostics.reset()


def get_diagnostics() -> dict[str, Any]:
    """Produce diagnostics information for the library."""
    return {k: v.as_dict() for (k, v) in MAP.items() if v.as_dict()}


REDACT_KEYS = {
    "name",
    "custom_name",
    "displayName",
    "parent",
    "assignee",
    "subject",
    "object",
    "userId",
    "resourceGroup",
    "eventId",
    "eventSessionId",
    "eventThreadId",
}
REDACTED = "**REDACTED**"


T = TypeVar("T")


def redact_data(data: T) -> T | dict | list:
    """Redact sensitive data in a dict."""
    if not isinstance(data, (Mapping, list)):
        return data

    if isinstance(data, list):
        return cast(T, [redact_data(item) for item in data])

    redacted = {**data}

    for key, value in redacted.items():
        if key in REDACT_KEYS:
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = redact_data(value)
        elif isinstance(value, list):
            redacted[key] = [redact_data(item) for item in value]

    return redacted
