"""Traits belonging to doorbell devices."""

from __future__ import annotations

import logging
from typing import Final

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel  # type: ignore

from .camera_traits import EventImage
from .event import DoorbellChimeEvent, ImageEventBase
from .traits import TRAIT_MAP

_LOGGER = logging.getLogger(__name__)


@TRAIT_MAP.register()
class DoorbellChimeTrait(BaseModel):
    """For any device that supports a doorbell chime and related press events."""

    NAME: Final = "sdm.devices.traits.DoorbellChime"
    EVENT_NAME: Final[str] = DoorbellChimeEvent.NAME

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
