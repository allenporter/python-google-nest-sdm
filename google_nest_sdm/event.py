"""Events from pubsub subscriber."""

from __future__ import annotations

import base64
import binascii
import datetime
import hashlib
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Mapping, Optional

from pydantic import BaseModel, Field, root_validator, validate_arguments, validator

from .auth import AbstractAuth
from .diagnostics import EVENT_DIAGNOSTICS as DIAGNOSTICS
from .exceptions import DecodeException
from .registry import Registry
from .traits import BuildTraits, Command
from .typing import cast_assert

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


class EventProcessingError(Exception):
    """Raised when there was an error handling an event."""


@dataclass
class EventImageContentType:
    """Event image content type."""

    content_type: str

    def __str__(self) -> str:
        """Return a string representation of the event image type."""
        return self.content_type


class EventImageType:
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

    event_session_id: str = Field(alias="eventSessionId")
    event_id: str = Field(alias="eventId")

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


class ImageEventBase(ABC):
    """Base class for all image related event types."""

    event_image_type: EventImageContentType

    def __init__(self, data: Mapping[str, Any], timestamp: datetime.datetime) -> None:
        """Initialize EventBase."""
        self._data = data
        self._timestamp = timestamp
        self._session_events: list[ImageEventBase] = []

    @property
    def event_token(self) -> str:
        """An identifier of this session / event combination."""
        token = EventToken(self.event_session_id, self.event_id)
        return token.encode()

    @property
    @abstractmethod
    def event_type(self) -> str:
        """The type of event."""

    @property
    def event_id(self) -> str:
        """ID associated with the event.

        Can be used with CameraEventImageTrait to download the imaage.
        """
        return cast_assert(str, self._data[EVENT_ID])

    @property
    def event_session_id(self) -> str:
        """ID used to associate separate messages with a single event."""
        return cast_assert(str, self._data[EVENT_SESSION_ID])

    @property
    def timestamp(self) -> datetime.datetime:
        """Timestamp when the event occurred."""
        return self._timestamp

    @property
    def expires_at(self) -> datetime.datetime:
        """Timestamp when the message expires."""
        return self._timestamp + datetime.timedelta(seconds=EVENT_IMAGE_EXPIRE_SECS)

    @property
    def is_expired(self) -> bool:
        """Return true if the event expiration has passed."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        return self.expires_at < now

    @property
    def session_events(self) -> list[ImageEventBase]:
        return self._session_events

    @session_events.setter
    def session_events(self, value: list[ImageEventBase]) -> None:
        self._session_events = value

    @property
    def zones(self) -> list[str]:
        """List of zones for the event."""
        return cast_assert(list, self._data.get(ZONES, []))

    def as_dict(self) -> dict[str, Any]:
        """Return as a dict form that can be serialized."""
        return {
            "event_type": self.event_type,
            "event_data": self._data,
            "timestamp": self._timestamp.isoformat(),
            "event_image_type": str(self.event_image_type),
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> ImageEventBase | None:
        """Parse from a serialized dictionary."""
        event_type = data["event_type"]
        event_data = data["event_data"]
        timestamp = datetime.datetime.fromisoformat(data["timestamp"])
        event = _BuildEvent(event_type, event_data, timestamp)
        if event and "event_image_type" in data:
            event.event_image_type = EventImageType.from_string(
                data["event_image_type"]
            )
        return event

    def __repr__(self) -> str:
        return (
            "<ImageEventBase "
            + str(self.as_dict())
            + " sessions="
            + str(len(self._session_events))
            + ">"
        )


@EVENT_MAP.register()
class CameraMotionEvent(ImageEventBase):
    """Motion has been detected by the camera."""

    NAME = "sdm.devices.events.CameraMotion.Motion"
    event_type = NAME
    event_image_type = EventImageType.IMAGE


@EVENT_MAP.register()
class CameraPersonEvent(ImageEventBase):
    """A person has been detected by the camera."""

    NAME = "sdm.devices.events.CameraPerson.Person"
    event_type = NAME
    event_image_type = EventImageType.IMAGE


@EVENT_MAP.register()
class CameraSoundEvent(ImageEventBase):
    """Sound has been detected by the camera."""

    NAME = "sdm.devices.events.CameraSound.Sound"
    event_type = NAME
    event_image_type = EventImageType.IMAGE


@EVENT_MAP.register()
class DoorbellChimeEvent(ImageEventBase):
    """The doorbell has been pressed."""

    NAME = "sdm.devices.events.DoorbellChime.Chime"
    event_type = NAME
    event_image_type = EventImageType.IMAGE


@EVENT_MAP.register()
class CameraClipPreviewEvent(ImageEventBase):
    """A video clip is available for preview, without extra download."""

    NAME = "sdm.devices.events.CameraClipPreview.ClipPreview"
    event_type = NAME
    event_image_type = EventImageType.CLIP_PREVIEW

    @property
    def event_id(self) -> str:
        """Use a URL hash as the event id.

        Since clip preview events already have a url associated with them,
        we don't have an event id for downloading the image.
        """
        return hashlib.blake2b(self.preview_url.encode()).hexdigest()

    @property
    def expires_at(self) -> datetime.datetime:
        """Event ids do not expire."""
        return self._timestamp + datetime.timedelta(
            seconds=CAMERA_CLIP_PREVIEW_EXPIRE_SECS
        )

    @property
    def preview_url(self) -> str:
        """A url 10 second frame video file in mp4 format."""
        return cast_assert(str, self._data[PREVIEW_URL])


class EventTrait(ABC):
    """Parent class for traits related to handling events."""

    def __init__(self) -> None:
        """Initialize an EventTrait."""
        self._last_event: Optional[ImageEventBase] = None

    @property
    def last_event(self) -> Optional[ImageEventBase]:
        """Last received event."""
        return self._last_event

    @property
    def active_event(self) -> Optional[ImageEventBase]:
        """Any current active events."""
        if not self._last_event:
            return None
        if self._last_event.is_expired:
            return None
        return self._last_event

    def handle_event(self, event: ImageEventBase) -> None:
        """Receive an event message."""
        self._last_event = event


class RelationUpdate(BaseModel):
    """Represents a relational update for a resource."""

    type: str
    """Type of relation event 'CREATED', 'UPDATED', 'DELETED'."""

    subject: str
    """Resource that the object is now in relation with."""

    object: str
    """Resource that triggered the event."""


def _BuildEvents(
    events: Mapping[str, Any],
    timestamp: datetime.datetime,
) -> Dict[str, ImageEventBase]:
    """Build a trait map out of a response dict."""
    result = {}
    for event_type, event_data in events.items():
        image_event = _BuildEvent(event_type, event_data, timestamp)
        if not image_event:
            continue
        result[event_type] = image_event
    return result


def _BuildEvent(
    event_type: str, event_data: Mapping[str, Any], timestamp: datetime.datetime
) -> ImageEventBase | None:
    if event_type not in EVENT_MAP:
        return None
    cls = EVENT_MAP[event_type]
    return cls(event_data, timestamp)  # type: ignore


def session_event_image_type(events: Iterable[ImageEventBase]) -> EventImageContentType:
    """Determine the event type to use based on the events in the session."""
    for event in events:
        if event.event_image_type != EventImageType.IMAGE:
            return event.event_image_type
    return EventImageType.IMAGE


@validate_arguments
def _validate_datetime(value: datetime.datetime) -> datetime.datetime:
    return value


class EventMessage(BaseModel):
    """Event for a change in trait value or device action."""

    event_id: str = Field(alias="eventId")
    timestamp: datetime.datetime
    resource_update_name: Optional[str]
    resource_update_events: Optional[dict[str, ImageEventBase]]
    resource_update_traits: Optional[dict[str, Any]]
    event_thread_state: Optional[str] = Field(alias="eventThreadState")
    relation_update: Optional[RelationUpdate] = Field(alias="relationUpdate")

    def __init__(self, raw_data: Mapping[str, Any], auth: AbstractAuth) -> None:
        """Initialize an EventMessage."""
        _LOGGER.debug("EventMessage raw_data=%s", raw_data)
        super().__init__(**raw_data, auth=auth)
        self._auth = auth

    @root_validator(pre=True)
    def _parse_resource_update(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse resource updates."""
        if update := values.get(RESOURCE_UPDATE):
            if name := update.get(NAME):
                values["resource_update_name"] = name
            if events := update.get(EVENTS):
                values["resource_update_events"] = events
                values["resource_update_events"][TIMESTAMP] = values.get(TIMESTAMP)
            if traits := update.get(TRAITS):
                values["resource_update_traits"] = traits
                values["resource_update_traits"][NAME] = update.get(NAME)
                values["resource_update_traits"]["auth"] = values["auth"]
        return values

    @validator("resource_update_events", pre=True)
    def _parse_resource_update_events(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse resource updates for events."""
        return _BuildEvents(values, _validate_datetime(values[TIMESTAMP]))

    @validator("resource_update_traits", pre=True)
    def _parse_resource_update_traits(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse resource updates to traits."""
        cmd = Command(values[NAME], values["auth"], DIAGNOSTICS)
        return BuildTraits(values, cmd)

    @property
    def event_sessions(self) -> Optional[dict[str, dict[str, ImageEventBase]]]:
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
                event.session_events = list(event_dict.values())
                event.event_image_type = event_image_type
        return event_sessions

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Return raw data for the event."""
        return self.dict()

    def with_events(
        self,
        event_keys: Iterable[str],
        merge_data: dict[str, ImageEventBase] | None = None,
    ) -> EventMessage:
        """Create a new EventMessage minus some existing events by key."""
        new_message = self.copy()
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
        return f"EventMessage{self.raw_data}"

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
