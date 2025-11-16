import datetime
from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.google_nest_api import GoogleNestAPI
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.device_traits import ConnectivityTrait
from google_nest_sdm.event import EventMessage

from .conftest import DeviceHandler, EventCallback, StructureHandler


@pytest.fixture(name="device_manager")
async def device_manager_fixture(
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    api: GoogleNestAPI,
) -> DeviceManager:
    """Create a DeviceManager fixture."""
    return DeviceManager(api)


@pytest.fixture
def event_message_with_time(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
) -> Callable[[str, str, str], EventMessage]:
    def make_event(device_id: str, timestamp: str, status: str) -> EventMessage:
        return fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": timestamp,
                "resourceUpdate": {
                    "name": device_id,
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


async def test_add_device(
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    device_manager: DeviceManager,
) -> None:
    structure_handler.add_structure()
    device_handler.add_device(device_type="sdm.devices.types.device-type1")
    device_handler.add_device(device_type="sdm.devices.types.device-type2")

    await device_manager.async_refresh()
    assert len(device_manager.devices) == 2


async def test_update_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.device-type1",
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "OFFLINE",
            },
        },
    )
    await device_manager.async_refresh()

    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status


async def test_device_created_in_structure(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    structure_handler: StructureHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        parent_relations=[],
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
    assert len(device.parent_relations) == 0

    structure_id = structure_handler.add_structure(
        traits={
            "sdm.structures.traits.Info": {
                "customName": "Structure Name",
            },
        }
    )
    await device_manager.async_refresh()

    assert len(device_manager.structures) == 1
    structure = device_manager.structures[structure_id]
    assert "sdm.structures.traits.Info" in structure.traits
    trait = structure.traits["sdm.structures.traits.Info"]
    assert "Structure Name" == trait.custom_name

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "relationUpdate": {
                    "type": "CREATED",
                    "subject": structure_id,
                    "object": device_id,
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = device_manager.devices[device_id]
    assert device.parent_relations == {
        structure_id: "Structure Name",
    }

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "relationUpdate": {
                    "type": "DELETED",
                    "subject": structure_id,
                    "object": device_id,
                },
                "userId": "AVPHwEuBfnPOnTqzVFT4IONX2Qqhu9EJ4ubO-bNnQ-yi",
            }
        )
    )
    device = device_manager.devices[device_id]
    assert len(device.parent_relations) == 0


async def test_device_event_callback(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "OFFLINE",
            }
        },
        parent_relations=[],
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status

    callback = EventCallback()
    unregister = device.add_event_callback(callback.async_handle_event)
    assert not callback.invoked

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status
    assert callback.invoked

    # Test event not for this device
    callback.invoked = False  # type: ignore[unreachable]
    await device_manager.async_handle_event(
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
    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    assert not callback.invoked


async def test_device_update_listener(
    fake_device: Callable[[Dict[str, Any]], Device],
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "OFFLINE",
            },
        },
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
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

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "ONLINE" == trait.status
    assert callback.invoked

    # Test event not for this device
    callback.invoked = False  # type: ignore[unreachable]
    await device_manager.async_handle_event(
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
    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status
    assert not callback.invoked


async def test_update_trait_with_field_alias(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test updating a trait that has fields with field aliases."""
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
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
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
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

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
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
    event_message_with_time: Callable[[str, str, str], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            "sdm.devices.traits.Connectivity": {
                "status": "OFFLINE",
            },
        },
    )
    await device_manager.async_refresh()

    def get_connectivity() -> ConnectivityTrait:
        assert len(device_manager.devices) == 1
        device = device_manager.devices[device_id]
        assert "sdm.devices.traits.Connectivity" in device.traits
        trait = device.traits["sdm.devices.traits.Connectivity"]
        assert isinstance(trait, ConnectivityTrait)
        return trait

    now = datetime.datetime.now(datetime.timezone.utc)
    assert get_connectivity().status == "OFFLINE"
    await device_manager.async_handle_event(
        event_message_with_time(device_id, now.isoformat(), "ONLINE")
    )
    assert get_connectivity().status == "ONLINE"
    now += datetime.timedelta(seconds=1)
    await device_manager.async_handle_event(
        event_message_with_time(device_id, now.isoformat(), "OFFLINE")
    )
    assert get_connectivity().status == "OFFLINE"
    # Event in past is ignored
    now -= datetime.timedelta(minutes=1)
    await device_manager.async_handle_event(
        event_message_with_time(device_id, now.isoformat(), "ONLINE")
    )
    assert get_connectivity().status == "OFFLINE"
    # Event in future is applied
    now += datetime.timedelta(hours=1)
    await device_manager.async_handle_event(
        event_message_with_time(device_id, now.isoformat(), "ONLINE")
    )
    assert get_connectivity().status == "ONLINE"


async def test_update_trait_with_new_field(
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test ignoring an update for a previously unseen trait."""
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
        },
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
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

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
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
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test event callback is registered before the device is added."""

    callback = EventCallback()
    device_manager.set_update_callback(callback.async_handle_event)
    assert not callback.invoked

    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            test_trait: {},
            "sdm.devices.traits.CameraEventImage": {},
        },
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test publishing an event without any associated event media."""

    callback = EventCallback()
    device_manager.set_update_callback(callback.async_handle_event)
    assert not callback.invoked

    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            test_trait: {},
        },
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1

    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    fake_event_message: Callable[[Dict[str, Any]], EventMessage],
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    device_id = device_handler.add_device(
        device_type="sdm.devices.types.SomeDeviceType",
        traits={
            "sdm.devices.traits.ThermostatHvac": {"status": "OFF"},
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "OFF",
            },
        },
    )
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    device = device_manager.devices[device_id]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "OFF"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "OFF"

    # Heat is enabled
    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "OFF"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEAT"

    # Heating has started.
    await device_manager.async_handle_event(
        fake_event_message(
            {
                "eventId": "0120ecc7-3b57-4eb4-9941-91609f189fb4",
                "timestamp": "2019-01-01T00:00:01Z",
                "resourceUpdate": {
                    "name": device_id,
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
    device = device_manager.devices[device_id]
    assert device.thermostat_hvac
    assert device.thermostat_hvac.status == "HEATING"
    assert device.thermostat_mode
    assert device.thermostat_mode.mode == "HEAT"


class ChangeCallback:
    """Test callback handler."""

    def __init__(self) -> None:
        """Initialize MyCallback."""
        self.invoked = False

    async def async_handle_change(self) -> None:
        """Handle a change."""
        self.invoked = True


async def test_change_callback_device_added(
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test invoking the callback when a device is added."""
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 0

    callback = ChangeCallback()
    device_manager.set_change_callback(callback.async_handle_change)
    assert not callback.invoked

    device_handler.add_device()
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    assert callback.invoked


async def test_change_callback_device_removed(
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test invoking the callback when a device is removed."""
    device_handler.add_device()
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1

    callback = ChangeCallback()
    device_manager.set_change_callback(callback.async_handle_change)
    assert not callback.invoked

    device_handler.clear_devices()
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 0
    assert callback.invoked


async def test_change_callback_structure_added(
    structure_handler: StructureHandler,
    device_manager: DeviceManager,
) -> None:
    """Test invoking the callback when a structure is added."""
    await device_manager.async_refresh()
    assert len(device_manager.structures) == 0

    callback = ChangeCallback()
    device_manager.set_change_callback(callback.async_handle_change)
    assert not callback.invoked

    structure_handler.add_structure()
    await device_manager.async_refresh()
    assert len(device_manager.structures) == 1
    assert callback.invoked


async def test_change_callback_structure_removed(
    structure_handler: StructureHandler,
    device_manager: DeviceManager,
) -> None:
    """Test invoking the callback when a structure is removed."""
    structure_handler.add_structure()
    await device_manager.async_refresh()
    assert len(device_manager.structures) == 1

    callback = ChangeCallback()
    device_manager.set_change_callback(callback.async_handle_change)
    assert not callback.invoked

    structure_handler.clear_structures()
    await device_manager.async_refresh()
    assert len(device_manager.structures) == 0
    assert callback.invoked


async def test_change_callback_no_change(
    device_handler: DeviceHandler,
    device_manager: DeviceManager,
) -> None:
    """Test not invoking the callback when nothing changes."""
    device_handler.add_device()
    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1

    callback = ChangeCallback()
    device_manager.set_change_callback(callback.async_handle_change)
    assert not callback.invoked

    await device_manager.async_refresh()
    assert len(device_manager.devices) == 1
    assert not callback.invoked
