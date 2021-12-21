"""Test for camera traits."""

from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.camera_traits import StreamingProtocol
from google_nest_sdm.device import Device


def test_camera_image_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraImage": {
                "maxImageResolution": {
                    "width": 500,
                    "height": 300,
                }
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraImage" in device.traits
    trait = device.traits["sdm.devices.traits.CameraImage"]
    assert trait.max_image_resolution.width == 500
    assert trait.max_image_resolution.height == 300


def test_camera_live_stream_traits(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 500,
                    "height": 300,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.max_video_resolution.width == 500
    assert trait.max_video_resolution.height == 300
    assert trait.video_codecs == ["H264"]
    assert trait.audio_codecs == ["AAC"]
    # Default value
    assert trait.supported_protocols == [StreamingProtocol.RTSP]


def test_camera_live_stream_webrtc_protocol(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [StreamingProtocol.WEB_RTC]


def test_camera_live_stream_multiple_protocols(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC", "RTSP"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [
        StreamingProtocol.WEB_RTC,
        StreamingProtocol.RTSP,
    ]


def test_camera_live_stream_unknown_protocols(
    fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "supportedProtocols": ["WEB_RTC", "XXX"],
            },
        },
    }
    device = fake_device(raw)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert trait.supported_protocols == [StreamingProtocol.WEB_RTC]


@pytest.mark.parametrize(
    "trait",
    [
        "sdm.devices.traits.CameraMotion",
        "sdm.devices.traits.CameraPerson",
        "sdm.devices.traits.CameraSound",
        "sdm.devices.traits.CameraClipPreview",
        "sdm.devices.traits.CameraEventImage",
    ],
)
def test_image_event_traits(
    trait: str, fake_device: Callable[[Dict[str, Any]], Device]
) -> None:
    raw = {
        "name": "my/device/name",
        "traits": {
            trait: {},
        },
    }
    device = fake_device(raw)
    assert trait in device.traits
