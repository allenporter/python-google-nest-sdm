from .auth import AbstractAuth

import datetime

from abc import abstractproperty, ABCMeta
from .traits import TRAIT_MAP, Command

STATUS = 'status'
CUSTOM_NAME = 'customName'
AMBIENT_HUMIDITY_PERCENT = 'ambientHumidityPercent'
AMBIENT_TEMPERATURE_CELSIUS = 'ambientTemperatureCelsius'


@TRAIT_MAP.register()
class ConnectivityTrait:
  """This trait belongs to any device that has connectivity information."""

  NAME = 'sdm.devices.traits.Connectivity'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def status(self) -> str:
    """Device connectivity status.

    Return:
      "OFFLINE", "ONLINE"
    """
    return self._data[STATUS]


@TRAIT_MAP.register()
class InfoTrait:
  """This trait belongs to any device for device-related information."""

  NAME = 'sdm.devices.traits.Info'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def custom_name(self) -> str:
    """Custom name of the device."""
    return self._data[CUSTOM_NAME]


@TRAIT_MAP.register()
class HumidityTrait:
  """This trait belongs to any device that has a sensor to measure humidity."""

  NAME = 'sdm.devices.traits.Humidity'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_humidity_percent(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_HUMIDITY_PERCENT]


@TRAIT_MAP.register()
class TemperatureTrait:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.Temperature'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_temperature_celsius(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_TEMPERATURE_CELSIUS]
