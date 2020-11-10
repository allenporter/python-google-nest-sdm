"""Subscriber for the Smart Device Management event based API."""
import asyncio
import json
import logging
from abc import ABC, abstractmethod

from google.cloud import pubsub_v1

from .auth import AbstractAuth
from .device_manager import DeviceManager
from .event import EventCallback, EventMessage
from .google_nest_api import GoogleNestAPI

_LOGGER = logging.getLogger(__name__)


class AbstractSusbcriberFactory(ABC):
    """Abstract class for creating a subscriber, to facilitate testing."""

    @abstractmethod
    async def new_subscriber(
        self, creds, subscription_name, callback
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Create a new event subscriber."""


class DefaultSubscriberFactory(AbstractSusbcriberFactory):
    """Default implementation that creates Google Pubsub subscriber."""

    async def new_subscriber(
        self, creds, subscription_name, callback
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        subscriber = pubsub_v1.SubscriberClient(credentials=creds)
        return subscriber.subscribe(subscription_name, callback)


class GoogleNestSubscriber:
    """Subscribes to events from the Google Nest feed."""

    def __init__(
        self,
        auth: AbstractAuth,
        project_id: str,
        subscriber_id: str,
        subscriber_factory: AbstractSusbcriberFactory = DefaultSubscriberFactory(),
        watchdog_delay: float = 10,
    ):
        """Initialize the subscriber for the specified topic"""
        self._auth = auth
        self._subscriber_id = subscriber_id
        self._api = GoogleNestAPI(auth, project_id)
        self._subscriber_factory = subscriber_factory
        self._subscriber_future = None
        self._callback = None
        self._device_manager_task = asyncio.create_task(
            self._async_create_device_manager()
        )
        self._watchdog_delay = watchdog_delay
        if self._watchdog_delay > 0:
            self._watchdog_task = asyncio.create_task(self._watchdog())
        else:
            self._watchdog_task = None

    def set_update_callback(self, callback: EventCallback):
        """Register a callback invoked when new messages are received."""
        self._callback = callback

    async def start_async(self):
        """Starts the subscriber."""
        creds = await self._auth.async_get_creds()
        self._subscriber_future = await self._subscriber_factory.new_subscriber(
            creds, self._subscriber_id, self._subscribe_callback
        )

    async def _watchdog(self):
        """Background task that watches the subscriber and restarts it."""
        _LOGGER.debug("Starting background watchdog thread")
        while True:
            if self._subscriber_future and self._subscriber_future.done():
                _LOGGER.debug("Subscriber shut down; restarting")
                await self.start_async()
            await asyncio.sleep(self._watchdog_delay)

    def wait(self):
        """Blocks on the subscriber."""
        self._subscriber_future.result()

    def stop_async(self):
        """Tells the subscriber to start shutting down."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._subscriber_future:
            self._subscriber_future.cancel()

    async def async_get_device_manager(self) -> DeviceManager:
        """Return the DeviceManger with the current state of devices."""
        return await self._device_manager_task

    async def _async_create_device_manager(self):
        """Creates a DeviceManager, populated with initial state."""
        device_manager = DeviceManager()
        structures = await self._api.async_get_structures()
        for structure in structures:
            device_manager.add_structure(structure)
        # Subscriber starts after a device fetch
        devices = await self._api.async_get_devices()
        for device in devices:
            device_manager.add_device(device)
        return device_manager

    def _subscribe_callback(self, message: pubsub_v1.subscriber.message.Message):
        payload = json.loads(bytes.decode(message.data))
        event = EventMessage(payload, self._auth)
        # Only accept device events once the Device Manager has been loaded.
        # We are ok with missing messages on startup since the device manager will
        # do a live read.
        if self._device_manager_task.done():
            self._device_manager_task.result().handle_event(event)
        if self._callback:
            self._callback.handle_event(event)
        message.ack()
