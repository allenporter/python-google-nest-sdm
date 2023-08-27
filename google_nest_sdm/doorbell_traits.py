"""Traits belonging to doorbell devices."""

from __future__ import annotations

import logging
from typing import Final

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel  # type: ignore

from .event import DoorbellChimeEvent

_LOGGER = logging.getLogger(__name__)


class DoorbellChimeTrait(BaseModel):
    """For any device that supports a doorbell chime and related press events."""

    NAME: Final = "sdm.devices.traits.DoorbellChime"
    EVENT_NAME: Final[str] = DoorbellChimeEvent.NAME

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
