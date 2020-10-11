from .auth import AbstractAuth

import datetime

from .traits import BuildTraits
from .traits import Command
from . import camera_traits
from . import device_traits
from . import thermostat_traits

DEVICE_NAME = 'name'
DEVICE_TYPE = 'type'
DEVICE_TRAITS = 'traits'
DEVICE_PARENT_RELATIONS = 'parentRelations'
PARENT = 'parent'
DISPLAYNAME = 'displayName'


class Device:
  """Class that represents a device object in the Google Nest SDM API."""

  def __init__(self, raw_data: dict, traits: dict):
    """Initialize a device."""
    self._raw_data = raw_data
    self._traits = traits
    self._relations = {}
    for d in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
      if not PARENT in d or not DISPLAYNAME in d:
        continue
      self._relations[d[PARENT]] = d[DISPLAYNAME]

  @staticmethod
  def MakeDevice(raw_data: dict, auth: AbstractAuth):
    """Creates a device with the appropriate traits."""
    device_id = raw_data.get(DEVICE_NAME)
    cmd = Command(device_id, auth)
    traits = raw_data.get(DEVICE_TRAITS, {})
    traits_dict = BuildTraits(traits, cmd)
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
    """Return a trait mixin or None."""
    return self._traits

  def _traits_data(self, trait) -> dict:
    """Return the raw dictionary for the specified trait."""
    traits_dict = self._raw_data.get(DEVICE_TRAITS, {})
    return traits_dict.get(trait, {})

  @property
  def parent_relations(self) -> dict:
    """"Assignee details of the device (e.g. room/structure)."""
    return self._relations
