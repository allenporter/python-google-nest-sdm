"""Traits for thermostats."""

from __future__ import annotations

from abc import ABC
from typing import Final

import aiohttp

try:
    from pydantic.v1 import Field
except ImportError:
    from pydantic import Field  # type: ignore

from .traits import CommandModel
from .model import TraitModel

__all__ = [
    "ThermostatEcoTrait",
    "ThermostatHvacTrait",
    "ThermostatModeTrait",
    "ThermostatTemperatureSetpointTrait",
]

STATUS: Final = "status"
AVAILABLE_MODES: Final = "availableModes"
MODE: Final = "mode"


class ThermostatHeatCoolTrait(CommandModel, ABC):
    """Parent class for traits related to temperature set points."""

    heat_celsius: float | None = Field(alias="heatCelsius")
    """Lowest temperature where thermostat begins heating."""

    cool_celsius: float | None = Field(alias="coolCelsius")
    """Highest cooling temperature where thermostat begins cooling."""


class ThermostatEcoTrait(ThermostatHeatCoolTrait):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: Final = "sdm.devices.traits.ThermostatEco"

    available_modes: list[str] = Field(alias="availableModes", default_factory=list)
    """List of supported Eco modes."""

    mode: str = Field(alias="mode", default="OFF")
    """Eco mode of the thermostat."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


class ThermostatHvacTrait(TraitModel):
    """This trait belongs to devices that can report HVAC details."""

    NAME: Final = "sdm.devices.traits.ThermostatHvac"

    status: str = Field("status")
    """HVAC status of the thermostat."""


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


class ThermostatTemperatureSetpointTrait(ThermostatHeatCoolTrait):
    """This trait belongs to devices that support setting target temperature."""

    NAME: Final = "sdm.devices.traits.ThermostatTemperatureSetpoint"

    async def set_heat(self, heat: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
            "params": {"heatCelsius": heat},
        }
        return await self.cmd.execute(data)

    async def set_cool(self, cool: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
            "params": {"coolCelsius": cool},
        }
        return await self.cmd.execute(data)

    async def set_range(self, heat: float, cool: float) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
            "params": {
                "heatCelsius": heat,
                "coolCelsius": cool,
            },
        }
        return await self.cmd.execute(data)
