from __future__ import annotations

import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional
from unittest.mock import create_autospec, Mock

import aiohttp
import pytest
from google.auth.exceptions import RefreshError, GoogleAuthError, TransportError
from google.api_core.exceptions import ClientError, Unauthenticated
from google.cloud import pubsub_v1
from google.oauth2.credentials import Credentials

from google_nest_sdm import diagnostics
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.event import EventMessage
from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.google_nest_subscriber import (
    AbstractSubscriberFactory,
    GoogleNestSubscriber,
    get_api_env,
    refresh_creds,
)

from .conftest import DeviceHandler, EventCallback, StructureHandler, assert_diagnostics

PROJECT_ID = "project-id1"
SUBSCRIBER_ID = "projects/some-project-id/subscriptions/subscriber-id1"


class FakeSubscriberFactory(AbstractSubscriberFactory):
    def __init__(self) -> None:
        self.tasks: Optional[Any] = None

    async def async_create_subscription(
        self,
        creds: Credentials,
        subscription_name: str,
        topic_name: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        return

    async def async_delete_subscription(
        self,
        creds: Credentials,
        subscription_name: str,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        return

    async def async_new_subscriber(
        self,
        creds: Credentials,
        subscription_name: str,
        loop: asyncio.AbstractEventLoop,
        async_callback: Callable[
            [pubsub_v1.subscriber.message.Message], Awaitable[None]
        ],
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        self._async_callback = async_callback
        if self.tasks:
            return asyncio.create_task(self.tasks.pop(0)())
        return None

    async def async_push_event(self, event: Dict[str, Any]) -> None:
        message = create_autospec(pubsub_v1.subscriber.message.Message, instance=True)
        message.data = json.dumps(event).encode()
        return await self._async_callback(message)


@pytest.fixture
def subscriber_factory() -> FakeSubscriberFactory:
    return FakeSubscriberFactory()


@pytest.fixture
def subscriber_client(
    subscriber_factory: FakeSubscriberFactory,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[GoogleNestSubscriber]]:
    async def make_subscriber(
        factory: Optional[AbstractSubscriberFactory] = subscriber_factory,
    ) -> GoogleNestSubscriber:
        auth = await auth_client()
        assert factory
        return GoogleNestSubscriber(auth, PROJECT_ID, SUBSCRIBER_ID, factory)

    return make_subscriber


async def test_refresh_creds() -> None:
    """Test low level refresh errors."""
    mock_refresh = Mock()
    mock_creds = Mock()
    mock_creds.refresh = mock_refresh
    refresh_creds(mock_creds)
    assert mock_refresh.call_count == 1


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (RefreshError(), AuthException),
        (TransportError(), SubscriberException),
        (GoogleAuthError(), SubscriberException),
    ],
)
async def test_refresh_creds_error(raised: Exception, expected: Any) -> None:
    """Test low level refresh errors."""
    mock_refresh = Mock()
    mock_refresh.side_effect = raised
    mock_creds = Mock()
    mock_creds.refresh = mock_refresh
    with pytest.raises(expected):
        refresh_creds(mock_creds)


async def test_subscribe_no_events(
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id1 in devices
    assert devices[device_id1].type == "sdm.devices.types.device-type1"
    assert device_id2 in devices
    assert devices[device_id2].type == "sdm.devices.types.device-type2"
    subscriber.stop_async()


async def test_subscribe_device_manager(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id1 in devices
    assert devices[device_id1].type == "sdm.devices.types.device-type1"
    assert device_id2 in devices
    assert devices[device_id2].type == "sdm.devices.types.device-type2"
    subscriber.stop_async()

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "subscriber": {
                "start": 1,
                "stop": 1,
            },
        },
    )


async def test_subscribe_update_trait(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "ONLINE",
            },
        }
    )
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    subscriber.cache_policy.event_cache_size = 5
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices
    device = devices[device_id]
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status

    event = {
        "eventId": "6f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:06.851Z",
        "resourceUpdate": {
            "name": device_id,
            "traits": {
                "sdm.devices.traits.Connectivity": {
                    "status": "OFFLINE",
                }
            },
        },
        "userId": "AVPHwEv75jw4WFshx6-XhBLhotn3r8IXOzCusfSOn5QU",
    }
    await subscriber_factory.async_push_event(event)

    devices = device_manager.devices
    assert device_id in devices
    device = devices[device_id]
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    subscriber.stop_async()

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "subscriber": {
                "message_acked_count": 1,
                "message_received_count": 1,
                "start": 1,
                "stop": 1,
            },
        },
    )
    assert_diagnostics(
        device.get_diagnostics(),
        {
            "event_media": {"event": 1},
            "data": {
                "name": "**REDACTED**",
                "parentRelations": [],
                "traits": {"sdm.devices.traits.Connectivity": {"status": "ONLINE"}},
                "type": "sdm.devices.types.device-type1",
            },
        },
    )


async def test_subscribe_device_manager_init(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    start_async = subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    await start_async
    devices = device_manager.devices
    assert device_id1 in devices
    assert devices[device_id1].type == "sdm.devices.types.device-type1"
    assert device_id2 in devices
    assert devices[device_id2].type == "sdm.devices.types.device-type2"
    subscriber.stop_async()


async def test_subscriber_watchdog(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    # Waits for the test to wake up the background thread
    event1 = asyncio.Event()

    async def task1() -> None:
        await event1.wait()

    event2 = asyncio.Event()

    async def task2() -> None:
        event2.set()

    subscriber_factory.tasks = [task1, task2]

    auth = await auth_client()
    subscriber = GoogleNestSubscriber(
        auth,
        PROJECT_ID,
        SUBSCRIBER_ID,
        subscriber_factory=subscriber_factory,
        watchdog_check_interval_seconds=0.1,
        watchdog_restart_delay_min_seconds=0.1,
    )
    assert len(subscriber_factory.tasks) == 2
    await subscriber.start_async()
    assert len(subscriber_factory.tasks) == 1
    # Wait for the subscriber to start, then shut it down
    event1.set()
    # Block until the new subscriber starts, and notifies this to wake up
    await event2.wait()
    assert len(subscriber_factory.tasks) == 0
    subscriber.stop_async()


async def test_subscriber_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[
        [Optional[AbstractSubscriberFactory]], Awaitable[GoogleNestSubscriber]
    ],
) -> None:
    class FailingFactory(FakeSubscriberFactory):
        async def async_new_subscriber(
            self,
            creds: Credentials,
            subscription_name: str,
            loop: asyncio.AbstractEventLoop,
            async_callback: Callable[
                [pubsub_v1.subscriber.message.Message], Awaitable[None]
            ],
        ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
            raise ClientError("Some error")  # type: ignore

    subscriber = await subscriber_client(FailingFactory())

    with pytest.raises(SubscriberException):
        await subscriber.start_async()
    subscriber.stop_async()

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "subscriber": {
                "start": 1,
                "start.api_error": 1,
                "stop": 1,
            },
        },
    )


async def test_subscriber_auth_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[
        [Optional[AbstractSubscriberFactory]], Awaitable[GoogleNestSubscriber]
    ],
) -> None:
    class FailingFactory(FakeSubscriberFactory):
        async def async_new_subscriber(
            self,
            creds: Credentials,
            subscription_name: str,
            loop: asyncio.AbstractEventLoop,
            async_callback: Callable[
                [pubsub_v1.subscriber.message.Message], Awaitable[None]
            ],
        ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
            raise Unauthenticated("Auth failure")  # type: ignore

    subscriber = await subscriber_client(FailingFactory())
    with pytest.raises(AuthException):
        await subscriber.start_async()
    subscriber.stop_async()


async def test_auth_refresh(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"token": "updated-token"})

    device_handler.token = "updated-token"
    device_id = device_handler.add_device(device_type="sdm.devices.types.device-type1")

    structure_handler.token = "updated-token"
    structure_handler.add_structure()

    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
    )
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices
    assert devices[device_id].type == "sdm.devices.types.device-type1"
    subscriber.stop_async()


async def test_auth_refresh_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    device_handler.token = "updated-token"
    device_handler.add_device()
    structure_handler.token = "updated-token"
    structure_handler.add_structure()

    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
    )

    with pytest.raises(AuthException):
        await subscriber.start_async()
    subscriber.stop_async()


async def test_subscriber_id_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    auth = await auth_client()

    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, "bad-subscriber-id", subscriber_factory
    )
    with pytest.raises(ConfigurationException):
        await subscriber.start_async()
    subscriber.stop_async()


async def test_subscribe_thread_update(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    subscriber.cache_policy.event_cache_size = 5
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices

    callback = EventCallback()
    subscriber.set_update_callback(callback.async_handle_event)

    event = {
        "eventId": "6f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:06.851Z",
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
        "userId": "AVPHwEv75jw4WFshx6-XhBLhotn3r8IXOzCusfSOn5QU",
        "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
        "resourcegroup": [
            "enterprises/project-id1/devices/device-id1",
        ],
        "eventThreadState": "STARTED",
    }
    await subscriber_factory.async_push_event(event)

    # End the thread (resource update is identical)
    event = {
        "eventId": "7f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:07.851Z",
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
        "userId": "AVPHwEv75jw4WFshx6-XhBLhotn3r8IXOzCusfSOn5QU",
        "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
        "resourcegroup": [
            "enterprises/project-id1/devices/device-id1",
        ],
        "eventThreadState": "ENDED",
    }
    await subscriber_factory.async_push_event(event)

    assert len(callback.messages) == 1
    message: EventMessage = callback.messages[0]
    assert message.event_id == "6f29332e-5537-47f6-a3f9-840c307340f5"
    assert message.event_sessions
    assert len(message.event_sessions) == 1
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in message.event_sessions
    events = message.event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert len(events) == 2
    assert "sdm.devices.events.CameraMotion.Motion" in events
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in events

    subscriber.stop_async()


async def test_subscribe_thread_update_new_events(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
            "sdm.devices.traits.CameraPerson": {},
        }
    )
    structure_handler.add_structure()

    subscriber = await subscriber_client()
    subscriber.cache_policy.event_cache_size = 5
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices

    callback = EventCallback()
    subscriber.set_update_callback(callback.async_handle_event)

    event = {
        "eventId": "6f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:06.851Z",
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
        "userId": "AVPHwEv75jw4WFshx6-XhBLhotn3r8IXOzCusfSOn5QU",
        "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
        "resourcegroup": [
            "enterprises/project-id1/devices/device-id1",
        ],
        "eventThreadState": "STARTED",
    }
    await subscriber_factory.async_push_event(event)

    # End the thread (resource update is identical)
    event2 = {
        "eventId": "7f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:07.851Z",
        "resourceUpdate": {
            "name": device_id,
            "events": {
                "sdm.devices.events.CameraMotion.Motion": {
                    "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId": "n:1",
                },
                "sdm.devices.events.CameraPerson.Person": {
                    "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "eventId": "n:2",
                },
                "sdm.devices.events.CameraClipPreview.ClipPreview": {
                    "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                    "previewUrl": "image-url-1",
                },
            },
        },
        "userId": "AVPHwEv75jw4WFshx6-XhBLhotn3r8IXOzCusfSOn5QU",
        "eventThreadId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
        "resourcegroup": [
            "enterprises/project-id1/devices/device-id1",
        ],
        "eventThreadState": "ENDED",
    }
    await subscriber_factory.async_push_event(event2)

    assert len(callback.messages) == 2
    message: EventMessage = callback.messages[0]
    assert message.event_id == "6f29332e-5537-47f6-a3f9-840c307340f5"
    assert message.event_sessions
    assert len(message.event_sessions) == 1
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in message.event_sessions
    events = message.event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert len(events) == 2
    assert "sdm.devices.events.CameraMotion.Motion" in events
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in events

    message = callback.messages[1]
    assert message.event_id == "7f29332e-5537-47f6-a3f9-840c307340f5"
    assert message.event_sessions
    assert len(message.event_sessions) == 1
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in message.event_sessions
    events = message.event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert len(events) == 1
    assert "sdm.devices.events.CameraPerson.Person" in events

    subscriber.stop_async()


def test_api_env_prod() -> None:
    env = get_api_env("prod")
    assert (
        env.authorize_url_format
        == "https://nestservices.google.com/partnerconnections/{project_id}/auth"
    )
    assert env.api_url == "https://smartdevicemanagement.googleapis.com/v1"

    env = get_api_env(None)
    assert (
        env.authorize_url_format
        == "https://nestservices.google.com/partnerconnections/{project_id}/auth"
    )
    assert env.api_url == "https://smartdevicemanagement.googleapis.com/v1"


def test_api_env_preprod() -> None:
    env = get_api_env("preprod")
    assert env.authorize_url_format == (
        "https://sdmresourcepicker-preprod.sandbox.google.com/partnerconnections/"
        "{project_id}/auth"
    )
    assert env.api_url == "https://preprod-smartdevicemanagement.googleapis.com/v1"


def test_api_env_invalid() -> None:
    with pytest.raises(ValueError):
        get_api_env("invalid")
