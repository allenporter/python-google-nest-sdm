"""Subscriber for the Smart Device Management event based API."""

from __future__ import annotations

import asyncio
import datetime
import logging
import json
from typing import Awaitable, Callable, AsyncIterable, Any, TYPE_CHECKING

from google import pubsub_v1

from .auth import AbstractAuth
from .diagnostics import STREAMING_MANAGER_DIAGNOSTICS as DIAGNOSTICS
from .exceptions import (
    GoogleNestException,
)
from .subscriber_client import SubscriberClient

_LOGGER = logging.getLogger(__name__)

MESSAGE_ACK_TIMEOUT_SECONDS = 30.0

NEW_SUBSCRIBER_TIMEOUT_SECONDS = 30.0

MIN_BACKOFF_INTERVAL = datetime.timedelta(seconds=10)
MAX_BACKOFF_INTERVAL = datetime.timedelta(minutes=10)
BACKOFF_MULTIPLIER = 1.5


class Message:
    """A message from the Pub/Sub stream."""

    def __init__(self, message: pubsub_v1.types.PubsubMessage) -> None:
        """Initialize the message."""
        self._message = message
        self._payload: dict[str, Any] | None = None

    @property
    def payload(self) -> dict[str, Any]:
        """Get the payload of the message."""
        if self._payload is None:
            self._payload = json.loads(bytes.decode(self._message.data)) or {}
        return self._payload

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> Message:
        """Create a message from an object for testing."""
        return cls(encode_pubsub_message(data))


def encode_pubsub_message(data: dict[str, Any]) -> pubsub_v1.types.PubsubMessage:
    """Encode a message for Pub/Sub."""
    return pubsub_v1.types.PubsubMessage(data=bytes(json.dumps(data), "utf-8"))


class StreamingManager:
    """Client for the Google Nest subscriber."""

    def __init__(
        self,
        auth: AbstractAuth,
        subscription_name: str,
        callback: Callable[[Message], Awaitable[None]],
    ) -> None:
        """Initialize the client."""
        self._subscription_name = subscription_name
        self._callback = callback
        self._background_task: asyncio.Task | None = None
        self._subscriber_client = SubscriberClient(auth, subscription_name)
        self._stream: AsyncIterable[pubsub_v1.types.StreamingPullResponse] | None = None
        self._healthy = False

    async def start(self) -> None:
        """Start the subscription background task and wait for initial startup."""
        DIAGNOSTICS.increment("start")
        self._stream = await self._connect(allow_retries=False)
        self._healthy = True
        loop = asyncio.get_event_loop()
        self._background_task = loop.create_task(self._run_task())

    @property
    def healthy(self) -> bool:
        """Return True if the subscription is healthy."""
        return self._healthy

    def stop(self) -> None:
        _LOGGER.debug("Stopping subscription %s", self._subscription_name)
        DIAGNOSTICS.increment("stop")
        if self._background_task:
            self._background_task.cancel()
        self._healthy = False

    async def _run_task(self) -> None:
        """"""
        try:
            await self._run()
        except asyncio.CancelledError:
            _LOGGER.debug("Subscription loop cancelled")
        except Exception as err:
            _LOGGER.error("Uncaught error in subscription loop: %s", err)
            DIAGNOSTICS.increment("uncaught_exception")
        self._healthy = False

    async def _run(self) -> None:
        """Run the subscription loop."""
        DIAGNOSTICS.increment("run")
        while True:
            _LOGGER.debug("Subscriber connected and waiting for messages")
            if TYPE_CHECKING:
                assert self._stream is not None
            self._healthy = True
            try:
                async for response in self._stream:
                    _LOGGER.debug(
                        "Received %s messages", len(response.received_messages)
                    )
                    ack_ids = []
                    for received_message in response.received_messages:
                        if await self._process_message(received_message.message):
                            ack_ids.append(received_message.ack_id)

                    if ack_ids:
                        _LOGGER.debug("Acknowledging %s messages", len(ack_ids))
                        try:
                            await self._subscriber_client.ack_messages(ack_ids)
                        except GoogleNestException as err:
                            _LOGGER.debug("Error while acknowledging messages: %s", err)
            except GoogleNestException as err:
                _LOGGER.debug("Error while processing messages: %s", err)
                DIAGNOSTICS.increment("exception")
            self._healthy = False

            _LOGGER.debug("Reconnecting stream")
            self._stream = await self._connect(allow_retries=True)

    async def _connect(
        self, allow_retries: bool = True
    ) -> AsyncIterable[pubsub_v1.types.StreamingPullResponse] | None:
        """Connect to the streaming pull."""
        backoff = MIN_BACKOFF_INTERVAL
        while True:
            _LOGGER.debug("Connecting with streaming pull")
            DIAGNOSTICS.increment("connect")
            try:
                return await self._subscriber_client.streaming_pull()
            except GoogleNestException as err:
                if not allow_retries:
                    raise err
                _LOGGER.warning("Error while reconnecting stream: %s", err)
                backoff = min(backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_INTERVAL)
                DIAGNOSTICS.increment("backoff")

            _LOGGER.debug("Reconnecting in %s seconds", backoff.total_seconds())
            await asyncio.sleep(backoff.total_seconds())

    async def _process_message(self, message: pubsub_v1.types.PubsubMessage) -> bool:
        """Process an incoming message from the stream."""
        DIAGNOSTICS.increment("process_message")
        try:
            async with asyncio.timeout(MESSAGE_ACK_TIMEOUT_SECONDS):
                await self._callback(Message(message))
                return True
        except TimeoutError as err:
            DIAGNOSTICS.increment("process_message_timeout")
            _LOGGER.error("Unexpected timeout while processing message: %s", err)
            return False
        except Exception as err:
            DIAGNOSTICS.increment("process_message_exception")
            _LOGGER.error("Uncaught error while processing message: %s", err)
            return False
