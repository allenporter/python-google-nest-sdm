"""Diagnostics for debugging."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


class Diagnostics:
    """Information for the library."""

    def __init__(self) -> None:
        """Initialize Diagnostics."""
        self._counter: Counter = Counter()
        self._subkeys: dict[str, Diagnostics] = {}

    def increment(self, key: str) -> None:
        """Increment a counter for the spcified key/event."""
        self._counter.update(Counter({key: 1}))

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

    def reset(self) -> None:
        """Clear all diagnostics, for testing."""
        self._counter = Counter()
        for d in self._subkeys.values():
            d.reset()


SUBSCRIBER_DIAGNOSTICS = Diagnostics()
EVENT_DIAGNOSTICS = Diagnostics()
EVENT_MEDIA_DIAGNOSTICS = Diagnostics()

MAP = {
    "subscriber": SUBSCRIBER_DIAGNOSTICS,
    "event": EVENT_DIAGNOSTICS,
    "event_media": EVENT_MEDIA_DIAGNOSTICS,
}


def reset() -> None:
    """Clear all diagnostics, for testing."""
    for diagnostics in MAP.values():
        diagnostics.reset()


def get_diagnostics() -> dict[str, Any]:
    return {k: v.as_dict() for (k, v) in MAP.items() if v.as_dict()}


REDACT_KEYS = {
    "name",
    "customName",
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


def redact_data(data: Mapping) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}

    for key, value in redacted.items():
        if key in REDACT_KEYS:
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = redact_data(value)
        elif isinstance(value, list):
            redacted[key] = [redact_data(item) for item in value]

    return redacted
