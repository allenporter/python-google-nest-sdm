"""Traits for thermostats."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Final, List, Mapping, cast

import aiohttp
try:
    from pydantic.v1 import Field
except ImportError:
    from pydantic import Field  # type: ignore

from .traits import TRAIT_MAP, Command, CommandModel
from .typing import cast_assert
from .model import TraitModel

STATUS: Final = "status"
AVAILABLE_MODES: Final = "availableModes"
MODE: Final = "mode"


class ThermostatHeatCoolTrait(CommandModel, ABC):
    """Parent class for traits related to temperature set points."""

    heat_celsius: float = Field(alias="heatCelsius")
    """Lowest temperature where thermostat begins heating."""

    cool_celsius: float = Field(alias="coolCelsius")
    """Highest cooling temperature where thermostat begins cooling."""


@TRAIT_MAP.register()
class ThermostatEcoTrait(ThermostatHeatCoolTrait):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: Final = "sdm.devices.traits.ThermostatEco"

    available_modes: list[str] = Field(alias="availableModes")
    """List of supported Eco modes."""

    mode: str = Field(alias="mode")
    """Eco mode of the thermostat."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@TRAIT_MAP.register()
class ThermostatHvacTrait(TraitModel):
    """This trait belongs to devices that can report HVAC details."""

    NAME: Final = "sdm.devices.traits.ThermostatHvac"

    status: str = Field("status")
    """HVAC status of the thermostat."""


@TRAIT_MAP.register()
class ThermostatModeTrait(CommandModel):
    """This trait belongs to devices that support different thermostat modes."""

    NAME: Final = "sdm.devices.traits.ThermostatMode"

    available_modes: list[str] = Field(alias="availableModes")
    """List of supported thermostat modes."""

    mode: str = Field(alias="mode")
    """Mode of the thermostat."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@TRAIT_MAP.register()
class ThermostatTemperatureSetpointTrait(ThermostatHeatCoolTrait):
    """This trait belongs to devices that support setting target temperature."""

    NAME: Final = "sdm.devices.traits.ThermostatTemperatureSetpoint"

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
