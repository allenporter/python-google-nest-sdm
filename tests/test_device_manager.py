import datetime
from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.device_traits import ConnectivityTrait
from google_nest_sdm.event import EventMessage
from google_nest_sdm.structure import Structure


@pytest.fixture
def event_message_with_time(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage]
) -> Callable[[str, str], EventMessage]:
    def make_event(timestamp: str, status: str) -> EventMessage:
        return fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": timestamp,
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": status,
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )

    return make_event


def test_add_device(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    mgr = DeviceManager()
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name1",
                "type": "sdm.devices.types.SomeDeviceType",
            }
        )
    )
    assert 1 == len(mgr.devices)
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name2",
                "type": "sdm.devices.types.SomeDeviceType",
            }
        )
    )
    assert 2 == len(mgr.devices)


def test_duplicate_device(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    mgr = DeviceManager()
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name1",
                "type": "sdm.devices.types.SomeDeviceType",
            }
        )
    )
    assert 1 == len(mgr.devices)
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name1",
                "type": "sdm.devices.types.SomeDeviceType",
            }
        )
    )
    assert 1 == len(mgr.devices)


async def test_update_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    mgr = DeviceManager()
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name1",
                "type": "sdm.devices.types.SomeDeviceType",
                "traits": {
                    "sdm.devices.traits.Connectivity": {
                        "status": "OFFLINE",
                    },
                },
            }
        )
    )
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "ONLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status


async def test_device_created_in_structure(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    mgr = DeviceManager()
    mgr.add_device(
        fake_device(
            {
                "name": "enterprises/project-id/devices/device-id",
                "type": "sdm.devices.types.SomeDeviceType",
                "parentRelations": [],
            }
        )
    )
    assert 1 == len(mgr.devices)
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    assert 0 == len(device.parent_relations)

    mgr.add_structure(
        Structure.MakeStructure(
            {
                "name": "enterprises/project-id/structures/structure-id",
                "traits": {
                    "sdm.structures.traits.Info": {
                        "customName": "Structure Name",
                    },
                },
            }
        )
    )
    assert 1 == len(mgr.structures)
    structure = mgr.structures["enterprises/project-id/structures/structure-id"]
    assert "sdm.structures.traits.Info" in structure.traits
    trait = structure.traits["sdm.structures.traits.Info"]
    assert "Structure Name" == trait.custom_name

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "relationUpdate": {
                    "type": "CREATED",
                    "subject": "enterprises/project-id/structures/structure-id",
                    "object": "enterprises/project-id/devices/device-id",
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    assert {
        "enterprises/project-id/structures/structure-id": "Structure Name",
    } == device.parent_relations

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "relationUpdate": {
                    "type": "DELETED",
                    "subject": "enterprises/project-id/structures/structure-id",
                    "object": "enterprises/project-id/devices/device-id",
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["enterprises/project-id/devices/device-id"]
    assert 0 == len(device.parent_relations)


async def test_device_event_callback(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.Connectivity": {
                    "status": "OFFLINE",
                },
            },
        }
    )
    mgr = DeviceManager()
    mgr.add_device(device)
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        async def async_handle_event(self, event_message: EventMessage) -> None:
            self.invoked = True

    callback = MyCallback()
    unregister = device.add_event_callback(callback.async_handle_event)
    assert not callback.invoked

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "ONLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status
    assert callback.invoked

    # Test event not for this device
    callback.invoked = False  # type: ignore[unreachable]
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "some-device-id",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "ONLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    assert not callback.invoked

    # Unregister the callback.  The event is still processed, but the callback
    # is not invoked
    unregister()
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "OFFLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    assert not callback.invoked


async def test_device_update_listener(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.Connectivity": {
                    "status": "OFFLINE",
                },
            },
        }
    )
    mgr = DeviceManager()
    mgr.add_device(device)
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        def async_handle_event(self) -> None:
            print("async_handle_event")
            self.invoked = True

    callback = MyCallback()
    unregister = device.add_update_listener(callback.async_handle_event)
    assert not callback.invoked

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "ONLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status
    assert callback.invoked

    # Test event not for this device
    callback.invoked = False  # type: ignore[unreachable]
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "some-device-id",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "ONLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    assert not callback.invoked

    # Unregister the callback.  The event is still processed, but the callback
    # is not invoked
    unregister()
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.Connectivity": {
                            "status": "OFFLINE",
                        }
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    assert not callback.invoked


async def test_event_image_tracking(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Hold on to the last receieved event image."""
    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.CameraEventImage": {},
                "sdm.devices.traits.CameraMotion": {},
                "sdm.devices.traits.CameraSound": {},
            },
        }
    )
    mgr = DeviceManager()
    mgr.add_device(device)
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    trait = device.traits["sdm.devices.traits.CameraMotion"]
    assert trait.active_event is None

    now = datetime.datetime.now(tz=datetime.timezone.utc)
    timestamp = now - datetime.timedelta(seconds=10)
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": timestamp.isoformat(timespec="seconds"),
                "resourceUpdate": {
                    "name": "my/device/name1",
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
    device = mgr.devices["my/device/name1"]
    assert "sdm.devices.traits.CameraMotion" in device.traits
    trait = device.traits["sdm.devices.traits.CameraMotion"]
    assert trait.active_event is not None

    assert device.active_event_trait == trait


async def test_update_trait_ordering(
    fake_device: Callable[[Dict[str, Any]], Device],
    event_message_with_time: Callable[[str, str], EventMessage],
) -> None:
    mgr = DeviceManager()
    mgr.add_device(
        fake_device(
            {
                "name": "my/device/name1",
                "type": "sdm.devices.types.SomeDeviceType",
                "traits": {
                    "sdm.devices.traits.Connectivity": {
                        "status": "OFFLINE",
                    },
                },
            }
        )
    )

    def get_connectivity() -> ConnectivityTrait:
        assert 1 == len(mgr.devices)
        device = mgr.devices["my/device/name1"]
        assert "sdm.devices.traits.Connectivity" in device.traits
        trait = device.traits["sdm.devices.traits.Connectivity"]
        assert isinstance(trait, ConnectivityTrait)
        return trait

    assert get_connectivity().status == "OFFLINE"
    await mgr.async_handle_event(
        event_message_with_time("2019-01-01T00:00:03Z", "ONLINE")
    )
    assert get_connectivity().status == "ONLINE"
    await mgr.async_handle_event(
        event_message_with_time("2019-01-01T00:00:04Z", "OFFLINE")
    )
    assert get_connectivity().status == "OFFLINE"
    # Event in past is igored
    await mgr.async_handle_event(
        event_message_with_time("2019-01-01T00:00:01Z", "ONLINE")
    )
    assert get_connectivity().status == "OFFLINE"
    # Event in future is applied
    await mgr.async_handle_event(
        event_message_with_time("2019-01-01T00:00:05Z", "ONLINE")
    )
    assert get_connectivity().status == "ONLINE"


@pytest.mark.parametrize(
    "test_trait,test_event_trait",
    [
        ("sdm.devices.traits.CameraMotion", "sdm.devices.events.CameraMotion.Motion"),
        ("sdm.devices.traits.CameraPerson", "sdm.devices.events.CameraPerson.Person"),
        ("sdm.devices.traits.CameraSound", "sdm.devices.events.CameraSound.Sound"),
        ("sdm.devices.traits.DoorbellChime", "sdm.devices.events.DoorbellChime.Chime"),
    ],
)
async def test_device_added_after_callback(
    test_trait: str,
    test_event_trait: str,
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test event callback is registered before the device is added."""

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        async def async_handle_event(self, event_message: EventMessage) -> None:
            self.invoked = True

    callback = MyCallback()
    mgr = DeviceManager()
    mgr.set_update_callback(callback.async_handle_event)
    assert not callback.invoked

    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                test_trait: {},
                "sdm.devices.traits.CameraEventImage": {},
            },
        }
    )
    mgr.add_device(device)
    assert 1 == len(mgr.devices)

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "events": {
                        test_event_trait: {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    assert callback.invoked


@pytest.mark.parametrize(
    "test_trait,test_event_trait",
    [
        ("sdm.devices.traits.CameraMotion", "sdm.devices.events.CameraMotion.Motion"),
        ("sdm.devices.traits.CameraPerson", "sdm.devices.events.CameraPerson.Person"),
        ("sdm.devices.traits.CameraSound", "sdm.devices.events.CameraSound.Sound"),
        ("sdm.devices.traits.DoorbellChime", "sdm.devices.events.DoorbellChime.Chime"),
    ],
)
async def test_publish_without_media(
    test_trait: str,
    test_event_trait: str,
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test event callback is registered before the device is added."""

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        async def async_handle_event(self, event_message: EventMessage) -> None:
            self.invoked = True

    callback = MyCallback()
    mgr = DeviceManager()
    mgr.set_update_callback(callback.async_handle_event)
    assert not callback.invoked

    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                test_trait: {},
            },
        }
    )
    mgr.add_device(device)
    assert 1 == len(mgr.devices)

    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "events": {
                        test_event_trait: {
                            "eventSessionId": "CjY5Y3VKaTZwR3o4Y19YbTVfMF...",
                            "eventId": "n:1",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    assert callback.invoked
