"""A device from the Smart Device Management API."""

from __future__ import annotations

import datetime
import logging
from typing import Any, Awaitable, Callable
from dataclasses import dataclass, field, fields, asdict

from mashumaro import field_options, DataClassDictMixin
from mashumaro.config import BaseConfig
from mashumaro.types import SerializationStrategy

from . import camera_traits, device_traits, doorbell_traits, thermostat_traits
from .auth import AbstractAuth
from .doorbell_traits import DoorbellChimeTrait
from .diagnostics import Diagnostics, redact_data
from .event import EventMessage, EventProcessingError
from .event_media import EventMediaManager
from .traits import Command
from .model import TraitDataClass, SDM_PREFIX, TRAITS

_LOGGER = logging.getLogger(__name__)


@dataclass
class ParentRelation(DataClassDictMixin):
    """Represents the parent structure/room of the current resource."""

    parent: str
    display_name: str = field(metadata=field_options(alias="displayName"))

    class Config(BaseConfig):
        serialize_by_alias = True


@dataclass
class TraitTypes(TraitDataClass):
    """Data model for parsing traits in the Google Nest SDM API."""

    # Device Traits
    connectivity: device_traits.ConnectivityTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.Connectivity",
        ),
        default=None,
    )
    fan: device_traits.FanTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.Fan",
        ),
        default=None,
    )
    info: device_traits.InfoTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.Info",
        ),
        default=None,
    )
    humidity: device_traits.HumidityTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.Humidity",
        ),
        default=None,
    )
    temperature: device_traits.TemperatureTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.Temperature",
        ),
        default=None,
    )

    # Thermostat Traits
    thermostat_eco: thermostat_traits.ThermostatEcoTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.ThermostatEco",
        ),
        default=None,
    )
    thermostat_hvac: thermostat_traits.ThermostatHvacTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.ThermostatHvac",
        ),
        default=None,
    )
    thermostat_mode: thermostat_traits.ThermostatModeTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.ThermostatMode",
        ),
        default=None,
    )
    thermostat_temperature_setpoint: (
        thermostat_traits.ThermostatTemperatureSetpointTrait | None
    ) = field(
        metadata=field_options(
            alias="sdm.devices.traits.ThermostatTemperatureSetpoint",
        ),
        default=None,
    )

    # # Camera Traits
    camera_image: camera_traits.CameraImageTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraImage",
        ),
        default=None,
    )
    camera_live_stream: camera_traits.CameraLiveStreamTrait | None = field(
        metadata=field_options(alias="sdm.devices.traits.CameraLiveStream"),
        default=None,
    )
    camera_event_image: camera_traits.CameraEventImageTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraEventImage",
        ),
        default=None,
    )
    camera_motion: camera_traits.CameraMotionTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraMotion",
        ),
        default=None,
    )
    camera_person: camera_traits.CameraPersonTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraPerson",
        ),
        default=None,
    )
    camera_sound: camera_traits.CameraSoundTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraSound",
        ),
        default=None,
    )
    camera_clip_preview: camera_traits.CameraClipPreviewTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.CameraClipPreview",
        ),
        default=None,
    )

    # # Doorbell Traits
    doorbell_chime: doorbell_traits.DoorbellChimeTrait | None = field(
        metadata=field_options(
            alias="sdm.devices.traits.DoorbellChime",
        ),
        default=None,
    )


class ParentRelationsSerializationStrategy(SerializationStrategy, use_annotations=True):
    """Parser to ignore invalid parent relations."""

    def serialize(self, value: list[ParentRelation]) -> list[dict[str, Any]]:
        return [x.to_dict() for x in value]

    def deserialize(self, value: list[dict[str, Any]]) -> list[ParentRelation]:
        return [
            ParentRelation.from_dict(relation)
            for relation in value
            if "parent" in relation and "displayName" in relation
        ]


def _name_required() -> str:
    """Raise an error if the name field is not provided.

    This is a workaround for the fact that dataclasses children can't have
    default fields out of order from the subclass.
    """
    raise ValueError("Field 'name' is required")


@dataclass
class Device(TraitTypes):
    """Class that represents a device object in the Google Nest SDM API."""

    name: str = field(default_factory=_name_required)
    """Resource name of the device such as 'enterprises/XYZ/devices/123'."""

    type: str | None = None
    """Type of device for display purposes.

    The device type should not be used to deduce or infer functionality of
    the actual device it is assigned to. Instead, use the returned traits for
    the device.
    """

    relations: list[ParentRelation] = field(
        metadata=field_options(alias="parentRelations"), default_factory=list
    )
    """Represents the parent structure or room of the device."""

    _auth: AbstractAuth = field(init=False, metadata={"serialize": "omit"})
    _diagnostics: Diagnostics = field(init=False, metadata={"serialize": "omit"})
    _event_media_manager: EventMediaManager = field(
        init=False, metadata={"serialize": "omit"}
    )
    _callbacks: list[Callable[[EventMessage], Awaitable[None]]] = field(
        init=False, metadata={"serialize": "omit"}, default_factory=list
    )
    _trait_event_ts: dict[str, datetime.datetime] = field(
        init=False, metadata={"serialize": "omit"}, default_factory=dict
    )

    @staticmethod
    def MakeDevice(raw_data: dict[str, Any], auth: AbstractAuth) -> Device:
        """Create a device with the appropriate traits."""

        # Hack for incorrect nest API response values
        if (type := raw_data.get("type")) and type == "sdm.devices.types.DOORBELL":
            if TRAITS not in raw_data:
                raw_data[TRAITS] = {}
            raw_data[TRAITS][DoorbellChimeTrait.NAME] = {}

        device: Device = Device.parse_trait_object(raw_data)
        device._auth = auth
        device._diagnostics = Diagnostics()
        cmd = Command(raw_data["name"], auth, device._diagnostics.subkey("command"))
        for trait in device.traits.values():
            if hasattr(trait, "_cmd"):
                trait._cmd = cmd

        event_traits = {
            trait.EVENT_NAME
            for trait in device.traits.values()
            if hasattr(trait, "EVENT_NAME")
        }
        device._event_media_manager = EventMediaManager(
            device.name or "",
            device.traits,
            event_traits,
            diagnostics=device._diagnostics.subkey("event_media"),
        )
        return device

    def add_update_listener(self, target: Callable[[], None]) -> Callable[[], None]:
        """Register a simple event listener notified on updates.

        This will not block on media being fetched. To wait for media, use
        the callback form the `EventMediaManager`.

        The return value is a callable that will unregister the callback.
        """

        async def handle_event(event_message: EventMessage) -> None:
            target()

        return self.add_event_callback(handle_event)

    def add_event_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> Callable[[], None]:
        """Register an event callback for updates to this device.

        This will not block on media being fetched. To wait for media, use
        the callback form the `EventMediaManager`.

        The return value is a callable that will unregister the callback.
        """
        self._callbacks.append(target)

        def remove_callback() -> None:
            """Remove the event_callback."""
            self._callbacks.remove(target)

        return remove_callback

    async def async_handle_event(self, event_message: EventMessage) -> None:
        """Process an event from the pubsub subscriber.

        This will invoke any directly registered callbacks (before fetching media)
        as well as any callbacks registered with the event media manager that
        fire post-media.
        """
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
        for callback in self._callbacks:
            await callback(event_message)
        await self._event_media_manager.async_handle_events(event_message)

    def _async_handle_traits(self, event_message: EventMessage) -> None:
        traits = event_message.resource_update_traits
        if not traits:
            return
        _LOGGER.debug("Trait update %s", traits)
        # Parse the traits using a separate object, then overwrite
        # each present field with an updated copy of the original trait with
        # the new fields merged in.
        parsed_traits = TraitTypes.parse_trait_object({TRAITS: traits})
        for trait_field in fields(parsed_traits):
            if (
                (alias := trait_field.metadata.get("alias")) is None
                or not alias.startswith(SDM_PREFIX)
                or not (new := getattr(parsed_traits, trait_field.name))
            ):
                continue
            # Discard updates to traits that are newer than the update
            if (
                self._trait_event_ts
                and (ts := self._trait_event_ts.get(trait_field.name))
                and ts > event_message.timestamp
            ):
                _LOGGER.debug("Discarding stale update (%s)", event_message.timestamp)
                continue

            # Only merge updates into existing models, updating the existing
            # fields present in the update trait
            if not (existing := getattr(self, trait_field.name)):
                continue
            for k, v in asdict(new).items():
                if v is not None:
                    setattr(existing, k, v)
            self._trait_event_ts[trait_field.name] = event_message.timestamp

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

    class Config(TraitTypes.Config):
        serialization_strategy = {
            list[ParentRelation]: ParentRelationsSerializationStrategy(),
        }
