"""Traits belonging to doorbell devices."""

from typing import Any, Mapping, Optional

from .camera_traits import CameraEventImageTrait, EventImage
from .event import DoorbellChimeEvent, EventTrait
from .traits import TRAIT_MAP, Command


@TRAIT_MAP.register()
class DoorbellChimeTrait(EventTrait):
    """For any device that supports a doorbell chime and related press events."""

    NAME = "sdm.devices.traits.DoorbellChime"
    EVENT_NAME = DoorbellChimeEvent.NAME

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize DoorbellChime."""
        super().__init__()
        self._data = data
        self._cmd = cmd
        self._event_image = CameraEventImageTrait({}, cmd)

    async def generate_active_event_image(self) -> Optional[EventImage]:
        """Provide a URL to download a camera image from the active event."""
        event = self.active_event
        if not event:
            return None
        assert event.event_id
        return await self._event_image.generate_image(event.event_id)
