import datetime
from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.device_traits import ConnectivityTrait
from google_nest_sdm.event import EventMessage
from google_nest_sdm.structure import Structure

from .conftest import EventCallback


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

    callback = EventCallback()
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


async def test_update_trait_with_field_alias(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test updating a trait that has fields with field aliases."""
    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.ThermostatHvac": {
                    "status": "HEATING",
                },
                "sdm.devices.traits.ThermostatMode": {
                    "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                    "mode": "HEAT",
                },
                "sdm.devices.traits.Temperature": {
                    "ambientTemperatureCelsius": 20.1,
                },
                "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                    "heatCelsius": 23.0,
                },
            },
        }
    )
    mgr = DeviceManager()
    mgr.add_device(device)
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEAT"
    assert device.temperature
    assert device.temperature.ambient_temperature_celsius == 20.1
    assert device.thermostat_temperature_setpoint
    assert device.thermostat_temperature_setpoint.heat_celsius == 23.0

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        def async_handle_event(self) -> None:
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
                        "sdm.devices.traits.ThermostatMode": {
                            "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                            "mode": "HEATCOOL",
                        },
                        "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                            "heatCelsius": 22.0,
                            "coolCelsius": 28.0,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEATCOOL"
    assert device.temperature
    assert device.temperature.ambient_temperature_celsius == 20.1
    assert device.thermostat_temperature_setpoint
    assert device.thermostat_temperature_setpoint.heat_celsius == 22.0
    assert device.thermostat_temperature_setpoint.cool_celsius == 28.0
    unregister()


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

    now = datetime.datetime.now(datetime.timezone.utc)
    assert get_connectivity().status == "OFFLINE"
    await mgr.async_handle_event(event_message_with_time(now.isoformat(), "ONLINE"))
    assert get_connectivity().status == "ONLINE"
    now += datetime.timedelta(seconds=1)
    await mgr.async_handle_event(event_message_with_time(now.isoformat(), "OFFLINE"))
    assert get_connectivity().status == "OFFLINE"
    # Event in past is ignored
    now -= datetime.timedelta(minutes=1)
    await mgr.async_handle_event(event_message_with_time(now.isoformat(), "ONLINE"))
    assert get_connectivity().status == "OFFLINE"
    # Event in future is applied
    now += datetime.timedelta(hours=1)
    await mgr.async_handle_event(event_message_with_time(now.isoformat(), "ONLINE"))
    assert get_connectivity().status == "ONLINE"


async def test_update_trait_with_new_field(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> None:
    """Test ignoring an update for a previously unseen trait."""
    device = fake_device(
        {
            "name": "my/device/name1",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.ThermostatHvac": {
                    "status": "HEATING",
                },
            },
        }
    )
    mgr = DeviceManager()
    mgr.add_device(device)
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert not device.temperature

    class MyCallback:
        def __init__(self) -> None:
            self.invoked = False

        def async_handle_event(self) -> None:
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
                        "sdm.devices.traits.Temperature": {
                            "ambientTemperatureCelsius": 20.1,
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert not device.temperature

    unregister()


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

    callback = EventCallback()
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
    """Test publishing an event without any associated event media."""

    callback = EventCallback()
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


async def test_update_with_new_trait(
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
                    "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
                    "sdm.devices.traits.ThermostatMode": {
                        "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                        "mode": "OFF",
                    },
                },
            }
        )
    )
    assert 1 == len(mgr.devices)
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "OFF"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "OFF"

    # Heat is enabled
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.ThermostatMode": {
                            "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                            "mode": "HEAT",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "OFF"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEAT"

    # Heating has started.
    await mgr.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": "my/device/name1",
                    "traits": {
                        "sdm.devices.traits.ThermostatHvac": {
                            "status": "HEATING",
                        },
                    },
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = mgr.devices["my/device/name1"]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEAT"
