"""Library for traits about devices."""

import datetime
from typing import Any, Dict, Mapping, Optional, cast, Final


try:
    from pydantic.v1 import Field, validator
except ImportError:
    from pydantic import Field, validator  # type: ignore

import aiohttp

from .traits import TRAIT_MAP, Command, CommandModel
from .model import TraitModel
from .typing import cast_assert, cast_optional

STATUS = "status"
TIMER_MODE = "timerMode"
TIMER_TIMEOUT = "timerTimeout"
CUSTOM_NAME = "customName"
AMBIENT_HUMIDITY_PERCENT = "ambientHumidityPercent"
AMBIENT_TEMPERATURE_CELSIUS = "ambientTemperatureCelsius"


@TRAIT_MAP.register()
class ConnectivityTrait(TraitModel):
    """This trait belongs to any device that has connectivity information."""

    NAME: Final ="sdm.devices.traits.Connectivity"

    status: str
    """Device connectivity status.

    Return:
        "OFFLINE", "ONLINE"
    """


@TRAIT_MAP.register()
class FanTrait(CommandModel):
    """This trait belongs to any device that can control the fan."""

    NAME: Final = "sdm.devices.traits.Fan"

    timer_mode: str | None = Field(alias=TIMER_MODE)
    """Timer mode for the fan.

    Return:
        "ON", "OFF"
    """

    timer_timeout: datetime.datetime | None = Field(alias=TIMER_TIMEOUT)

    async def set_timer(
        self, timer_mode: str, duration: Optional[int] = None
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
        return await self._cmd.execute(data)


@TRAIT_MAP.register()
class InfoTrait(TraitModel):
    """This trait belongs to any device for device-related information."""

    NAME: Final = "sdm.devices.traits.Info"

    custom_name: str | None = Field(alias=CUSTOM_NAME)
    """Name of the device."""


@TRAIT_MAP.register()
class HumidityTrait(TraitModel):
    """This trait belongs to any device that has a sensor to measure humidity."""

    NAME: Final = "sdm.devices.traits.Humidity"

    ambient_humidity_percent: float = Field(alias=AMBIENT_HUMIDITY_PERCENT)
    """Percent humidity, measured at the device."""


@TRAIT_MAP.register()
class TemperatureTrait(TraitModel):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: Final = "sdm.devices.traits.Temperature"

    ambient_temperature_celsius: float = Field(alias=AMBIENT_TEMPERATURE_CELSIUS)
    """Percent humidity, measured at the device."""