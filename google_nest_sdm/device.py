"""A device from the Smart Device Management API."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Mapping

try:
    from pydantic.v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field  # type: ignore

from . import camera_traits, device_traits, doorbell_traits, thermostat_traits
from .auth import AbstractAuth
from .diagnostics import Diagnostics, redact_data
from .event import EventMessage, EventProcessingError, EventTrait
from .event_media import EventMediaManager
from .traits import Command
from .model import TraitModel

_LOGGER = logging.getLogger(__name__)


def _MakeEventTraitMap(
    traits: Mapping[str, Any]
) -> dict[str, camera_traits.EventImageGenerator]:
    event_trait_map: dict[str, Any] = {}
    for trait_name, trait in traits.items():
        if not isinstance(trait, camera_traits.EventImageGenerator):
            continue
        event_trait_map[trait.event_type] = trait
    return event_trait_map


class ParentRelation(BaseModel):
    """Represents the parent structure/room of the current resource."""

    parent: str
    display_name: str = Field(alias="displayName")


class Device(TraitModel):
    """Class that represents a device object in the Google Nest SDM API."""

    name: str = Field(alias="name")
    """Resource name of the device such as 'enterprises/XYZ/devices/123'."""

    type: str | None = Field(alias="type")
    """Type of device for display purposes.

    The device type should not be used to deduce or infer functionality of
    the actual device it is assigned to. Instead, use the returned traits for
    the device.
    """

    # Device Traits
    connectivity: device_traits.ConnectivityTrait | None = Field(
        alias="sdm.devices.traits.Connectivity", exclude=True
    )
    fan: device_traits.FanTrait | None = Field(
        alias="sdm.devices.traits.Fan", exclude=True
    )
    info: device_traits.InfoTrait | None = Field(
        alias="sdm.devices.traits.Info", exclude=True
    )
    humidity: device_traits.HumidityTrait | None = Field(
        alias="sdm.devices.traits.Humidity", exclude=True
    )
    temperature: device_traits.TemperatureTrait | None = Field(
        alias="sdm.devices.traits.Temperature", exclude=True
    )

    # Thermostat Traits
    thermostat_eco: thermostat_traits.ThermostatEcoTrait | None = Field(
        alias="sdm.devices.traits.ThermostatEco", exclude=True
    )
    thermostat_hvac: thermostat_traits.ThermostatHvacTrait | None = Field(
        alias="sdm.devices.traits.ThermostatHvac", exclude=True
    )
    thermostat_mode: thermostat_traits.ThermostatModeTrait | None = Field(
        alias="sdm.devices.traits.ThermostatMode", exclude=True
    )
    thermostat_temperature_setpoint: thermostat_traits.ThermostatTemperatureSetpointTrait | None = Field(  # noqa: E501
        alias="sdm.devices.traits.ThermostatTemperatureSetpoint", exclude=True
    )

    # Camera Traits
    camera_image: camera_traits.CameraImageTrait | None = Field(
        alias="sdm.devices.traits.CameraImage", exclude=True
    )
    camera_live_stream: camera_traits.CameraLiveStreamTrait | None = Field(
        alias="sdm.devices.traits.CameraLiveStream", exclude=True
    )
    camera_event_image: camera_traits.CameraEventImageTrait | None = Field(
        alias="sdm.devices.traits.CameraEventImage", exclude=True
    )
    camera_motion: camera_traits.CameraMotionTrait | None = Field(
        alias="sdm.devices.traits.CameraMotion", exclude=True
    )
    camera_person: camera_traits.CameraPersonTrait | None = Field(
        alias="sdm.devices.traits.CameraPerson", exclude=True
    )
    camera_sound: camera_traits.CameraSoundTrait | None = Field(
        alias="sdm.devices.traits.CameraSound", exclude=True
    )
    camera_clip_preview: camera_traits.CameraClipPreviewTrait | None = Field(
        alias="sdm.devices.traits.CameraClipPreview", exclude=True
    )

    # Doorbell Traits
    doorbell_chime: doorbell_traits.DoorbellChimeTrait | None = Field(
        alias="sdm.devices.traits.DoorbellChime", exclude=True
    )

    relations: list[ParentRelation] = Field(
        alias="parentRelations", default_factory=list
    )
    """Represents the parent structure or room of the device."""

    def __init__(
        self,
        auth: AbstractAuth,
        **raw_data: Mapping[str, Any],
    ) -> None:
        """Initialize a device."""
        super().__init__(**raw_data)
        self._auth = auth
        self._diagnostics = Diagnostics()

        self._cmd = Command(self.name, auth, self._diagnostics.subkey("command"))

        # Propagate command and image creator to appropriate traits
        event_image_trait: camera_traits.EventImageCreator | None = None
        if self.camera_event_image:
            event_image_trait = self.camera_event_image
        elif self.camera_clip_preview:
            event_image_trait = self.camera_clip_preview
        for trait in self.traits.values():
            if hasattr(trait, "_cmd"):
                trait._cmd = self._cmd
            if hasattr(trait, "event_image_creator") and event_image_trait:
                trait.event_image_creator = event_image_trait

        self._event_media_manager = EventMediaManager(
            self.name,
            self.traits,
            _MakeEventTraitMap(self.traits),
            support_fetch=(event_image_trait is not None),
            diagnostics=self._diagnostics.subkey("event_media"),
        )
        self._callbacks: list[Callable[[EventMessage], Awaitable[None]]] = []

        if self.type and self.type == "sdm.devices.types.DOORBELL":
            self.doorbell_chime = doorbell_traits.DoorbellChimeTrait()

    @staticmethod
    def MakeDevice(raw_data: Mapping[str, Any], auth: AbstractAuth) -> Device:
        """Create a device with the appropriate traits."""
        return Device(auth=auth, **raw_data)

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
        _LOGGER.debug("Trait update %s", traits)
        self.update_traits(traits, event_message.timestamp)

    @property
    def event_media_manager(self) -> EventMediaManager:
        return self._event_media_manager

    @property
    def active_event_trait(self) -> EventTrait | None:
        """Return trait with the most recently received active event."""
        return self._event_media_manager.active_event_trait

    @property
    def parent_relations(self) -> dict:
        """Room or structure for the device."""
        return {relation.parent: relation.display_name for relation in self.relations}

    def delete_relation(self, parent: str) -> None:
        """Remove a device relationship with the parent."""
        self.relations = [
            relation for relation in self.relations if relation.parent != parent
        ]

    def create_relation(self, relation: ParentRelation) -> None:
        """Add a new device relation."""
        self.relations.append(relation)

    @property
    def raw_data(self) -> dict[str, Any]:
        """Return raw data for the device."""
        return self.dict(
            by_alias=True,
            exclude=Device._EXCLUDE_FIELDS,
            exclude_unset=True,
            exclude_defaults=True,
        )

    def get_diagnostics(self) -> dict[str, Any]:
        return {
            "data": redact_data(self.raw_data),
            **self._diagnostics.as_dict(),
        }

    _EXCLUDE_FIELDS = (
        set({"_auth", "_callbacks", "_cmd", "_diagnostics", "_event_media_manager"})
        | TraitModel._EXCLUDE_FIELDS
    )

    class Config:
        extra = "allow"
