"""Tests for device traits."""

import datetime
from typing import Any, Callable, Dict

import pytest

from google_nest_sdm.device import Device

from .conftest import assert_diagnostics


def test_info_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "Device Name",
                },
            },
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert "Device Name" == trait.custom_name

    assert_diagnostics(
        device.get_diagnostics(),
        {
            "data": {
                "name": "**REDACTED**",
                "parentRelations": [],
                "traits": {
                    "sdm.devices.traits.Info": {
                        "custom_name": "**REDACTED**",
                    }
                },
            },
        },
    )


def test_connectivity_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Connectivity": {
                    "status": "OFFLINE",
                },
            },
        }
    )
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status


def test_fan_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Fan": {
                    "timerMode": "ON",
                    "timerTimeout": "2019-05-10T03:22:54Z",
                },
            },
        }
    )
    assert "sdm.devices.traits.Fan" in device.traits
    trait = device.traits["sdm.devices.traits.Fan"]
    assert "ON" == trait.timer_mode
    assert (
        datetime.datetime(2019, 5, 10, 3, 22, 54, tzinfo=datetime.timezone.utc)
        == trait.timer_timeout
    )


def test_fan_traits_empty(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Fan": {},
            },
        }
    )
    assert "sdm.devices.traits.Fan" in device.traits
    trait = device.traits["sdm.devices.traits.Fan"]
    assert trait.timer_mode is None
    assert trait.timer_timeout is None


def test_humidity_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Humidity": {
                    "ambientHumidityPercent": 25.3,
                },
            },
        }
    )
    assert "sdm.devices.traits.Humidity" in device.traits
    trait = device.traits["sdm.devices.traits.Humidity"]
    assert 25.3 == trait.ambient_humidity_percent


def test_humidity_int_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Humidity": {
                    "ambientHumidityPercent": 25,
                },
            },
        }
    )
    assert "sdm.devices.traits.Humidity" in device.traits
    trait = device.traits["sdm.devices.traits.Humidity"]
    assert 25 == trait.ambient_humidity_percent


def test_temperature_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Temperature": {
                    "ambientTemperatureCelsius": 31.1,
                },
            },
        }
    )
    assert "sdm.devices.traits.Temperature" in device.traits
    trait = device.traits["sdm.devices.traits.Temperature"]
    assert 31.1 == trait.ambient_temperature_celsius


def test_multiple_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "type": "sdm.devices.types.SomeDeviceType",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": "Device Name",
                },
                "sdm.devices.traits.Connectivity": {
                    "status": "OFFLINE",
                },
            },
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.types.SomeDeviceType" == device.type
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert "Device Name" == trait.custom_name
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status


def test_info_traits_type_error(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Info": {
                    "customName": 12345,
                },
            },
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert trait.custom_name == "12345"


def test_info_traits_missing_optional_field(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.Info": {},
            },
        }
    )
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert trait.custom_name is None


def test_connectivity_traits_missing_required_field(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    with pytest.raises(ValueError):
        fake_device(
            {
                "name": "my/device/name",
                "traits": {
                    "sdm.devices.traits.Connectivity": {},
                },
            }
        )
