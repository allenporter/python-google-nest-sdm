"""Traits for thermostats."""

from __future__ import annotations

from abc import ABC
from typing import Any, Final, List, Mapping, cast

import aiohttp

from .traits import TRAIT_MAP, Command
from .typing import cast_assert

STATUS: Final = "status"
AVAILABLE_MODES: Final = "availableModes"
MODE: Final = "mode"
HEAT_CELSIUS: Final = "heatCelsius"
COOL_CELSIUS: Final = "coolCelsius"


class ThermostatHeatCoolTrait(ABC):
    """Parent class for traits related to temperature set points."""

    @property
    def heat_celsius(self) -> float:
        """Lowest temperature where Eco mode begins heating."""

    @property
    def cool_celsius(self) -> float:
        """Highest cooling temperature where Eco mode begins cooling."""


@TRAIT_MAP.register()
class ThermostatEcoTrait(ThermostatHeatCoolTrait):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME = "sdm.devices.traits.ThermostatEco"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize ThermostatEcoTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def available_modes(self) -> List[str]:
        """List of supported Eco modes."""
        return cast(List[str], self._data[AVAILABLE_MODES])

    @property
    def mode(self) -> str:
        """Eco mode of the thermostat."""
        return cast_assert(str, self._data[MODE])

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self._cmd.execute(data)

    @property
    def heat_celsius(self) -> float:
        """Lowest temperature where Eco mode begins heating."""
        return cast(float, self._data[HEAT_CELSIUS])

    @property
    def cool_celsius(self) -> float:
        """Highest cooling temperature where Eco mode begins cooling."""
        return cast(float, self._data[COOL_CELSIUS])


@TRAIT_MAP.register()
class ThermostatHvacTrait:
    """This trait belongs to devices that can report HVAC details."""

    NAME = "sdm.devices.traits.ThermostatHvac"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize ThermostatHvacTrait."""
        self._data = data

    @property
    def status(self) -> List[str]:
        """HVAC status of the thermostat."""
        return cast(List[str], self._data[STATUS])


@TRAIT_MAP.register()
class ThermostatModeTrait:
    """This trait belongs to devices that support different thermostat modes."""

    NAME = "sdm.devices.traits.ThermostatMode"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize ThermostatModeTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def available_modes(self) -> List[str]:
        """List of supported thermostat modes."""
        return cast(List[str], self._data[AVAILABLE_MODES])

    @property
    def mode(self) -> str:
        """Mode of the thermostat."""
        return cast_assert(str, self._data[MODE])

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode},
        }
        return await self._cmd.execute(data)


@TRAIT_MAP.register()
class ThermostatTemperatureSetpointTrait(ThermostatHeatCoolTrait):
    """This trait belongs to devices that support setting target temperature."""

    NAME = "sdm.devices.traits.ThermostatTemperatureSetpoint"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize ThermostatTemperatureSetpointTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def heat_celsius(self) -> float:
        """Lowest temperature where Eco mode begins heating."""
        return cast(float, self._data[HEAT_CELSIUS])

    @property
    def cool_celsius(self) -> float:
        """Highest cooling temperature where Eco mode begins cooling."""
        return cast(float, self._data[COOL_CELSIUS])

    async def set_heat(self, heat: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            "params": {"heatCelsius": heat},
        }
        return await self._cmd.execute(data)

    async def set_cool(self, cool: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
            "params": {"coolCelsius": cool},
        }
        return await self._cmd.execute(data)

    async def set_range(self, heat: float, cool: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
            "params": {
                "heatCelsius": heat,
                "coolCelsius": cool,
            },
        }
        return await self._cmd.execute(data)
