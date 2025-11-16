"""Tests for thermostat traits."""

from typing import Any, Callable, Dict

import aiohttp
import pytest

from google_nest_sdm import google_nest_api
from google_nest_sdm.device import Device

from .conftest import DeviceHandler, Recorder


def test_thermostat_eco_traits(fake_device: Callable[[Dict[str, Any]], Device]) -> None:
    device = fake_device(
        {
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
    )
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert ["MANUAL_ECHO", "OFF"] == trait.available_modes
    assert "MANUAL_ECHO" == trait.mode
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


def test_thermostat_hvac_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatHvac": {
                    "status": "HEATING",
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatHvac" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatHvac"]
    assert "HEATING" == trait.status


def test_thermostat_mode_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatMode": {
                    "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                    "mode": "COOL",
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatMode" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert ["HEAT", "COOL", "HEATCOOL", "OFF"] == trait.available_modes
    assert "COOL" == trait.mode


def test_thermostat_temperature_setpoint_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {
                "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                    "heatCelsius": 20.0,
                    "coolCelsius": 22.0,
                },
            },
        }
    )
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert 20.0 == trait.heat_celsius
    assert 22.0 == trait.cool_celsius


@pytest.mark.parametrize(
    "data",
    [
        ({}),
        ({"heatCelsius": 20.0}),
        ({"coolCelsius": 22.0}),
        ({"heatCelsius": 20.0, "coolCelsius": 22.0}),
    ],
)
def test_thermostat_temperature_setpoint_optional_fields(
    fake_device: Callable[[Dict[str, Any]], Device], data: dict[str, Any]
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {"sdm.devices.traits.ThermostatTemperatureSetpoint": data},
        }
    )
    assert "sdm.devices.traits.ThermostatTemperatureSetpoint" in device.traits
    assert device.thermostat_temperature_setpoint


def test_thermostat_multiple_traits(
    fake_device: Callable[[Dict[str, Any]], Device],
) -> None:
    device = fake_device(
        {
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
    )
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


@pytest.mark.parametrize(
    "data",
    [
        ({}),
        ({"mode": "OFF"}),
    ],
)
def test_thermostat_eco_optional_fields(
    fake_device: Callable[[Dict[str, Any]], Device], data: dict[str, Any]
) -> None:
    device = fake_device(
        {
            "name": "my/device/name",
            "traits": {"sdm.devices.traits.ThermostatEco": data},
        }
    )
    assert "sdm.devices.traits.ThermostatEco" in device.traits
    assert device.thermostat_eco
    assert device.thermostat_eco.mode == "OFF"


async def test_fan_set_timer(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.Fan": {
                "timerMode": "OFF",
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])

    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device_id == device.name
    trait = device.traits["sdm.devices.traits.Fan"]
    assert trait.timer_mode == "OFF"
    await trait.set_timer("ON", 3600)
    assert recorder.request == {
        "command": "sdm.devices.commands.Fan.SetTimer",
        "params": {
            "timerMode": "ON",
            "duration": "3600s",
        },
    }


async def test_thermostat_eco_set_mode(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatEco": {
                "availableModes": ["MANUAL_ECO", "OFF"],
                "mode": "MANUAL_ECO",
                "heatCelsius": 20.0,
                "coolCelsius": 22.0,
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])

    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatEco"]
    assert trait.mode == "MANUAL_ECO"
    await trait.set_mode("OFF")
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatEco.SetMode",
        "params": {"mode": "OFF"},
    }


async def test_thermostat_mode_set_mode(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatMode": {
                "availableModes": ["HEAT", "COOL", "HEATCOOL", "OFF"],
                "mode": "COOL",
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])

    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatMode"]
    assert trait.mode == "COOL"
    await trait.set_mode("HEAT")
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatMode.SetMode",
        "params": {"mode": "HEAT"},
    }


async def test_thermostat_temperature_set_point(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 23.0,
                "coolCelsius": 24.0,
            },
        }
    )
    device_handler.add_device_command(device_id, [{}, {}, {}])

    devices = await api.async_get_devices()
    assert len(devices) == 1
    device = devices[0]
    assert device.name == device_id
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert trait.heat_celsius == 23.0
    assert trait.cool_celsius == 24.0
    await trait.set_heat(25.0)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 25.0},
    }

    await trait.set_cool(26.0)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params": {"coolCelsius": 26.0},
    }

    await trait.set_range(27.0, 28.0)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {
            "heatCelsius": 27.0,
            "coolCelsius": 28.0,
        },
    }
