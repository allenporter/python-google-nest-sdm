"""Libraries related to providing a device level interface for event related media."""

from __future__ import annotations

import datetime
import logging
from abc import ABC
from collections import OrderedDict
from collections.abc import Iterable
from typing import Any, Dict, Optional

from .camera_traits import EventImageGenerator, EventImageType
from .event import EventMessage, ImageEventBase
from .exceptions import GoogleNestException

_LOGGER = logging.getLogger(__name__)

DEFAULT_CACHE_SIZE = 2


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
        event_id: str,
        event_type: str,
        event_timestamp: datetime.datetime,
        media: Media,
    ) -> None:
        self._event_id = event_id
        self._event_type = event_type
        self._event_timestamp = event_timestamp
        self._media = media

    @property
    def event_id(self) -> str:
        """Return the event id."""
        return self._event_id

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

    async def async_load(self) -> list | None:
        """Load data."""

    async def async_save(self, data: list | None) -> None:
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
        self._data: list | None = None
        self._media: dict[str, bytes] = {}

    async def async_load(self) -> list | None:
        """Load data."""
        return self._data

    async def async_save(self, data: list | None) -> None:
        """Save data."""
        self._data = data

    def get_media_key(self, device_id: str, event: ImageEventBase) -> str:
        """Return the media key to use for the device and event."""
        suffix = "jpg" if event.event_image_type == EventImageType.IMAGE else "mp4"
        return f"{device_id}_{event.timestamp}_{event.event_id}.{suffix}"

    async def async_load_media(self, media_key: str) -> bytes | None:
        """Load media content."""
        return self._media.get(media_key)

    async def async_save_media(self, media_key: str, content: bytes) -> None:
        """Remove media content."""
        self._media[media_key] = content

    async def async_remove_media(self, media_key: str) -> None:
        """Remove media content."""
        del self._media[media_key]


class EventMediaModelItem:
    """Structure used to persist the event in EventMediaStore."""

    def __init__(self, event: ImageEventBase, media_key: str | None = None) -> None:
        """Initialize EventMediaModelItem."""
        self._event = event
        self._media_key = media_key

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EventMediaModelItem | None:
        if not (event := ImageEventBase.from_dict(data["event"])):
            return None
        return EventMediaModelItem(event, data.get("media_key"))

    @property
    def event(self) -> ImageEventBase:
        return self._event

    @property
    def media_key(self) -> str | None:
        return self._media_key

    @media_key.setter
    def media_key(self, value: str) -> None:
        """Update the media_key."""
        self._media_key = value

    def get_media(self, content: bytes) -> Media:
        return Media(content, self.event.event_image_type)

    def get_event_media(self, content: bytes) -> EventMedia:
        return EventMedia(
            self.event.event_id,
            self.event.event_type,
            self.event.timestamp,
            self.get_media(content),
        )

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"event": self._event.as_dict()}
        if self._media_key:
            result["media_key"] = self._media_key
        return result

    def __repr__(self) -> str:
        return (
            "<EventMediaModelItem event="
            + str(self._event)
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

    @property
    def cache_policy(self) -> CachePolicy:
        """Return the current CachePolicy."""
        return self._cache_policy

    @cache_policy.setter
    def cache_policy(self, value: CachePolicy) -> None:
        """Update the CachePolicy."""
        self._cache_policy = value

    async def _async_load(self) -> OrderedDict[str, EventMediaModelItem]:
        """Load the model from the store."""
        event_data: OrderedDict[str, EventMediaModelItem] = OrderedDict()
        data = await self._cache_policy.store.async_load()
        if data and isinstance(data, list):
            for item_data in data:
                item = EventMediaModelItem.from_dict(item_data)
                if not item:
                    continue
                event_data[item.event.event_id] = item
        return event_data

    async def _async_save(
        self, event_data: OrderedDict[str, EventMediaModelItem]
    ) -> None:
        """Save the model to the store."""
        data: list[dict[str, Any]] = []
        for item in event_data.values():
            data.append(item.as_dict())
        await self._cache_policy._store.async_save(data)

    async def get_media(
        self, event_id: str, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[EventMedia]:
        """Get media for the specified event.

        Note that the height and width hints are best effort and may not be
        honored (e.g. if image is already cached).
        """
        event_data = await self._async_load()
        if not (item := event_data.get(event_id)):
            return None
        event = item.event
        if item.media_key:
            media_key = item.media_key
        else:
            media_key = self._cache_policy._store.get_media_key(self._device_id, event)

        contents = await self._cache_policy._store.async_load_media(media_key)
        if contents is None:
            if not (generator := self._event_trait_map.get(event.event_type)):
                return None
            event_image = await generator.generate_event_image(event)
            if not event_image:
                return None
            contents = await event_image.contents(width=width, height=height)
            await self._cache_policy._store.async_save_media(media_key, contents)

        if not item.media_key:
            item.media_key = media_key
            await self._async_save(event_data)

        return item.get_event_media(contents)

    async def async_events(self) -> Iterable[ImageEventBase]:
        """Return revent events."""
        event_data = await self._async_load()
        result: list[EventMediaModelItem] = list(event_data.values())
        result.sort(key=lambda x: x.event.timestamp, reverse=True)

        def _filter(x: EventMediaModelItem) -> bool:
            """Return events already fetched or that could be fetched."""
            return x.media_key is not None or not x.event.is_expired

        result = list(filter(_filter, result))

        def _get_event(x: EventMediaModelItem) -> ImageEventBase:
            return x.event

        return list(map(_get_event, result))

    async def async_handle_events(self, event_message: EventMessage) -> None:
        """Handle the EventMessage."""
        events = event_message.resource_update_events
        if not events:
            return
        _LOGGER.debug("Event Update %s", events.keys())
        for (event_name, event) in events.items():
            if event_name not in self._event_trait_map:
                continue
            self._event_trait_map[event_name].handle_event(event)

            # Update event cache
            event_data = await self._async_load()
            event_data[event.event_id] = EventMediaModelItem(event)
            if len(event_data) > self._cache_policy.event_cache_size:
                (key, item) = event_data.popitem(last=False)
                if item.media_key:
                    await self._cache_policy.store.async_remove_media(item.media_key)
            await self._async_save(event_data)

            # Prefetch media, otherwise we may
            if self._cache_policy.fetch:
                try:
                    await self.get_media(event.event_id)
                except GoogleNestException as err:
                    _LOGGER.warning(
                        "Failure when pre-fetching event '%s': %s",
                        event.event_id,
                        str(err),
                    )

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
