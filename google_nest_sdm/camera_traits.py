"""Traits belonging to camera devices."""

from __future__ import annotations

import datetime
import urllib.parse as urlparse
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, List, Mapping, Optional, cast

from .event import CameraMotionEvent, CameraPersonEvent, CameraSoundEvent, EventTrait
from .traits import TRAIT_MAP, Command
from .typing import cast_assert, cast_optional

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
EXPIRES_AT = "expiresAt"
ANSWER_SDP = "answerSdp"
MEDIA_SESSION_ID = "mediaSessionId"


class Resolution:
    """Maximum Resolution of an image or stream."""

    width: Optional[int] = None
    height: Optional[int] = None


@TRAIT_MAP.register()
class CameraImageTrait:
    """This trait belongs to any device that supports taking images."""

    NAME = "sdm.devices.traits.CameraImage"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraImageTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def max_image_resolution(self) -> Resolution:
        """Maximum resolution of the camera image."""
        res = Resolution()
        res.width = self._data[MAX_IMAGE_RESOLUTION][WIDTH]
        res.height = self._data[MAX_IMAGE_RESOLUTION][HEIGHT]
        return res


class Stream(ABC):
    """Base class for streams."""

    def __init__(self, data: Mapping[str, Any]):
        self._data = data

    @property
    def expires_at(self) -> datetime.datetime:
        """Time at which both streamExtensionToken and streamToken expire."""
        expires_at = self._data[EXPIRES_AT]
        return datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    @abstractmethod
    async def extend_stream(self) -> Stream:
        """Extend the lifetime of the stream."""
        raise NotImplementedError

    @abstractmethod
    async def stop_stream(self) -> None:
        """Invalidate the stream."""
        raise NotImplementedError


class RtspStream(Stream):
    """Provides access an RTSP live stream URL."""

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize RstpStream."""
        super().__init__(data)
        self._cmd = cmd

    @property
    def rtsp_stream_url(self) -> str:
        """RTSP live stream URL."""
        rtsp_stream_url = self._data[STREAM_URLS][RTSP_URL]
        assert isinstance(rtsp_stream_url, str)
        return rtsp_stream_url

    @property
    def stream_token(self) -> str:
        """Token to use to access an RTSP live stream."""
        stream_token = self._data[STREAM_TOKEN]
        assert isinstance(stream_token, str)
        return stream_token

    @property
    def stream_extension_token(self) -> str:
        """Token to use to access an RTSP live stream."""
        return cast_assert(str, self._data[STREAM_EXTENSION_TOKEN])

    async def extend_stream(self) -> Stream | RtspStream:
        """Extend the lifetime of the stream."""
        return await self.extend_rtsp_stream()

    async def extend_rtsp_stream(self) -> RtspStream:
        """Request a new RTSP live stream URL access token."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        resp = await self._cmd.execute(data)
        response_data = await resp.json()
        results = response_data[RESULTS]
        # Update the stream url with the new token
        stream_token = results[STREAM_TOKEN]
        parsed = urlparse.urlparse(self.rtsp_stream_url)
        parsed = parsed._replace(query=f"auth={stream_token}")
        url = urlparse.urlunparse(parsed)
        results[STREAM_URLS] = {}
        results[STREAM_URLS][RTSP_URL] = url
        return RtspStream(results, self._cmd)

    async def stop_stream(self) -> None:
        """Invalidate the stream."""
        return await self.stop_rtsp_stream()

    async def stop_rtsp_stream(self) -> None:
        """Invalidates a valid RTSP access token and stops the RTSP live stream."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.StopRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        await self._cmd.execute(data)


class WebRtcStream(Stream):
    """Provides access an RTSP live stream URL."""

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize RstpStream."""
        super().__init__(data)
        self._cmd = cmd

    @property
    def answer_sdp(self) -> str:
        """An SDP answer to use with the local device dispalying the stream."""
        answer_sdp = self._data[ANSWER_SDP]
        assert isinstance(answer_sdp, str)
        return answer_sdp

    @property
    def media_session_id(self) -> str:
        """Media Session ID of the live stream."""
        media_session_id = self._data[MEDIA_SESSION_ID]
        assert isinstance(media_session_id, str)
        return media_session_id

    async def extend_stream(self) -> WebRtcStream:
        """Request a new RTSP live stream URL access token."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendWebRtcStream",
            "params": {MEDIA_SESSION_ID: self.media_session_id},
        }
        resp = await self._cmd.execute(data)
        response_data = await resp.json()
        # Preserve original answerSdp, and merge with response that contains
        # the other fields (expiresAt, and mediaSessionId.
        results = response_data[RESULTS]
        results[ANSWER_SDP] = self.answer_sdp
        return WebRtcStream(results, self._cmd)

    async def stop_stream(self) -> None:
        """Invalidates a valid RTSP access token and stops the RTSP live stream."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.StopWebRtcStream",
            "params": {MEDIA_SESSION_ID: self.media_session_id},
        }
        await self._cmd.execute(data)


class StreamingProtocol(Enum):
    """Streaming protocols supported by the device."""

    RTSP = (1,)
    WEB_RTC = (2,)


@TRAIT_MAP.register()
class CameraLiveStreamTrait:
    """This trait belongs to any device that supports live streaming."""

    NAME = "sdm.devices.traits.CameraLiveStream"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraLiveStreamTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def max_video_resolution(self) -> Resolution:
        """Maximum resolution of the video live stream."""
        res = Resolution()
        res.width = self._data[MAX_VIDEO_RESOLUTION][WIDTH]
        res.height = self._data[MAX_VIDEO_RESOLUTION][HEIGHT]
        return res

    @property
    def video_codecs(self) -> List[str]:
        """Video codecs supported for the live stream."""
        assert isinstance(self._data[VIDEO_CODECS], list)
        return cast(List[str], self._data[VIDEO_CODECS])

    @property
    def audio_codecs(self) -> List[str]:
        """Audio codecs supported for the live stream."""
        return cast(List[str], self._data[AUDIO_CODECS])

    @property
    def supported_protocols(self) -> List[StreamingProtocol]:
        """Streaming protocols supported for the live stream."""
        return [
            StreamingProtocol[x]
            for x in self._data.get(SUPPORTED_PROTOCOLS, ["RTSP"])
            if x in StreamingProtocol.__members__
        ]

    async def generate_rtsp_stream(self) -> RtspStream:
        """Request a token to access an RTSP live stream URL."""
        if StreamingProtocol.RTSP not in self.supported_protocols:
            raise ValueError("Device does not support RTSP stream")
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
            "params": {},
        }
        resp = await self._cmd.execute(data)
        response_data = await resp.json()
        results = response_data[RESULTS]
        return RtspStream(results, self._cmd)

    async def generate_web_rtc_stream(self, offer_sdp: str) -> WebRtcStream:
        """Request a token to access a Web RTC live stream URL."""
        if StreamingProtocol.WEB_RTC not in self.supported_protocols:
            raise ValueError("Device does not support WEB_RTC stream")
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateWebRtcStream",
            "params": {"offerSdp": offer_sdp},
        }
        resp = await self._cmd.execute(data)
        response_data = await resp.json()
        results = response_data[RESULTS]
        return WebRtcStream(results, self._cmd)


class EventImage:
    """Provides access to an image in response to an event.

    Use a ?width or ?height query parameters to customize the resolution
    of the downloaded image. Only one of these parameters need to specified.
    The other parameter is scaled automatically according to the camera's
    aspect ratio.

    The token should be added as an HTTP header:
    Authorization: Basic <token>
    """

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize the EventImage."""
        self._data = data
        self._cmd = cmd

    @property
    def url(self) -> Optional[str]:
        """URL to download the camera image from."""
        return cast_optional(str, self._data.get(URL))

    @property
    def token(self) -> Optional[str]:
        """Token to use in the HTTP Authorization header when downloading."""
        return cast_optional(str, self._data.get(TOKEN))

    async def contents(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> bytes:
        """Download the image bytes."""
        if width:
            fetch_url = f"{self.url}?width={width}"
        elif height:
            fetch_url = f"{self.url}?width={height}"
        else:
            assert self.url
            fetch_url = self.url
        return await self._cmd.fetch_image(fetch_url, basic_auth=self.token)


@TRAIT_MAP.register()
class CameraEventImageTrait:
    """This trait belongs to any device that generates images from events."""

    NAME = "sdm.devices.traits.CameraEventImage"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraEventImageTrait."""
        self._data = data
        self._cmd = cmd

    async def generate_image(self, event_id: str) -> EventImage:
        """Provide a URL to download a camera image from."""
        data = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {
                "eventId": event_id,
            },
        }
        resp = await self._cmd.execute(data)
        response_data = await resp.json()
        results = response_data[RESULTS]
        return EventImage(results, self._cmd)


class EventImageGenerator(ABC):
    """Parenet class for a trait that generates an images from events."""

    async def generate_active_event_image(self) -> Optional[EventImage]:
        """Provide a URL to download a camera image from the active event."""


@TRAIT_MAP.register()
class CameraMotionTrait(EventTrait, EventImageGenerator):
    """For any device that supports motion detection events."""

    NAME = "sdm.devices.traits.CameraMotion"
    EVENT_NAME = CameraMotionEvent.NAME

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraMotionTrait."""
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


@TRAIT_MAP.register()
class CameraPersonTrait(EventTrait, EventImageGenerator):
    """For any device that supports person detection events."""

    NAME = "sdm.devices.traits.CameraPerson"
    EVENT_NAME = CameraPersonEvent.NAME

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraPersonTrait."""
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


@TRAIT_MAP.register()
class CameraSoundTrait(EventTrait, EventImageGenerator):
    """For any device that supports sound detection events."""

    NAME = "sdm.devices.traits.CameraSound"
    EVENT_NAME = CameraSoundEvent.NAME

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize CameraSoundTrait."""
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
