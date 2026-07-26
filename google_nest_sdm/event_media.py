"""Libraries related to providing a device level interface for event related media.

An `EventMediaManager` is associated with a single device and manages the
state for events and the lifecycle of media for those events. The manager is
invoked by the subscriber when new events arrive and it handles any fetching
related to the media, as well as transcoding video clips of needed. The
`CachePolicy` settings determine lifecycle options such as how many events
to keep around in the underlying store.
"""

from __future__ import annotations

import asyncio
import datetime
import itertools
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, cast

from mashumaro import DataClassDictMixin
from mashumaro.types import SerializationStrategy
from mashumaro.config import BaseConfig

from .camera_traits import (
    CameraClipPreviewTrait,
    CameraEventImageTrait,
    EventImageContentType,
)
from .diagnostics import EVENT_MEDIA_DIAGNOSTICS as DIAGNOSTICS
from .diagnostics import Diagnostics
from .event import (
    CameraClipPreviewEvent,
    EventImageType,
    EventMessage,
    EventToken,
    ImageEventBase,
    session_event_image_type,
    CameraPersonEvent,
    CameraMotionEvent,
    CameraSoundEvent,
    DoorbellChimeEvent,
)
from .exceptions import GoogleNestException, TranscodeException
from .transcoder import Transcoder

__all__ = [
    "EventMediaManager",
    "ImageSession",
    "ClipPreviewSession",
    "Media",
    "EventMediaStore",
    "CachePolicy",
]

_LOGGER = logging.getLogger(__name__)

# Should be large enough for processing, but not too large to be a size issue
SNAPSHOT_WIDTH_PX = 1600

DEFAULT_CACHE_SIZE = 2

# Events are collapsed in the order shown here
VISIBLE_EVENTS = [
    DoorbellChimeEvent.NAME,
    CameraPersonEvent.NAME,
    CameraMotionEvent.NAME,
    CameraSoundEvent.NAME,
]

# Percentage of items to delete when bulk purging from the cache
EXPIRE_CACHE_BATCH_SIZE = 0.05


@dataclass
class Media:
    """Represents media related to an event."""

    contents: bytes
    """Media content."""

    event_image_type: EventImageContentType
    """Content event image type of the media."""

    @property
    def content_type(self) -> str:
        """Content type of the media."""
        return self.event_image_type.content_type


@dataclass
class ImageSession:
    """An object that holds an image based event."""

    event_token: str
    """A token that can be used to fetch the media for the event."""

    timestamp: datetime.datetime
    """Timestamp when the event happened."""

    event_type: str
    """A label for the type of event."""


@dataclass
class ClipPreviewSession:
    """An object that holds a clip based event."""

    event_token: str
    """A token that can be used to fetch the media for the event."""

    timestamp: datetime.datetime
    """Timestamp when the event happened."""

    event_types: list[str]
    """A label for the type of event."""


class EventMediaStore(ABC):
    """Interface for external storage."""

    @abstractmethod
    async def async_load(self) -> dict | None:
        """Load data."""

    @abstractmethod
    async def async_save(self, data: dict) -> None:
        """Save data."""

    @abstractmethod
    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename to use for the device and event."""

    def get_image_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename for image media."""
        return self.get_media_key(device_id, event)

    def get_clip_preview_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the filename for clip preview media."""
        return self.get_media_key(device_id, event)

    def get_clip_preview_thumbnail_media_key(
        self, device_id: str, event: ImageEventBase
    ) -> str | None:
        """Return the filename for thumbnail for clip preview media."""
        return None

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

    async def async_save(self, data: dict) -> None:
        """Save data."""
        self._data = data

    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the media key to use for the device and event."""
        suffix = "jpg" if event.event_image_type == EventImageType.IMAGE else "mp4"
        return f"{device_id}_{event.timestamp}_{event.event_session_id}.{suffix}"

    def get_image_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the media key to use for the device and event."""
        return (
            f"{device_id}_{event.timestamp}_{event.event_session_id}_"
            f"{event.event_id}.jpg"
        )

    def get_clip_preview_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the media key to use for the device and event."""
        return f"{device_id}_{event.timestamp}_{event.event_session_id}.mp4"

    def get_clip_preview_thumbnail_media_key(
        self, device_id: str, event: ImageEventBase
    ) -> str | None:
        """Return the media key to use for the clip preview thumbnail."""
        return f"{device_id}_{event.timestamp}_{event.event_session_id}_thumb.jpg"

    async def async_load_media(self, media_key: str) -> bytes | None:
        """Load media content."""
        with DIAGNOSTICS.timer("load_media"):
            return self._media.get(media_key)

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Remove media content."""
        with DIAGNOSTICS.timer("save_media"):
            self._media[media_key] = content

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""
        with DIAGNOSTICS.timer("remove_media"):
            if media_key in self._media:
                del self._media[media_key]


@dataclass
class CachePolicy:
    """Policy for how many local objects to cache in memory."""

    event_cache_size: int = DEFAULT_CACHE_SIZE
    """Number of events to keep in memory per device."""

    fetch: bool = False
    """Determine if event media should be pre-fetched."""

    store: EventMediaStore = field(default_factory=InMemoryEventMediaStore)
    """The EventMediaStore object for storing media content."""

    transcoder: Transcoder | None = None
    """The transcoder for encoding media."""

    @property
    def event_cache_expire_count(self) -> int:
        """Number of events to keep in memory per device."""
        return max(int(self.event_cache_size * EXPIRE_CACHE_BATCH_SIZE), 1)


class ImageEventSerializationStrategy(SerializationStrategy):
    """Serialization strategy for ImageEventBase."""

    def serialize(self, value: dict[str, ImageEventBase]) -> dict[str, Any]:
        """Serialize ImageEventBase."""
        return dict((k, v.as_dict()) for k, v in value.items())

    def deserialize(self, value: dict[str, Any]) -> dict[str, ImageEventBase]:
        """Deserialize ImageEventBase."""
        events: dict[str, ImageEventBase] = {}
        for event_type, event_data in value.items():
            # Propagate timestamps to child nodes
            if (timestamp := event_data.get("timestamp")) and (
                data := event_data.get("event_data")
            ):
                data["timestamp"] = timestamp
            if event := ImageEventBase.parse_event_dict(event_data):
                events[event_type] = event

        # Link events to other events in the session
        event_image_type = session_event_image_type(events.values())
        for event in events.values():
            event.event_image_type = event_image_type
        return events


@dataclass
class EventMediaModelItem(DataClassDictMixin):
    """Structure used to persist the event in EventMediaStore."""

    event_session_id: str
    events: dict[str, ImageEventBase] = field(default_factory=dict)
    media_key: str | None = field(default=None)
    event_media_keys: dict[str, str] = field(default_factory=dict)
    thumbnail_media_key: str | None = field(default=None)
    pending_event_keys: set[str] = field(default_factory=set)

    @property
    def visible_event(self) -> ImageEventBase | None:
        """Get the primary visible event for this item."""
        for event_type in VISIBLE_EVENTS:
            if event := self.events.get(event_type):
                return event
        return None

    def merge_events(self, new_events: dict[str, ImageEventBase]) -> None:
        """Merge new incoming events with the existing set."""
        new_keys = new_events.keys() - self.events.keys()
        self.events.update(new_events)
        self.pending_event_keys |= new_keys

    @property
    def pending_events(self) -> dict[str, ImageEventBase]:
        """Return all associated events with this record."""
        return {
            key: value
            for key, value in self.events.items()
            if key in self.pending_event_keys
        }

    def notified(self, event_keys: Iterable[str]) -> None:
        """Mark the specified events as notified."""
        self.pending_event_keys = self.pending_event_keys - set(event_keys)

    def media_key_for_token(self, token: EventToken) -> str | None:
        """Return media key for the specified event token."""
        if token.event_id:
            if token.event_id in self.event_media_keys:
                return self.event_media_keys[token.event_id]
            # Fallback to legacy single event per session
        return self.media_key

    @property
    def any_media_key(self) -> str | None:
        """Return any media item for compatibility with legacy APIs."""
        if self.media_key:
            return self.media_key
        if self.event_media_keys.values():
            return next(iter(self.event_media_keys.values()))
        return None

    @property
    def all_media_keys(self) -> list[str]:
        """Return all media items for purging media keys."""
        keys = [self.media_key, self.thumbnail_media_key] + list(
            self.event_media_keys.values()
        )
        return [key for key in keys if key is not None]

    class Config(BaseConfig):
        serialization_strategy = {
            dict[str, ImageEventBase]: ImageEventSerializationStrategy(),
        }


class EventMediaManager:
    """Responsible for handling recent events and fetching associated media."""

    def __init__(
        self,
        device_id: str,
        traits: dict[str, Any],
        event_traits: set[str],
        diagnostics: Diagnostics,
    ) -> None:
        """Initialize DeviceEventMediaManager."""
        self._device_id = device_id
        self._traits = traits
        self._event_traits = event_traits
        self._cache_policy = CachePolicy()
        self._callback: Callable[[EventMessage], Awaitable[None]] | None = None
        self._support_fetch = (
            CameraClipPreviewTrait.NAME in traits
            or CameraEventImageTrait.NAME in traits
        )
        self._diagnostics = diagnostics
        self._lock: asyncio.Lock | None = None

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
                try:
                    item = EventMediaModelItem.from_dict(item_data)
                except Exception as err:
                    _LOGGER.debug("Failed to parse event item: %s", str(err))
                    raise err
                event_data[item.event_session_id] = item
        return event_data

    async def _async_update(self, event_data: dict[str, EventMediaModelItem]) -> None:
        """Save the device specific model to the store."""
        # Event order is preserved so popping from the oldest entry works
        device_data: list[dict[str, Any]] = []
        for item in event_data.values():
            device_data.append(item.to_dict())

        # Read data from the store and update information for this device
        store_data = await self._cache_policy.store.async_load()
        if not store_data:
            store_data = {}
        store_data[self._device_id] = device_data
        await self._cache_policy.store.async_save(store_data)

    async def _async_load_item(
        self, event_session_id: str
    ) -> EventMediaModelItem | None:
        """Load the specific item from the store."""
        event_data = await self._async_load()
        return event_data.get(event_session_id)

    async def _async_update_item(self, item: EventMediaModelItem) -> None:
        """Update the specific item in the store."""
        if not self._lock:
            self._lock = asyncio.Lock()
        async with self._lock:
            event_data = await self._async_load()
            event_data[item.event_session_id] = item
            await self._async_update(event_data)

    async def _expire_cache(self) -> None:
        """Garbage collect any items from the cache."""
        if not self._lock:
            self._lock = asyncio.Lock()
        async with self._lock:
            event_data = await self._async_load()
            _LOGGER.debug("Checking cache size %s", len(event_data))
            if len(event_data) <= self._cache_policy.event_cache_size:
                return
            _LOGGER.debug(
                "Expiring cache %s", self._cache_policy.event_cache_expire_count
            )
            # Bulk pop items
            for i in range(0, self._cache_policy.event_cache_expire_count):
                (key, old_item) = event_data.popitem(last=False)
                _LOGGER.debug(
                    "Expiring media %s (%s)",
                    old_item.all_media_keys,
                    old_item.event_session_id,
                )
                for media_key in old_item.all_media_keys:
                    await self._cache_policy.store.async_remove_media(media_key)
            await self._async_update(event_data)

    async def _fetch_media(self, item: EventMediaModelItem) -> None:
        """Fetch media from the server in response to a pubsub event."""
        store = self._cache_policy.store
        if CameraClipPreviewTrait.NAME in self._traits:
            self._diagnostics.increment("fetch_clip")
            if (
                item.media_key
                or not item.visible_event
                or not (
                    clip_event := cast(
                        CameraClipPreviewEvent,
                        item.events.get(CameraClipPreviewEvent.NAME),
                    )
                )
                or clip_event.is_expired
            ):
                self._diagnostics.increment("fetch_clip.skip")
                return
            clip_preview_trait: CameraClipPreviewTrait = self._traits[
                CameraClipPreviewTrait.NAME
            ]
            event_image = await clip_preview_trait.generate_event_image(
                clip_event.preview_url
            )
            if event_image:
                content = await event_image.contents()
                # Caller will persist the media key assignment
                media_key = store.get_clip_preview_media_key(
                    self._device_id, item.visible_event
                )
                item.media_key = media_key
                _LOGGER.debug("Saving media %s (%s)", media_key, item.event_session_id)
                self._diagnostics.increment("fetch_clip.save")
                await store.async_save_media(media_key, content)
                return

        if CameraEventImageTrait.NAME not in self._traits:
            return
        self._diagnostics.increment("fetch_image")

        event_image_trait: CameraEventImageTrait = self._traits[
            CameraEventImageTrait.NAME
        ]
        for event in item.events.values():
            if event.event_id in item.event_media_keys or event.is_expired:
                self._diagnostics.increment("fetch_image.skip")
                continue
            event_image = await event_image_trait.generate_image(event.event_id)
            content = await event_image.contents(width=SNAPSHOT_WIDTH_PX)

            # Caller will persist the media key assignment
            media_key = store.get_image_media_key(self._device_id, event)
            item.event_media_keys[event.event_id] = media_key
            _LOGGER.debug("Saving media %s (%s)", media_key, item.event_session_id)
            self._diagnostics.increment("fetch_image.save")
            await store.async_save_media(media_key, content)

    async def get_media_from_token(self, event_token: str) -> Media | None:
        """Get media based on the event token."""
        token = EventToken.decode(event_token)
        if not (item := await self._async_load_item(token.event_session_id)):
            self._diagnostics.increment("get_media.invalid_event")
            _LOGGER.debug(
                "No event information found for event id: %s", token.event_session_id
            )
            return None
        media_key = item.media_key_for_token(token)
        if not media_key:
            self._diagnostics.increment("get_media.no_media")
            _LOGGER.debug("No persisted media for event id %s", token)
            return None
        contents = await self._cache_policy.store.async_load_media(media_key)
        if not contents:
            self._diagnostics.increment("get_media.empty")
            _LOGGER.debug(
                "Unable to load persisted media for event id: (%s, %s, %s)",
                token.event_session_id,
                token.event_id,
                item.media_key,
            )
            return None
        assert item.visible_event
        self._diagnostics.increment("get_media.success")
        return Media(contents, item.visible_event.event_image_type)

    async def get_clip_thumbnail_from_token(self, event_token: str) -> Media | None:
        """Get a thumbnail from the event token."""
        self._diagnostics.increment("get_clip")
        token = EventToken.decode(event_token)
        if (
            not (item := await self._async_load_item(token.event_session_id))
            or not item.visible_event
        ):
            self._diagnostics.increment("get_clip.invalid_event")
            _LOGGER.debug(
                "No event information found for event id: %s", token.event_session_id
            )
            return None

        if item.thumbnail_media_key:
            # Load cached thumbnail
            contents = await self._cache_policy.store.async_load_media(
                item.thumbnail_media_key
            )
            if contents:
                self._diagnostics.increment("get_clip.cached")
                return Media(contents, EventImageType.IMAGE_PREVIEW)
            _LOGGER.debug(
                "Thumbnail %s does not exist; transcoding", item.thumbnail_media_key
            )

        # Check for existing primary media
        media_key = item.media_key_for_token(token)
        if not media_key:
            self._diagnostics.increment("get_clip.no_media")
            _LOGGER.debug("No persisted media for event id %s", token)
            return None

        thumbnail_media_key = (
            self._cache_policy.store.get_clip_preview_thumbnail_media_key(
                self._device_id, item.visible_event
            )
        )
        if not self._cache_policy.transcoder or not thumbnail_media_key:
            self._diagnostics.increment("get_clip.no_transcoding")
            _LOGGER.debug("Clip transcoding disabled")
            return None

        try:
            await self._cache_policy.transcoder.transcode_clip(
                media_key, thumbnail_media_key
            )
        except TranscodeException as err:
            self._diagnostics.increment("get_clip.transcode_error")
            _LOGGER.debug("Failure to transcode clip thumbnail: %s", str(err))
            return None

        contents = await self._cache_policy.store.async_load_media(thumbnail_media_key)
        if not contents:
            self._diagnostics.increment("get_clip.load_error")
            _LOGGER.debug(
                "Failed to load transcoded clip: %s", item.thumbnail_media_key
            )
            return None

        item.thumbnail_media_key = thumbnail_media_key
        await self._async_update_item(item)

        self._diagnostics.increment("get_clip.success")
        return Media(contents, EventImageType.IMAGE_PREVIEW)

    async def async_image_sessions(self) -> list[ImageSession]:
        """Return revent events."""
        self._diagnostics.increment("load_image_sessions")

        def _get_events(x: EventMediaModelItem) -> list[ImageEventBase]:
            # Only return events that have successful media fetches
            return [
                y
                for y in x.events.values()
                if x.media_key or y.event_id in x.event_media_keys
            ]

        result = await self._items_with_media()
        events_list = list(map(_get_events, result))
        events: Iterable[ImageEventBase] = itertools.chain(*events_list)

        def _get_session(x: ImageEventBase) -> ImageSession:
            return ImageSession(x.event_token, x.timestamp, x.event_type)

        event_result = list(map(_get_session, events))
        event_result.sort(key=lambda x: x.timestamp, reverse=True)
        return event_result

    async def async_clip_preview_sessions(self) -> list[ClipPreviewSession]:
        """Return revent events for a device that supports clips."""
        self._diagnostics.increment("load_clip_previews")

        def _event_visible(x: ImageEventBase) -> bool:
            return x.event_type in VISIBLE_EVENTS

        def _get_event_session(x: EventMediaModelItem) -> ClipPreviewSession | None:
            assert x.visible_event
            events = list(filter(_event_visible, x.events.values()))
            events.sort(key=lambda x: x.timestamp)
            if not events:
                _LOGGER.debug("Partial event in storage")
                return None
            visible_event = events[0]
            return ClipPreviewSession(
                visible_event.event_token,
                visible_event.timestamp,
                [y.event_type for y in events],
            )

        result = await self._items_with_media()
        clips: Iterable[ClipPreviewSession | None] = iter(
            map(_get_event_session, result)
        )
        valid_clips: list[ClipPreviewSession] = [x for x in clips if x is not None]
        valid_clips.sort(key=lambda x: x.timestamp, reverse=True)
        return valid_clips

    async def _items_with_media(self) -> list[EventMediaModelItem]:
        """Return items in the model that have media for serving."""

        def _filter(x: EventMediaModelItem) -> bool:
            """Return events already fetched or that could be fetched."""
            if x.media_key or x.event_media_keys:
                return True
            return False

        event_data = await self._async_load()
        return list(filter(_filter, event_data.values()))

    def set_update_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> None:
        """Register a callback invoked when new messages are received."""
        self._callback = target

    async def async_handle_events(self, event_message: EventMessage) -> None:
        """Handle the EventMessage."""
        self._diagnostics.increment("event")
        event_sessions: dict[str, dict[str, ImageEventBase]] | None = (
            event_message.event_sessions
        )
        if not event_sessions:
            return
        _LOGGER.debug("Event Update %s", event_sessions.keys())
        recv_latency_ms = int((time.time() - event_message.timestamp.timestamp()) * 100)

        # Notify traits to cache most recent event
        pairs = list(event_sessions.items())
        for event_session_id, event_dict in pairs:
            supported = False
            for event_name, event in event_dict.items():
                if not event.is_expired:
                    self._diagnostics.elapsed(event_name, recv_latency_ms)
                else:
                    self._diagnostics.elapsed(f"{event_name}_expired", recv_latency_ms)
                if event_name not in self._event_traits:
                    self._diagnostics.increment(f"event.unsupported.{event_name}")
                    _LOGGER.debug("Unsupported event trait: %s", event_name)
                    continue
                supported = True

            # Skip any entirely unsupported events
            if not supported:
                del event_sessions[event_session_id]

        model_items = []
        failure = False
        for event_session_id, event_dict in event_sessions.items():
            # Track all related events together with the same session
            if model_item := await self._async_load_item(event_session_id):
                self._diagnostics.increment("event.update")
                model_item.merge_events(event_dict)
            else:
                self._diagnostics.increment("event.new")
                # A new event session
                model_item = EventMediaModelItem(
                    event_session_id=event_session_id,
                    events=event_dict,
                    media_key=None,
                    event_media_keys={},
                    thumbnail_media_key=None,
                    pending_event_keys=set(event_dict.keys()),
                )
            model_items.append(model_item)

            if self._support_fetch and self._cache_policy.fetch:
                self._diagnostics.increment("event.fetch")
                try:
                    await self._fetch_media(model_item)
                except GoogleNestException as err:
                    self._diagnostics.increment("event.fetch_error")
                    failure = True
                    _LOGGER.warning(
                        "Failure when pre-fetching event '%s': %s",
                        event.event_session_id,
                        str(err),
                    )

        # Send notifications for any undelivered events that have media.
        pending_events: dict[str, ImageEventBase] = {}
        for model_item in model_items:
            if (
                model_item.any_media_key is None
                and self._support_fetch
                and self._cache_policy.fetch
                and not event_message.is_thread_ended
                and not failure
            ):
                continue
            pending_events.update(model_item.pending_events)

        if pending_events:
            _LOGGER.debug("Message contains notifiable events: %s", pending_events)
            event_message = event_message.with_events(
                pending_events.keys(), pending_events
            )
            if self._callback:
                self._diagnostics.increment("event.notify")
                await self._callback(event_message)
        else:
            _LOGGER.debug("Message did not contain notifiable events")

        for model_item in model_items:
            model_item.notified(pending_events.keys())
            await self._async_update_item(model_item)

        await self._expire_cache()
