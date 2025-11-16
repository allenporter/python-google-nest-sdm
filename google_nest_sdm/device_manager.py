"""Device Manager keeps track of the current state of all devices."""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Dict

from .device import Device, ParentRelation
from .exceptions import ApiException
from .event import EventMessage, RelationUpdate
from .event_media import CachePolicy
from .google_nest_api import GoogleNestAPI
from .structure import Structure
from .diagnostics import DEVICE_MANAGER_DIAGNOSTICS as DIAGNOSTICS

_LOGGER = logging.getLogger(__name__)


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
        self._update_callback: Callable[[EventMessage], Awaitable[None]] | None = None
        self._change_callback: Callable[[], Awaitable[None]] | None = None

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
        self._update_callback = target
        for device in self._devices.values():
            device.event_media_manager.set_update_callback(target)

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Handle a new message received."""

        if _is_invalid_thermostat_trait_update(event_message):
            _LOGGER.debug(
                "Ignoring event with invalid update traits; Refreshing devices: %s",
                event_message.resource_update_traits,
            )
            await self._hack_refresh_devices()
            return

        if event_message.relation_update:
            _LOGGER.debug("Handling relation update: %s", event_message.relation_update)
            self._handle_device_relation(event_message.relation_update)
            # Also discover any new devices/structures
            try:
                await self.async_refresh()
            except ApiException:
                _LOGGER.debug("Failed to refresh devices")
            if self._update_callback:
                await self._update_callback(event_message)
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
        old_structure_ids = set(self._structures.keys())
        new_structures = {
            structure.name: structure for structure in structures if structure.name
        }
        for structure in new_structures.values():
            if structure.name not in self._structures:
                _LOGGER.debug("Adding structure %s", structure.name)
                self._structures[structure.name] = structure
        removed_structure_ids = old_structure_ids - set(new_structures.keys())
        for structure_id in removed_structure_ids:
            _LOGGER.debug("Removing structure %s", structure_id)
            del self._structures[structure_id]

        # Refresh devices
        devices = await self._api.async_get_devices()
        old_device_ids = set(self._devices.keys())
        new_devices = {device.name: device for device in devices if device.name}
        for device in new_devices.values():
            if existing_device := self._devices.get(device.name):
                existing_device.merge_from_update(device)
            else:
                _LOGGER.debug("Adding device %s", device.name)
                self._add_device(device)

        removed_device_ids = old_device_ids - set(new_devices.keys())
        for device_id in removed_device_ids:
            _LOGGER.debug("Removing device %s", device_id)
            del self._devices[device_id]

        if self._change_callback and (
            old_device_ids != set(self._devices.keys())
            or old_structure_ids != set(self._structures.keys())
        ):
            await self._change_callback()

    def _add_device(self, device: Device) -> None:
        """Track the specified device."""
        assert device.name
        self._devices[device.name] = device
        # Share a single cache policy across all devices
        device.event_media_manager.cache_policy = self._cache_policy
        if self._update_callback:
            device.event_media_manager.set_update_callback(self._update_callback)

    def set_change_callback(self, target: Callable[[], Awaitable[None]]) -> None:
        """Register a callback invoked when devices or structures change."""
        self._change_callback = target

    async def _hack_refresh_devices(self) -> None:
        """Update the device manager with refreshed devices from the API."""
        DIAGNOSTICS.increment("invalid-thermostat-update")
        try:
            await self.async_refresh()
        except ApiException:
            DIAGNOSTICS.increment("invalid-thermostat-update-refresh-failure")
            _LOGGER.debug("Failed to refresh devices after invalid message")
        else:
            DIAGNOSTICS.increment("invalid-thermostat-update-refresh-success")


def _is_invalid_thermostat_trait_update(event: EventMessage) -> bool:
    """Return true if this is an invalid thermostat trait update."""
    if (
        event.resource_update_traits is not None
        and (
            thermostat_mode := event.resource_update_traits.get(
                "sdm.devices.traits.ThermostatMode"
            )
        )
        and (available_modes := thermostat_mode.get("availableModes")) is not None
        and available_modes == ["OFF"]
    ):
        return True
    return False
