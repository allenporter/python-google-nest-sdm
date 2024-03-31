"""Traits for thermostats."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, ClassVar

import aiohttp
from mashumaro import field_options, DataClassDictMixin

from .traits import CommandDataClass, TraitType

__all__ = [
    "ThermostatEcoTrait",
    "ThermostatHvacTrait",
    "ThermostatModeTrait",
    "ThermostatTemperatureSetpointTrait",
]

STATUS: Final = "status"
AVAILABLE_MODES: Final = "availableModes"
MODE: Final = "mode"


@dataclass
class ThermostatEcoTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_ECO

    available_modes: list[str] = field(
        metadata=field_options(alias="availableModes"), default_factory=list
    )
    """List of supported Eco modes."""

    mode: str = field(metadata=field_options(alias="mode"), default="OFF")
    """Eco mode of the thermostat."""

    heat_celsius: float | None = field(
        metadata=field_options(alias="heatCelsius"), default=None
    )
    """Lowest temperature where thermostat begins heating."""

    cool_celsius: float | None = field(
        metadata=field_options(alias="coolCelsius"), default=None
    )
    """Highest cooling temperature where thermostat begins cooling."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@dataclass
class ThermostatHvacTrait:
    """This trait belongs to devices that can report HVAC details."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_HVAC

    status: str
    """HVAC status of the thermostat."""


@dataclass
class ThermostatModeTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to devices that support different thermostat modes."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_MODE

    available_modes: list[str] = field(metadata=field_options(alias="availableModes"))
    """List of supported thermostat modes."""

    mode: str = field(metadata=field_options(alias="mode"))
    """Mode of the thermostat."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@dataclass
class ThermostatTemperatureSetpointTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to devices that support setting target temperature."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_TEMPERATURE_SETPOINT

    heat_celsius: float | None = field(
        metadata=field_options(alias="heatCelsius"), default=None
    )
    """Lowest temperature where thermostat begins heating."""

    cool_celsius: float | None = field(
        metadata=field_options(alias="coolCelsius"), default=None
    )
    """Highest cooling temperature where thermostat begins cooling."""

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
