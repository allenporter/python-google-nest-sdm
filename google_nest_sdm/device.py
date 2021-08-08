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
from .traits import BuildTraits, Command
from .typing import cast_assert

_LOGGER = logging.getLogger(__name__)

DEVICE_NAME = "name"
DEVICE_TYPE = "type"
DEVICE_TRAITS = "traits"
DEVICE_PARENT_RELATIONS = "parentRelations"
PARENT = "parent"
DISPLAYNAME = "displayName"


def _MakeEventTraitMap(traits: Mapping[str, Any]) -> Dict[str, Any]:
    if camera_traits.CameraEventImageTrait.NAME not in traits:
        return {}
    event_trait_map: Dict[str, Any] = {}
    for (trait_name, trait) in traits.items():
        if not hasattr(trait, "EVENT_NAME"):
            continue
        event_trait_map[trait.EVENT_NAME] = trait
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
        self._event_trait_map = _MakeEventTraitMap(self._traits)

    @staticmethod
    def MakeDevice(raw_data: Mapping[str, Any], auth: AbstractAuth) -> Device:
        """Create a device with the appropriate traits."""
        device_id = raw_data.get(DEVICE_NAME)
        if not device_id:
            raise ValueError(f"raw_data missing field '{DEVICE_NAME}'")
        cmd = Command(device_id, auth)
        traits = raw_data.get(DEVICE_TRAITS, {})
        traits_dict = BuildTraits(traits, cmd, raw_data.get(DEVICE_TYPE))
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
        self._async_handle_events(event_message)
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

    def _async_handle_events(self, event_message: EventMessage) -> None:
        events = event_message.resource_update_events
        if not events:
            return
        _LOGGER.debug("Event Update %s", events.keys())
        for (event_name, event) in events.items():
            if event_name not in self._event_trait_map:
                continue
            self._event_trait_map[event_name].handle_event(event)

    def active_events(self, event_types: list) -> dict:
        """Return any active events for the specified trait names."""
        active_events = {}
        for event_type in event_types:
            trait = self._event_trait_map.get(event_type)
            if not trait or not trait.active_event:
                continue
            active_events[event_type] = trait.active_event
        return active_events

    @property
    def active_event_trait(self) -> Optional[EventTrait]:
        """Return trait with the most recently received active event."""
        trait_to_return: EventTrait | None = None
        for trait in self._event_trait_map.values():
            if not trait.active_event:
                continue
            if trait_to_return is None:
                trait_to_return = trait
            else:
                event = trait.last_event
                if not event or not trait_to_return.last_event:
                    continue
                if event.expires_at > trait_to_return.last_event.expires_at:
                    trait_to_return = trait
        return trait_to_return

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Return raw data for the device."""
        return dict(self._raw_data)
