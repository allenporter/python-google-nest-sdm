"""Library for traits about devices."""

import datetime
from typing import Any, Dict, ClassVar
from dataclasses import dataclass, field

import aiohttp
from mashumaro import field_options, DataClassDictMixin

from .traits import CommandDataClass, TraitType


@dataclass
class ConnectivityTrait(DataClassDictMixin):
    """This trait belongs to any device that has connectivity information."""

    NAME: ClassVar[TraitType] = TraitType.CONNECTIVITY

    status: str
    """Device connectivity status.

    Return:
        "OFFLINE", "ONLINE"
    """


@dataclass
class FanTrait(DataClassDictMixin, CommandDataClass):
    """This trait belongs to any device that can control the fan."""

    NAME: ClassVar[TraitType] = TraitType.FAN

    timer_mode: str | None = field(
        metadata=field_options(alias="timerMode"), default=None
    )
    """Timer mode for the fan.

    Return:
        "ON", "OFF"
    """

    timer_timeout: datetime.datetime | None = field(
        metadata=field_options(alias="timerTimeout"), default=None
    )

    async def set_timer(
        self, timer_mode: str, duration: int | None = None
    ) -> aiohttp.ClientResponse:
        """Change the fan timer."""
        data: Dict[str, Any] = {
            "command": "sdm.devices.commands.Fan.SetTimer",
            "params": {
                "timerMode": timer_mode,
            },
        }
        if duration:
            data["params"]["duration"] = f"{duration}s"
        return await self.cmd.execute(data)


@dataclass
class InfoTrait(DataClassDictMixin):
    """This trait belongs to any device for device-related information."""

    NAME: ClassVar[TraitType] = TraitType.INFO

    custom_name: str | None = field(
        metadata=field_options(alias="customName"), default=None
    )
    """Name of the device."""


@dataclass
class HumidityTrait(DataClassDictMixin):
    """This trait belongs to any device that has a sensor to measure humidity."""

    NAME: ClassVar[TraitType] = TraitType.HUMIDITY

    ambient_humidity_percent: float = field(
        metadata=field_options(alias="ambientHumidityPercent")
    )
    """Percent humidity, measured at the device."""


@dataclass
class TemperatureTrait(DataClassDictMixin):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: ClassVar[TraitType] = TraitType.TEMPERATURE

    ambient_temperature_celsius: float = field(
        metadata=field_options(alias="ambientTemperatureCelsius")
    )
    """Percent humidity, measured at the device."""
