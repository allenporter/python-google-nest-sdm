"""Traits belonging to camera devices."""

from __future__ import annotations

import datetime
import logging
import urllib.parse as urlparse
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Final

try:
    from pydantic.v1 import BaseModel, Field, validator
except ImportError:
    from pydantic import BaseModel, Field, validator  # type: ignore

from .event import (
    CameraClipPreviewEvent,
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    EventImageContentType,
    EventImageType,
    EventTrait,
    ImageEventBase,
)
from .traits import TRAIT_MAP, CommandModel

_LOGGER = logging.getLogger(__name__)

MAX_IMAGE_RESOLUTION = "maxImageResolution"
MAX_VIDEO_RESOLUTION = "maxVideoResolution"
WIDTH = "width"
HEIGHT = "height"
VIDEO_CODECS = "videoCodecs"
AUDIO_CODECS = "audioCodecs"
SUPPORTED_PROTOCOLS = "supportedProtocols"
STREAM_URLS = "streamUrls"
RESULTS = "results"
RTSP_URL = "rtspUrl"
STREAM_EXTENSION_TOKEN = "streamExtensionToken"
STREAM_TOKEN = "streamToken"
URL = "url"
TOKEN = "token"
ANSWER_SDP = "answerSdp"
MEDIA_SESSION_ID = "mediaSessionId"

EVENT_IMAGE_CLIP_PREVIEW = "clip_preview"


@dataclass
class Resolution:
    """Maximum Resolution of an image or stream."""

    width: int | None = None
    height: int | None = None


@TRAIT_MAP.register()
class CameraImageTrait(BaseModel):
    """This trait belongs to any device that supports taking images."""

    NAME: Final = "sdm.devices.traits.CameraImage"

    max_image_resolution: Resolution = Field(alias="maxImageResolution")
    """Maximum resolution of the camera image."""


class Stream(CommandModel, ABC):
    """Base class for streams."""

    expires_at: datetime.datetime = Field(alias="expiresAt")
    """Time at which both streamExtensionToken and streamToken expire."""

    @abstractmethod
    async def extend_stream(self) -> Stream:
        """Extend the lifetime of the stream."""

    @abstractmethod
    async def stop_stream(self) -> None:
        """Invalidate the stream."""


@dataclass
class StreamUrls:
    """Response object for stream urls"""

    rtsp_url: str = Field(alias="rtspUrl")
    """RTSP live stream URL."""


class RtspStream(Stream):
    """Provides access an RTSP live stream URL."""

    stream_urls: StreamUrls = Field(alias="streamUrls")
    """Stream urls to access the live stream."""

    stream_token: str = Field(alias="streamToken")
    """Token to use to access an RTSP live stream."""

    stream_extension_token: str = Field(alias="streamExtensionToken")
    """Token to use to extend access to an RTSP live stream."""

    @property
    def rtsp_stream_url(self) -> str:
        """RTSP live stream URL."""
        return self.stream_urls.rtsp_url

    async def extend_stream(self) -> Stream | RtspStream:
        """Extend the lifetime of the stream."""
        return await self.extend_rtsp_stream()

    async def extend_rtsp_stream(self) -> RtspStream:
        """Request a new RTSP live stream URL access token."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        response_data = await self.cmd.execute_json(data)
        results = response_data[RESULTS]
        # Update the stream url with the new token
        stream_token = results[STREAM_TOKEN]
        parsed = urlparse.urlparse(self.rtsp_stream_url)
        parsed = parsed._replace(query=f"auth={stream_token}")
        url = urlparse.urlunparse(parsed)
        results[STREAM_URLS] = {}
        results[STREAM_URLS][RTSP_URL] = url
        obj = RtspStream(**results)
        obj._cmd = self.cmd
        return obj

    async def stop_stream(self) -> None:
        """Invalidate the stream."""
        return await self.stop_rtsp_stream()

    async def stop_rtsp_stream(self) -> None:
        """Invalidates a valid RTSP access token and stops the RTSP live stream."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.StopRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        await self.cmd.execute(data)


class WebRtcStream(Stream):
    """Provides access an RTSP live stream URL."""

    answer_sdp: str = Field(alias="answerSdp")
    """An SDP answer to use with the local device displaying the stream."""

    media_session_id: str = Field(alias="mediaSessionId")
    """Media Session ID of the live stream."""

    async def extend_stream(self) -> WebRtcStream:
        """Request a new RTSP live stream URL access token."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
            "params": {MEDIA_SESSION_ID: self.media_session_id},
        }
        response_data = await self.cmd.execute_json(data)
        # Preserve original answerSdp, and merge with response that contains
        # the other fields (expiresAt, and mediaSessionId.
        results = response_data[RESULTS]
        results[ANSWER_SDP] = self.answer_sdp
        obj = WebRtcStream(**results)
        obj._cmd = self.cmd
        return obj

    async def stop_stream(self) -> None:
        """Invalidates a valid RTSP access token and stops the RTSP live stream."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.StopWebRtcStream",
            "params": {MEDIA_SESSION_ID: self.media_session_id},
        }
        await self.cmd.execute(data)


class StreamingProtocol(str, Enum):
    """Streaming protocols supported by the device."""

    RTSP = "RTSP"
    WEB_RTC = "WEB_RTC"


@TRAIT_MAP.register()
class CameraLiveStreamTrait(CommandModel):
    """This trait belongs to any device that supports live streaming."""

    NAME: Final = "sdm.devices.traits.CameraLiveStream"

    max_video_resolution: Resolution = Field(
        alias="maxVideoResolution", default_factory=dict
    )
    """Maximum resolution of the video live stream."""

    video_codecs: list[str] = Field(alias="videoCodecs", default_factory=list)
    """Video codecs supported for the live stream."""

    audio_codecs: list[str] = Field(alias="audioCodecs", default_factory=list)
    """Audio codecs supported for the live stream."""

    supported_protocols: list[StreamingProtocol] = Field(
        alias="supportedProtocols",
        default_factory=list,
    )
    """Streaming protocols supported for the live stream."""

    @validator("supported_protocols", pre=True, always=True)
    def validate_supported_protocols(
        cls, val: Iterable[str] | None
    ) -> list[StreamingProtocol]:
        return [
            StreamingProtocol[x]
            for x in val or []
            if x in StreamingProtocol.__members__
        ] or [StreamingProtocol.RTSP]

    async def generate_rtsp_stream(self) -> RtspStream:
        """Request a token to access an RTSP live stream URL."""
        if StreamingProtocol.RTSP not in self.supported_protocols:
            raise ValueError("Device does not support RTSP stream")
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
            "params": {},
        }
        response_data = await self.cmd.execute_json(data)
        results = response_data[RESULTS]
        obj = RtspStream(**results)
        obj._cmd = self.cmd
        return obj

    async def generate_web_rtc_stream(self, offer_sdp: str) -> WebRtcStream:
        """Request a token to access a Web RTC live stream URL."""
        if StreamingProtocol.WEB_RTC not in self.supported_protocols:
            raise ValueError("Device does not support WEB_RTC stream")
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream",
            "params": {"offerSdp": offer_sdp},
        }
        response_data = await self.cmd.execute_json(data)
        results = response_data[RESULTS]
        obj = WebRtcStream(**results)
        obj._cmd = self.cmd
        return obj


class EventImage(CommandModel):
    """Provides access to an image in response to an event.

    Use a ?width or ?height query parameters to customize the resolution
    of the downloaded image. Only one of these parameters need to specified.
    The other parameter is scaled automatically according to the camera's
    aspect ratio.

    The token should be added as an HTTP header:
    Authorization: Basic <token>
    """

    event_image_type: EventImageContentType
    """Return the type of event image."""

    url: str | None = Field(default=None)
    """URL to download the camera image from."""

    token: str | None = Field(default=None)
    """Token to use in the HTTP Authorization header when downloading."""

    async def contents(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> bytes:
        """Download the image bytes."""
        if width:
            fetch_url = f"{self.url}?width={width}"
        elif height:
            fetch_url = f"{self.url}?width={height}"
        else:
            assert self.url
            fetch_url = self.url
        return await self.cmd.fetch_image(fetch_url, basic_auth=self.token)


class EventImageCreator(ABC):
    """Responsible for turning events into an EventImage."""

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide an object that can be used to fetch media for an event."""


@TRAIT_MAP.register()
class CameraEventImageTrait(CommandModel, EventImageCreator):
    """This trait belongs to any device that generates images from events."""

    NAME: Final = "sdm.devices.traits.CameraEventImage"

    async def generate_image(self, event_id: str) -> EventImage:
        """Provide a URL to download a camera image."""
        data = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {
                "eventId": event_id,
            },
        }
        response_data = await self.cmd.execute_json(data)
        results = response_data[RESULTS]
        img = EventImage(**results, event_image_type=EventImageType.IMAGE)
        img._cmd = self.cmd
        return img

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from an event."""
        return await self.generate_image(event.event_id)


class EventImageGenerator(EventTrait, EventImageCreator, ABC):
    """Parenet class for a trait that generates an images from events."""

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Event types supported by this trait."""

    async def generate_active_event_image(self) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        event = self.active_event
        if not event:
            _LOGGER.debug("No active event")
            return None
        return await self.generate_event_image(event)


@TRAIT_MAP.register()
class CameraMotionTrait(BaseModel, EventImageGenerator):
    """For any device that supports motion detection events."""

    NAME: Final = "sdm.devices.traits.CameraMotion"
    EVENT_NAME: Final[str] = CameraMotionEvent.NAME
    event_type: Final[str] = CameraMotionEvent.NAME
    event_image_creator: EventImageCreator | None = None

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        if not isinstance(event, CameraMotionEvent):
            return None
        assert event.event_id
        if not self.event_image_creator:
            raise ValueError("Camera does not have trait to fetch snapshots")
        return await self.event_image_creator.generate_event_image(event)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


@TRAIT_MAP.register()
class CameraPersonTrait(BaseModel, EventImageGenerator):
    """For any device that supports person detection events."""

    NAME: Final = "sdm.devices.traits.CameraPerson"
    EVENT_NAME: Final[str] = CameraPersonEvent.NAME
    event_type: Final[str] = CameraPersonEvent.NAME
    event_image_creator: EventImageCreator | None = None

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        if not isinstance(event, CameraPersonEvent):
            return None
        assert event.event_id
        if not self.event_image_creator:
            raise ValueError("Camera does not have trait to fetch snapshots")
        return await self.event_image_creator.generate_event_image(event)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


@TRAIT_MAP.register()
class CameraSoundTrait(BaseModel, EventImageGenerator):
    """For any device that supports sound detection events."""

    NAME: Final = "sdm.devices.traits.CameraSound"
    EVENT_NAME: Final[str] = CameraSoundEvent.NAME
    event_type: Final[str] = CameraSoundEvent.NAME
    event_image_creator: EventImageCreator | None = None

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        if not isinstance(event, CameraSoundEvent):
            return None
        assert event.event_id
        if not self.event_image_creator:
            raise ValueError("Camera does not have trait to fetch snapshots")
        return await self.event_image_creator.generate_event_image(event)

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True


@TRAIT_MAP.register()
class CameraClipPreviewTrait(CommandModel, EventImageGenerator):
    """For any device that supports a clip preview."""

    NAME: Final = "sdm.devices.traits.CameraClipPreview"
    EVENT_NAME: Final[str] = CameraClipPreviewEvent.NAME
    event_type: Final[str] = CameraClipPreviewEvent.NAME

    async def generate_event_image(self, event: ImageEventBase) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        preview_event: CameraClipPreviewEvent | None = None
        if isinstance(event, CameraClipPreviewEvent):
            preview_event = event
        else:
            for session_event in event.session_events:
                if isinstance(session_event, CameraClipPreviewEvent):
                    preview_event = session_event
                    break
            if preview_event is None:
                _LOGGER.debug(
                    "Event did not contain fetchable camera clip preview: %s", event
                )
                return None
        # Clip preview events have the url baked in without an additional
        # step to generate the image
        assert preview_event
        img = EventImage(
            url=preview_event.preview_url, event_image_type=EventImageType.CLIP_PREVIEW
        )
        img._cmd = self.cmd
        return img
