from .auth import AbstractAuth

from abc import abstractproperty, ABCMeta

# Every trait is implemented as a mixin that is attached to Device.  Each
# mixin expects to be able to get its traits from the device itself.
class WithTraits(object):
  __metaclass__ = ABCMeta

  @abstractproperty
  def _traits(self, trait) -> dict:
    pass


class InfoMixin:
  """This trait belongs to any device for device-related information."""

  NAME = 'sdm.devices.traits.Info'

  @property
  def custom_name(self) -> str:
    """Custom name of the device."""
    data = self._traits(InfoMixin.NAME)
    return data['customName']


# Create a map of all traits names to the class that can create it
_DEVICE_TRAIT_MIXINS = [
  InfoMixin,
]
_DEVICE_TRAIT_MAP = { cls.NAME: cls for cls in _DEVICE_TRAIT_MIXINS }

_DEVICE_NAME = "name"
_DEVICE_TYPE = "type"
_DEVICE_TRAITS = "traits"


class Device(WithTraits):
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, auth: AbstractAuth):
    """Initialize a device."""
    self._raw_data = raw_data
    self._auth = auth

  @staticmethod
  def MakeDevice(raw_data: dict, auth: AbstractAuth):
    bases = [Device]
    if _DEVICE_TRAITS in raw_data:
      for (trait, data) in raw_data[_DEVICE_TRAITS].items():
        if trait in _DEVICE_TRAIT_MAP:
          cls = _DEVICE_TRAIT_MAP[trait]
          bases.append(cls)
    d = Device(raw_data, auth)
    d.__class__ = type('DynamicDevice', tuple(bases), {})
    return d
    

  @property
  def name(self) -> str:
    """Return the full name and device identifier for the device."""
    return self._raw_data[_DEVICE_NAME] 

  @property
  def type(self) -> str:
    return self._raw_data[_DEVICE_TYPE]

  def _traits(self, trait) -> dict:
    """Return the raw dictionary for the specified trait."""
    if (not _DEVICE_TRAITS in self._raw_data or
        not trait in self._raw_data[_DEVICE_TRAITS]):
      return {}
    return self._raw_data[_DEVICE_TRAITS][trait]
