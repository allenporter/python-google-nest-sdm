from .auth import AbstractAuth

from abc import abstractproperty, ABCMeta

DEVICE_NAME = 'name'
DEVICE_TYPE = 'type'
DEVICE_TRAITS = 'traits'
DEVICE_PARENT_RELATIONS = 'parentRelations'
STATUS = 'status'
CUSTOM_NAME = 'customName'
AMBIENT_HUMIDITY_PERCENT = 'ambientHumidityPercent'
AMBIENT_TEMPERATURE_CELSIUS = 'ambientTemperatureCelsius'
AVAILABLE_MODES = 'availableModes'
MODE = 'mode'
HEAT_CELSIUS = 'heatCelsius'
COOL_CELSIUS = 'coolCelsius'
PARENT = 'parent'
DISPLAYNAME = 'displayName'


class Command:
  """Base class for executing commands."""

  def __init__(self, device_id: str, auth: AbstractAuth):
    self._device_id = device_id
    self._auth = auth

  async def execute(self, data):
    return await self._auth.request(
        "post", f"devices/{self._device_id}:executeCommand", json=data)


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


class InfoTrait:
  """This trait belongs to any device for device-related information."""

  NAME = 'sdm.devices.traits.Info'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def custom_name(self) -> str:
    """Custom name of the device."""
    return self._data[CUSTOM_NAME]


class HumidityTrait:
  """This trait belongs to any device that has a sensor to measure humidity."""

  NAME = 'sdm.devices.traits.Humidity'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_humidity_percent(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_HUMIDITY_PERCENT]


class TemperatureTrait:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.Temperature'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def ambient_temperature_celsius(self) -> float:
    """Percent humidity, measured at the device."""
    return self._data[AMBIENT_TEMPERATURE_CELSIUS]


class ThermostatEcoTrait:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.ThermostatEco'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def available_modes(self) -> list:
    """List of supported Eco modes."""
    return self._data[AVAILABLE_MODES]

  @property
  def mode(self) -> str:
    """The current Eco mode of the thermostat."""
    return self._data[MODE]

  async def set_mode(self, mode):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatEco.SetMode",
        "params" : { "mode" : mode }
    }
    return await self._cmd.execute(data)


  @property
  def heat_celsius(self) -> float:
    """Lowest temperature where Eco mode begins heating."""
    return self._data[HEAT_CELSIUS]

  @property
  def cool_celsius(self) -> float:
    """Highest cooling temperature where Eco mode begins cooling."""
    return self._data[COOL_CELSIUS]


class ThermostatHvacTrait:
  """This trait belongs to devices that can report HVAC details."""

  NAME = 'sdm.devices.traits.ThermostatHvac'

  def __init__(self, data: dict, cmd: Command):
    self._data = data

  @property
  def status(self) -> list:
    """Current HVAC status of the thermostat."""
    return self._data[STATUS]


class ThermostatModeTrait:
  """This trait belongs to devices that support different thermostat modes."""

  NAME = 'sdm.devices.traits.ThermostatMode'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def available_modes(self) -> list:
    """List of supported thermostat modes."""
    return self._data[AVAILABLE_MODES]

  @property
  def mode(self) -> str:
    """The current mode of the thermostat."""
    return self._data[MODE]

  async def set_mode(self, mode):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatMode.SetMode",
        "params" : { "mode" : mode }
    }
    return await self._cmd.execute(data)


class ThermostatTemperatureSetpointTrait:
  """This trait belongs to devices that support setting target temperature."""

  NAME = 'sdm.devices.traits.ThermostatTemperatureSetpoint'

  def __init__(self, data: dict, cmd: Command):
    self._data = data
    self._cmd = cmd

  @property
  def heat_celsius(self) -> float:
    """Lowest temperature where Eco mode begins heating."""
    return self._data[HEAT_CELSIUS]

  @property
  def cool_celsius(self) -> list:
    """Highest cooling temperature where Eco mode begins cooling."""
    return self._data[COOL_CELSIUS]

  async def set_heat(self, heat: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
        "params" : { "heatCelsius" : heat }
    }
    return await self._cmd.execute(data)

  async def set_cool(self, cool: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
        "params" : { "coolCelsius" : cool }
    }
    return await self._cmd.execute(data)

  async def set_range(self, heat: float, cool: float):
    """Change the thermostat Eco mode."""
    data = {
        "command" : "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
        "params" : {
            "heatCelsius" : heat,
            "coolCelsius" : cool,
        }
    }
    return await self._cmd.execute(data)



_ALL_TRAITS = [
  ConnectivityTrait,
  InfoTrait,
  HumidityTrait,
  TemperatureTrait,
  ThermostatEcoTrait,
  ThermostatHvacTrait,
  ThermostatModeTrait,
  ThermostatTemperatureSetpointTrait,
]
_ALL_TRAIT_MAP = { cls.NAME: cls for cls in _ALL_TRAITS }


def _TraitsDict(traits: dict, trait_map: dict, cmd: Command):
  d = {}
  for (trait, trait_data) in traits.items():
    if not trait in trait_map:
      continue
    cls = trait_map[trait]
    d[trait] = cls(trait_data, cmd)
  return d


class Device:
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, traits: dict):
    """Initialize a device."""
    self._raw_data = raw_data
    self._traits = traits

  @staticmethod
  def MakeDevice(raw_data: dict, auth: AbstractAuth):
    """Creates a device with the appropriate traits."""
    traits = raw_data.get(DEVICE_TRAITS, {})
    device_id = raw_data.get(DEVICE_NAME, '').rsplit('/', 1)[1]
    cmd = Command(device_id, auth)
    traits_dict = _TraitsDict(traits, _ALL_TRAIT_MAP, cmd)
    return Device(raw_data, traits_dict)

  @property
  def name(self) -> str:
    """The resource name of the device such as 'enterprises/XYZ/devices/123'."""
    return self._raw_data[DEVICE_NAME] 

  @property
  def type(self) -> str:
    """Type of device for display purposes.

    The device type should not be used to deduce or infer functionality of
    the actual device it is assigned to. Instead, use the returned traits for
    the device.
    """
    return self._raw_data[DEVICE_TYPE]

  @property
  def traits(self) -> dict:
    """Return a trait mixin on None."""
    return self._traits

  def _traits_data(self, trait) -> dict:
    """Return the raw dictionary for the specified trait."""
    traits_dict = self._raw_data.get(DEVICE_TRAITS, {})
    return traits_dict.get(trait, {})

  @property
  def parent_relations(self) -> dict:
    """"Assignee details of the device (e.g. room/structure)."""
    relations = {}
    for d in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
      if not PARENT in d or not DISPLAYNAME in d:
        continue
      relations[d[PARENT]] = d[DISPLAYNAME]
    return relations
