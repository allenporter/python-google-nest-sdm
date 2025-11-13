"""Events from pubsub subscriber."""

from __future__ import annotations

from abc import ABC, abstractmethod
import base64
import binascii
from dataclasses import dataclass, field
import datetime
from enum import StrEnum
import hashlib
import json
import logging
import traceback
from typing import Any, Iterable, Mapping, ClassVar

from mashumaro import DataClassDictMixin, field_options
from mashumaro.config import (
    BaseConfig,
)
from mashumaro.types import SerializationStrategy

from .auth import AbstractAuth
from .exceptions import DecodeException
from .registry import Registry

__all__ = [
    "EventMessage",
    "CameraMotionEvent",
    "CameraPersonEvent",
    "CameraSoundEvent",
    "DoorbellChimeEvent",
    "CameraClipPreviewEvent",
    "EventImageType",
    "EventProcessingError",
]

EVENT_ID = "eventId"
EVENT_SESSION_ID = "eventSessionId"
TIMESTAMP = "timestamp"
RESOURCE_UPDATE = "resourceUpdate"
NAME = "name"
TRAITS = "traits"
EVENTS = "events"
PREVIEW_URL = "previewUrl"
ZONES = "zones"
EVENT_THREAD_STATE_ENDED = "ENDED"

# Event images expire 30 seconds after the event is published
EVENT_IMAGE_EXPIRE_SECS = 30

# Camera clip previews don't list an expiration in the API. Lets say 15 minutes
# as an arbitrary number for now.
CAMERA_CLIP_PREVIEW_EXPIRE_SECS = 15 * 60

EVENT_MAP = Registry()

_LOGGER = logging.getLogger(__name__)


class EventType(StrEnum):
    """Types of events."""

    CAMERA_MOTION = "sdm.devices.events.CameraMotion.Motion"
    CAMERA_PERSON = "sdm.devices.events.CameraPerson.Person"
    CAMERA_SOUND = "sdm.devices.events.CameraSound.Sound"
    DOORBELL_CHIME = "sdm.devices.events.DoorbellChime.Chime"
    CAMERA_CLIP_PREVIEW = "sdm.devices.events.CameraClipPreview.ClipPreview"


class EventProcessingError(Exception):
    """Raised when there was an error handling an event."""


@dataclass(frozen=True)
class EventImageContentType(DataClassDictMixin):
    """Event image content type."""

    content_type: str

    def __str__(self) -> str:
        """Return a string representation of the event image type."""
        return self.content_type


class EventImageType(ABC):
    IMAGE = EventImageContentType("image/jpeg")
    CLIP_PREVIEW = EventImageContentType("video/mp4")
    IMAGE_PREVIEW = EventImageContentType("image/gif")

    @staticmethod
    def from_string(content_type: str) -> EventImageContentType:
        """Parse an EventImageType from a string representation."""
        if content_type == EventImageType.CLIP_PREVIEW.content_type:
            return EventImageType.CLIP_PREVIEW
        elif content_type == EventImageType.IMAGE.content_type:
            return EventImageType.IMAGE
        elif content_type == EventImageType.IMAGE_PREVIEW.content_type:
            return EventImageType.IMAGE_PREVIEW
        else:
            return EventImageContentType(content_type)


@dataclass
class EventToken:
    """Identifier for a unique event."""

    event_session_id: str = field(metadata=field_options(alias="eventSessionId"))
    event_id: str = field(metadata=field_options(alias="eventId"))

    def encode(self) -> str:
        """Encode the event token as a serialized string."""
        data = [self.event_session_id, self.event_id]
        b = json.dumps(data).encode("utf-8")
        return base64.b64encode(b).decode("utf-8")

    @staticmethod
    def decode(content: str) -> EventToken:
        """Decode an event token into a class."""
        try:
            s = base64.b64decode(content).decode("utf-8")
        except binascii.Error as err:
            raise DecodeException from err
        data = json.loads(s)
        if not isinstance(data, list) or len(data) != 2:
            raise DecodeException("Unexpected data type: %s", data)
        return EventToken(data[0], data[1])

    def __repr__(self) -> str:
        if not self.event_id:
            return "<EventToken event_session_id" + self.event_session_id + ">"
        return (
            "<EventToken event_session_id"
            + self.event_session_id
            + " event_id="
            + self.event_id
            + ">"
        )


class EventImageTypeSerializationStrategy(SerializationStrategy):
    def serialize(self, value: EventImageContentType) -> str:
        return value.content_type

    def deserialize(self, value: str) -> EventImageContentType:
        return EventImageType.from_string(value)


@dataclass
class ImageEventBase(DataClassDictMixin, ABC):
    """Base class for all image related event types."""

    event_session_id: str = field(metadata=field_options(alias="eventSessionId"))
    """ID used to associate separate messages with a single event."""

    timestamp: datetime.datetime
    """Timestamp when the event occurred."""

    event_id: str = field(metadata=field_options(alias="eventId"), default="")
    """ID used to associate separate messages with a single event."""

    event_image_type: EventImageContentType = field(default=EventImageType.IMAGE)
    """Type of the event."""

    zones: list[str] = field(default_factory=list)
    """List of zones for the event."""

    @property
    def event_token(self) -> str:
        """An identifier of this session / event combination."""
        token = EventToken(self.event_session_id, self.event_id)
        return token.encode()

    @property
    @abstractmethod
    def event_type(self) -> EventType:
        """The type of event."""

    @property
    def expires_at(self) -> datetime.datetime:
        """Timestamp when the message expires."""
        return self.timestamp + datetime.timedelta(seconds=EVENT_IMAGE_EXPIRE_SECS)

    @property
    def is_expired(self) -> bool:
        """Return true if the event expiration has passed."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        return self.expires_at < now

    def as_dict(self) -> dict[str, Any]:
        """Return as a dict form that can be serialized for persistence."""
        return {
            "event_type": self.event_type,
            "event_data": self.to_dict(),
            "timestamp": self.timestamp.isoformat(),
            "event_image_type": str(self.event_image_type),
        }

    @staticmethod
    def parse_event_dict(data: dict[str, Any]) -> ImageEventBase | None:
        """Parse from a persisted serialized dictionary."""
        event_type = data["event_type"]
        event_data = data["event_data"]
        event = _BuildEvent(event_type, event_data)
        if event and "event_image_type" in data:
            event.event_image_type = EventImageType.from_string(
                data["event_image_type"]
            )
        return event

    class Config(BaseConfig):
        serialization_strategy = {
            EventImageContentType: EventImageTypeSerializationStrategy(),
        }
        code_generation_options = [
            "TO_DICT_ADD_BY_ALIAS_FLAG",
            "TO_DICT_ADD_OMIT_NONE_FLAG",
        ]
        allow_deserialization_not_by_alias = True


@EVENT_MAP.register()
@dataclass
class CameraMotionEvent(ImageEventBase):
    """Motion has been detected by the camera."""

    NAME: ClassVar[EventType] = EventType.CAMERA_MOTION
    event_image_type: EventImageContentType = field(default=EventImageType.IMAGE)

    @property
    def event_type(self) -> EventType:
        """The type of event."""
        return EventType.CAMERA_MOTION


@EVENT_MAP.register()
@dataclass
class CameraPersonEvent(ImageEventBase):
    """A person has been detected by the camera."""

    NAME: ClassVar[EventType] = EventType.CAMERA_PERSON
    event_image_type: EventImageContentType = field(default=EventImageType.IMAGE)

    @property
    def event_type(self) -> EventType:
        """The type of event."""
        return EventType.CAMERA_PERSON


@EVENT_MAP.register()
@dataclass
class CameraSoundEvent(ImageEventBase):
    """Sound has been detected by the camera."""

    NAME: ClassVar[EventType] = EventType.CAMERA_SOUND
    event_image_type: EventImageContentType = field(default=EventImageType.IMAGE)

    @property
    def event_type(self) -> EventType:
        """The type of event."""
        return EventType.CAMERA_SOUND


@EVENT_MAP.register()
@dataclass
class DoorbellChimeEvent(ImageEventBase):
    """The doorbell has been pressed."""

    NAME: ClassVar[EventType] = EventType.DOORBELL_CHIME
    event_image_type: EventImageContentType = field(default=EventImageType.IMAGE)

    @property
    def event_type(self) -> EventType:
        """The type of event."""
        return EventType.DOORBELL_CHIME


@EVENT_MAP.register()
@dataclass
class CameraClipPreviewEvent(ImageEventBase):
    """A video clip is available for preview, without extra download."""

    NAME: ClassVar[EventType] = EventType.CAMERA_CLIP_PREVIEW
    event_image_type: EventImageContentType = field(default=EventImageType.CLIP_PREVIEW)

    preview_url: str = field(metadata=field_options(alias="previewUrl"), default="")
    """A url 10 second frame video file in mp4 format."""

    @property
    def event_type(self) -> EventType:
        """The type of event."""
        return EventType.CAMERA_CLIP_PREVIEW

    @classmethod
    def __pre_deserialize__(cls, d: dict[Any, Any]) -> dict[Any, Any]:
        """Validate the event id to use a URL hash as the event id.

        Since clip preview events already have a url associated with them,
        we don't have an event id for downloading the image.
        """
        if not (preview_url := d.get("previewUrl", d.get("preview_url"))):
            raise ValueError("missing required field previewUrl")
        d["eventId"] = hashlib.blake2b(preview_url.encode()).hexdigest()
        return d

    @property
    def expires_at(self) -> datetime.datetime:
        """Event ids do not expire."""
        return self.timestamp + datetime.timedelta(
            seconds=CAMERA_CLIP_PREVIEW_EXPIRE_SECS
        )


@dataclass
class RelationUpdate(DataClassDictMixin):
    """Represents a relational update for a resource."""

    type: str
    """Type of relation event 'CREATED', 'UPDATED', 'DELETED'."""

    subject: str
    """Resource that the object is now in relation with."""

    object: str
    """Resource that triggered the event."""


def _BuildEvent(
    event_type: str, event_data: Mapping[str, Any]
) -> ImageEventBase | None:
    if event_type not in EVENT_MAP:
        _LOGGER.debug("Event type %s not found (%s)", event_type, EVENT_MAP.keys())
        return None
    cls = EVENT_MAP[event_type]
    try:
        return cls.from_dict(event_data)  # type: ignore
    except Exception as err:
        traceback.print_exc()
        _LOGGER.debug("Failed to parse event: %s (event_data=%s)", err, event_data)
        raise err


def session_event_image_type(events: Iterable[ImageEventBase]) -> EventImageContentType:
    """Determine the event type to use based on the events in the session."""
    for event in events:
        if event.event_image_type != EventImageType.IMAGE:
            return event.event_image_type
    return EventImageType.IMAGE


class UpdateEventsSerializationStrategy(SerializationStrategy, use_annotations=True):
    """Parser to ignore invalid parent relations."""

    def serialize(self, value: dict[str, ImageEventBase]) -> dict[str, Any]:
        return {k: v.to_dict(by_alias=True) for k, v in value.items()}

    def deserialize(self, value: dict[str, Any]) -> dict[str, ImageEventBase]:
        result = {}
        for event_type, event_data in value.items():
            image_event = _BuildEvent(event_type, event_data)
            if not image_event:
                continue
            result[event_type] = image_event
        return result


@dataclass
class EventMessage(DataClassDictMixin):
    """Event for a change in trait value or device action."""

    timestamp: datetime.datetime
    event_id: str = field(metadata=field_options(alias="eventId"))
    resource_update_name: str | None = field(default=None)
    resource_update_events: dict[str, ImageEventBase] | None = field(default=None)
    resource_update_traits: dict[str, Any] | None = field(default=None)
    event_thread_state: str | None = field(
        metadata=field_options(alias="eventThreadState"), default=None
    )
    relation_update: RelationUpdate | None = field(
        metadata=field_options(alias="relationUpdate"), default=None
    )

    _auth: AbstractAuth = field(init=False, metadata={"serialize": "omit"})

    @classmethod
    def create_event(
        cls, raw_data: dict[str, Any], auth: AbstractAuth
    ) -> "EventMessage":
        """Initialize an EventMessage."""
        event_data = {**raw_data}
        _LOGGER.debug("EventMessage raw_data=%s", event_data)
        if update := event_data.get(RESOURCE_UPDATE):
            if name := update.get(NAME):
                event_data["resource_update_name"] = name
            if events := update.get(EVENTS):
                timestamp = event_data.get(TIMESTAMP)
                for event_updates in events.values():
                    event_updates[TIMESTAMP] = timestamp
                event_data["resource_update_events"] = events
            if traits := update.get(TRAITS):
                event_data["resource_update_traits"] = traits
                event_data["resource_update_traits"][NAME] = update.get(NAME)

        event = cls.from_dict(event_data)
        event._auth = auth
        return event

    @property
    def event_sessions(self) -> dict[str, dict[str, ImageEventBase]] | None:
        events = self.resource_update_events
        if not events:
            return None
        event_sessions: dict[str, dict[str, ImageEventBase]] = {}
        for event_name, event in events.items():
            d = event_sessions.get(event.event_session_id, {})
            d[event_name] = event
            event_sessions[event.event_session_id] = d
        # Build associations between all events
        for event_session_id, event_dict in event_sessions.items():
            event_image_type = session_event_image_type(events.values())
            for event_type, event in event_dict.items():
                event.event_image_type = event_image_type
        return event_sessions

    @property
    def raw_data(self) -> dict[str, Any]:
        """Return raw data for the event."""
        return self.to_dict(by_alias=True)

    def with_events(
        self,
        event_keys: Iterable[str],
        merge_data: dict[str, ImageEventBase] | None = None,
    ) -> EventMessage:
        """Create a new EventMessage minus some existing events by key."""
        new_message = EventMessage.create_event(self.to_dict(by_alias=True), self._auth)
        if not merge_data:
            merge_data = {}
        new_events = {}
        for key in event_keys:
            if (
                new_message.resource_update_events
                and key in new_message.resource_update_events
            ):
                new_events[key] = new_message.resource_update_events[key]
            elif merge_data and key in merge_data:
                new_events[key] = merge_data[key]
        new_message.resource_update_events = new_events
        return new_message

    @property
    def is_thread_ended(self) -> bool:
        """Return true if the message indicates the thread is ended."""
        return self.event_thread_state == EVENT_THREAD_STATE_ENDED

    def __repr__(self) -> str:
        """Debug information."""
        return f"EventMessage{self.to_dict()}"

    class Config(BaseConfig):
        serialization_strategy = {
            dict[str, ImageEventBase]: UpdateEventsSerializationStrategy(),
        }
        code_generation_options = [
            "TO_DICT_ADD_BY_ALIAS_FLAG",
            "TO_DICT_ADD_OMIT_NONE_FLAG",
        ]
