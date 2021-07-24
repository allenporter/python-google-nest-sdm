import datetime
import pytest
from google_nest_sdm.device import Device


def test_info_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Info": {
                "customName": "Device Name",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert "Device Name" == trait.custom_name


def test_connectivity_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Connectivity": {
                "status": "OFFLINE",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status


def test_fan_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Fan": {
                "timerMode": "ON",
                "timerTimeout": "2019-05-10T03:22:54Z",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Fan" in device.traits
    trait = device.traits["sdm.devices.traits.Fan"]
    assert "ON" == trait.timer_mode
    assert (
        datetime.datetime(2019, 5, 10, 3, 22, 54, tzinfo=datetime.timezone.utc)
        == trait.timer_timeout
    )


def test_fan_traits_empty():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Fan": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Fan" in device.traits
    trait = device.traits["sdm.devices.traits.Fan"]
    assert trait.timer_mode is None
    assert trait.timer_timeout is None


def test_humidity_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": 25.3,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Humidity" in device.traits
    trait = device.traits["sdm.devices.traits.Humidity"]
    assert 25.3 == trait.ambient_humidity_percent


def test_temperature_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": 31.1,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Temperature" in device.traits
    trait = device.traits["sdm.devices.traits.Temperature"]
    assert 31.1 == trait.ambient_temperature_celsius


def test_multiple_traits():
    raw = {
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
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.types.SomeDeviceType" == device.type
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert "Device Name" == trait.custom_name
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    assert "OFFLINE" == trait.status


def test_info_traits_type_error():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Info": {
                "customName": 12345,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    with pytest.raises(AssertionError, match="Expected data with type"):
        trait.custom_name


def test_info_traits_missing_optional_field():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Info": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.traits.Info" in device.traits
    trait = device.traits["sdm.devices.traits.Info"]
    assert trait.custom_name is None


def test_connectivity_traits_missing_required_field():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Connectivity": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Connectivity" in device.traits
    trait = device.traits["sdm.devices.traits.Connectivity"]
    with pytest.raises(KeyError):
        trait.status
