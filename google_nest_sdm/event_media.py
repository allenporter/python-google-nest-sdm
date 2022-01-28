"""Libraries related to providing a device level interface for event related media."""

from __future__ import annotations

import asyncio
import datetime
import itertools
import logging
from abc import ABC
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any, Awaitable, Callable, Dict

from .camera_traits import (
    CameraClipPreviewTrait,
    CameraEventImageTrait,
    EventImageContentType,
    EventImageGenerator,
)
from .diagnostics import EVENT_MEDIA_DIAGNOSTICS as DIAGNOSTICS
from .diagnostics import Diagnostics
from .event import (
    CameraMotionEvent,
    CameraPersonEvent,
    CameraSoundEvent,
    DoorbellChimeEvent,
    EventImageType,
    EventMessage,
    EventToken,
    ImageEventBase,
    session_event_image_type,
)
from .exceptions import GoogleNestException, TranscodeException
from .transcoder import Transcoder

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


class CachePolicy:
    """Policy for how many local objects to cache in memory."""

    def __init__(self, event_cache_size: int = DEFAULT_CACHE_SIZE, fetch: bool = False):
        self._event_cache_size = event_cache_size
        self._fetch = fetch
        self._store: EventMediaStore = InMemoryEventMediaStore()
        self._transcoder: Transcoder | None = None

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

    @property
    def transcoder(self) -> Transcoder | None:
        """Return the transcoder."""
        return self._transcoder

    @transcoder.setter
    def transcoder(self, value: Transcoder) -> None:
        """Update the Transcoder."""
        self._transcoder = value


class Media:
    """Represents media related to an event."""

    def __init__(
        self, contents: bytes, event_image_type: EventImageContentType
    ) -> None:
        """Initialize Media."""
        self._contents = contents
        self._event_image_type = event_image_type

    @property
    def contents(self) -> bytes:
        """Media content."""
        return self._contents

    @property
    def event_image_type(self) -> EventImageContentType:
        """Content event image type of the media."""
        return self._event_image_type

    @property
    def content_type(self) -> str:
        """Content type of the media."""
        return self._event_image_type.content_type


class ImageSession(ABC):
    """An object that holds events that happened within a time range."""

    def __init__(
        self,
        event_token: str,
        event_timestamp: datetime.datetime,
        event_type: str,
    ) -> None:
        self._event_token = event_token
        self._event_timestamp = event_timestamp
        self._event_type = event_type

    @property
    def event_token(self) -> str:
        return self._event_token

    @property
    def timestamp(self) -> datetime.datetime:
        """Return timestamp that the event ocurred."""
        return self._event_timestamp

    @property
    def event_type(self) -> str:
        return self._event_type


class ClipPreviewSession(ABC):
    """An object that holds events that happened within a time range."""

    def __init__(
        self,
        event_token: str,
        event_timestamp: datetime.datetime,
        event_types: list[str],
    ) -> None:
        self._event_token = event_token
        self._event_timestamp = event_timestamp
        self._event_types = event_types

    @property
    def event_token(self) -> str:
        return self._event_token

    @property
    def timestamp(self) -> datetime.datetime:
        """Return timestamp that the event ocurred."""
        return self._event_timestamp

    @property
    def event_types(self) -> list[str]:
        return self._event_types


class EventMedia:
    """Represents an event and its associated media."""

    def __init__(
        self,
        event_session_id: str,
        event_id: str,
        event_type: str,
        event_timestamp: datetime.datetime,
        media: Media,
    ) -> None:
        self._event_session_id = event_session_id
        self._event_id = event_id
        self._event_type = event_type
        self._event_timestamp = event_timestamp
        self._media = media

    @property
    def event_session_id(self) -> str:
        """Return the event session id."""
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

    async def async_save(self, data: dict) -> None:
        """Save data."""

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
        return f"{device_id}_{event.timestamp}_{event.event_session_id}_{event.event_id}.jpg"

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
        DIAGNOSTICS.increment("load_media")
        return self._media.get(media_key)

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Remove media content."""
        DIAGNOSTICS.increment("save_media")
        self._media[media_key] = content

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""
        DIAGNOSTICS.increment("remove_media")
        if media_key in self._media:
            del self._media[media_key]


class EventMediaModelItem:
    """Structure used to persist the event in EventMediaStore."""

    def __init__(
        self,
        event_session_id: str,
        events: dict[str, ImageEventBase],
        media_key: str | None,
        event_media_keys: dict[str, str],
        thumbnail_media_key: str | None,
    ) -> None:
        """Initialize EventMediaModelItem."""
        self._event_session_id = event_session_id
        self._events = events
        self._media_key = media_key
        self._event_media_keys = event_media_keys if event_media_keys else {}
        self._thumbnail_media_key = thumbnail_media_key

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
            data["event_session_id"],
            events,
            data.get("media_key"),
            data.get("event_media_keys", {}),
            data.get("thumbnail_media_key"),
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

    @property
    def event_media_keys(self) -> dict[str, str]:
        return self._event_media_keys

    def media_key_for_token(self, token: EventToken) -> str | None:
        """Return media key for the specified event token."""
        if token.event_id:
            if token.event_id in self._event_media_keys:
                return self._event_media_keys[token.event_id]
            # Fallback to legacy single event per session
        return self._media_key

    @property
    def any_media_key(self) -> str | None:
        """Return any media item for compatibility with legacy APIs."""
        if self._media_key:
            return self._media_key
        if self._event_media_keys.values():
            return next(iter(self._event_media_keys.values()))
        return None

    @property
    def thumbnail_media_key(self) -> str | None:
        return self._thumbnail_media_key

    @thumbnail_media_key.setter
    def thumbnail_media_key(self, value: str) -> None:
        """Update the thumbnail_media_key."""
        self._thumbnail_media_key = value

    def get_media(self, content: bytes) -> Media:
        assert self.visible_event
        return Media(content, self.visible_event.event_image_type)

    def get_event_media(self, content: bytes) -> EventMedia:
        assert self.visible_event
        return EventMedia(
            self.visible_event.event_session_id,
            self.visible_event.event_id,
            self.visible_event.event_type,
            self.visible_event.timestamp,
            self.get_media(content),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a EventMediaModelItem as a serializable dict."""
        result: dict[str, Any] = {
            "event_session_id": self._event_session_id,
            "events": dict((k, v.as_dict()) for k, v in self._events.items()),
            "event_media_keys": self._event_media_keys,
        }
        if self._media_key:
            result["media_key"] = self._media_key
        if self._thumbnail_media_key:
            result["thumbnail_media_key"] = self._thumbnail_media_key
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
        self,
        device_id: str,
        traits: Dict[str, Any],
        event_trait_map: Dict[str, EventImageGenerator],
        support_fetch: bool,
        diagnostics: Diagnostics,
    ) -> None:
        """Initialize DeviceEventMediaManager."""
        self._device_id = device_id
        self._traits = traits
        self._event_trait_map = event_trait_map
        self._cache_policy = CachePolicy()
        self._callback: Callable[[EventMessage], Awaitable[None]] | None = None
        self._support_fetch = support_fetch
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
            if len(event_data) <= self._cache_policy.event_cache_size:
                return
            (key, old_item) = event_data.popitem(last=False)
            if old_item.media_key:
                _LOGGER.debug(
                    "Expiring media %s (%s)",
                    old_item.media_key,
                    old_item.event_session_id,
                )
                await self._cache_policy.store.async_remove_media(old_item.media_key)
            if old_item.thumbnail_media_key:
                _LOGGER.debug(
                    "Expiring media %s (%s)",
                    old_item.thumbnail_media_key,
                    old_item.event_session_id,
                )
                await self._cache_policy.store.async_remove_media(
                    old_item.thumbnail_media_key
                )
            for old_media_key in old_item.event_media_keys.values():
                _LOGGER.debug(
                    "Expiring event media %s (%s)",
                    old_media_key,
                    old_item.event_session_id,
                )
                await self._cache_policy.store.async_remove_media(old_media_key)
            await self._async_update(event_data)

    async def get_media(
        self, event_session_id: str, width: int | None = None, height: int | None = None
    ) -> EventMedia | None:
        """Get media for the specified event.

        Note that the height and width hints are best effort and may not be
        honored (e.g. if image is already cached).
        """
        self._diagnostics.increment("get_media")
        if not (item := await self._async_load_item(event_session_id)):
            return None
        event = item.visible_event
        if not event:
            _LOGGER.debug(
                "Skipping fetch; No visible event; event_session_id=%s",
                event_session_id,
            )
            return None
        media_key = item.any_media_key
        if media_key:
            contents = await self._cache_policy._store.async_load_media(media_key)
            if contents:
                return item.get_event_media(contents)

        if event.is_expired:
            _LOGGER.debug(
                "Skipping fetch; Event expired; event_session_id=%s",
                event_session_id,
            )
            return None
        _LOGGER.debug("Fetching media for event_session_id=%s", event_session_id)
        if not (generator := self._event_trait_map.get(event.event_type)):
            return None
        event_image = await generator.generate_event_image(event)
        if not event_image:
            return None
        contents = await event_image.contents(width=width, height=height)
        media_key = self._cache_policy._store.get_media_key(self._device_id, event)
        await self._cache_policy.store.async_save_media(media_key, contents)
        item.media_key = media_key
        await self._async_update_item(item)
        return item.get_event_media(contents)

    async def _fetch_media(self, item: EventMediaModelItem) -> None:
        """Fetch media from the server in response to a pubsub event."""
        store = self._cache_policy.store
        if CameraClipPreviewTrait.NAME in self._traits:
            self._diagnostics.increment("fetch_clip")
            if (
                item.media_key
                or not item.visible_event
                or item.visible_event.is_expired
            ):
                self._diagnostics.increment("fetch_clip.skip")
                return
            clip_preview_trait: CameraClipPreviewTrait = self._traits[
                CameraClipPreviewTrait.NAME
            ]
            event_image = await clip_preview_trait.generate_event_image(
                item.visible_event
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
        contents = await self._cache_policy._store.async_load_media(media_key)
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
            contents = await self._cache_policy._store.async_load_media(
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
            self._cache_policy._store.get_clip_preview_thumbnail_media_key(
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

        contents = await self._cache_policy._store.async_load_media(thumbnail_media_key)
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

    async def async_events(self) -> Iterable[ImageEventBase]:
        """Return revent events."""
        self._diagnostics.increment("load_events")
        result = await self._visible_items()

        def _get_event(x: EventMediaModelItem) -> ImageEventBase:
            assert x.visible_event
            return x.visible_event

        event_result = list(map(_get_event, result))
        event_result.sort(key=lambda x: x.timestamp, reverse=True)
        return event_result

    async def async_image_sessions(self) -> Iterable[ImageSession]:
        """Return revent events."""
        self._diagnostics.increment("load_image_sessions")

        def _get_events(x: EventMediaModelItem) -> list[ImageEventBase]:
            return list(x.events.values())

        result = await self._items_with_media()
        events_list = list(map(_get_events, result))
        events: Iterable[ImageEventBase] = itertools.chain(*events_list)

        def _get_session(x: ImageEventBase) -> ImageSession:
            return ImageSession(x.event_token, x.timestamp, x.event_type)

        event_result = list(map(_get_session, events))
        event_result.sort(key=lambda x: x.timestamp, reverse=True)
        return event_result

    async def async_clip_preview_sessions(self) -> Iterable[ClipPreviewSession]:
        """Return revent events."""
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

    async def _visible_items(self) -> list[EventMediaModelItem]:
        """Return items in the modle that are visible events for serving."""

        def _filter(x: EventMediaModelItem) -> bool:
            """Return events already fetched or that could be fetched."""
            return x.visible_event is not None and (
                x.media_key is not None or not x.visible_event.is_expired
            )

        event_data = await self._async_load()
        return list(filter(_filter, event_data.values()))

    async def _items_with_media(self) -> list[EventMediaModelItem]:
        """Return items in the modle that have media for serving."""

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
                    self._diagnostics.increment("event.unsupported_trait")
                    _LOGGER.debug("Unsupported event trait: %s", event_name)
                    continue
                supported = True
                trait.handle_event(event)

            # Skip any entirely unsupported events
            if not supported:
                del event_sessions[event_session_id]

        # Update interal event media representation. Events are only published
        # to downstream subscribers the first time they are seen to avoid
        # firing on updated event threads multiple times.
        suppress_keys: set[str] = set({})
        valid_events = 0
        for event_session_id, event_dict in event_sessions.items():

            # Track all related events together with the same session
            if model_item := await self._async_load_item(event_session_id):
                self._diagnostics.increment("event.update")
                # Update the existing event session with new/updated events. Only
                # new events are published.
                suppress_keys |= set(model_item.events.keys())
                valid_events += len(
                    set(event_dict.keys()) - set(model_item.events.keys())
                )
                model_item.events.update(event_dict)
            else:
                self._diagnostics.increment("event.new")
                # A new event session
                valid_events += len(event_dict.keys())
                model_item = EventMediaModelItem(
                    event_session_id,
                    event_dict,
                    media_key=None,
                    event_media_keys={},
                    thumbnail_media_key=None,
                )

            await self._async_update_item(model_item)

            if self._support_fetch and self._cache_policy.fetch:
                self._diagnostics.increment("event.fetch")
                try:
                    await self._fetch_media(model_item)
                except GoogleNestException as err:
                    self._diagnostics.increment("event.fetch_error")
                    _LOGGER.warning(
                        "Failure when pre-fetching event '%s': %s",
                        event.event_session_id,
                        str(err),
                    )
                # Update any new media keys
                await self._async_update_item(model_item)

        await self._expire_cache()

        if not self._callback:
            return
        # Notify any listeners about the arrival of a new event
        if suppress_keys:
            event_message = event_message.omit_events(suppress_keys)
        if valid_events > 0:
            self._diagnostics.increment("event.notify")
            await self._callback(event_message)

    @property
    def active_event_trait(self) -> EventImageGenerator | None:
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

    async def get_active_event_media(
        self, width: int | None = None, height: int | None = None
    ) -> EventMedia | None:
        """Return a snapshot image for a very recent event if any."""
        if not (trait := self.active_event_trait):
            return None
        event: ImageEventBase | None = trait.last_event
        if not event:
            return None
        return await self.get_media(event.event_session_id, width, height)
