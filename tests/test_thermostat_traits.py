"""Tests for thermostat traits."""

import asyncio
import datetime
from collections.abc import Callable
from typing import Any

import aiohttp
import pytest
from freezegun import freeze_time

from google_nest_sdm import google_nest_api
from google_nest_sdm.device import Device
from google_nest_sdm.rate_limiter import RateLimiter
from google_nest_sdm.thermostat_traits import PendingSetpoint

from .conftest import DeviceHandler, Recorder


def test_thermostat_eco_traits(fake_device: Callable[[dict[str, Any]], Device]) -> None:
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
    fake_device: Callable[[dict[str, Any]], Device],
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
    fake_device: Callable[[dict[str, Any]], Device],
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
    fake_device: Callable[[dict[str, Any]], Device],
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
    fake_device: Callable[[dict[str, Any]], Device], data: dict[str, Any]
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
    fake_device: Callable[[dict[str, Any]], Device],
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
    fake_device: Callable[[dict[str, Any]], Device], data: dict[str, Any]
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
    trait.cmd._rate_limiter = RateLimiter(
        delays=(0.0, 0.0, 0.0), reset_after_seconds=0.0
    )
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


async def test_thermostat_temperature_coalesce_burst(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    # First immediate command + second coalesced command
    device_handler.add_device_command(device_id, [{}, {}])

    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    # Configure fast schedule for test
    trait.cmd._rate_limiter = RateLimiter(
        delays=(0.0, 0.02, 0.05), reset_after_seconds=0.1
    )

    # Rapid burst
    await trait.set_heat(21.0)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 21.0},
    }

    await trait.set_heat(22.0)
    await trait.set_heat(23.0)
    await trait.set_heat(24.0)

    # Optimistic reflects latest value immediately
    assert trait.heat_celsius == 24.0

    # Await background dispatch
    await asyncio.sleep(0.05)

    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 24.0},
    }


async def test_thermostat_temperature_range_merge(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
                "coolCelsius": 26.0,
            },
        }
    )
    device_handler.add_device_command(device_id, [{}, {}])

    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    trait.cmd._rate_limiter = RateLimiter(
        delays=(0.0, 0.02, 0.05), reset_after_seconds=0.1
    )

    # First immediate call
    await trait.set_heat(21.0)

    # Follow-up rapid heat and cool changes merge into range
    await trait.set_heat(22.0)
    await trait.set_cool(25.0)

    assert trait.heat_celsius == 22.0
    assert trait.cool_celsius == 25.0

    await asyncio.sleep(0.05)

    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {
            "heatCelsius": 22.0,
            "coolCelsius": 25.0,
        },
    }


async def test_thermostat_temperature_optimistic_expiry(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])
    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    assert trait.heat_celsius == 20.0

    with freeze_time("2026-08-16 12:00:00") as frozen_time:
        await trait.set_heat(25.0)

        # Within 30s optimistic window
        assert trait.heat_celsius == 25.0

        # Expired (> 30s)
        frozen_time.tick(delta=datetime.timedelta(seconds=31))
        assert trait.heat_celsius == 20.0


async def test_thermostat_temperature_pubsub_reconciliation(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
    fake_event_message: Callable[[dict[str, Any]], Any],
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    device_handler.add_device_command(device_id, [{}])
    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    # User adjusts temperature -> optimistic state reflects target immediately
    await trait.set_heat(23.0)
    assert trait.heat_celsius == 23.0

    # PubSub update arrives confirming new temperature
    event = fake_event_message(
        {
            "eventId": "event-id-1",
            "timestamp": "2026-08-16T20:00:00.000Z",
            "resourceUpdate": {
                "name": device_id,
                "traits": {
                    "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                        "heatCelsius": 23.0,
                    },
                },
            },
        }
    )
    await device.async_handle_event(event)

    # Trait reads confirmed value
    assert trait.heat_celsius == 23.0


async def test_thermostat_temperature_failed_precondition_clears_optimistic(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    # First command succeeds, second command returns FAILED_PRECONDITION
    device_handler.add_device_command(
        device_id,
        [
            {},
            {
                "error": {
                    "code": 400,
                    "message": "Thermostat is in ECO mode.",
                    "status": "FAILED_PRECONDITION",
                }
            },
        ],
    )

    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]
    trait.cmd._rate_limiter = RateLimiter(
        delays=(0.0, 0.02, 0.04), reset_after_seconds=0.1
    )

    # Immediate call succeeds
    await trait.set_heat(21.0)
    assert trait.heat_celsius == 21.0

    # Second call is rate-limited and dispatched in background where API rejects it
    await trait.set_heat(25.0)
    assert trait.heat_celsius == 25.0

    # Wait for background dispatch to fail and clear optimistic state
    await asyncio.sleep(0.03)
    assert trait.heat_celsius == 20.0


async def test_thermostat_temperature_coalesce_multiple_waves(
    app: aiohttp.web.Application,
    recorder: Recorder,
    device_handler: DeviceHandler,
    api: google_nest_api.GoogleNestAPI,
) -> None:
    device_id = device_handler.add_device(
        traits={
            "sdm.devices.traits.ThermostatTemperatureSetpoint": {
                "heatCelsius": 20.0,
            },
        }
    )
    # 3 commands: 1st immediate, 2nd first coalesced wave, 3rd second coalesced wave
    device_handler.add_device_command(device_id, [{}, {}, {}])

    devices = await api.async_get_devices()
    device = devices[0]
    trait = device.traits["sdm.devices.traits.ThermostatTemperatureSetpoint"]

    trait.cmd._rate_limiter = RateLimiter(
        delays=(0.0, 0.02, 0.04), reset_after_seconds=0.1
    )

    # 1st wave: immediate call
    await trait.set_heat(21.0)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 21.0},
    }

    # 2nd wave: rapid burst queued for background
    await trait.set_heat(22.0)
    await trait.set_heat(23.0)

    # Allow worker to pick up 2nd wave
    await asyncio.sleep(0.025)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 23.0},
    }

    # 3rd wave: arrives while background worker is still active/throttled
    await trait.set_heat(24.0)
    await trait.set_heat(25.0)

    # Allow worker to process remaining queue
    await asyncio.sleep(0.045)
    assert recorder.request == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 25.0},
    }


def test_pending_setpoint_merge_heat() -> None:
    """Test merging heat setpoints."""
    p1 = PendingSetpoint(heat_celsius=20.0)
    p2 = PendingSetpoint(heat_celsius=22.0)
    merged = p1.merge(p2)
    assert merged.heat_celsius == 22.0
    assert merged.cool_celsius is None


def test_pending_setpoint_merge_heat_and_cool() -> None:
    """Test merging heat and cool setpoints into range."""
    p1 = PendingSetpoint(heat_celsius=20.0)
    p2 = PendingSetpoint(cool_celsius=25.0)
    merged = p1.merge(p2)
    assert merged.heat_celsius == 20.0
    assert merged.cool_celsius == 25.0


def test_pending_setpoint_merge_range() -> None:
    """Test merging into an existing range."""
    p1 = PendingSetpoint(heat_celsius=20.0, cool_celsius=25.0)
    p2 = PendingSetpoint(heat_celsius=21.0)
    merged = p1.merge(p2)
    assert merged.heat_celsius == 21.0
    assert merged.cool_celsius == 25.0


def test_pending_setpoint_as_command() -> None:
    """Test converting setpoints to command payloads."""
    p_heat = PendingSetpoint(heat_celsius=21.0)
    assert p_heat.as_command() == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params": {"heatCelsius": 21.0},
    }

    p_cool = PendingSetpoint(cool_celsius=26.0)
    assert p_cool.as_command() == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params": {"coolCelsius": 26.0},
    }

    p_range = PendingSetpoint(heat_celsius=20.0, cool_celsius=25.0)
    assert p_range.as_command() == {
        "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params": {"heatCelsius": 20.0, "coolCelsius": 25.0},
    }

    with pytest.raises(ValueError, match="Invalid pending setpoint state"):
        PendingSetpoint().as_command()
