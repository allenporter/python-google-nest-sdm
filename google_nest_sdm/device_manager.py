"""Device Manager keeps track of the current state of all devices."""

from __future__ import annotations

from typing import Awaitable, Callable, Dict

from .device import Device, ParentRelation
from .event import EventMessage, RelationUpdate
from .event_media import CachePolicy
from .google_nest_api import GoogleNestAPI
from .structure import Structure


class DeviceManager:
    """DeviceManager holds current state of all devices."""

    def __init__(
        self, api: GoogleNestAPI, cache_policy: CachePolicy | None = None
    ) -> None:
        """Initialize DeviceManager."""
        self._api = api
        self._devices: Dict[str, Device] = {}
        self._structures: Dict[str, Structure] = {}
        self._cache_policy = cache_policy if cache_policy else CachePolicy()
        self._callback: Callable[[EventMessage], Awaitable[None]] | None = None

    @property
    def devices(self) -> Dict[str, Device]:
        """Return current state of devices."""
        return self._devices

    @property
    def structures(self) -> Dict[str, Structure]:
        """Return current state of structures."""
        return self._structures

    @property
    def cache_policy(self) -> CachePolicy:
        """Return cache policy shared by device EventMediaManager objects."""
        return self._cache_policy

    def set_update_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> None:
        """Register a callback invoked when new messages are received.

        If the event is associated with media, then the callback will only
        be invoked once the media has been fetched.
        """
        self._callback = target
        for device in self._devices.values():
            device.event_media_manager.set_update_callback(target)

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a new message received."""
        if event_message.relation_update:
            self._handle_device_relation(event_message.relation_update)
            if self._callback:
                await self._callback(event_message)
            return

        if event_message.resource_update_name:
            device_id = event_message.resource_update_name
            if device_id in self._devices:
                device = self._devices[device_id]
                await device.async_handle_event(event_message)

    def _structure_name(self, relation_subject: str) -> str:
        if relation_subject in self._structures:
            structure = self._structures[relation_subject]
            for trait in [structure.info, structure.room_info]:
                if trait and trait.custom_name:
                    return trait.custom_name
        return "Unknown"

    def _handle_device_relation(self, relation: RelationUpdate) -> None:
        if relation.object not in self._devices:
            return

        device = self._devices[relation.object]
        if relation.type == "DELETED":
            # Delete device from room/structure
            device.delete_relation(relation.subject)

        if relation.type == "UPDATED" or relation.type == "CREATED":
            # Device moved to a room
            assert relation.subject
            device.create_relation(
                ParentRelation.from_dict(
                    {
                        "parent": relation.subject,
                        "displayName": self._structure_name(relation.subject),
                    }
                )
            )

    async def async_refresh(self) -> None:
        """Refresh devices and structures from the API."""
        # Refresh structures
        structures = await self._api.async_get_structures()
        new_structures = {
            structure.name: structure for structure in structures if structure.name
        }
        for structure_id, structure in new_structures.items():
            self._add_structure(structure)
        removed_structure_ids = self._structures.keys() - new_structures.keys()
        for structure_id in removed_structure_ids:
            del self._structures[structure_id]

        # Refresh devices
        devices = await self._api.async_get_devices()
        new_devices = {device.name: device for device in devices if device.name}
        # Add/update devices
        for device_id, device in new_devices.items():
            self._add_device(device)

        # Remove devices that no longer exist
        removed_ids = self._devices.keys() - new_devices.keys()
        for device_id in removed_ids:
            del self._devices[device_id]

    def _add_device(self, device: Device) -> None:
        """Track the specified device."""
        assert device.name
        self._devices[device.name] = device
        # Share a single cache policy across all devices
        device.event_media_manager.cache_policy = self._cache_policy
        if self._callback:
            device.event_media_manager.set_update_callback(self._callback)

    def _add_structure(self, structure: Structure) -> None:
        """Track the specified device."""
        assert structure.name
        self._structures[structure.name] = structure
