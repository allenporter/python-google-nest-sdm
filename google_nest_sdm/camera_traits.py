"""Traits belonging to camera devices."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import datetime
from enum import Enum
import logging
from typing import ClassVar
import urllib.parse as urlparse

from mashumaro import DataClassDictMixin, field_options
from mashumaro.config import BaseConfig
from mashumaro.types import SerializationStrategy

from .event import (
    CameraClipPreviewEvent,
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    EventImageContentType,
    EventImageType,
    EventType,
)
from .traits import CommandDataClass, TraitType
from .webrtc_util import fix_sdp_answer

__all__ = [
    "CameraImageTrait",
    "CameraLiveStreamTrait",
    "CameraEventImageTrait",
    "CameraMotionTrait",
    "CameraPersonTrait",
    "CameraSoundTrait",
    "CameraClipPreviewTrait",
    "Resolution",
    "Stream",
    "StreamUrls",
    "RtspStream",
    "WebRtcStream",
    "StreamingProtocol",
    "EventImage",
]

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


@dataclass
class CameraImageTrait(DataClassDictMixin):
    """This trait belongs to any device that supports taking images."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_IMAGE

    max_image_resolution: Resolution | None = field(
        metadata=field_options(alias="maxImageResolution"), default=None
    )
    """Maximum resolution of the camera image."""


@dataclass
class Stream(DataClassDictMixin, CommandDataClass, ABC):
    """Base class for streams."""

    expires_at: datetime.datetime = field(metadata=field_options(alias="expiresAt"))
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

    rtsp_url: str = field(metadata=field_options(alias="rtspUrl"))
    """RTSP live stream URL."""


@dataclass
class RtspStream(Stream):
    """Provides access an RTSP live stream URL."""

    stream_urls: StreamUrls = field(metadata=field_options(alias="streamUrls"))
    """Stream urls to access the live stream."""

    stream_token: str = field(metadata=field_options(alias="streamToken"))
    """Token to use to access an RTSP live stream."""

    stream_extension_token: str = field(
        metadata=field_options(alias="streamExtensionToken")
    )
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
        obj = RtspStream.from_dict(results)
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


@dataclass
class WebRtcStream(Stream):
    """Provides access an RTSP live stream URL."""

    answer_sdp: str = field(metadata=field_options(alias="answerSdp"))
    """An SDP answer to use with the local device displaying the stream."""

    media_session_id: str = field(metadata=field_options(alias="mediaSessionId"))
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
        obj = WebRtcStream.from_dict(results)
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


def _default_streaming_protocol() -> list[StreamingProtocol]:
    return [
        StreamingProtocol.RTSP,
    ]


class StreamingProtocolSerializationStrategy(
    SerializationStrategy, use_annotations=True
):
    """Parser for streaming protocols that ignores invalid values."""

    def serialize(self, value: list[StreamingProtocol]) -> list[str]:
        return [str(x.name) for x in value]

    def deserialize(self, value: list[str]) -> list[StreamingProtocol]:
        return [
            StreamingProtocol[x] for x in value if x in StreamingProtocol.__members__
        ] or _default_streaming_protocol()


@dataclass
class CameraLiveStreamTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to any device that supports live streaming."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_LIVE_STREAM

    max_video_resolution: Resolution = field(
        metadata=field_options(alias="maxVideoResolution"), default_factory=Resolution
    )
    """Maximum resolution of the video live stream."""

    video_codecs: list[str] = field(
        metadata=field_options(alias="videoCodecs"), default_factory=list
    )
    """Video codecs supported for the live stream."""

    audio_codecs: list[str] = field(
        metadata=field_options(alias="audioCodecs"), default_factory=list
    )
    """Audio codecs supported for the live stream."""

    supported_protocols: list[StreamingProtocol] = field(
        metadata=field_options(alias="supportedProtocols"),
        default_factory=_default_streaming_protocol,
    )
    """Streaming protocols supported for the live stream."""

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
        obj = RtspStream.from_dict(results)
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
        obj = WebRtcStream.from_dict(results)
        obj._cmd = self.cmd
        _LOGGER.debug("Received answer_sdp: %s", obj.answer_sdp)
        obj.answer_sdp = fix_sdp_answer(offer_sdp, obj.answer_sdp)
        _LOGGER.debug("Return answer_sdp: %s", obj.answer_sdp)
        return obj

    class Config(BaseConfig):
        serialization_strategy = {
            list[StreamingProtocol]: StreamingProtocolSerializationStrategy(),
        }
        serialize_by_alias = True


@dataclass
class EventImage(DataClassDictMixin, CommandDataClass):
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

    url: str | None = field(default=None)
    """URL to download the camera image from."""

    token: str | None = field(default=None)
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


@dataclass
class CameraEventImageTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to any device that generates images from events."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_EVENT_IMAGE

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


@dataclass
class CameraMotionTrait:
    """For any device that supports motion detection events."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_MOTION
    EVENT_NAME: ClassVar[EventType] = CameraMotionEvent.NAME


@dataclass
class CameraPersonTrait:
    """For any device that supports person detection events."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_PERSON
    EVENT_NAME: ClassVar[EventType] = CameraPersonEvent.NAME


@dataclass
class CameraSoundTrait:
    """For any device that supports sound detection events."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_SOUND
    EVENT_NAME: ClassVar[EventType] = CameraSoundEvent.NAME


@dataclass
class CameraClipPreviewTrait(DataClassDictMixin, CommandDataClass):
    """For any device that supports a clip preview."""

    NAME: ClassVar[TraitType] = TraitType.CAMERA_CLIP_PREVIEW
    EVENT_NAME: ClassVar[EventType] = CameraClipPreviewEvent.NAME

    async def generate_event_image(self, preview_url: str) -> EventImage | None:
        """Provide a URL to download a camera image from the active event."""
        img = EventImage(url=preview_url, event_image_type=EventImageType.CLIP_PREVIEW)
        img._cmd = self.cmd
        return img
