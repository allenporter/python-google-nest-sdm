"""Traits belonging to doorbell devices."""

from typing import Any, Mapping, Optional

from .camera_traits import CameraEventImageTrait, EventImage, EventImageGenerator
from .event import DoorbellChimeEvent, ImageEventBase
from .traits import TRAIT_MAP, Command


@TRAIT_MAP.register()
class DoorbellChimeTrait(EventImageGenerator):
    """For any device that supports a doorbell chime and related press events."""

    NAME = "sdm.devices.traits.DoorbellChime"
    EVENT_NAME = DoorbellChimeEvent.NAME
    event_type = EVENT_NAME

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize DoorbellChime."""
        super().__init__()
        self._data = data
        self._event_image = CameraEventImageTrait({}, cmd)

    async def generate_event_image(self, event: ImageEventBase) -> Optional[EventImage]:
        """Provide a URL to download a camera image from the active event."""
        if not isinstance(event, DoorbellChimeEvent):
            return None
        assert event.event_id
        return await self._event_image.generate_image(event.event_id)
