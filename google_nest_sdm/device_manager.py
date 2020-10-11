"""Device Manager keeps track of the current state of all devices."""

from .device import Device
from .structure import InfoTrait, Structure, RoomInfoTrait
from .event import EventCallback, EventMessage

class DeviceManager(EventCallback):
  """DeviceManager holds current state of all devices."""

  def __init__(self):
    self._devices = {}
    self._structures = {}
    self._callback = None

  @property
  def devices(self) -> dict:
    return self._devices

  @property
  def structures(self) -> dict:
    return self._structures

  def add_device(self, device: Device):
    """Tracks the specified device."""
    self._devices[device.name] = device

  def add_structure(self, structure: Structure):
    """Tracks the specified device."""
    self._structures[structure.name] = structure

  def handle_event(self, event_message: EventMessage):
    """Invokes by the subscriber when a new message is received."""
    if event_message.resource_update_name:
      device_id = event_message.resource_update_name
      if device_id in self._devices:
        device = self._devices[device_id]
        for (trait_name, trait) in event_message.resource_update_traits.items():
          device.traits[trait_name] = trait

    if event_message.relation_update:
      relation = event_message.relation_update
      if relation.object in self._devices:
        device = self._devices[relation.object]
        if relation.type == 'DELETED':
          # Delete device from room/structure
          if relation.subject in device.parent_relations:
            del device.parent_relations[relation.subject]

        # Device moved to a room
        if relation.type == 'UPDATED' or relation.type == 'CREATED':
          name = 'Unknown'
          if relation.subject in self._structures:
            structure = self._structures[relation.subject]
            for trait_name in [InfoTrait.NAME, RoomInfoTrait.NAME]:
              if trait_name in structure.traits:
                name = structure.traits[trait_name].custom_name
                continue
          device.parent_relations[relation.subject] = name
