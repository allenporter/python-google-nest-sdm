"""Tests for event_media.py"""

import datetime
from typing import Any, Awaitable, Callable, Dict
from unittest.mock import patch
import logging

import pytest
import aiohttp

from google_nest_sdm import diagnostics, google_nest_api
from google_nest_sdm.device import Device
from google_nest_sdm.event import EventMessage, EventToken
from google_nest_sdm.event_media import InMemoryEventMediaStore
from google_nest_sdm.transcoder import Transcoder
from google_nest_sdm.camera_traits import (
    CameraMotionTrait,
    CameraPersonTrait,
    CameraClipPreviewTrait,
    CameraEventImageTrait,
)
from google_nest_sdm.doorbell_traits import DoorbellChimeTrait


from .conftest import (
    DeviceHandler,
    EventCallback,
    Recorder,
    assert_diagnostics,
)


_LOGGER = logging.getLogger(__name__)


IMAGE_CAMERA_TRAITS = [
    CameraEventImageTrait.NAME,
    CameraMotionTrait.NAME,
    CameraPersonTrait.NAME,
    CameraPersonTrait.NAME,
]
IMAGE_MOTION_ONLY_CAMERA_TRAITS = [CameraEventImageTrait.NAME, CameraMotionTrait.NAME]
IMAGE_DOORBELL_TRAITS = [
    CameraEventImageTrait.NAME,
    DoorbellChimeTrait.NAME,
    CameraMotionTrait.NAME,
]
CLIP_CAMERA_TRAITS = [
    CameraClipPreviewTrait.NAME,
    CameraMotionTrait.NAME,
    CameraPersonTrait.NAME,
]
CLIP_DOORBELL_TRAITS = [
    CameraClipPreviewTrait.NAME,
    DoorbellChimeTrait.NAME,
    CameraMotionTrait.NAME,
]


@pytest.fixture(name="device_traits")
def mock_device_traits() -> list[str]:
    """Fixture for tests to setup default device traits"""
    return []


@pytest.fixture(name="device_id")
def mock_device_id(
    device_handler: DeviceHandler,
    device_traits: list[str],
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> str:
    return device_handler.add_device(traits={k: {} for k in device_traits})


class MediaRouter:
    """Fixture for serving event media."""

    def __init__(
        self,
        app: aiohttp.web.Application,
        recorder: Recorder,
        device_handler: DeviceHandler,
    ) -> None:
        self.app = app
        self.recorder = recorder
        self.device_handler = device_handler
        self.api_responses: dict[str, list[aiohttp.web.Response]] = {}
        self.image_responses: dict[str, aiohttp.web.Response] = {}
        self.clip_responses: dict[str, aiohttp.web.Response] = {}
        self.token_cnt = -1
        self.app.add_routes(
            [
                aiohttp.web.get(r"/image-url/{device_id:.*}", self.image_token_handler),
                aiohttp.web.get(
                    r"/clip-url/{device_id:.*}/token/{token:.*}", self.clip_handler
                ),
            ]
        )

    def image(self, device_id: str) -> None:
        """Prepare an image response"""
        self.token_cnt += 1
        token = f"g.{self.token_cnt}.eventToken"
        # Prepare API to generate image url + token
        if device_id not in self.api_responses:
            self.api_responses[device_id] = []
        self.device_handler.add_device_command(
            device_id,
            [
                {
                    "results": {
                        "url": f"image-url/{device_id}",
                        "token": token,
                    },
                }
            ],
        )
        # Prepare image serving
        self.image_responses[token] = aiohttp.web.Response(
            body=f"image-bytes-{token}".encode()
        )

    def clip(self, device_id: str) -> str:
        """Prepare an clip response and return the url."""
        self.token_cnt += 1
        token = f"g.{self.token_cnt}.eventToken"
        # Prepare ckip serving
        self.clip_responses[token] = aiohttp.web.Response(
            body=f"clip-bytes-{token}".encode()
        )
        return f"clip-url/{device_id}/token/{token}"

    async def api_handler(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        device_id = request.match_info["device_id"]
        assert device_id
        _LOGGER.debug("API handler %s", device_id)
        responses = self.api_responses[device_id]
        response = responses.pop(0)
        return response

    async def image_token_handler(
        self, request: aiohttp.web.Request
    ) -> aiohttp.web.Response:
        device_id = request.match_info["device_id"]
        assert device_id
        _LOGGER.debug("Image token handler %s - %s", device_id, self.image_responses)
        auth_header = request.headers["Authorization"]
        assert auth_header.startswith("Basic ")
        token = auth_header[6:]
        if (response := self.image_responses.pop(token)) is None:
            raise ValueError(f"No image response configured for token {token}")
        return response

    async def clip_handler(self, request: aiohttp.web.Request) -> aiohttp.web.Response:
        device_id = request.match_info["device_id"]
        token = request.match_info["token"]
        _LOGGER.debug("Clip handler %s", device_id)
        if (response := self.clip_responses.pop(token)) is None:
            raise ValueError(f"No image response configured for token {token}")
        return response


@pytest.fixture(name="media_router", autouse=True)
def mock_media_router(
    app: aiohttp.web.Application, recorder: Recorder, device_handler: DeviceHandler
) -> MediaRouter:
    """Fixture for preparing API and content serving calls."""
    return MediaRouter(app, recorder, device_handler)


@pytest.fixture
def event_cache_size() -> int:
    """Fixture to configure the event cache size."""
    return 8


@pytest.fixture
def event_fetch() -> bool:
    """Fixture to configure the event cache size."""
    return True


@pytest.fixture(autouse=True)
def mock_event_media_manager(
    media_router: MediaRouter, device: Device, event_fetch: bool, event_cache_size: int
) -> None:
    """Fixture to prepare the event media manager for fetching media."""
    device.event_media_manager.cache_policy.fetch = event_fetch
    device.event_media_manager.cache_policy.event_cache_size = event_cache_size


@pytest.fixture(name="transcoder")
def mock_transcoder(device: Device) -> Transcoder:
    """Fixture that enables a transcoder."""
    fake_transcoder = Transcoder("/bin/echo", "")
    device.event_media_manager.cache_policy.transcoder = fake_transcoder
    return fake_transcoder


@pytest.fixture(name="device")
async def mock_device(
    device_id: str,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
) -> Device:
    api = await api_client()
    devices = await api.async_get_devices()
    for device in devices:
        if device.name == device_id:
            return device
    raise ValueError("Invalid test state, couldn't find device.")


@pytest.mark.parametrize(
    ("device_traits", "event_cache_size"), [(IMAGE_MOTION_ONLY_CAMERA_TRAITS, 10)]
)
async def test_event_manager_event_expiration(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    media_router.image(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    ts2 = ts1 + datetime.timedelta(seconds=5)
    media_router.image(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "a94b2115-3b57-4eb4-8830-80519f188ec9",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "DgY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "ABCZQRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # Event is in the past and is expired
    ts3 = ts1 - datetime.timedelta(seconds=90)
    media_router.image(device.name)  # Ignored
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "b83c2115-3b57-4eb4-8830-80519f167fa8",
                "timestamp": ts3.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "EkY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "1234QRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    event_media_manager = device.event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 2


@pytest.mark.parametrize(("device_traits"), [(IMAGE_MOTION_ONLY_CAMERA_TRAITS)])
async def test_event_manager_cache_expiration(
    media_router: MediaRouter,
    device: Device,
    # event_media_store: InMemoryEventMediaStore,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    num_events = 10
    event_tokens = []
    for i in range(0, num_events):
        media_router.image(device.name)
        ts = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=i
        )
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": device.name,
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": f"CjY5Y3VK..{i}...",
                                "eventId": f"FWWVQVU..{i}...",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                }
            )
        )
        image_sessions = await device.event_media_manager.async_image_sessions()
        event_tokens.append(image_sessions[0].event_token)

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "event_media": {
                "save_media_count": 10,
                "remove_media_count": 2,
            },
        },
    )
    assert_diagnostics(
        device.get_diagnostics(),
        {
            "command": {
                "fetch_image_count": 10,
                "sdm.devices.commands.CameraEventImage.GenerateImage_count": 10,
            },
            "data": {
                "name": "**REDACTED**",
                "parentRelations": [],
                "traits": {
                    "sdm.devices.traits.CameraEventImage": {},
                    "sdm.devices.traits.CameraMotion": {},
                },
                "type": "sdm.devices.types.device-type1",
            },
            "event_media": {
                "event": 10,
                "event.fetch": 10,
                "event.new": 10,
                "fetch_image": 10,
                "fetch_image.save": 10,
                "load_image_sessions": 10,
                "sdm.devices.events.CameraMotion.Motion_count": 10,
            },
        },
    )

    event_media_manager = device.event_media_manager
    # All old items are evicted from the cache
    assert len(list(await event_media_manager.async_image_sessions())) == 8

    # Old items are evicted from the media store
    assert await event_media_manager.get_media_from_token(event_tokens[0]) is None
    assert await event_media_manager.get_media_from_token(event_tokens[1]) is None
    for i in range(2, num_events):
        media = await event_media_manager.get_media_from_token(event_tokens[i])
        assert media
        assert media.contents == f"image-bytes-g.{i}.eventToken".encode()

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "event_media": {
                "load_media_count": 8,
                "save_media_count": 10,
                "remove_media_count": 2,
            },
        },
    )


@pytest.mark.parametrize("device_traits", [IMAGE_CAMERA_TRAITS])
async def test_prefetch_image_failure_in_session(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    """Exercise case where one image within a session fails."""
    # Send one failure response, then 3 other valid responses. The cache size
    # is too small so we're exercising events dropping out of the cache.
    media_router.image(device.name)
    media_router.api_responses[device.name].append(aiohttp.web.Response(status=502))

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    ts1 = now + datetime.timedelta(seconds=1)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-1",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y.......",
                            "eventId": "FWWVQVU..1...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    ts2 = now + datetime.timedelta(seconds=2)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-2",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraPerson.Person": {
                            "eventSessionId": "CjY5Y.......",
                            "eventId": "FWWVQVU..2...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_image_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y......."
    assert event_token.event_id == "FWWVQVU..1..."
    assert event.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event.timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )


@pytest.mark.parametrize(("device", "mock_event_media_manager"), [(None, None)])
async def test_multi_device_events(
    media_router: MediaRouter,
    device: Device | None,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id1 = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )
    device_id2 = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )
    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 2
    device = devices[0]
    assert device
    assert device.name == device_id1
    device = devices[1]
    assert device
    assert device.name == device_id2

    # Use shared event store for all devices
    store = InMemoryEventMediaStore()
    devices[0].event_media_manager.cache_policy.store = store
    devices[0].event_media_manager.cache_policy.fetch = True
    devices[1].event_media_manager.cache_policy.store = store
    devices[1].event_media_manager.cache_policy.fetch = True

    # Each device has no sessions
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 0
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 0

    ts = datetime.datetime.now(tz=datetime.timezone.utc)
    media_router.image(device_id1)
    await devices[0].async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-1",
                "timestamp": ts.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id1,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVU..1...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # First device has a single event
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 0

    media_router.image(device_id2)
    await devices[1].async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-2",
                "timestamp": ts.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id2,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVU..2...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    # Each device has a single event
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 1


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_event_session_image(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    media_router.image(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    ts2 = ts1 + datetime.timedelta(seconds=5)
    media_router.image(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "90120ecc7-3b57-4eb4-9941-91609f278ec3",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "ABCZQRUdGNUlTU2V4MGV3bRZ23...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_image_sessions())
    assert len(events) == 2
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
    assert event_token.event_id == "ABCZQRUdGNUlTU2V4MGV3bRZ23..."
    assert event.event_type == "sdm.devices.events.DoorbellChime.Chime"
    assert event.timestamp.isoformat(timespec="seconds") == ts2.isoformat(
        timespec="seconds"
    )

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-g.1.eventToken"
    assert media.content_type == "image/jpeg"

    event = events[1]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
    assert event_token.event_id == "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    assert event.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event.timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-g.0.eventToken"
    assert media.content_type == "image/jpeg"


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_event_session_clip_preview(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "previewUrl": url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )
    assert callback.invoked
    assert len(callback.messages) == 1
    assert callback.messages[0].event_sessions
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in callback.messages[0].event_sessions
    session = callback.messages[0].event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert "sdm.devices.events.CameraMotion.Motion" in session
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in session

    assert_diagnostics(
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 1,
            "event.fetch": 1,
            "event.new": 1,
            "event.notify": 1,
            "fetch_clip": 1,
            "fetch_clip.save": 1,
            "sdm.devices.events.CameraClipPreview.ClipPreview_count": 1,
            "sdm.devices.events.CameraMotion.Motion_count": 1,
        },
    )
    ts2 = ts1 + datetime.timedelta(seconds=5)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:2",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "ENDED",
            }
        )
    )
    event_media_manager = device.event_media_manager

    # Update callback was invoked because there is a new event type
    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "event_media": {
                "save_media_count": 1,
            },
        },
    )
    assert_diagnostics(
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 2,
            "event.fetch": 2,
            "event.new": 1,
            "event.notify": 2,
            "event.update": 1,
            "fetch_clip": 2,
            "fetch_clip.save": 1,
            "fetch_clip.skip": 1,
            "sdm.devices.events.CameraClipPreview.ClipPreview_count": 1,
            "sdm.devices.events.CameraMotion.Motion_count": 1,
            "sdm.devices.events.DoorbellChime.Chime_count": 1,
        },
    )
    # New event published where we already have media
    assert len(callback.messages) == 2
    assert callback.messages[1].event_sessions
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in callback.messages[1].event_sessions
    session = callback.messages[1].event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert "sdm.devices.events.DoorbellChime.Chime" in session

    events = list(await event_media_manager.async_clip_preview_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
    assert event_token.event_id == "n:1"
    assert event.event_types == [
        "sdm.devices.events.CameraMotion.Motion",
        "sdm.devices.events.DoorbellChime.Chime",
    ]
    assert event.timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"clip-bytes-g.0.eventToken"
    assert media.content_type == "video/mp4"


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_event_session_without_clip(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )

    # Event is received, but does not contain media
    # Do not invoke callback without media
    assert_diagnostics(
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 1,
            "event.fetch": 1,
            "event.new": 1,
            "fetch_clip": 1,
            "fetch_clip.skip": 1,
            "sdm.devices.events.CameraMotion.Motion_count": 1,
        },
    )
    assert not callback.invoked

    ts2 = ts1 + datetime.timedelta(seconds=5)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:2",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "ENDED",
            }
        )
    )

    # The event ENDED without any media, so notify
    assert callback.invoked  # type: ignore[unreachable]
    assert len(callback.messages) == 1  # type: ignore[unreachable]
    assert callback.messages[0].event_sessions
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in callback.messages[0].event_sessions
    session = callback.messages[0].event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert "sdm.devices.events.DoorbellChime.Chime" in session
    assert "sdm.devices.events.CameraMotion.Motion" in session

    event_media_manager = device.event_media_manager

    # There are no event media clips
    events = list(await event_media_manager.async_clip_preview_sessions())
    assert not events


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_event_session_clip_preview_in_second_message(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )

    # Do not invoke callback without media
    assert not callback.invoked
    assert_diagnostics(
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 1,
            "event.fetch": 1,
            "event.new": 1,
            "fetch_clip": 1,
            "fetch_clip.skip": 1,
            "sdm.devices.events.DoorbellChime.Chime_count": 1,
        },
    )

    ts2 = ts1 + datetime.timedelta(seconds=5)
    clip_url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "previewUrl": clip_url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "ENDED",
            }
        )
    )

    # Callback invoked now that media arrived. The previous events are now received.
    assert callback.invoked  # type: ignore[unreachable]
    assert len(callback.messages) == 1  # type: ignore[unreachable]
    assert callback.messages[0].event_sessions
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in callback.messages[0].event_sessions
    session = callback.messages[0].event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in session
    assert "sdm.devices.events.DoorbellChime.Chime" in session

    assert_diagnostics(  # type: ignore[unreachable]
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 2,
            "event.fetch": 2,
            "event.new": 1,
            "event.update": 1,
            "event.notify": 1,
            "fetch_clip": 2,
            "fetch_clip.skip": 1,
            "fetch_clip.save": 1,
            "sdm.devices.events.CameraClipPreview.ClipPreview_count": 1,
            "sdm.devices.events.DoorbellChime.Chime_count": 1,
        },
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_clip_preview_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y3VKaTZwR3o4Y19YbTVfMF..."
    assert event_token.event_id == "n:1"
    assert event.event_types == [
        "sdm.devices.events.DoorbellChime.Chime",
    ]
    assert event.timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"clip-bytes-g.0.eventToken"
    assert media.content_type == "video/mp4"


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_event_session_clip_preview_issue(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    """Exercise event session clip preview event ordering behavior.

    Reproduces issue https://github.com/home-assistant/core/issues/86314
    """
    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "1635497756",
                            "eventId": "n:1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )

    assert_diagnostics(
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 1,
            "event.fetch": 1,
            "event.new": 1,
            "fetch_clip": 1,
            "fetch_clip.skip": 1,
            "sdm.devices.events.DoorbellChime.Chime_count": 1,
        },
    )

    ts2 = ts1 + datetime.timedelta(seconds=5)
    clip_url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "1635497756",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "1635497756",
                            "previewUrl": clip_url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "UPDATED",
            }
        )
    )

    # Callback invoked now that media arrived
    assert callback.invoked  # type: ignore[unreachable]
    assert_diagnostics(  # type: ignore[unreachable]
        device.get_diagnostics().get("event_media", {}),
        {
            "event": 2,
            "event.fetch": 2,
            "event.new": 1,
            "event.update": 1,
            "event.notify": 1,
            "fetch_clip": 2,
            "fetch_clip.skip": 1,
            "fetch_clip.save": 1,
            "sdm.devices.events.CameraClipPreview.ClipPreview_count": 1,
            "sdm.devices.events.DoorbellChime.Chime_count": 2,
        },
    )
    # Event containing the media is delivered
    assert len(callback.messages) == 1
    assert callback.messages[0].event_sessions
    assert "1635497756" in callback.messages[0].event_sessions
    message = callback.messages[0].event_sessions["1635497756"]
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in message
    assert "sdm.devices.events.DoorbellChime.Chime" in message


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_persisted_storage_image_event_media_keys(device: Device) -> None:
    data = {
        device.name: [
            {
                "event_session_id": "AVPHwEtyzgSxu6EuaIOfvz...",
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "event_type": "sdm.devices.events.CameraMotion.Motion",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxrwjZjb0daCbmE...",
                        },
                        "timestamp": "2021-12-23T06:35:35.791000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "event_type": "sdm.devices.events.DoorbellChime.Chime",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxr_zoChpekrBmo...",
                        },
                        "timestamp": "2021-12-23T06:35:36.101000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                },
                "event_media_keys": {
                    "CiUA2vuxrwjZjb0daCbmE...": (
                        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg"
                    ),
                    "CiUA2vuxr_zoChpekrBmo...": (
                        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg"
                    ),
                },
            },
        ],
    }
    event_media_manager = device.event_media_manager
    store = event_media_manager.cache_policy.store
    await store.async_save(data)
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg",
        b"image-bytes-1",
    )
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg",
        b"image-bytes-2",
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_image_sessions())
    assert len(events) == 2
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "AVPHwEtyzgSxu6EuaIOfvz..."
    assert event_token.event_id == "CiUA2vuxr_zoChpekrBmo..."
    assert event.event_type == "sdm.devices.events.DoorbellChime.Chime"
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-23T06:35:36+00:00"

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-2"
    assert media.content_type == "image/jpeg"

    event = events[1]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "AVPHwEtyzgSxu6EuaIOfvz..."
    assert event_token.event_id == "CiUA2vuxrwjZjb0daCbmE..."
    assert event.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-23T06:35:35+00:00"

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "image/jpeg"

    # Test fallback to other media within the same session
    await store.async_remove_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg"
    )
    assert await event_media_manager.get_media_from_token(event.event_token)
    await store.async_remove_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg",
    )
    assert not await event_media_manager.get_media_from_token(event.event_token)


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_persisted_storage_image(device: Device) -> None:
    data = {
        device.name: [
            {
                "event_session_id": "AVPHwEtyzgSxu6EuaIOfvz...",
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "event_type": "sdm.devices.events.CameraMotion.Motion",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxrwjZjb0daCbmE...",
                        },
                        "timestamp": "2021-12-23T06:35:35.791000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "event_type": "sdm.devices.events.DoorbellChime.Chime",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxr_zoChpekrBmo...",
                        },
                        "timestamp": "2021-12-23T06:35:36.101000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                },
                "media_key": (
                    "AVPHwEtyzgSxu6EuaIOfvzmr7oaxdtpvXrJCJXcjIwQ4RQ6CMZW97Gb2dupC4uHJcx_NrAPRAPyD7KFraR32we-LAFgMjA-doorbell_chime.jpg"
                ),
            },
        ],
    }
    event_media_manager = device.event_media_manager
    store = event_media_manager.cache_policy.store
    await store.async_save(data)
    # Legacy storage where only one media is stored for multiple image events
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7oaxdtpvXrJCJXcjIwQ4RQ6CMZW97Gb2dupC4uHJcx_NrAPRAPyD7KFraR32we-LAFgMjA-doorbell_chime.jpg",
        b"image-bytes-1",
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_image_sessions())
    assert len(events) == 2
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "AVPHwEtyzgSxu6EuaIOfvz..."
    assert event_token.event_id == "CiUA2vuxr_zoChpekrBmo..."
    assert event.event_type == "sdm.devices.events.DoorbellChime.Chime"
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-23T06:35:36+00:00"

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "image/jpeg"

    event = events[1]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "AVPHwEtyzgSxu6EuaIOfvz..."
    assert event_token.event_id == "CiUA2vuxrwjZjb0daCbmE..."
    assert event.event_type == "sdm.devices.events.CameraMotion.Motion"
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-23T06:35:35+00:00"

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "image/jpeg"

    # Test failure where media key points to removed media
    await store.async_remove_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7oaxdtpvXrJCJXcjIwQ4RQ6CMZW97Gb2dupC4uHJcx_NrAPRAPyD7KFraR32we-LAFgMjA-doorbell_chime.jpg"
    )
    assert not await event_media_manager.get_media_from_token(event.event_token)


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_persisted_storage_clip_preview(device: Device) -> None:
    data = {
        device.name: [
            {
                "event_session_id": "1632710204",
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "event_type": "sdm.devices.events.CameraMotion.Motion",
                        "event_data": {
                            "eventSessionId": "1632710204",
                            "eventId": "n:1",
                        },
                        "timestamp": "2021-12-21T21:13:18.734000+00:00",
                        "event_image_type": "video/mp4",
                    },
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "event_type": "sdm.devices.events.DoorbellChime.Chime",
                        "event_data": {
                            "eventSessionId": "1632710204",
                            "eventId": "n:2",
                        },
                        "timestamp": "2021-12-21T21:13:18.734000+00:00",
                        "event_image_type": "video/mp4",
                    },
                    "sdm.devices.events.CameraClipPreview.ClipPreview": {
                        "event_type": (
                            "sdm.devices.events.CameraClipPreview.ClipPreview"
                        ),
                        "event_data": {
                            "eventSessionId": "1632710204",
                            "previewUrl": "https://127.0.0.1/example",
                        },
                        "timestamp": "2021-12-21T21:13:18.734000+00:00",
                        "event_image_type": "video/mp4",
                    },
                },
                "media_key": "1640121198-1632710204-doorbell_chime.mp4",
            }
        ],
    }
    event_media_manager = device.event_media_manager
    store = event_media_manager.cache_policy.store
    await store.async_save(data)
    await store.async_save_media(
        "1640121198-1632710204-doorbell_chime.mp4", b"image-bytes-1"
    )

    events = list(await event_media_manager.async_clip_preview_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "1632710204"
    assert event_token.event_id == "n:1"
    assert event.event_types == [
        "sdm.devices.events.CameraMotion.Motion",
        "sdm.devices.events.DoorbellChime.Chime",
    ]
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-21T21:13:18+00:00"

    media = await event_media_manager.get_media_from_token(event.event_token)
    assert media
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "video/mp4"

    # Test failure where media key points to removed media
    await store.async_remove_media("1640121198-1632710204-doorbell_chime.mp4")
    assert not await event_media_manager.get_media_from_token(event.event_token)


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_event_image_lookup_failure(
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    # Disable pre-fetch
    event_media_manager = device.event_media_manager
    event_media_manager.cache_policy.fetch = False

    token = EventToken(
        "CjY5Y3VKaTZwR3o4Y19YbTVfMF...", "FWWVQVUdGNUlTU2V4MGV2aTNXV..."
    ).encode()
    assert not await event_media_manager.get_media_from_token(token)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": now.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "FWWVQVUdGNUlTU2V4MGV2aTNXV...",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    assert not await event_media_manager.get_media_from_token(token)


@pytest.mark.parametrize("device_traits", [CLIP_DOORBELL_TRAITS])
async def test_clip_preview_lookup_failure(
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    event_media_manager = device.event_media_manager
    # No media fetch so media is not visible
    event_media_manager.cache_policy.fetch = False

    token = EventToken("CjY5Y3VKaTZwR3o4Y19YbTVfMF...", "ignored-event-id").encode()
    assert not await event_media_manager.get_media_from_token(token)

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": now.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "previewUrl": "image-url-1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )
    assert not await event_media_manager.get_media_from_token(token)


@pytest.mark.parametrize("device_traits", [CLIP_CAMERA_TRAITS])
async def test_clip_preview_transcode(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
    transcoder: Transcoder,
) -> None:
    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    clip_url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "previewUrl": clip_url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_clip_preview_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "CjY5Y3VKaTZwR3o4Y19YbTVfMF"
    assert event_token.event_id == "n:1"
    assert event.event_types == [
        "sdm.devices.events.CameraMotion.Motion",
    ]
    assert event.timestamp.isoformat(timespec="seconds") == ts1.isoformat(
        timespec="seconds"
    )

    cnt = 0

    def values() -> Callable[[str], bool]:
        def func(filename: str) -> bool:
            nonlocal cnt
            cnt = cnt + 1
            if cnt == 1:
                # input file exists
                return True
            return False

        return func

    with (
        patch("google_nest_sdm.transcoder.os.path.exists", new_callable=values),
        patch(
            "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
            return_value=b"fake-video-thumb-bytes",
        ),
    ):
        media = await event_media_manager.get_clip_thumbnail_from_token(
            event.event_token
        )
        assert media
        assert media.contents == b"fake-video-thumb-bytes"
        assert media.content_type == "image/gif"

    # Test cache
    with patch(
        "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
        return_value=b"fake-video-thumb-bytes",
    ):
        media = await event_media_manager.get_clip_thumbnail_from_token(
            event.event_token
        )
        assert media
        assert media.contents == b"fake-video-thumb-bytes"
        assert media.content_type == "image/gif"

    ts2 = ts1 + datetime.timedelta(seconds=5)
    clip_url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "DjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "DjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "previewUrl": clip_url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                "resourcegroup": [
                    "enterprises/project-id1/devices/device-id1",
                ],
                "eventThreadState": "STARTED",
            }
        )
    )

    events = list(await event_media_manager.async_clip_preview_sessions())
    assert len(events) == 2
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "DjY5Y3VKaTZwR3o4Y19YbTVfMF"

    # Test failure mode
    with patch("google_nest_sdm.transcoder.os.path.exists", return_value=False):
        assert not await event_media_manager.get_clip_thumbnail_from_token(
            event.event_token
        )

    with patch(
        "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
        return_value=None,
    ):
        assert not await event_media_manager.get_clip_thumbnail_from_token(
            event.event_token
        )

    # Disable transcoding
    event_media_manager.cache_policy.transcoder = None
    assert not await event_media_manager.get_clip_thumbnail_from_token(
        event.event_token
    )


@pytest.mark.parametrize(
    ("device_traits", "event_cache_size"), [(CLIP_CAMERA_TRAITS, 5)]
)
async def test_event_manager_event_expiration_with_transcode(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
    transcoder: Transcoder,
) -> None:
    event_media_manager = device.event_media_manager

    num_events = 7
    event_tokens = []
    for i in range(0, num_events):
        ts = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=i
        )
        clip = media_router.clip(device.name)
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": device.name,
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": f"CjY5Y3VK..{i}...",
                                "eventId": f"n:{i}",
                            },
                            "sdm.devices.events.CameraClipPreview.ClipPreview": {
                                "eventSessionId": f"CjY5Y3VK..{i}...",
                                "previewUrl": clip,
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                }
            )
        )
        events = list(await event_media_manager.async_clip_preview_sessions())
        assert len(events) > 0
        event_token = events[0].event_token
        media = await event_media_manager.get_media_from_token(event_token)
        assert media
        assert media.contents == f"clip-bytes-g.{i}.eventToken".encode()

        event_tokens.append(event_token)

        cnt = 0

        def values() -> Callable[[str], bool]:
            def func(filename: str) -> bool:
                nonlocal cnt
                cnt = cnt + 1
                if cnt == 1:
                    # input file exists
                    return True
                return False

            return func

        # Cache a clip thumbnail to ensure it is expired later
        with (
            patch("google_nest_sdm.transcoder.os.path.exists", new_callable=values),
            patch(
                "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
                return_value=b"fake-video-thumb-bytes",
            ),
        ):
            media = await event_media_manager.get_clip_thumbnail_from_token(event_token)
            assert media
            assert media.contents == b"fake-video-thumb-bytes"
            assert media.content_type == "image/gif"

    event_media_manager = device.event_media_manager
    # All old items are evicted from the cache
    assert len(list(await event_media_manager.async_clip_preview_sessions())) == 5

    # Old items are evicted from the media store
    assert await event_media_manager.get_media_from_token(event_tokens[0]) is None
    assert await event_media_manager.get_media_from_token(event_tokens[1]) is None
    for token in event_tokens[2:]:
        assert await event_media_manager.get_media_from_token(token) is not None


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_unsupported_event_trait(
    media_router: MediaRouter,
    device: Device,
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    ts = datetime.datetime.now(tz=datetime.timezone.utc)
    clip_url = media_router.clip(device.name)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device.name,
                    "events": {
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VK..0...",
                            "previewUrl": clip_url,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    event_media_manager = device.event_media_manager
    assert len(list(await event_media_manager.async_image_sessions())) == 0
    assert len(list(await event_media_manager.async_clip_preview_sessions())) == 0


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_unknown_event_type(device: Device) -> None:
    data = {
        device.name: [
            {
                "event_session_id": "AVPHwEtyzgSxu6EuaIOfvz...",
                "events": {
                    "sdm.devices.events.Ignored.Ignored": {
                        "event_type": "sdm.devices.events.Ignored.Ignored",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxrwjZjb0daCbmE...",
                        },
                        "timestamp": "2021-12-23T06:35:35.791000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "event_type": "sdm.devices.events.DoorbellChime.Chime",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxr_zoChpekrBmo...",
                        },
                        "timestamp": "2021-12-23T06:35:36.101000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                },
                "event_media_keys": {
                    "CiUA2vuxrwjZjb0daCbmE...": (
                        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg"
                    ),
                    "CiUA2vuxr_zoChpekrBmo...": (
                        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg"
                    ),
                },
            },
        ],
    }
    event_media_manager = device.event_media_manager
    store = event_media_manager.cache_policy.store
    await store.async_save(data)
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg",
        b"image-bytes-1",
    )
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg",
        b"image-bytes-2",
    )

    event_media_manager = device.event_media_manager

    events = list(await event_media_manager.async_image_sessions())
    assert len(events) == 1
    event = events[0]
    event_token = EventToken.decode(event.event_token)
    assert event_token.event_session_id == "AVPHwEtyzgSxu6EuaIOfvz..."
    assert event_token.event_id == "CiUA2vuxr_zoChpekrBmo..."
    assert event.event_type == "sdm.devices.events.DoorbellChime.Chime"
    assert event.timestamp.isoformat(timespec="seconds") == "2021-12-23T06:35:36+00:00"


@pytest.mark.parametrize("device_traits", [IMAGE_DOORBELL_TRAITS])
async def test_invalid_events_persisted(device: Device) -> None:
    data = {
        device.name: [
            {
                "event_session_id": "AVPHwEtyzgSxu6EuaIOfvz...",
                "events": {
                    "sdm.devices.events.CameraMotion.Motion": {
                        "event_type": "sdm.devices.events.CameraMotion.Motion",
                    },
                    "sdm.devices.events.DoorbellChime.Chime": {
                        "event_type": "sdm.devices.events.DoorbellChime.Chime",
                        "event_data": {
                            "eventSessionId": "AVPHwEtyzgSxu6EuaIOfvz...",
                            "eventId": "CiUA2vuxr_zoChpekrBmo...",
                        },
                        "timestamp": "2021-12-23T06:35:36.101000+00:00",
                        "event_image_type": "image/jpeg",
                    },
                },
                "event_media_keys": {
                    "CiUA2vuxr_zoChpekrBmo...": (
                        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg"
                    ),
                },
            },
        ],
    }
    event_media_manager = device.event_media_manager
    store = event_media_manager.cache_policy.store
    await store.async_save(data)
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxrwjZjb0daCbmE-motion.jpg",
        b"image-bytes-1",
    )
    await store.async_save_media(
        "AVPHwEtyzgSxu6EuaIOfvzmr7-CiUA2vuxr_zoChpekrBmo-doorbell.jpg",
        b"image-bytes-2",
    )

    event_media_manager = device.event_media_manager

    with pytest.raises(ValueError, match="EventMediaModelItem has invalid value"):
        list(await event_media_manager.async_image_sessions())
