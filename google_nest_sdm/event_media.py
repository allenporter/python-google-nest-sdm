"""Libraries related to providing a device level interface for event related media."""

from __future__ import annotations

import datetime
import logging
from abc import ABC
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any, Awaitable, Callable, Dict, Optional

from .camera_traits import EventImageGenerator, EventImageType
from .event import (
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    DoorbellChimeEvent,
    EventMessage,
    ImageEventBase,
    session_event_image_type,
)
from .exceptions import GoogleNestException

_LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_SIZE = 2

# Events are collapsed in the order shown here
VISIBLE_EVENTS = [
    DoorbellChimeEvent.NAME,
    CameraPersonEvent.NAME,
    CameraMotionEvent.NAME,
    CameraSoundEvent.NAME,
]


class CachePolicy:
    """Policy for how many local objects to cache in memory."""

    def __init__(self, event_cache_size: int = DEFAULT_CACHE_SIZE, fetch: bool = False):
        self._event_cache_size = event_cache_size
        self._fetch = fetch
        self._store: EventMediaStore = InMemoryEventMediaStore()

    @property
    def event_cache_size(self) -> int:
        """Number of events to keep in memory per device."""
        return self._event_cache_size

    @event_cache_size.setter
    def event_cache_size(self, value: int) -> None:
        """Set the number of events to keep in memory per device."""
        self._event_cache_size = value

    @property
    def fetch(self) -> bool:
        """Return true if event media should be pre-fetched."""
        return self._fetch

    @fetch.setter
    def fetch(self, value: bool) -> None:
        """Update the value for whether event media should be pre-fetched."""
        self._fetch = value

    @property
    def store(self) -> EventMediaStore:
        """Return the EventMediaStore object."""
        return self._store

    @store.setter
    def store(self, value: EventMediaStore) -> None:
        """Update the EventMediaStore."""
        self._store = value


class Media:
    """Represents media related to an event."""

    def __init__(self, contents: bytes, event_image_type: EventImageType) -> None:
        """Initialize Media."""
        self._contents = contents
        self._event_image_type = event_image_type

    @property
    def contents(self) -> bytes:
        """Media content."""
        return self._contents

    @property
    def event_image_type(self) -> EventImageType:
        """Content event image type of the media."""
        return self._event_image_type


class EventMedia:
    """Represents an event and its associated media."""

    def __init__(
        self,
        event_session_id: str,
        event_type: str,
        event_timestamp: datetime.datetime,
        media: Media,
    ) -> None:
        self._event_session_id = event_session_id
        self._event_type = event_type
        self._event_timestamp = event_timestamp
        self._media = media

    @property
    def event_session_id(self) -> str:
        """Return the event id."""
        return self._event_session_id

    @property
    def event_type(self) -> str:
        """Return the event type."""
        return self._event_type

    @property
    def event_timestamp(self) -> datetime.datetime:
        """Return timestamp that the event ocurred."""
        return self._event_timestamp

    @property
    def media(self) -> Media:
        return self._media


class EventMediaStore(ABC):
    """Interface for external storage."""

    async def async_load(self) -> dict | None:
        """Load data."""

    async def async_save(self, data: dict | None) -> None:
        """Save data."""

    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename to use for the device and event."""

    async def async_load_media(self, media_key: str) -> bytes | None:
        """Load media content."""

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Write media content."""

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""


class InMemoryEventMediaStore(EventMediaStore):
    """An in memory implementation of EventMediaStore."""

    def __init__(self) -> None:
        self._data: dict | None = None
        self._media: dict[str, bytes] = {}

    async def async_load(self) -> dict | None:
        """Load data."""
        return self._data

    async def async_save(self, data: dict | None) -> None:
        """Save data."""
        self._data = data

    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the media key to use for the device and event."""
        suffix = "jpg" if event.event_image_type == EventImageType.IMAGE else "mp4"
        return f"{device_id}_{event.timestamp}_{event.event_session_id}.{suffix}"

    async def async_load_media(self, media_key: str) -> bytes | None:
        """Load media content."""
        return self._media.get(media_key)

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Remove media content."""
        self._media[media_key] = content

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""
        if media_key in self._media:
            del self._media[media_key]


class EventMediaModelItem:
    """Structure used to persist the event in EventMediaStore."""

    def __init__(
        self,
        event_session_id: str,
        events: dict[str, ImageEventBase],
        media_key: str | None = None,
    ) -> None:
        """Initialize EventMediaModelItem."""
        self._event_session_id = event_session_id
        self._events = events
        self._media_key = media_key

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EventMediaModelItem:
        """Read from serialized dictionary."""
        events: dict[str, ImageEventBase] = {}
        input_events = data.get("events", {})
        for (event_type, event_data) in input_events.items():
            if not (event := ImageEventBase.from_dict(event_data)):
                continue
            events[event_type] = event
        # Link events to other events in the session
        event_image_type = session_event_image_type(events.values())
        for event in events.values():
            event.session_events = list(events.values())
            event.event_image_type = event_image_type
        return EventMediaModelItem(
            data["event_session_id"], events, data.get("media_key")
        )

    @property
    def event_session_id(self) -> str:
        return self._event_session_id

    @property
    def visible_event(self) -> ImageEventBase | None:
        """Get the primary visible event for this item."""
        for event_type in VISIBLE_EVENTS:
            if event := self._events.get(event_type):
                return event
        return None

    @property
    def events(self) -> dict[str, ImageEventBase]:
        """Return all associated events with this record."""
        return self._events

    @property
    def media_key(self) -> str | None:
        return self._media_key

    @media_key.setter
    def media_key(self, value: str) -> None:
        """Update the media_key."""
        self._media_key = value

    def get_media(self, content: bytes) -> Media:
        assert self.visible_event
        return Media(content, self.visible_event.event_image_type)

    def get_event_media(self, content: bytes) -> EventMedia:
        assert self.visible_event
        return EventMedia(
            self.visible_event.event_session_id,
            self.visible_event.event_type,
            self.visible_event.timestamp,
            self.get_media(content),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a EventMediaModelItem as a serializable dict."""
        result: dict[str, Any] = {
            "event_session_id": self._event_session_id,
            "events": dict((k, v.as_dict()) for k, v in self._events.items()),
        }
        if self._media_key:
            result["media_key"] = self._media_key
        return result

    def __repr__(self) -> str:
        return (
            "<EventMediaModelItem events="
            + str(self._events)
            + " media_key="
            + str(self._media_key)
            + ">"
        )


class EventMediaManager:
    """Responsible for handling recent events and fetching associated media."""

    def __init__(
        self, device_id: str, event_trait_map: Dict[str, EventImageGenerator]
    ) -> None:
        """Initialize DeviceEventMediaManager."""
        self._device_id = device_id
        self._event_trait_map = event_trait_map
        self._cache_policy = CachePolicy()
        self._callback: Callable[[EventMessage], Awaitable[None]] | None = None

    @property
    def cache_policy(self) -> CachePolicy:
        """Return the current CachePolicy."""
        return self._cache_policy

    @cache_policy.setter
    def cache_policy(self, value: CachePolicy) -> None:
        """Update the CachePolicy."""
        self._cache_policy = value

    async def _async_load(self) -> OrderedDict[str, EventMediaModelItem]:
        """Load the device specific data from the store."""
        store_data = await self._cache_policy.store.async_load()
        event_data: OrderedDict[str, EventMediaModelItem] = OrderedDict()
        if store_data:
            device_data = store_data.get(self._device_id, [])
            for item_data in device_data:
                item = EventMediaModelItem.from_dict(item_data)
                event_data[item.event_session_id] = item
        return event_data

    async def _async_update(self, event_data: dict[str, EventMediaModelItem]) -> None:
        """Save the device specific model to the store."""
        # Event order is preserved so popping from the oldest entry works
        device_data: list[dict[str, Any]] = []
        for item in event_data.values():
            device_data.append(item.as_dict())

        # Read data from the store and update information for this device
        store_data = await self._cache_policy.store.async_load()
        if not store_data:
            store_data = {}
        store_data[self._device_id] = device_data
        await self._cache_policy._store.async_save(store_data)

    async def get_media(
        self,
        event_session_id: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> Optional[EventMedia]:
        """Get media for the specified event.

        Note that the height and width hints are best effort and may not be
        honored (e.g. if image is already cached).
        """
        event_data = await self._async_load()
        if not (item := event_data.get(event_session_id)):
            return None
        event = item.visible_event
        if not event:
            _LOGGER.debug(
                "Skipping fetch; No visible event; event_session_id=%s",
                event_session_id,
            )
            return None
        _LOGGER.debug("Fetching media for event_session_id=%s", event_session_id)
        if item.media_key:
            media_key = item.media_key
        else:
            media_key = self._cache_policy._store.get_media_key(self._device_id, event)

        contents = await self._cache_policy._store.async_load_media(media_key)
        if contents is None:
            if event.is_expired:
                _LOGGER.debug(
                    "Skipping fetch; Event expired; event_session_id=%s",
                    event_session_id,
                )
                return None
            if not (generator := self._event_trait_map.get(event.event_type)):
                return None
            event_image = await generator.generate_event_image(event)
            if not event_image:
                return None
            contents = await event_image.contents(width=width, height=height)
            await self._cache_policy._store.async_save_media(media_key, contents)

        if not item.media_key:
            item.media_key = media_key
            await self._async_update(event_data)

        return item.get_event_media(contents)

    async def async_events(self) -> Iterable[ImageEventBase]:
        """Return revent events."""

        def _filter(x: EventMediaModelItem) -> bool:
            """Return events already fetched or that could be fetched."""
            return x.visible_event is not None and (
                x.media_key is not None or not x.visible_event.is_expired
            )

        event_data = await self._async_load()
        result: list[EventMediaModelItem] = list(filter(_filter, event_data.values()))

        def _get_event(x: EventMediaModelItem) -> ImageEventBase:
            assert x.visible_event
            return x.visible_event

        event_result = list(map(_get_event, result))
        event_result.sort(key=lambda x: x.timestamp, reverse=True)
        return event_result

    def set_update_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> None:
        """Register a callback invoked when new messages are received."""
        self._callback = target

    async def async_handle_events(self, event_message: EventMessage) -> None:
        """Handle the EventMessage."""
        event_sessions: dict[
            str, dict[str, ImageEventBase]
        ] | None = event_message.event_sessions
        if not event_sessions:
            return
        _LOGGER.debug("Event Update %s", event_sessions.keys())

        # Notify traits to cache most recent event
        pairs = list(event_sessions.items())
        for event_session_id, event_dict in pairs:
            supported = False
            for event_name, event in event_dict.items():
                if not (trait := self._event_trait_map.get(event_name)):
                    continue
                supported = True
                trait.handle_event(event)

            # Skip any entirely unsupported events
            if not supported:
                del event_sessions[event_session_id]

        # Update interal event media representation. Events are only published
        # to downstream subscribers the first time they are seen to avoid
        # firing on updated event threads multiple times.
        suppress = False
        for event_session_id, event_dict in event_sessions.items():

            # Track all related events together with the same session
            event_data = await self._async_load()

            if model_item := event_data.get(event_session_id):
                # Update the existing event session with new/updated events
                model_item.events.update(event_dict)
                suppress = True
            else:
                # A new event session
                model_item = EventMediaModelItem(event_session_id, event_dict)
                event_data[event_session_id] = model_item

                if len(event_data) > self._cache_policy.event_cache_size:
                    (key, old_item) = event_data.popitem(last=False)
                    if old_item.media_key:
                        await self._cache_policy.store.async_remove_media(
                            old_item.media_key
                        )

            await self._async_update(event_data)

            # Prefetch media, otherwise we may
            if self._cache_policy.fetch:
                try:
                    await self.get_media(event_session_id)
                except GoogleNestException as err:
                    _LOGGER.warning(
                        "Failure when pre-fetching event '%s': %s",
                        event.event_id,
                        str(err),
                    )

        # Notify any listeners about the arrival of a new event
        if self._callback and not suppress:
            await self._callback(event_message)

    def active_events(self, event_types: list) -> Dict[str, ImageEventBase]:
        """Return any active events for the specified trait names."""
        active_events = {}
        for event_type in event_types:
            trait = self._event_trait_map.get(event_type)
            if not trait or not trait.active_event:
                continue
            active_events[event_type] = trait.active_event
        return active_events

    @property
    def active_event_trait(self) -> Optional[EventImageGenerator]:
        """Return trait with the most recently received active event."""
        trait_to_return: EventImageGenerator | None = None
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
