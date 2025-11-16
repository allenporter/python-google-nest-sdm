from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict
from collections.abc import Generator
from unittest.mock import Mock, patch

import aiohttp
import pytest

from google_nest_sdm import diagnostics
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.event import EventMessage
from google_nest_sdm.exceptions import (
    ConfigurationException,
)
from google_nest_sdm.google_nest_subscriber import (
    GoogleNestSubscriber,
    get_api_env,
)
from google_nest_sdm.streaming_manager import Message, StreamingManager

from .conftest import DeviceHandler, EventCallback, StructureHandler, assert_diagnostics

_LOGGER = logging.getLogger(__name__)

PROJECT_ID = "project-id1"
SUBSCRIPTION_NAME = "projects/some-project-id/subscriptions/subscriber-id1"


@pytest.fixture(name="streaming_manager", autouse=True)
def mock_streaming_manager() -> Generator[Mock, None, None]:
    """Patch StreamingManager and capture the callback."""
    with patch(
        "google_nest_sdm.google_nest_subscriber.StreamingManager", spec=StreamingManager
    ) as mock_manager:
        # Use side_effect to capture the callback
        def mock_init(**kwargs: Any) -> Mock:
            mock_manager.callback = kwargs["callback"]
            return mock_manager

        mock_manager.side_effect = mock_init
        yield mock_manager


@pytest.fixture
def subscriber_client(
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> Callable[[], Awaitable[GoogleNestSubscriber]]:
    async def make_subscriber() -> GoogleNestSubscriber:
        auth = await auth_client()
        return GoogleNestSubscriber(auth, PROJECT_ID, SUBSCRIPTION_NAME)

    return make_subscriber


@pytest.fixture(name="subscriber")
async def subscriber_fixture(
    subscriber_client: Callable[[], Awaitable[GoogleNestSubscriber]],
) -> GoogleNestSubscriber:
    return await subscriber_client()


async def test_subscribe_no_events(
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")
    structure_handler.add_structure()

    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id1 in devices
    assert devices[device_id1].type == "sdm.devices.types.device-type1"
    assert device_id2 in devices
    assert devices[device_id2].type == "sdm.devices.types.device-type2"


async def test_subscribe_update_trait(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
    streaming_manager: Mock,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "ONLINE",
            },
        }
    )
    structure_handler.add_structure()

    subscriber.cache_policy.event_cache_size = 5
    unsub = await subscriber.start_async()
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
    await streaming_manager.callback(Message.from_data(event))

    devices = device_manager.devices
    assert device_id in devices
    device = devices[device_id]
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    unsub()

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "subscriber": {
                "message_processed_count": 1,
                "message_received_count": 1,
                "start": 1,
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
                "traits": {"sdm.devices.traits.Connectivity": {"status": "OFFLINE"}},
                "type": "sdm.devices.types.device-type1",
            },
        },
    )


async def test_subscribe_device_manager_init(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
) -> None:
    device_id1 = device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_id2 = device_handler.add_device(device_type="sdm.devices.types.device-type2")
    structure_handler.add_structure()

    start_async = subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    unsub = await start_async
    devices = device_manager.devices
    assert device_id1 in devices
    assert devices[device_id1].type == "sdm.devices.types.device-type1"
    assert device_id2 in devices
    assert devices[device_id2].type == "sdm.devices.types.device-type2"
    unsub()


async def test_subscriber_id_error(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
    auth = await auth_client()

    subscriber = GoogleNestSubscriber(
        auth,
        PROJECT_ID,
        "bad-subscriber-id",
    )
    with pytest.raises(ConfigurationException):
        await subscriber.start_async()


async def test_subscribe_thread_update(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
    streaming_manager: Mock,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
        }
    )
    structure_handler.add_structure()

    subscriber.cache_policy.event_cache_size = 5
    unsub = await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices

    subscriber_callback = EventCallback()
    subscriber.set_update_callback(subscriber_callback.async_handle_event)

    device_callback = EventCallback()
    devices[device_id].add_event_callback(device_callback.async_handle_event)

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
    await streaming_manager.callback(Message.from_data(event))

    # Verify the message is received. The full content is verified below.
    assert len(subscriber_callback.messages) == 1
    message: EventMessage = subscriber_callback.messages[0]
    assert message.event_id == "6f29332e-5537-47f6-a3f9-840c307340f5"

    # Device-level callback also received the message
    assert len(device_callback.messages) == 1

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
    await streaming_manager.callback(Message.from_data(event))

    assert len(subscriber_callback.messages) == 1
    message = subscriber_callback.messages[0]
    assert message.event_id == "6f29332e-5537-47f6-a3f9-840c307340f5"
    assert message.event_sessions
    assert len(message.event_sessions) == 1
    assert "CjY5Y3VKaTZwR3o4Y19YbTVfMF..." in message.event_sessions
    events = message.event_sessions["CjY5Y3VKaTZwR3o4Y19YbTVfMF..."]
    assert len(events) == 2
    assert "sdm.devices.events.CameraMotion.Motion" in events
    assert "sdm.devices.events.CameraClipPreview.ClipPreview" in events

    # Device-level callback invoked with both raw messages
    assert len(device_callback.messages) == 2
    message = device_callback.messages[0]
    assert message.event_id == "6f29332e-5537-47f6-a3f9-840c307340f5"
    message = device_callback.messages[1]
    assert message.event_id == "7f29332e-5537-47f6-a3f9-840c307340f5"

    unsub()


async def test_subscribe_thread_update_new_events(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
    streaming_manager: Mock,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.CameraClipPreview": {},
            "sdm.devices.traits.CameraMotion": {},
            "sdm.devices.traits.CameraPerson": {},
        }
    )
    structure_handler.add_structure()

    subscriber.cache_policy.event_cache_size = 5

    unsub = await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices

    callback = EventCallback()
    subscriber.set_update_callback(callback.async_handle_event)

    device_callback = EventCallback()
    devices[device_id].add_event_callback(device_callback.async_handle_event)

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
    await streaming_manager.callback(Message.from_data(event))
    assert len(callback.messages) == 1

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
    await streaming_manager.callback(Message.from_data(event2))

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

    # Device also receives the same messages
    assert len(device_callback.messages) == 2

    unsub()


async def test_message_ack_timeout(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    streaming_manager: Mock,
    subscriber: GoogleNestSubscriber,
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "ONLINE",
            },
        }
    )
    structure_id = structure_handler.add_structure()

    subscriber.cache_policy.event_cache_size = 5
    unsub = await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()
    devices = device_manager.devices
    assert device_id in devices

    async def async_handle_event(_: Any) -> None:
        await asyncio.sleep(10)

    subscriber.set_update_callback(async_handle_event)
    event = {
        "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
        "timestamp": "2019-01-01T00:00:01Z",
        "relationUpdate": {
            "type": "CREATED",
            "subject": structure_id,
            "object": device_id,
        },
        "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
    }
    with patch(
        "google_nest_sdm.google_nest_subscriber.MESSAGE_ACK_TIMEOUT_SECONDS", 0.01
    ):
        with pytest.raises(TimeoutError, match="Message ack timeout"):
            await streaming_manager.callback(Message.from_data(event))

    unsub()


async def test_refresh_hack_on_invalid_thermostat_traits(
    app: aiohttp.web.Application,
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    subscriber: GoogleNestSubscriber,
    streaming_manager: Mock,
) -> None:
    """Test that invalid thermostat traits are ignored and triggers a refresh."""

    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "MANUAL_ECO",
                "heatCelsius": 20.0,
                "coolCelsius": 22.0,
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "HEAT",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    structure_handler.add_structure()

    subscriber.cache_policy.event_cache_size = 5
    unsub = await subscriber.start_async()
    device_manager = await subscriber.async_get_device_manager()

    device = device_manager.devices.get(device_id)
    assert device

    # Verify initial device state
    trait = device.traits.get("sdm.devices.traits.ThermostatEco")
    assert trait
    assert set(trait.available_modes) == set(["MANUAL_ECO", "OFF"])
    assert trait.mode == "MANUAL_ECO"
    assert trait.heat_celsius == 20.0
    assert trait.cool_celsius == 22.0

    trait = device.traits.get("sdm.devices.traits.ThermostatMode")
    assert trait
    assert set(trait.available_modes) == set(["HEAT", "COOL", "HEATCOOL", "OFF"])
    assert trait.mode == "HEAT"

    trait = device.traits.get("sdm.devices.traits.ThermostatHvac")
    assert trait
    assert trait.status == "HEATING"

    trait = device.traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint")
    assert trait
    assert trait.heat_celsius == 20.0

    # Update the state on the server to something arbitrary. Later we will verify
    # that a request was made to get the latest server state.
    trait = device_handler.devices[device_id]["traits"][
        "sdm.devices.traits.ThermostatEco"
    ]
    trait["heatCelsius"] = 19.0

    # Simulate a case where the nest publisher sends an invalid message. This
    # will be ignored and will trigger another state refresh.
    await streaming_manager.callback(
        Message.from_data(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device.name,
                    "traits": {
                        "sdm.devices.traits.ThermostatMode": {
                            "mode": "OFF",
                            "availableModes": ["OFF"],
                        },
                        "sdm.devices.traits.ThermostatEco": {
                            "availableModes": ["OFF", "MANUAL_ECO"],
                            "mode": "OFF",
                            "heatCelsius": 0.0,
                            "coolCelsius": 0.0,
                        },
                        "sdm.devices.traits.ThermostatTemperatureSetpoint": {},
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )

    device = device_manager.devices.get(device_id)
    assert device

    # Verify the invalid message is dropped and the server update is reflected
    trait = device.traits.get("sdm.devices.traits.ThermostatEco")
    assert trait
    assert set(trait.available_modes) == set(["MANUAL_ECO", "OFF"])
    assert trait.mode == "MANUAL_ECO"
    assert trait.heat_celsius == 19.0  # State update reflected
    assert trait.cool_celsius == 22.0

    trait = device.traits.get("sdm.devices.traits.ThermostatMode")
    assert trait
    assert set(trait.available_modes) == set(["HEAT", "COOL", "HEATCOOL", "OFF"])
    assert trait.mode == "HEAT"

    trait = device.traits.get("sdm.devices.traits.ThermostatHvac")
    assert trait
    assert trait.status == "HEATING"

    trait = device.traits.get("sdm.devices.traits.ThermostatTemperatureSetpoint")
    assert trait
    assert trait.heat_celsius == 20.0

    unsub()


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
