import asyncio
import json
from unittest.mock import create_autospec

import aiohttp
import pytest
from google.api_core.exceptions import ClientError, Unauthenticated
from google.cloud import pubsub_v1

from google_nest_sdm.device import AbstractAuth
from google_nest_sdm.exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)
from google_nest_sdm.google_nest_subscriber import (
    AbstractSusbcriberFactory,
    GoogleNestSubscriber,
)

PROJECT_ID = "project-id1"
SUBSCRIBER_ID = "projects/some-project-id/subscriptions/subscriber-id1"
FAKE_TOKEN = "some-token"


class FakeAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "")

    async def async_get_access_token(self) -> str:
        return FAKE_TOKEN


class RefreshingAuth(FakeAuth):
    def __init__(self, websession):
        super().__init__(websession)
        self._updated_token = None

    async def async_get_access_token(self) -> str:
        if not self._updated_token:
            resp = await self._websession.request("get", "/refresh-auth")
            resp.raise_for_status()
            json = await resp.json()
            self._updated_token = json["token"]
        return self._updated_token


class FakeSubscriberFactory(AbstractSusbcriberFactory):
    def __init__(self, tasks: list = None):
        self.tasks = tasks

    async def async_new_subscriber(
        self, creds, subscription_name, loop, async_callback
    ):
        self._async_callback = async_callback
        if self.tasks:
            return asyncio.create_task(self.tasks.pop(0)())
        return None

    async def async_push_event(self, event):
        message = create_autospec(pubsub_v1.subscriber.message.Message, instance=True)
        message.data = json.dumps(event).encode()
        return await self._async_callback(message)


class Recorder:
    request = None


def NewDeviceHandler(r: Recorder, devices: dict, token=FAKE_TOKEN):
    return NewHandler(r, [{"devices": devices}], token=token)


def NewStructureHandler(r: Recorder, structures: dict, token=FAKE_TOKEN):
    return NewHandler(r, [{"structures": structures}], token=token)


def NewHandler(r: Recorder, response: list, token=FAKE_TOKEN):
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.headers["Authorization"] == "Bearer %s" % token
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(response.pop(0))

    return handler


async def test_subscribe_no_events(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, FakeSubscriberFactory()
        )
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


async def test_subscribe_device_manager(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client),
            PROJECT_ID,
            SUBSCRIBER_ID,
            FakeSubscriberFactory(),
        )
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


async def test_subscribe_update_trait(aiohttp_server) -> None:
    subscriber_factory = FakeSubscriberFactory()
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

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client),
            PROJECT_ID,
            SUBSCRIBER_ID,
            subscriber_factory=subscriber_factory,
        )
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


async def test_subscribe_device_manager_init(aiohttp_server) -> None:
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

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, FakeSubscriberFactory()
        )
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


async def test_subscriber_watchdog(aiohttp_server) -> None:
    # Waits for the test to wake up the background thread
    event1 = asyncio.Event()

    async def task1():
        await event1.wait()

    event2 = asyncio.Event()

    async def task2():
        event2.set()

    subscriber_factory = FakeSubscriberFactory(tasks=[task1, task2])
    r = Recorder()
    app = aiohttp.web.Application()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client),
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


async def test_subscriber_error(aiohttp_server) -> None:
    class FailingFactory(AbstractSusbcriberFactory):
        async def async_new_subscriber(
            self, creds, subscription_name, loop, async_callback
        ):
            raise ClientError("Some error")

    app = aiohttp.web.Application()
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, FailingFactory()
        )
        with pytest.raises(SubscriberException):
            await subscriber.start_async()
        subscriber.stop_async()


async def test_subscriber_auth_error(aiohttp_server) -> None:
    class FailingFactory(AbstractSusbcriberFactory):
        async def async_new_subscriber(
            self, creds, subscription_name, loop, async_callback
        ):
            raise Unauthenticated("Auth failure")

    app = aiohttp.web.Application()
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, FailingFactory()
        )
        with pytest.raises(AuthException):
            await subscriber.start_async()
        subscriber.stop_async()


async def test_auth_refresh(aiohttp_server) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response({"token": "updated-token"})

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            RefreshingAuth(client), PROJECT_ID, SUBSCRIBER_ID, FakeSubscriberFactory()
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


async def test_auth_refresh_error(aiohttp_server) -> None:
    r = Recorder()

    async def auth_handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app = aiohttp.web.Application()
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
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            RefreshingAuth(client), PROJECT_ID, SUBSCRIBER_ID, FakeSubscriberFactory()
        )
        with pytest.raises(AuthException):
            await subscriber.start_async()
        subscriber.stop_async()


async def test_subscriber_id_error(aiohttp_server) -> None:
    app = aiohttp.web.Application()
    r = Recorder()
    app.router.add_get("/enterprises/project-id1/devices", NewDeviceHandler(r, []))
    app.router.add_get(
        "/enterprises/project-id1/structures",
        NewStructureHandler(r, []),
    )
    server = await aiohttp_server(app)

    async with aiohttp.test_utils.TestClient(server) as client:
        subscriber = GoogleNestSubscriber(
            FakeAuth(client), PROJECT_ID, "bad-subscriber-id", FakeSubscriberFactory()
        )
        with pytest.raises(ConfigurationException):
            await subscriber.start_async()
        subscriber.stop_async()
