"""Device Manager keeps track of the current state of all devices."""

from .device import Device
from .event import EventMessage, RelationUpdate
from .structure import InfoTrait, RoomInfoTrait, Structure


class DeviceManager:
    """DeviceManager holds current state of all devices."""

    def __init__(self):
        """Initialize DeviceManager."""
        self._devices = {}
        self._structures = {}
        self._callback = None

    @property
    def devices(self) -> dict:
        """Return current state of devices."""
        return self._devices

    @property
    def structures(self) -> dict:
        """Return current state of structures."""
        return self._structures

    def add_device(self, device: Device) -> None:
        """Track the specified device."""
        self._devices[device.name] = device

    def add_structure(self, structure: Structure) -> None:
        """Track the specified device."""
        self._structures[structure.name] = structure

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a new message received."""
        if event_message.relation_update:
            self._handle_device_relation(event_message.relation_update)

        if event_message.resource_update_name:
            device_id = event_message.resource_update_name
            if device_id in self._devices:
                device = self._devices[device_id]
                await device.async_handle_event(event_message)

    def _structure_name(self, relation_subject: str) -> str:
        if relation_subject in self._structures:
            structure = self._structures[relation_subject]
            for trait_name in [InfoTrait.NAME, RoomInfoTrait.NAME]:
                if trait_name in structure.traits:
                    return structure.traits[trait_name].custom_name
        return "Unknown"

    def _handle_device_relation(self, relation: RelationUpdate) -> None:
        if relation.object not in self._devices:
            return

        device = self._devices[relation.object]
        if relation.type == "DELETED":
            # Delete device from room/structure
            if relation.subject in device.parent_relations:
                del device.parent_relations[relation.subject]

        if relation.type == "UPDATED" or relation.type == "CREATED":
            # Device moved to a room
            device.parent_relations[relation.subject] = self._structure_name(
                relation.subject
            )
