"""Library for traits about devices."""

import datetime
from typing import Any, Dict, Mapping, Optional, cast

import aiohttp

from .traits import TRAIT_MAP, Command
from .typing import cast_assert, cast_optional

STATUS = "status"
TIMER_MODE = "timerMode"
TIMER_TIMEOUT = "timerTimeout"
CUSTOM_NAME = "customName"
AMBIENT_HUMIDITY_PERCENT = "ambientHumidityPercent"
AMBIENT_TEMPERATURE_CELSIUS = "ambientTemperatureCelsius"


@TRAIT_MAP.register()
class ConnectivityTrait:
    """This trait belongs to any device that has connectivity information."""

    NAME = "sdm.devices.traits.Connectivity"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize ConnectivityTrait."""
        self._data = data

    @property
    def status(self) -> str:
        """Device connectivity status.

        Return:
          "OFFLINE", "ONLINE"
        """
        return cast_assert(str, self._data[STATUS])


@TRAIT_MAP.register()
class FanTrait:
    """This trait belongs to any device that can control the fan."""

    NAME = "sdm.devices.traits.Fan"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize FanTrait."""
        self._data = data
        self._cmd = cmd

    @property
    def timer_mode(self) -> Optional[str]:
        """Timer mode for the fan.

        Return:
          "ON", "OFF"
        """
        return cast_optional(str, self._data.get(TIMER_MODE))

    @property
    def timer_timeout(self) -> Optional[datetime.datetime]:
        """Timestamp at which timer mode will turn to OFF."""
        if TIMER_TIMEOUT not in self._data:
            return None
        timestamp = self._data[TIMER_TIMEOUT]
        return datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

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
class InfoTrait:
    """This trait belongs to any device for device-related information."""

    NAME = "sdm.devices.traits.Info"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize InfoTrait."""
        self._data = data

    @property
    def custom_name(self) -> Optional[str]:
        """Name of the device."""
        return cast_optional(str, self._data.get(CUSTOM_NAME))


@TRAIT_MAP.register()
class HumidityTrait:
    """This trait belongs to any device that has a sensor to measure humidity."""

    NAME = "sdm.devices.traits.Humidity"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize HumidityTrait."""
        self._data = data

    @property
    def ambient_humidity_percent(self) -> float:
        """Percent humidity, measured at the device."""
        return cast(float, self._data[AMBIENT_HUMIDITY_PERCENT])


@TRAIT_MAP.register()
class TemperatureTrait:
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME = "sdm.devices.traits.Temperature"

    def __init__(self, data: Mapping[str, Any], cmd: Command):
        """Initialize TemperatureTrait."""
        self._data = data

    @property
    def ambient_temperature_celsius(self) -> float:
        """Percent humidity, measured at the device."""
        return cast(float, self._data[AMBIENT_TEMPERATURE_CELSIUS])
