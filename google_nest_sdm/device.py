"""A device from the Smart Device Management API."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Awaitable, Callable

try:
    from pydantic.v1 import BaseModel, Field, root_validator
except ImportError:
    from pydantic import BaseModel, Field, root_validator # type: ignore

from . import camera_traits, device_traits, doorbell_traits, thermostat_traits
from .auth import AbstractAuth
from .diagnostics import Diagnostics, redact_data
from .event import EventMessage, EventProcessingError
from .event_media import EventMediaManager
from .traits import Command
from .model import TraitModel

_LOGGER = logging.getLogger(__name__)


class ParentRelation(BaseModel):
    """Represents the parent structure/room of the current resource."""

    parent: str
    display_name: str = Field(alias="displayName")


class DeviceTraits(TraitModel):
    """Pydantic model for parsing traits in the Google Nest SDM API."""

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

    class Config:
        extra = "allow"


class Device(DeviceTraits):
    """Class that represents a device object in the Google Nest SDM API."""

    name: str
    """Resource name of the device such as 'enterprises/XYZ/devices/123'."""

    type: str | None
    """Type of device for display purposes.

    The device type should not be used to deduce or infer functionality of
    the actual device it is assigned to. Instead, use the returned traits for
    the device.
    """

    relations: list[ParentRelation] = Field(
        alias="parentRelations", default_factory=list
    )
    """Represents the parent structure or room of the device."""

    def __init__(self, raw_data: dict[str, Any], auth: AbstractAuth) -> None:
        """Initialize a device."""
        # Hack for incorrect nest API response values
        if (type := raw_data.get("type")) and type == "sdm.devices.types.DOORBELL":
            if "traits" not in raw_data:
                raw_data["traits"] = {}
            raw_data["traits"][doorbell_traits.DoorbellChimeTrait.NAME] = {}
        super().__init__(**raw_data)
        self._auth = auth
        self._diagnostics = Diagnostics()
        self._cmd = Command(raw_data["name"], auth, self._diagnostics.subkey("command"))
        for trait in self.traits.values():
            if hasattr(trait, "_cmd"):
                trait._cmd = self._cmd

        event_traits = {
            trait.EVENT_NAME
            for trait in self.traits.values()
            if hasattr(trait, "EVENT_NAME")
        }
        self._event_media_manager = EventMediaManager(
            self.name,
            self.traits,
            event_traits,
            diagnostics=self._diagnostics.subkey("event_media"),
        )
        self._callbacks: list[Callable[[EventMessage], Awaitable[None]]] = []
        self._trait_event_ts: dict[str, datetime.datetime] = {}

    @staticmethod
    def MakeDevice(raw_data: dict[str, Any], auth: AbstractAuth) -> Device:
        """Create a device with the appropriate traits."""
        return Device(raw_data, auth)

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
        # Parse the traits using a separate pydantic object, then overwrite
        # each present field with an updated copy of the original trait with
        # the new fields merged in.
        parsed_traits = DeviceTraits.parse_obj({"traits": traits})
        for field in parsed_traits.__fields__.values():
            if not (new := getattr(parsed_traits, field.name)) or not isinstance(
                new, BaseModel
            ):
                continue
            # Discard updates to traits that are newer than the update
            if (
                self._trait_event_ts
                and (ts := self._trait_event_ts.get(field.name))
                and ts > event_message.timestamp
            ):
                _LOGGER.debug("Discarding stale update (%s)", event_message.timestamp)
                continue

            # Only merge updates into existing models
            if not (existing := getattr(self, field.name)) or not isinstance(
                existing, BaseModel
            ):
                continue
            obj = existing.copy(update=new.dict())
            setattr(self, field.name, obj)
            self._trait_event_ts[field.name] = event_message.timestamp

    @property
    def event_media_manager(self) -> EventMediaManager:
        return self._event_media_manager

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

    def get_diagnostics(self) -> dict[str, Any]:
        return {
            "data": redact_data(self.raw_data),
            **self._diagnostics.as_dict(),
        }

    @root_validator(pre=True)
    def _parent_relations(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Ignore invalid parentRelations."""
        if not (relations := values.get("parentRelations")):
            return values
        values["parentRelations"] = [
            relation for relation in relations if "parent" in relation and "displayName" in relation 
        ]
        return values


    _EXCLUDE_FIELDS = (
        set({"_auth", "_callbacks", "_cmd", "_diagnostics", "_event_media_manager"})
        | TraitModel._EXCLUDE_FIELDS
    )

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
