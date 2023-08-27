"""Tests for event_media.py"""
import datetime
import itertools
from typing import Any, Awaitable, Callable, Dict
from unittest.mock import patch

import aiohttp

from google_nest_sdm import diagnostics, google_nest_api
from google_nest_sdm.event import EventMessage, EventToken, ImageEventBase
from google_nest_sdm.event_media import InMemoryEventMediaStore
from google_nest_sdm.transcoder import Transcoder

from .conftest import (
    FAKE_TOKEN,
    DeviceHandler,
    EventCallback,
    NewHandler,
    NewImageHandler,
    Recorder,
    assert_diagnostics,
)


async def test_event_manager_event_expiration(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    device.event_media_manager.cache_policy.event_cache_size = 10

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "a94b2115-3b57-4eb4-8830-80519f188ec9",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "b83c2115-3b57-4eb4-8830-80519f167fa8",
                "timestamp": ts3.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    assert len(list(await event_media_manager.async_events())) == 2


async def test_event_manager_cache_expiration(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    response = {
        "results": {
            "url": "image-url-1",
            "token": "g.1.eventToken",
        },
    }
    num_events = 10
    post_handler = NewHandler(recorder, list(itertools.repeat(response, num_events)))
    app.router.add_post(f"/{device_id}:executeCommand", post_handler)
    app.router.add_get(
        "/image-url-1",
        NewImageHandler(
            list(itertools.repeat(b"image-bytes-1", num_events)), token="g.1.eventToken"
        ),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Turn on event fetching
    device.event_media_manager.cache_policy.fetch = True
    device.event_media_manager.cache_policy.event_cache_size = 8

    class TestStore(InMemoryEventMediaStore):
        def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
            """Return a predictable media key."""
            return event.event_session_id

        def get_image_media_key(self, device_id: str, event: ImageEventBase) -> str:
            """Return a predictable media key."""
            return event.event_session_id

    store = TestStore()
    device.event_media_manager.cache_policy.store = store

    for i in range(0, num_events):
        ts = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=i
        )
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": device_id,
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
                "sdm.devices.events.CameraMotion.Motion_count": 10,
            },
        },
    )

    event_media_manager = device.event_media_manager
    # All old items are evicted from the cache
    assert len(list(await event_media_manager.async_events())) == 8

    # Old items are evicted from the media store
    assert await store.async_load_media("CjY5Y3VK..0...") is None
    assert await store.async_load_media("CjY5Y3VK..1...") is None
    for i in range(2, num_events):
        assert await store.async_load_media(f"CjY5Y3VK..{i}...") == b"image-bytes-1"

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "event_media": {
                "load_media_count": 10,
                "save_media_count": 10,
                "remove_media_count": 2,
            },
        },
    )


async def test_prefetch_image_failure_in_session(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    """Exercise case where one image within a session fails."""
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.CameraMotion": {},
            "sdm.devices.traits.CameraPerson": {},
        }
    )

    # Send one failure response, then 3 other valid responses. The cache size
    # is too small so we're exercising events dropping out of the cache.
    responses = [
        aiohttp.web.json_response(
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            }
        ),
        aiohttp.web.Response(status=502),
    ]

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return responses.pop(0)

    app.router.add_post(f"/{device_id}:executeCommand", handler)
    app.router.add_get(
        "/image-url-1",
        NewImageHandler([b"image-bytes-1"], token="g.1.eventToken"),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Turn on event fetching
    device.event_media_manager.cache_policy.fetch = True

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    ts1 = now + datetime.timedelta(seconds=1)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-1",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
                    "name": device_id,
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


async def test_multi_device_events(
    app: aiohttp.web.Application,
    recorder: Recorder,
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

    response = {
        "results": {
            "url": "image-url-1",
            "token": "g.1.eventToken",
        },
    }
    num_events = 4
    post_handler = NewHandler(recorder, list(itertools.repeat(response, num_events)))
    app.router.add_post(f"/{device_id1}:executeCommand", post_handler)
    app.router.add_get(
        "/image-url-1",
        NewImageHandler(
            list(itertools.repeat(b"image-bytes-1", num_events)), token="g.1.eventToken"
        ),
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 2
    device = devices[0]
    assert device.name == device_id1
    device = devices[1]
    assert device.name == device_id2

    # Use shared event store for all devices
    store = InMemoryEventMediaStore()
    devices[0].event_media_manager.cache_policy.store = store
    devices[1].event_media_manager.cache_policy.store = store

    # Each device has
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0

    ts = datetime.datetime.now(tz=datetime.timezone.utc)
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

    # Each device has a single event
    event_media_manager = devices[0].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 0

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
    assert len(list(await event_media_manager.async_events())) == 1
    event_media_manager = devices[1].event_media_manager
    assert len(list(await event_media_manager.async_events())) == 1


async def test_event_session_image(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    post_handler = NewHandler(
        recorder,
        [
            {
                "results": {
                    "url": "image-url-1",
                    "token": "g.1.eventToken",
                },
            },
            {
                "results": {
                    "url": "image-url-2",
                    "token": "g.2.eventToken",
                },
            },
        ],
    )
    app.router.add_post(f"/{device_id}:executeCommand", post_handler)
    app.router.add_get(
        "/image-url-1", NewImageHandler([b"image-bytes-1"], token="g.1.eventToken")
    )
    app.router.add_get(
        "/image-url-2", NewImageHandler([b"image-bytes-2"], token="g.2.eventToken")
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "90120ecc7-3b57-4eb4-9941-91609f278ec3",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    assert media.contents == b"image-bytes-2"
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
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "image/jpeg"


async def test_event_session_clip_preview(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True

    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
                    "name": device_id,
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
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "video/mp4"


async def test_event_session_without_clip(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True

    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
                    "name": device_id,
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


async def test_event_session_clip_preview_in_second_message(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True

    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
                    "events": {
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
    assert media.contents == b"image-bytes-1"
    assert media.content_type == "video/mp4"


async def test_event_session_clip_preview_issue(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    """Exercise event session clip preview event ordering behavior.

    Reproduces issue https://github.com/home-assistant/core/issues/86314
    """
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True

    callback = EventCallback()
    device.event_media_manager.set_update_callback(callback.async_handle_event)

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
                    "events": {
                        "sdm.devices.events.DoorbellChime.Chime": {
                            "eventSessionId": "1635497756",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "1635497756",
                            "previewUrl": "image-url-1",
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


async def test_persisted_storage_image_event_media_keys(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    data = {
        device_id: [
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


async def test_persisted_storage_image(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    data = {
        device_id: [
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


async def test_persisted_storage_clip_preview(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    data = {
        device_id: [
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


async def test_event_image_lookup_failure(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraEventImage": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

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
                    "name": device_id,
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


async def test_clip_preview_lookup_failure(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.DoorbellChime": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

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
                    "name": device_id,
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


async def test_clip_preview_transcode(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    fake_transcoder = Transcoder("/bin/echo", "")

    # Enable pre-fetch
    device.event_media_manager.cache_policy.fetch = True
    device.event_media_manager.cache_policy.transcoder = fake_transcoder

    ts1 = datetime.datetime.now(tz=datetime.timezone.utc)
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts1.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "previewUrl": "image-url-1",
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

    with patch("google_nest_sdm.transcoder.os.path.exists", new_callable=values), patch(
        "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
        return_value=b"fake-video-thumb-bytes",
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
    await device.async_handle_event(
        await event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": ts2.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": device_id,
                    "events": {
                        "sdm.devices.events.CameraMotion.Motion": {
                            "eventSessionId": "DjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "eventId": "n:1",
                        },
                        "sdm.devices.events.CameraClipPreview.ClipPreview": {
                            "eventSessionId": "DjY5Y3VKaTZwR3o4Y19YbTVfMF",
                            "previewUrl": "image-url-1",
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


async def test_event_manager_event_expiration_with_transcode(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    api_client: Callable[[], Awaitable[google_nest_api.GoogleNestAPI]],
    event_message: Callable[[Dict[str, Any]], Awaitable[EventMessage]],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )

    async def img_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % FAKE_TOKEN
        return aiohttp.web.Response(body=b"image-bytes-1")

    app.router.add_get("/image-url-1", img_handler)

    api = await api_client()
    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id

    fake_transcoder = Transcoder("/bin/echo", "")

    class TestStore(InMemoryEventMediaStore):
        def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
            """Return a predictable media key."""
            return event.event_session_id

        def get_image_media_key(self, device_id: str, event: ImageEventBase) -> str:
            """Return a predictable media key."""
            return event.event_session_id

        def get_clip_preview_media_key(
            self, device_id: str, event: ImageEventBase
        ) -> str:
            """Return a predictable media key."""
            return event.event_session_id

        def get_clip_preview_thumbnail_media_key(
            self, device_id: str, event: ImageEventBase
        ) -> str:
            """Return a predictable media key."""
            return event.event_session_id + "-thumb"

    store = TestStore()
    device.event_media_manager.cache_policy.store = store
    device.event_media_manager.cache_policy.fetch = True
    device.event_media_manager.cache_policy.transcoder = fake_transcoder
    device.event_media_manager.cache_policy.event_cache_size = 5
    event_media_manager = device.event_media_manager

    num_events = 7

    for i in range(0, num_events):
        ts = datetime.datetime.now(tz=datetime.timezone.utc) + datetime.timedelta(
            seconds=i
        )
        await device.async_handle_event(
            await event_message(
                {
                    "eventId": f"0120ecc7-{i}",
                    "timestamp": ts.isoformat(timespec="seconds"),
                    "resourceUpdate": {
                        "name": device_id,
                        "events": {
                            "sdm.devices.events.CameraMotion.Motion": {
                                "eventSessionId": f"CjY5Y3VK..{i}...",
                                "eventId": f"n:{i}",
                            },
                            "sdm.devices.events.CameraClipPreview.ClipPreview": {
                                "eventSessionId": f"CjY5Y3VK..{i}...",
                                "previewUrl": "image-url-1",
                            },
                        },
                    },
                    "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
                }
            )
        )
        assert await store.async_load_media(f"CjY5Y3VK..{i}...") == b"image-bytes-1"

        events = list(await event_media_manager.async_clip_preview_sessions())
        event_token = events[0].event_token

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
        with patch(
            "google_nest_sdm.transcoder.os.path.exists", new_callable=values
        ), patch(
            "google_nest_sdm.event_media.InMemoryEventMediaStore.async_load_media",
            return_value=b"fake-video-thumb-bytes",
        ):
            media = await event_media_manager.get_clip_thumbnail_from_token(event_token)
            assert media
            assert media.contents == b"fake-video-thumb-bytes"
            assert media.content_type == "image/gif"

    event_media_manager = device.event_media_manager
    # All old items are evicted from the cache
    assert len(list(await event_media_manager.async_events())) == 5

    # Old items are evicted from the media store
    assert await store.async_load_media("CjY5Y3VK..0...") is None
    assert await store.async_load_media("CjY5Y3VK..1...") is None
    for i in range(2, num_events):
        assert await store.async_load_media(f"CjY5Y3VK..{i}...") == b"image-bytes-1"
