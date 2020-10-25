"""A device from the Smart Device Management API."""

import logging

# Import traits for registration
from typing import Callable

from . import camera_traits  # noqa: F401
from . import device_traits  # noqa: F401
from . import thermostat_traits  # noqa: F401
from .auth import AbstractAuth
from .event import EventCallback, EventMessage, EventProcessingError
from .traits import BuildTraits, Command

_LOGGER = logging.getLogger(__name__)

DEVICE_NAME = "name"
DEVICE_TYPE = "type"
DEVICE_TRAITS = "traits"
DEVICE_PARENT_RELATIONS = "parentRelations"
PARENT = "parent"
DISPLAYNAME = "displayName"


class Device:
    """Class that represents a device object in the Google Nest SDM API."""

    def __init__(self, raw_data: dict, traits: dict):
        """Initialize a device."""
        self._raw_data = raw_data
        self._traits = traits
        self._relations = {}
        for relation in self._raw_data.get(DEVICE_PARENT_RELATIONS, []):
            if PARENT not in relation or DISPLAYNAME not in relation:
                continue
            self._relations[relation[PARENT]] = relation[DISPLAYNAME]
        self._callbacks = []

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

    def add_event_callback(self, event_callback: EventCallback) -> Callable[[], None]:
        """Register an EventCallback for udpates to this device.

        The return value is a callable that will unregister the callback.
        """
        self._callbacks.append(event_callback)

        def remove_callback():
            """Remove the event_callback."""
            self._callbacks.remove(event_callback)

        return remove_callback

    def handle_event(self, event_message: EventMessage) -> None:
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
        traits = event_message.resource_update_traits
        if traits:
            _LOGGER.debug("Trait update %s", traits.keys())
        events = event_message.resource_update_events
        if events:
            _LOGGER.debug("Event Update %s", events.keys())

        for (trait_name, trait) in traits.items():
            self._traits[trait_name] = trait

        for callback in self._callbacks:
            callback.handle_event(event_message)
