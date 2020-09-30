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
PARENT = 'parent'
DISPLAYNAME = 'displayName'

class WithTraits(object):
  """Base class for Devices that support traits.

  Every trait is implemented as a mixin that is attached to Device.  Each
  mixin expects to be able to get traits from the device itself using
  the _traits_data method defined in this class.
  """

  __metaclass__ = ABCMeta

  @abstractproperty
  def _traits_data(self, trait: str) -> dict:
    pass


class ConnectivityMixin:
  """This trait belongs to any device that has connectivity information."""

  NAME = 'sdm.devices.traits.Connectivity'

  @property
  def status(self) -> str:
    """Device connectivity status.

    Return:
      "OFFLINE", "ONLINE"
    """
    data = self._traits_data(ConnectivityMixin.NAME)
    return data[STATUS]


class InfoMixin:
  """This trait belongs to any device for device-related information."""

  NAME = 'sdm.devices.traits.Info'

  @property
  def custom_name(self) -> str:
    """Custom name of the device."""
    data = self._traits_data(InfoMixin.NAME)
    return data[CUSTOM_NAME]


class HumidityMixin:
  """This trait belongs to any device that has a sensor to measure humidity."""

  NAME = 'sdm.devices.traits.Humidity'

  @property
  def ambient_humidity_percent(self) -> float:
    """Percent humidity, measured at the device."""
    data = self._traits_data(HumidityMixin.NAME)
    return data[AMBIENT_HUMIDITY_PERCENT]


class TemperatureMixin:
  """This trait belongs to any device that has a sensor to measure temperature."""

  NAME = 'sdm.devices.traits.Temperature'

  @property
  def ambient_temperature_celsius(self) -> float:
    """Percent humidity, measured at the device."""
    data = self._traits_data(TemperatureMixin.NAME)
    return data[AMBIENT_TEMPERATURE_CELSIUS]


# Create a map of all traits names to the class that can create it
_DEVICE_TRAIT_MIXINS = [
  ConnectivityMixin,
  InfoMixin,
  HumidityMixin,
  TemperatureMixin,
]
_DEVICE_TRAIT_MAP = { cls.NAME: cls for cls in _DEVICE_TRAIT_MIXINS }


class Device(WithTraits):
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, auth: AbstractAuth):
    """Initialize a device."""
    self._raw_data = raw_data
    self._auth = auth

  @staticmethod
  def MakeDevice(raw_data: dict, auth: AbstractAuth):
    """Creates a device with the appropriate traits."""
    bases = [Device]
    if DEVICE_TRAITS in raw_data:
      for (trait, data) in raw_data[DEVICE_TRAITS].items():
        if trait in _DEVICE_TRAIT_MAP:
          cls = _DEVICE_TRAIT_MAP[trait]
          bases.append(cls)
    d = Device(raw_data, auth)
    d.__class__ = type('DynamicDevice', tuple(bases), {})
    return d

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
  def traits(self) -> list:
    """Device traits."""
    if not DEVICE_TRAITS in self._raw_data:
      return {}
    return list(self._raw_data[DEVICE_TRAITS].keys())

  def has_trait(self, trait: str) -> bool:
    """Return True if the device has the specified trait."""
    if not DEVICE_TRAITS in self._raw_data:
      return False
    return trait in self._raw_data[DEVICE_TRAITS]


  def _traits_data(self, trait) -> dict:
    """Return the raw dictionary for the specified trait."""
    if not self.has_trait(trait):
      return {}
    return self._raw_data[DEVICE_TRAITS][trait]

  @property
  def parent_relations(self) -> dict:
    """"Assignee details of the device (e.g. room/structure)."""
    relations = {}
    for d in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
      if not PARENT in d or not DISPLAYNAME in d:
        continue
      relations[d[PARENT]] = d[DISPLAYNAME]
    return relations
