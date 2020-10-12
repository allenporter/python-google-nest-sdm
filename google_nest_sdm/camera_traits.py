"""Traits belonging to camera devices."""

import datetime

from .traits import Command
from .traits import TRAIT_MAP

MAX_IMAGE_RESOLUTION = "maxImageResolution"
MAX_VIDEO_RESOLUTION = "maxVideoResolution"
WIDTH = "width"
HEIGHT = "height"
VIDEO_CODECS = "videoCodecs"
AUDIO_CODECS = "audioCodecs"
STREAM_URLS = "streamUrls"
RESULTS = "results"
RTSP_URL = "rtspUrl"
STREAM_EXTENSION_TOKEN = "streamExtensionToken"
STREAM_TOKEN = "streamToken"
URL = "url"
TOKEN = "token"
EXPIRES_AT = "expiresAt"


class Resolution:
    """Maximum Resolution of an image or stream."""
    width = None
    height = None


@TRAIT_MAP.register()
class CameraImageTrait:
    """This trait belongs to any device that supports taking images."""

    NAME = "sdm.devices.traits.CameraImage"

    def __init__(self, data: dict, cmd: Command):
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


class RtspStream:
    """Provides access an RTSP live stream URL."""

    def __init__(self, data: dict, cmd: Command):
        """Initialize RstpStream."""
        self._data = data
        self._cmd = cmd

    @property
    def rtsp_stream_url(self) -> str:
        """RTSP live stream URL."""
        return self._data[STREAM_URLS][RTSP_URL]

    @property
    def stream_token(self) -> str:
        """Token to use to access an RTSP live stream."""
        return self._data[STREAM_TOKEN]

    @property
    def stream_extension_token(self) -> str:
        """Token to use to access an RTSP live stream."""
        return self._data[STREAM_EXTENSION_TOKEN]

    @property
    def expires_at(self) -> datetime:
        """Time at which both streamExtensionToken and streamToken expire."""
        expires_at = self._data[EXPIRES_AT]
        return datetime.datetime.fromisoformat(expires_at.replace("Z", "+00:00"))

    async def extend_rtsp_stream(self):
        """Request a new RTSP live stream URL access token."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.ExtendRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        resp = await self._cmd.execute(data)
        resp.raise_for_status()
        response_data = await resp.json()
        results = response_data[RESULTS]
        return RtspStream(results, self._cmd)

    async def stop_rtsp_stream(self):
        """Invalidates a valid RTSP access token and stops the RTSP live stream."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.StopRtspStream",
            "params": {"streamExtensionToken": self.stream_extension_token},
        }
        resp = await self._cmd.execute(data)
        resp.raise_for_status()


@TRAIT_MAP.register()
class CameraLiveStreamTrait:
    """This trait belongs to any device that supports live streaming."""

    NAME = "sdm.devices.traits.CameraLiveStream"

    def __init__(self, data: dict, cmd: Command):
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
    def video_codecs(self) -> list:
        """Video codecs supported for the live stream."""
        return self._data[VIDEO_CODECS]

    @property
    def audio_codecs(self) -> list:
        """Audio codecs supported for the live stream."""
        return self._data[AUDIO_CODECS]

    async def generate_rtsp_stream(self) -> RtspStream:
        """Request a token to access an RTSP live stream URL."""
        data = {
            "command": "sdm.devices.commands.CameraLiveStream.GenerateRtspStream",
            "params": {},
        }
        resp = await self._cmd.execute(data)
        resp.raise_for_status()
        response_data = await resp.json()
        results = response_data[RESULTS]
        return RtspStream(results, self._cmd)


class EventImage:
    """Provides access an RTSP live stream URL.

    Use a ?width or ?height query parameters to customize the resolution
    of the downloaded image. Only one of these parameters need to specified.
    The other parameter is scaled automatically according to the camera's
    aspect ratio.

    The token should be added as an HTTP header:
    Authorization: Basic <token>
    """

    def __init__(self, data: dict, cmd: Command):
        self._data = data
        self._cmd = cmd

    @property
    def url(self) -> str:
        """The URL to download the camera image from."""

        return self._data[URL]

    @property
    def token(self) -> str:
        """Token to use in the HTTP Authorization header when downloading."""
        return self._data[TOKEN]


@TRAIT_MAP.register()
class CameraEventImageTrait:
    """This trait belongs to any device that generates images from events."""

    NAME = "sdm.devices.traits.CameraEventImage"

    def __init__(self, data: dict, cmd: Command):
        """Initialize CameraEventImageTrait."""
        self._data = data
        self._cmd = cmd

    async def generate_image(self, event_id: str) -> EventImage:
        """Provides a URL to download a camera image from."""
        data = {
            "command": "sdm.devices.commands.CameraEventImage.GenerateImage",
            "params": {
                "eventId": event_id,
            },
        }
        resp = await self._cmd.execute(data)
        resp.raise_for_status()
        response_data = await resp.json()
        results = response_data[RESULTS]
        return EventImage(results, self._cmd)
