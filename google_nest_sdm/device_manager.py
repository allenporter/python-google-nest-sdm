"""Device Manager keeps track of the current state of all devices."""

from .device import Device
from .event import EventCallback, EventMessage

class DeviceManager(EventCallback):
  """DeviceManager holds current state of all devices."""

  def __init__(self):
    self._devices = {}

  @property
  def devices(self) -> dict:
    return self._devices

  def add_device(self, device: Device):
    """Tracks the specified device."""
    self._devices[device.name] = device

  def handle_event(self, event_message: EventMessage):
    """Invokes by the subscriber when a new message is received."""
    device_id = event_message.resource_update_name
    if device_id in self._devices:
      device = self._devices[device_id]
      for (trait_name, trait) in event_message.resource_update_traits.items():
        device.traits[trait_name] = trait
