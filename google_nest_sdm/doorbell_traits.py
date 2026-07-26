"""Traits belonging to doorbell devices."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import ClassVar

from .event import DoorbellChimeEvent, EventType
from .traits import TraitType

_LOGGER = logging.getLogger(__name__)


@dataclass
class DoorbellChimeTrait:
    """For any device that supports a doorbell chime and related press events."""

    NAME: ClassVar[TraitType] = TraitType.DOORBELL_CHIME
    EVENT_NAME: ClassVar[EventType] = DoorbellChimeEvent.NAME
