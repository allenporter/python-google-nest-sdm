"""Library for traits about devices."""

import datetime
from typing import Any, Dict, Final


try:
    from pydantic.v1 import Field
except ImportError:
    from pydantic import Field  # type: ignore

import aiohttp

from .traits import TRAIT_MAP, CommandModel
from .model import TraitModel


@TRAIT_MAP.register()
class ConnectivityTrait(TraitModel):
    """This trait belongs to any device that has connectivity information."""

    NAME: Final = "sdm.devices.traits.Connectivity"

    status: str
    """Device connectivity status.

    Return:
        "OFFLINE", "ONLINE"
    """


@TRAIT_MAP.register()
class FanTrait(CommandModel):
    """This trait belongs to any device that can control the fan."""

    NAME: Final = "sdm.devices.traits.Fan"

    timer_mode: str | None = Field(alias="timerMode")
    """Timer mode for the fan.

    Return:
        "ON", "OFF"
    """

    timer_timeout: datetime.datetime | None = Field(alias="timerTimeout")

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


@TRAIT_MAP.register()
class InfoTrait(TraitModel):
    """This trait belongs to any device for device-related information."""

    NAME: Final = "sdm.devices.traits.Info"

    custom_name: str | None = Field(alias="customName")
    """Name of the device."""


@TRAIT_MAP.register()
class HumidityTrait(TraitModel):
    """This trait belongs to any device that has a sensor to measure humidity."""

    NAME: Final = "sdm.devices.traits.Humidity"

    ambient_humidity_percent: float = Field(alias="ambientHumidityPercent")
    """Percent humidity, measured at the device."""


@TRAIT_MAP.register()
class TemperatureTrait(TraitModel):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: Final = "sdm.devices.traits.Temperature"

    ambient_temperature_celsius: float = Field(alias="ambientTemperatureCelsius")
    """Percent humidity, measured at the device."""
