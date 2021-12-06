"""A device from the Smart Device Management API."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, cast

# Import traits for registration
from . import camera_traits  # noqa: F401
from . import device_traits  # noqa: F401
from . import doorbell_traits  # noqa: F401
from . import thermostat_traits  # noqa: F401
from .auth import AbstractAuth
from .event import EventMessage, EventProcessingError, EventTrait
from .event_media import EventMediaManager
from .traits import BuildTraits, Command
from .typing import cast_assert

_LOGGER = logging.getLogger(__name__)

DEVICE_NAME = "name"
DEVICE_TYPE = "type"
DEVICE_TRAITS = "traits"
DEVICE_PARENT_RELATIONS = "parentRelations"
PARENT = "parent"
DISPLAYNAME = "displayName"


def _MakeEventTraitMap(
    traits: Mapping[str, Any]
) -> Dict[str, camera_traits.EventImageGenerator]:
    if (
        camera_traits.CameraEventImageTrait.NAME not in traits
        and camera_traits.CameraClipPreviewTrait.NAME not in traits
    ):
        return {}
    event_trait_map: Dict[str, Any] = {}
    for (trait_name, trait) in traits.items():
        if not isinstance(trait, camera_traits.EventImageGenerator):
            continue
        event_trait_map[trait.event_type] = trait
    return event_trait_map


class Device:
    """Class that represents a device object in the Google Nest SDM API."""

    def __init__(self, raw_data: Mapping[str, Any], traits: Dict[str, Any]):
        """Initialize a device."""
        self._raw_data = raw_data
        self._traits = traits
        self._trait_event_ts: Dict[str, datetime.datetime] = {}
        self._relations = {}
        for relation in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
            if PARENT not in relation or DISPLAYNAME not in relation:
                continue
            self._relations[relation[PARENT]] = relation[DISPLAYNAME]
        self._callbacks: List[Callable[[EventMessage], Awaitable[None]]] = []
        event_trait_map = _MakeEventTraitMap(self._traits)

        self._event_media_manager = EventMediaManager(self.name, event_trait_map)

    @staticmethod
    def MakeDevice(raw_data: Mapping[str, Any], auth: AbstractAuth) -> Device:
        """Create a device with the appropriate traits."""
        device_id = raw_data.get(DEVICE_NAME)
        if not device_id:
            raise ValueError(f"raw_data missing field '{DEVICE_NAME}'")
        cmd = Command(device_id, auth)
        traits = raw_data.get(DEVICE_TRAITS, {})
        traits_dict = BuildTraits(traits, cmd, raw_data.get(DEVICE_TYPE))

        # Hack to wire up camera traits to the event image generator
        event_image_trait: camera_traits.EventImageCreator | None = None
        if camera_traits.CameraEventImageTrait.NAME in traits_dict:
            event_image_trait = traits_dict[camera_traits.CameraEventImageTrait.NAME]
        elif camera_traits.CameraClipPreviewTrait.NAME in traits_dict:
            event_image_trait = traits_dict[camera_traits.CameraClipPreviewTrait.NAME]
        if event_image_trait:
            for trait_class in traits_dict.values():
                if hasattr(trait_class, "event_image_creator"):
                    trait_class.event_image_creator = event_image_trait

        return Device(raw_data, traits_dict)

    @property
    def name(self) -> str:
        """Resource name of the device such as 'enterprises/XYZ/devices/123'."""
        return cast_assert(str, self._raw_data[DEVICE_NAME])

    @property
    def type(self) -> str:
        """Type of device for display purposes.

        The device type should not be used to deduce or infer functionality of
        the actual device it is assigned to. Instead, use the returned traits for
        the device.
        """
        return cast_assert(str, self._raw_data[DEVICE_TYPE])

    @property
    def traits(self) -> Dict[str, Any]:
        """Return a trait mixin or None."""
        return self._traits

    def _traits_data(self, trait: str) -> Dict[str, Any]:
        """Return the raw dictionary for the specified trait."""
        traits_dict = self._raw_data.get(DEVICE_TRAITS, {})
        return cast(Dict[str, Any], traits_dict.get(trait, {}))

    @property
    def parent_relations(self) -> dict:
        """Room or structure for the device."""
        return self._relations

    def add_update_listener(self, target: Callable[[], None]) -> Callable[[], None]:
        """Register a simple event listener notified on updates.

        The return value is a callable that will unregister the callback.
        """

        async def handle_event(event_message: EventMessage) -> None:
            target()

        return self.add_event_callback(handle_event)

    def add_event_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> Callable[[], None]:
        """Register an event callback for updates to this device.

        The return value is a callable that will unregister the callback.
        """
        self._callbacks.append(target)

        def remove_callback() -> None:
            """Remove the event_callback."""
            self._callbacks.remove(target)

        return remove_callback

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Process an event from the pubsub subscriber."""
        _LOGGER.debug(
            "Processing update %s @ %s", event_message.event_id, event_message.timestamp
        )
        if not event_message.resource_update_name:
            raise EventProcessingError("Event was not resource update event")
        if self.name != event_message.resource_update_name:
            raise EventProcessingError(
                f"Mismatch {self.name} != {event_message.resource_update_name}"
            )
        self._async_handle_traits(event_message)
        await self._event_media_manager.async_handle_events(event_message)
        for callback in self._callbacks:
            await callback(event_message)

    def _async_handle_traits(self, event_message: EventMessage) -> None:
        traits = event_message.resource_update_traits
        if not traits:
            return
        _LOGGER.debug("Trait update %s", traits.keys())
        for (trait_name, trait) in traits.items():
            # Discard updates older than prior events
            # Note: There is still a race where traits read from the API on
            # startup are overwritten with old messages. We assume that the
            # event messages will eventually correct that.
            if trait_name in self._trait_event_ts:
                ts = self._trait_event_ts[trait_name]
                if ts > event_message.timestamp:
                    continue
            self._traits[trait_name] = trait
            self._trait_event_ts[trait_name] = event_message.timestamp

    @property
    def event_media_manager(self) -> EventMediaManager:
        return self._event_media_manager

    def active_events(self, event_types: list) -> dict:
        """Return any active events for the specified trait names."""
        return self._event_media_manager.active_events(event_types)

    @property
    def active_event_trait(self) -> Optional[EventTrait]:
        """Return trait with the most recently received active event."""
        return self._event_media_manager.active_event_trait

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Return raw data for the device."""
        return dict(self._raw_data)
