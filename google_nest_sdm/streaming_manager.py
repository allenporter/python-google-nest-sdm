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
        self._auth = auth
        self._subscriber_client: SubscriberClient | None = None
        self._stream: AsyncIterable[pubsub_v1.types.StreamingPullResponse] | None = None
        self._ack_ids: list[str] = []
        self._healthy = False
        self._backoff = MIN_BACKOFF_INTERVAL

    async def start(self) -> None:
        """Start the subscription background task and wait for initial startup."""
        DIAGNOSTICS.increment("start")
        self._stream = await self._connect()
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
        self._subscriber_client = None

    async def _run_task(self) -> None:
        """"""
        try:
            await self._run()
        except asyncio.CancelledError:
            _LOGGER.debug("Subscription loop cancelled")
        except Exception as err:
            _LOGGER.info("Uncaught error in subscription loop: %s", err)
            DIAGNOSTICS.increment("uncaught_exception")
        self._healthy = False

    async def _run(self) -> None:
        """Run the subscription loop."""
        DIAGNOSTICS.increment("run")
        while True:
            if TYPE_CHECKING:
                assert self._stream is not None
            self._healthy = True
            _LOGGER.debug("Event stream connection established")
            try:
                async for response in self._stream:
                    _LOGGER.debug(
                        "Received %s messages", len(response.received_messages)
                    )
                    # Reset backoff anytime we receive messages
                    self._backoff = MIN_BACKOFF_INTERVAL
                    for received_message in response.received_messages:
                        if await self._process_message(received_message.message):
                            self._ack_ids.append(received_message.ack_id)
            except GoogleNestException as err:
                _LOGGER.debug("Disconnected from event stream: %s", err)
                DIAGNOSTICS.increment("exception")
            self._healthy = False
            self._subscriber_client = None

            while True:
                _LOGGER.debug(
                    "Reconnecting stream in %s seconds", self._backoff.total_seconds()
                )
                await asyncio.sleep(self._backoff.total_seconds())
                try:
                    self._stream = await self._connect()
                    break
                except GoogleNestException as err:
                    _LOGGER.debug("Error connecting to event stream: %s", err)
                    self._backoff = min(
                        self._backoff * BACKOFF_MULTIPLIER, MAX_BACKOFF_INTERVAL
                    )
                    DIAGNOSTICS.increment("backoff")

    async def _connect(self) -> AsyncIterable[pubsub_v1.types.StreamingPullResponse]:
        """Connect to the streaming pull."""
        _LOGGER.debug("Connecting with streaming pull")
        DIAGNOSTICS.increment("connect")
        self._subscriber_client = SubscriberClient(self._auth, self._subscription_name)
        return await self._subscriber_client.streaming_pull(self.pending_ack_ids)

    def pending_ack_ids(self) -> list[str]:
        """Generate the ack IDs for the next streaming pull request and clear."""
        ack_ids = [*self._ack_ids]
        self._ack_ids = []
        return ack_ids

    async def _process_message(self, message: pubsub_v1.types.PubsubMessage) -> bool:
        """Process an incoming message from the stream."""
        DIAGNOSTICS.increment("process_message")
        try:
            async with asyncio.timeout(MESSAGE_ACK_TIMEOUT_SECONDS):
                await self._callback(Message(message))
                return True
        except TimeoutError as err:
            DIAGNOSTICS.increment("process_message_timeout")
            _LOGGER.info("Unexpected timeout while processing message: %s", err)
            return False
        except Exception as err:
            DIAGNOSTICS.increment("process_message_exception")
            _LOGGER.info("Uncaught error while processing message: %s", err)
            return False
