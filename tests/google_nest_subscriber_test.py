from .context import google_nest_sdm

import aiohttp
import datetime
import json
import mock
import pytest
from pytest_aiohttp import aiohttp_server

from google.auth.credentials import Credentials
from google.cloud import pubsub_v1

from google_nest_sdm.device import AbstractAuth
from google_nest_sdm import google_nest_api
from google_nest_sdm.google_nest_subscriber import (
    AbstractSusbcriberFactory,
    GoogleNestSubscriber,
    EventCallback,
)

PROJECT_ID = "project-id1"
SUBSCRIBER_ID = "subscriber-id1"


class FakeAuth(AbstractAuth):
    def __init__(self, websession):
        super().__init__(websession, "")

    async def async_get_access_token(self) -> str:
        return "some-token"

    async def creds(self) -> Credentials:
        return None


class FakeSubscriberFactory(AbstractSusbcriberFactory):
    async def new_subscriber(self, creds, subscription_name, callback):
        self._callback = callback
        return None

    def push_event(self, event):
        message = mock.create_autospec(
            pubsub_v1.subscriber.message.Message, instance=True
        )
        message.data = json.dumps(event).encode()
        self._callback(message)


class Recorder:
    request = None


class Callback(EventCallback):
    events = []

    def handle_event(self, event):
        self.events.append(event)


def NewDeviceHandler(r: Recorder, devices: dict):
    return NewRequestRecorder(r, [{"devices": devices}])


def NewStructureHandler(r: Recorder, structures: dict):
    return NewRequestRecorder(r, [{"structures": structures}])


def NewRequestRecorder(r: Recorder, response: list):
    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        print(f"handler{response}")
        assert request.headers["Authorization"] == "Bearer some-token"
        s = await request.text()
        r.request = await request.json() if s else {}
        return aiohttp.web.json_response(response.pop(0))

    return handler


async def test_subscribe_no_events(aiohttp_server) -> None:
    subscriber_factory = FakeSubscriberFactory()
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
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
        )
        device_manager = await subscriber.start_async()
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


async def test_subscribe_device_manager(aiohttp_server) -> None:
    subscriber_factory = FakeSubscriberFactory()
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
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
        )
        await subscriber.start_async()
        device_manager = await subscriber.async_device_manager
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
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
        )
        c = Callback()
        device_manager = await subscriber.start_async()
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
        subscriber_factory.push_event(event)

        devices = device_manager.devices
        assert "enterprises/project-id1/devices/device-id1" in devices
        device = devices["enterprises/project-id1/devices/device-id1"]
        trait = device.traits["sdm.devices.traits.Connectivity"]
        assert "OFFLINE" == trait.status


async def test_subscribe_device_manager_init(aiohttp_server) -> None:
    subscriber_factory = FakeSubscriberFactory()
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
            FakeAuth(client), PROJECT_ID, SUBSCRIBER_ID, subscriber_factory
        )
        start_async = subscriber.start_async()
        device_manager = await subscriber.async_device_manager
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
