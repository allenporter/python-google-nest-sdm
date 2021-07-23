"""Subscriber for the Smart Device Management event based API."""
import asyncio
import concurrent.futures
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Awaitable, Callable, Optional

from aiohttp.client_exceptions import ClientError
from google.api_core.exceptions import GoogleAPIError, NotFound, Unauthenticated
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.cloud import pubsub_v1

from .auth import AbstractAuth
from .device_manager import DeviceManager
from .event import EventMessage
from .exceptions import AuthException, ConfigurationException, SubscriberException
from .google_nest_api import GoogleNestAPI

_LOGGER = logging.getLogger(__name__)

# Used to catch invalid subscriber id
EXPECTED_SUBSCRIBER_REGEXP = re.compile("projects/.*/subscriptions/.*")

# Used to catch a topic misconfiguration
EXPECTED_TOPIC_REGEXP = re.compile("projects/sdm-[a-z]+/topics/.*")

WATCHDOG_CHECK_INTERVAL_SECONDS = 10

# Restart the subscriber after some delay, with exponential backoff
WATCHDOG_RESTART_DELAY_MIN_SECONDS = 10
WATCHDOG_RESTART_DELAY_MAX_SECONDS = 300
# Reset watchdog backoff
WATCHDOG_RESET_THRESHOLD_SECONDS = 60


class AbstractSubscriberFactory(ABC):
    """Abstract class for creating a subscriber, to facilitate testing."""

    @abstractmethod
    async def async_new_subscriber(
        self,
        creds: Credentials,
        subscription_name: str,
        loop: asyncio.AbstractEventLoop,
        async_callback: Callable[
            [pubsub_v1.subscriber.message.Message], Awaitable[None]
        ],
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Create a new event subscriber."""


class DefaultSubscriberFactory(AbstractSubscriberFactory):
    """Default implementation that creates Google Pubsub subscriber."""

    async def async_new_subscriber(
        self,
        creds: Credentials,
        subscription_name: str,
        loop: asyncio.AbstractEventLoop,
        async_callback: Callable[
            [pubsub_v1.subscriber.message.Message], Awaitable[None]
        ],
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Create a new subscriber with a blocking to async bridge."""

        def callback_wrapper(message: pubsub_v1.subscriber.message.Message) -> None:
            if loop.is_closed():
                return
            assert async_callback
            future: concurrent.futures.Future = asyncio.run_coroutine_threadsafe(
                async_callback(message), loop
            )
            future.result()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            return await loop.run_in_executor(
                executor,
                self._new_subscriber,
                creds,
                subscription_name,
                callback_wrapper,
            )

    def _new_subscriber(
        self,
        creds: Credentials,
        subscription_name: str,
        callback_wrapper: Callable[[pubsub_v1.subscriber.message.Message], None],
    ) -> pubsub_v1.subscriber.futures.StreamingPullFuture:
        """Issue a command to verify subscriber creds are correct."""

        try:
            creds.refresh(Request())
        except RefreshError as err:
            raise AuthException(f"Access token failure: {err}") from err

        subscriber = pubsub_v1.SubscriberClient(credentials=creds)
        subscription = subscriber.get_subscription(subscription=subscription_name)
        if subscription.topic:
            if not EXPECTED_TOPIC_REGEXP.match(subscription.topic):
                raise ConfigurationException(
                    "Subscription misconfigured. Expected topic name to "
                    f"match '{EXPECTED_TOPIC_REGEXP.pattern}' but was "
                    f"'{subscription.topic}'."
                )
            else:
                _LOGGER.debug(
                    "Subscriber '%s' configured on topic '%s'",
                    subscription_name,
                    subscription.topic,
                )
        return subscriber.subscribe(subscription_name, callback_wrapper)


class GoogleNestSubscriber:
    """Subscribe to events from the Google Nest feed."""

    def __init__(
        self,
        auth: AbstractAuth,
        project_id: str,
        subscriber_id: str,
        subscriber_factory: AbstractSubscriberFactory = DefaultSubscriberFactory(),
        loop: Optional[asyncio.AbstractEventLoop] = None,
        watchdog_check_interval_seconds: float = WATCHDOG_CHECK_INTERVAL_SECONDS,
        watchdog_restart_delay_min_seconds: float = WATCHDOG_RESTART_DELAY_MIN_SECONDS,
    ):
        """Initialize the subscriber for the specified topic."""
        self._auth = auth
        self._subscriber_id = subscriber_id
        self._api = GoogleNestAPI(auth, project_id)
        self._loop = loop or asyncio.get_event_loop()
        self._device_manager_task: Optional[asyncio.Task[DeviceManager]] = None
        self._subscriber_factory = subscriber_factory
        self._subscriber_future: Optional[
            pubsub_v1.subscriber.futures.StreamingPullFuture
        ] = None
        self._callback: Optional[Callable[[EventMessage], Awaitable[None]]] = None
        self._healthy = True
        self._watchdog_check_interval_seconds = watchdog_check_interval_seconds
        self._watchdog_restart_delay_min_seconds = watchdog_restart_delay_min_seconds
        self._watchdog_restart_delay_seconds = watchdog_restart_delay_min_seconds
        self._watchdog_task: Optional[asyncio.Task] = None
        if self._watchdog_check_interval_seconds > 0:
            self._watchdog_task = asyncio.create_task(self._watchdog())

    def set_update_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> None:
        """Register a callback invoked when new messages are received."""
        self._callback = target

    async def start_async(self) -> None:
        """Start the subscriber."""
        if not EXPECTED_SUBSCRIBER_REGEXP.match(self._subscriber_id):
            raise ConfigurationException(
                "Subscription misconfigured. Expected subscriber_id to "
                f"match '{EXPECTED_SUBSCRIBER_REGEXP.pattern}' but was "
                f"'{self._subscriber_id}'"
            )
        try:
            creds = await self._auth.async_get_creds()
        except ClientError as err:
            raise AuthException(f"Access token failure: {err}") from err

        try:
            self._subscriber_future = (
                await self._subscriber_factory.async_new_subscriber(
                    creds, self._subscriber_id, self._loop, self._async_message_callback
                )
            )
        except NotFound as err:
            raise SubscriberException(
                f"Failed to create subscriber '{self._subscriber_id}' id was not found"
            ) from err
        except Unauthenticated as err:
            raise AuthException("Failed to authenticate subscriber: {err}") from err
        except GoogleAPIError as err:
            raise SubscriberException(
                f"Failed to create subscriber '{self._subscriber_id}': {err}"
            ) from err

        if not self._healthy:
            _LOGGER.debug("Subscriber reconnected")
            self._healthy = True
            self._watchdog_restart_delay_seconds = (
                self._watchdog_restart_delay_min_seconds
            )
        if self._subscriber_future:
            self._subscriber_future.add_done_callback(self._done_callback)

    async def _watchdog(self) -> None:
        """Background task that watches the subscriber and restarts it."""
        _LOGGER.debug("Starting background watchdog thread")
        while True:
            if self._subscriber_future and self._subscriber_future.done():
                _LOGGER.debug(
                    "Watchdog: subscriber shut down; restarting in %s seconds",
                    self._watchdog_restart_delay_seconds,
                )
                await asyncio.sleep(self._watchdog_restart_delay_seconds)
                self._watchdog_restart_delay_seconds *= 2
                self._watchdog_restart_delay_seconds = max(
                    self._watchdog_restart_delay_seconds,
                    WATCHDOG_RESTART_DELAY_MAX_SECONDS,
                )
                await self.start_async()
            await asyncio.sleep(self._watchdog_check_interval_seconds)

    def wait(self) -> None:
        """Block on the subscriber."""
        assert self._subscriber_future
        self._subscriber_future.result()

    def stop_async(self) -> None:
        """Tell the subscriber to start shutting down."""
        if self._device_manager_task:
            self._device_manager_task.cancel()
        if self._watchdog_task:
            self._watchdog_task.cancel()
        if self._subscriber_future:
            self._subscriber_future.cancel()

    async def async_get_device_manager(self) -> DeviceManager:
        """Return the DeviceManger with the current state of devices."""
        if not self._device_manager_task:
            self._device_manager_task = asyncio.create_task(
                self._async_create_device_manager()
            )
        assert self._device_manager_task
        return await self._device_manager_task

    async def _async_create_device_manager(self) -> DeviceManager:
        """Create a DeviceManager, populated with initial state."""
        device_manager = DeviceManager()
        structures = await self._api.async_get_structures()
        for structure in structures:
            device_manager.add_structure(structure)
        # Subscriber starts after a device fetch
        devices = await self._api.async_get_devices()
        for device in devices:
            device_manager.add_device(device)
        return device_manager

    def _done_callback(
        self, future: pubsub_v1.subscriber.futures.StreamingPullFuture
    ) -> None:
        """Teardown subscriber."""
        if future.exception():
            ex = future.exception()
            if self._healthy:
                self._healthy = False
            _LOGGER.debug("Subscriber disconnected, will restart: %s: %s", type(ex), ex)

    async def _async_message_callback(
        self, message: pubsub_v1.subscriber.message.Message
    ) -> None:
        """Handle a received message."""
        payload = json.loads(bytes.decode(message.data))
        event = EventMessage(payload, self._auth)
        # Only accept device events once the Device Manager has been loaded.
        # We are ok with missing messages on startup since the device manager
        # will do a live read .
        if self._device_manager_task and self._device_manager_task.done():
            await self._device_manager_task.result().async_handle_event(event)
        if self._callback:
            await self._callback(event)
        message.ack()
