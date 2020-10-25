import datetime

from google_nest_sdm.device import Device


def test_device_id():
    raw = {
        "name": "my/device/name",
        "type": "sdm.devices.types.SomeDeviceType",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert "sdm.devices.types.SomeDeviceType" == device.type


def test_no_traits():
    raw = {
        "name": "my/device/name",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert not ("sdm.devices.traits.Info" in device.traits)


def test_empty_traits():
    raw = {
        "name": "my/device/name",
        "traits": {},
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert not ("sdm.devices.traits.Info" in device.traits)


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


def test_humidity_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Humidity": {
                "ambientHumidityPercent": "25.3",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Humidity" in device.traits
    trait = device.traits["sdm.devices.traits.Humidity"]
    assert "25.3" == trait.ambient_humidity_percent


def test_temperature_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.Temperature": {
                "ambientTemperatureCelsius": "31.1",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.Temperature" in device.traits
    trait = device.traits["sdm.devices.traits.Temperature"]
    assert "31.1" == trait.ambient_temperature_celsius


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


def test_no_parent_relations():
    raw = {
        "name": "my/device/name",
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_empty_parent_relations():
    raw = {
        "name": "my/device/name",
        "parentRelations": [],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {} == device.parent_relations


def test_parent_relation():
    raw = {
        "name": "my/device/name",
        "parentRelations": [
            {
                "parent": "my/structure/or/room",
                "displayName": "Some Name",
            },
        ],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {"my/structure/or/room": "Some Name"} == device.parent_relations


def test_multiple_parent_relations():
    raw = {
        "name": "my/device/name",
        "parentRelations": [
            {
                "parent": "my/structure/or/room1",
                "displayName": "Some Name1",
            },
            {
                "parent": "my/structure/or/room2",
                "displayName": "Some Name2",
            },
        ],
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "my/device/name" == device.name
    assert {
        "my/structure/or/room1": "Some Name1",
        "my/structure/or/room2": "Some Name2",
    } == device.parent_relations


def test_thermostat_eco_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECHO", "OFF"],
                "mode": "MANUAL_ECHO",
                "heatCelsius": 20.0,
                "coolCelsius": 22.0,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert ["MANUAL_ECHO", "OFF"] == trait.available_modes
    assert "MANUAL_ECHO" == trait.mode
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


def test_thermostat_hvac_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.ThermostatHvac" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    assert "HEATING" == trait.status


def test_thermostat_mode_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.ThermostatMode" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert ["HEAT", "COOL", "HEATCOOL", "OFF"] == trait.available_modes
    assert "COOL" == trait.mode


def test_thermostat_temperature_setpoint_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
                "coolCelsius": 22.0,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


def test_thermostat_multiple_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECHO", "OFF"],
                "mode": "MANUAL_ECHO",
                "heatCelsius": 21.0,
                "coolCelsius": 22.0,
            },
            "sdm.devices.traits.ThermostatHvac": {
                "status": "HEATING",
            },
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 23.0,
                "coolCelsius": 24.0,
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    assert "sdm.devices.traits.ThermostatHvac" in device.traits
    assert "sdm.devices.traits.ThermostatMode" in device.traits
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert ["MANUAL_ECHO", "OFF"] == trait.available_modes
    assert "MANUAL_ECHO" == trait.mode
    assert 21.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    assert "HEATING" == trait.status
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert ["HEAT", "COOL", "HEATCOOL", "OFF"] == trait.available_modes
    assert "COOL" == trait.mode
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert 23.0 == trait.heat_celsius
    assert 24.0 == trait.cool_celsius


def test_camera_image_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraImage": {
                "maxImageResolution": {
                    "width": 500,
                    "height": 300,
                }
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.CameraImage" in device.traits
    trait = device.traits["sdm.devices.traits.CameraImage"]
    assert 500 == trait.max_image_resolution.width
    assert 300 == trait.max_image_resolution.height


def test_camera_live_stream_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraLiveStream": {
                "maxVideoResolution": {
                    "width": 500,
                    "height": 300,
                },
                "videoCodecs": ["H264"],
                "audioCodecs": ["AAC"],
            },
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.CameraLiveStream" in device.traits
    trait = device.traits["sdm.devices.traits.CameraLiveStream"]
    assert 500 == trait.max_video_resolution.width
    assert 300 == trait.max_video_resolution.height
    assert ["H264"] == trait.video_codecs
    assert ["AAC"] == trait.audio_codecs


def test_camera_event_image_traits():
    raw = {
        "name": "my/device/name",
        "traits": {
            "sdm.devices.traits.CameraEventImage": {},
        },
    }
    device = Device.MakeDevice(raw, auth=None)
    assert "sdm.devices.traits.CameraEventImage" in device.traits
