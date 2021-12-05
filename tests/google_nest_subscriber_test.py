import asyncio
import json
from typing import Any, Awaitable, Callable, Dict, Optional
from unittest.mock import create_autospec

import aiohttp
import pytest
from google.api_core.exceptions import ClientError, Unauthenticated
from google.cloud import pubsub_v1
from google.oauth2.credentials import Credentials

from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.google_nest_subscriber import (
    AbstractSubscriberFactory,
    GoogleNestSubscriber,
)

from .conftest import NewDeviceHandler, NewStructureHandler, Recorder

PROJECT_ID = "project-id1"
SUBSCRIBER_ID = "projects/some-project-id/subscriptions/subscriber-id1"
FAKE_TOKEN = "some-token"


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


async def test_subscribe_no_events(
    app: aiohttp.web.Application,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "type": "sdm.devices.types.device-type1",
                "traits": {},
                "parentRelations": [],
            },
            {
                "name": "enterprises/project-id1/devices/device-id2",
                "type": "sdm.devices.types.device-type2",
                "traits": {},
                "parentRelations": [],
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
        ),
    )

    subscriber = await subscriber_client()
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert "enterprises/project-id1/devices/device-id1" in devices
    assert (
        "sdm.devices.types.device-type1"
        == devices["enterprises/project-id1/devices/device-id1"].type
    )
    assert "enterprises/project-id1/devices/device-id2" in devices
    assert (
        "sdm.devices.types.device-type2"
        == devices["enterprises/project-id1/devices/device-id2"].type
    )
    subscriber.stop_async()


async def test_subscribe_device_manager(
    app: aiohttp.web.Application,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "type": "sdm.devices.types.device-type1",
                "traits": {},
                "parentRelations": [],
            },
            {
                "name": "enterprises/project-id1/devices/device-id2",
                "type": "sdm.devices.types.device-type2",
                "traits": {},
                "parentRelations": [],
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
        ),
    )

    subscriber = await subscriber_client()
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert "enterprises/project-id1/devices/device-id1" in devices
    assert (
        "sdm.devices.types.device-type1"
        == devices["enterprises/project-id1/devices/device-id1"].type
    )
    assert "enterprises/project-id1/devices/device-id2" in devices
    assert (
        "sdm.devices.types.device-type2"
        == devices["enterprises/project-id1/devices/device-id2"].type
    )
    subscriber.stop_async()


async def test_subscribe_update_trait(
    app: aiohttp.web.Application,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "type": "sdm.devices.types.device-type1",
                "traits": {
                    "sdm.devices.traits.Connectivity": {
                        "status": "ONLINE",
                    },
                },
                "parentRelations": [],
            }
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
        ),
    )

    subscriber = await subscriber_client()
    subscriber.cache_policy.event_cache_size = 5
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert "enterprises/project-id1/devices/device-id1" in devices
    device = devices["enterprises/project-id1/devices/device-id1"]
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status

    event = {
        "eventId": "6f29332e-5537-47f6-a3f9-840c307340f5",
        "timestamp": "2020-10-10T07:09:06.851Z",
        "resourceUpdate": {
            "name": "enterprises/project-id1/devices/device-id1",
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
    assert "enterprises/project-id1/devices/device-id1" in devices
    device = devices["enterprises/project-id1/devices/device-id1"]
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    subscriber.stop_async()


async def test_subscribe_device_manager_init(
    app: aiohttp.web.Application,
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> None:
    r = Recorder()
    handler = NewDeviceHandler(
        r,
        [
            {
                "name": "enterprises/project-id1/devices/device-id1",
                "type": "sdm.devices.types.device-type1",
                "traits": {},
                "parentRelations": [],
            },
            {
                "name": "enterprises/project-id1/devices/device-id2",
                "type": "sdm.devices.types.device-type2",
                "traits": {},
                "parentRelations": [],
            },
        ],
    )

    app.router.add_get("/enterprises/project-id1/devices", handler)
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
        ),
    )

    subscriber = await subscriber_client()
    start_async = subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    await start_async
    devices = device_manager.devices
    assert "enterprises/project-id1/devices/device-id1" in devices
    assert (
        "sdm.devices.types.device-type1"
        == devices["enterprises/project-id1/devices/device-id1"].type
    )
    assert "enterprises/project-id1/devices/device-id2" in devices
    assert (
        "sdm.devices.types.device-type2"
        == devices["enterprises/project-id1/devices/device-id2"].type
    )
    subscriber.stop_async()


async def test_subscriber_watchdog(
    app: aiohttp.web.Application,
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
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )

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

    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )

    subscriber = await subscriber_client(FailingFactory())

    with pytest.raises(SubscriberException):
        await subscriber.start_async()
    subscriber.stop_async()


async def test_subscriber_auth_error(
    app: aiohttp.web.Application,
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

    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )
    subscriber = await subscriber_client(FailingFactory())
    with pytest.raises(AuthException):
        await subscriber.start_async()
    subscriber.stop_async()


async def test_auth_refresh(
    app: aiohttp.web.Application,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"token": "updated-token"})

    app.router.add_get(
        "/enterprises/project-id1/devices",
        NewDeviceHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "type": "sdm.devices.types.device-type1",
                    "traits": {},
                    "parentRelations": [],
                },
            ],
            token="updated-token",
        ),
    )
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
            token="updated-token",
        ),
    )
    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
    )
    await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert "enterprises/project-id1/devices/device-id1" in devices
    assert (
        "sdm.devices.types.device-type1"
        == devices["enterprises/project-id1/devices/device-id1"].type
    )
    subscriber.stop_async()


async def test_auth_refresh_error(
    app: aiohttp.web.Application,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app.router.add_get(
        "/enterprises/project-id1/devices",
        NewDeviceHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/devices/device-id1",
                    "type": "sdm.devices.types.device-type1",
                    "traits": {},
                    "parentRelations": [],
                },
            ],
            token="updated-token",
        ),
    )
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(
            r,
            [
                {
                    "name": "enterprises/project-id1/structures/structure-id1",
                }
            ],
            token="updated-token",
        ),
    )
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
    auth_client: Callable[[], Awaitable[AbstractAuth]],
    subscriber_factory: FakeSubscriberFactory,
) -> None:
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )

    auth = await auth_client()

    subscriber = GoogleNestSubscriber(
        auth, PROJECT_ID, "bad-subscriber-id", subscriber_factory
    )
    with pytest.raises(ConfigurationException):
        await subscriber.start_async()
    subscriber.stop_async()
