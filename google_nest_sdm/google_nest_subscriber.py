"""Subscriber for the Smart Device Management event based API."""

from __future__ import annotations

import asyncio
import enum
import logging
import re
import time
from typing import Awaitable, Callable


from .auth import AbstractAuth
from .device_manager import DeviceManager
from .diagnostics import SUBSCRIBER_DIAGNOSTICS as DIAGNOSTICS
from .event import EventMessage
from .event_media import CachePolicy
from .exceptions import (
    ConfigurationException,
    ApiException,
)
from .google_nest_api import GoogleNestAPI
from .streaming_manager import StreamingManager, Message

__all__ = [
    "GoogleNestSubscriber",
    "ApiEnv",
]


_LOGGER = logging.getLogger(__name__)

# Used to catch invalid subscriber id
EXPECTED_SUBSCRIBER_REGEXP = re.compile("projects/.*/subscriptions/.*")

MESSAGE_ACK_TIMEOUT_SECONDS = 30.0

# Note: Users of non-prod instances will have to manually configure a topic
TOPIC_FORMAT = "projects/sdm-prod/topics/enterprise-{project_id}"

OAUTH2_AUTHORIZE_FORMAT = (
    "https://nestservices.google.com/partnerconnections/{project_id}/auth"
)
OAUTH2_TOKEN = "https://www.googleapis.com/oauth2/v4/token"
SDM_SCOPES = [
    "https://www.googleapis.com/auth/sdm.service",
    "https://www.googleapis.com/auth/pubsub",
]
API_URL = "https://smartdevicemanagement.googleapis.com/v1"


class ApiEnv(enum.Enum):
    PROD = (OAUTH2_AUTHORIZE_FORMAT, API_URL)
    PREPROD = (
        "https://sdmresourcepicker-preprod.sandbox.google.com/partnerconnections/{project_id}/auth",
        "https://preprod-smartdevicemanagement.googleapis.com/v1",
    )

    def __init__(self, authorize_url: str, api_url: str) -> None:
        """Init ApiEnv."""
        self._authorize_url = authorize_url
        self._api_url = api_url

    @property
    def authorize_url_format(self) -> str:
        """OAuth Authorize url format string."""
        return self._authorize_url

    @property
    def api_url(self) -> str:
        """API url."""
        return self._api_url


def get_api_env(env: str | None) -> ApiEnv:
    """Create an ApiEnv from a string."""
    if env is None or env == "prod":
        return ApiEnv.PROD
    if env == "preprod":
        return ApiEnv.PREPROD
    raise ValueError("Invalid ApiEnv: %s" % env)


def _validate_subscription_name(subscription_name: str) -> None:
    """Validates that a subscription name is correct.

    Raises ConfigurationException on failure.
    """
    if not EXPECTED_SUBSCRIBER_REGEXP.match(subscription_name):
        DIAGNOSTICS.increment("subscription_name_invalid")
        _LOGGER.debug("Subscription name did not match pattern: %s", subscription_name)
        raise ConfigurationException(
            "Subscription misconfigured. Expected subscriber_id to "
            f"match '{EXPECTED_SUBSCRIBER_REGEXP.pattern}' but was "
            f"'{subscription_name}'"
        )


class GoogleNestSubscriber:
    """Subscribe to events from the Google Nest feed."""

    def __init__(
        self,
        auth: AbstractAuth,
        project_id: str,
        subscription_name: str,
    ) -> None:
        """Initialize the subscriber for the specified topic."""
        self._auth = auth
        self._subscription_name = subscription_name
        self._project_id = project_id
        self._api = GoogleNestAPI(auth, project_id)
        self._device_manager_task: asyncio.Task[DeviceManager] | None = None
        self._callback: Callable[[EventMessage], Awaitable[None]] | None = None
        self._cache_policy = CachePolicy()

    @property
    def subscription_name(self) -> str:
        """Return the configured subscriber name."""
        return self._subscription_name

    @property
    def project_id(self) -> str:
        """Return the configured SDM project_id."""
        return self._project_id

    def set_update_callback(
        self, target: Callable[[EventMessage], Awaitable[None]]
    ) -> None:
        """Register a callback invoked when new messages are received.

        If the event is associated with media, then the callback will only
        be invoked once the media has been fetched.
        """
        self._callback = target
        if self._device_manager_task and self._device_manager_task.done():
            self._device_manager_task.result().set_update_callback(target)

    async def start_async(self) -> Callable[[], None]:
        """Start the subscription.

        Returns a callable used to stop/cancel the subscription. Received
        messages are passed to the callback provided to `set_update_callback`.
        """
        _validate_subscription_name(self._subscription_name)
        _LOGGER.debug("Starting subscription %s", self._subscription_name)
        DIAGNOSTICS.increment("start")

        stream = StreamingManager(
            auth=self._auth,
            subscription_name=self._subscription_name,
            callback=self._async_message_callback_with_timeout,
        )
        await stream.start()
        return stream.stop

    @property
    def cache_policy(self) -> CachePolicy:
        """Return cache policy shared by device EventMediaManager objects."""
        return self._cache_policy

    async def async_get_device_manager(self) -> DeviceManager:
        """Return the DeviceManger with the current state of devices."""
        if not self._device_manager_task:
            self._device_manager_task = asyncio.create_task(
                self._async_create_device_manager()
            )
        return await self._device_manager_task

    async def _async_create_device_manager(self) -> DeviceManager:
        """Create a DeviceManager, populated with initial state."""
        device_manager = DeviceManager(self._cache_policy)
        structures = await self._api.async_get_structures()
        for structure in structures:
            device_manager.add_structure(structure)
        # Subscriber starts after a device fetch
        devices = await self._api.async_get_devices()
        for device in devices:
            device_manager.add_device(device)
        if self._callback:
            device_manager.set_update_callback(self._callback)
        return device_manager

    async def _async_message_callback_with_timeout(self, message: Message) -> None:
        """Handle a received message."""
        try:
            async with asyncio.timeout(MESSAGE_ACK_TIMEOUT_SECONDS):
                await self._async_message_callback(message)
        except TimeoutError as err:
            DIAGNOSTICS.increment("message_ack_timeout")
            raise TimeoutError("Message ack timeout processing message") from err

    async def _async_message_callback(self, message: Message) -> None:
        """Handle a received message."""
        event = EventMessage.create_event(message.payload, self._auth)
        recv = time.time()
        latency_ms = int((recv - event.timestamp.timestamp()) * 1000)
        DIAGNOSTICS.elapsed("message_received", latency_ms)
        # Only accept device events once the Device Manager has been loaded.
        # We are ok with missing messages on startup since the device manager
        # will do a live read. This checks for an exception to avoid throwing
        # inside the pubsub callback and further wedging the pubsub client library.
        if (
            self._device_manager_task
            and self._device_manager_task.done()
            and not self._device_manager_task.exception()
        ):
            device_manager = self._device_manager_task.result()
            if _is_invalid_thermostat_trait_update(event):
                _LOGGER.debug(
                    "Ignoring event with invalid update traits; Refreshing devices: %s",
                    event.resource_update_traits,
                )
                await _hack_refresh_devices(self._api, device_manager)
            else:
                await device_manager.async_handle_event(event)

        process_latency_ms = int((time.time() - recv) * 1000)
        DIAGNOSTICS.elapsed("message_processed", process_latency_ms)


def _is_invalid_thermostat_trait_update(event: EventMessage) -> bool:
    """Return true if this is an invalid thermostat trait update."""
    if (
        event.resource_update_traits is not None
        and (
            thermostat_mode := event.resource_update_traits.get(
                "sdm.devices.traits.ThermostatMode"
            )
        )
        and (available_modes := thermostat_mode.get("availableModes")) is not None
        and available_modes == ["OFF"]
    ):
        return True
    return False


async def _hack_refresh_devices(
    api: GoogleNestAPI, device_manager: DeviceManager
) -> None:
    """Update the device manager with refreshed devices from the API."""
    DIAGNOSTICS.increment("invalid-thermostat-update")
    try:
        devices = await api.async_get_devices()
    except ApiException:
        DIAGNOSTICS.increment("invalid-thermostat-update-refresh-failure")
        _LOGGER.debug("Failed to refresh devices after invalid message")
    else:
        DIAGNOSTICS.increment("invalid-thermostat-update-refresh-success")
        for device in devices:
            device_manager.add_device(device)
