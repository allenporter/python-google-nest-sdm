"""Traits belonging to doorbell devices."""

from __future__ import annotations

import logging
from typing import Final

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel  # type: ignore

from .camera_traits import EventImage, EventImageCreator, EventImageGenerator
from .event import DoorbellChimeEvent, ImageEventBase
from .traits import TRAIT_MAP

_LOGGER = logging.getLogger(__name__)


@TRAIT_MAP.register()
class DoorbellChimeTrait(BaseModel, EventImageGenerator):
    """For any device that supports a doorbell chime and related press events."""

    NAME: Final = "sdm.devices.traits.DoorbellChime"
    EVENT_NAME: Final[str] = DoorbellChimeEvent.NAME
    event_type: Final[str] = DoorbellChimeEvent.NAME
    event_image_creator: EventImageCreator | None = None

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        _LOGGER.debug("Generating image for event")
        if not isinstance(event, DoorbellChimeEvent):
            return None
        assert event.event_id
        if not self.event_image_creator:
            raise ValueError("Camera does not have trait to fetch snapshots")
        return await self.event_image_creator.generate_event_image(event)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
