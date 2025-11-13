from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, TypeVar, TypeGuard
from unittest.mock import Mock, patch, AsyncMock
from collections.abc import AsyncGenerator, Generator
import datetime

import pytest
from google.api_core.exceptions import ClientError, Unauthenticated, GoogleAPIError
from google.cloud import pubsub_v1

from google_nest_sdm import diagnostics
from google_nest_sdm.auth import AbstractAuth
from google_nest_sdm.exceptions import (
    AuthException,
    SubscriberException,
)
from google_nest_sdm.streaming_manager import (
    StreamingManager,
    Message,
    encode_pubsub_message,
)

from .conftest import DeviceHandler, assert_diagnostics

_LOGGER = logging.getLogger(__name__)

PROJECT_ID = "project-id1"
SUBSCRIPTION_NAME = "projects/some-project-id/subscriptions/subscriber-id1"

_T = TypeVar("_T")


def object_is(obj: Any, value: _T) -> TypeGuard[_T]:
    """Assertion hack to workaround https://github.com/python/mypy/issues/11969"""
    return obj is value


class MessageQueue:
    """A queue of messages to simulate a pubsub subscription."""

    def __init__(self) -> None:
        self.event = asyncio.Event()
        self.messages: list[pubsub_v1.types.PubsubMessage] = []
        self.errors: list[Exception] = []
        self.next_ack_id = 0

    async def async_push_events(
        self, events: list[Dict[str, Any]], sleep: bool = True
    ) -> None:
        """Push an event into the queue."""
        for event in events:
            _LOGGER.debug("Pushing event %s", event)
            self.messages.append(encode_pubsub_message(event))
        self.event.set()
        if sleep:
            await asyncio.sleep(0)

    async def async_push_errors(self, errors: list[Exception]) -> None:
        """Push an event into the queue."""
        _LOGGER.debug("Pushing errors")
        self.errors.extend(errors)
        self.event.set()
        await asyncio.sleep(0)

    async def __aiter__(
        self,
    ) -> AsyncGenerator[pubsub_v1.types.StreamingPullResponse, None]:
        """Get a message from the queue."""
        while True:
            _LOGGER.debug("Waiting for message")
            await self.event.wait()
            if self.errors:
                _LOGGER.debug("Raising error for StreamingPullResponse")
                raise self.errors.pop(0)
            messages = [*self.messages]
            self.messages.clear()
            self.event.clear()
            _LOGGER.debug("Streaming Pull Response has %d messages", len(messages))
            yield pubsub_v1.types.StreamingPullResponse(
                received_messages=[
                    pubsub_v1.types.ReceivedMessage(
                        ack_id=self.next_id(),
                        message=message,
                        delivery_attempt=1,
                    )
                    for message in messages
                ]
            )

    def next_id(self) -> str:
        """Generate a new ack ID."""
        ack_id = f"ack-{self.next_ack_id}"
        self.next_ack_id += 1
        return ack_id


@pytest.fixture(name="message_queue")
def mock_pubsub_queue() -> MessageQueue:
    """Fixture to allow tests to add messages to the pubsub feed."""
    return MessageQueue()


@pytest.fixture(name="pull_exception")
def mock_pull_exception() -> Exception | list[Exception] | None:
    """Fixture to allow tests to add messages to the pubsub feed."""
    return None


@pytest.fixture(name="callback_exception")
def mock_callback_exception() -> Exception | None:
    """Fixture to allow tests to add messages to the pubsub feed."""
    return None


@pytest.fixture(name="subscriber_async_client")
def mock_subscriber_async_client(
    message_queue: MessageQueue,
    pull_exception: Exception | list[Exception] | None,
) -> Generator[Mock, None, None]:
    """Fixture to mock the subscriber."""

    with patch(
        "google_nest_sdm.subscriber_client.pubsub_v1.SubscriberAsyncClient"
    ) as mock:

        def pull_result(**kwargs: Any) -> Any:
            if pull_exception is not None:
                if not isinstance(pull_exception, list):
                    raise pull_exception
                else:
                    exc = pull_exception.pop(0)
                    if exc is not None:
                        raise exc
            return message_queue

        mock_pull = AsyncMock()
        mock_pull.side_effect = pull_result
        mock.return_value.streaming_pull = mock_pull
        mock.return_value.acknowledge = AsyncMock()
        yield mock


@pytest.fixture(name="messages_received")
def messages_received() -> list[Message]:
    """Fixture to allow tests to add messages to the pubsub feed."""
    return []


@pytest.fixture(name="factory")
def mock_streaming_manager_factory(
    subscriber_async_client: Mock,
    auth_client: Callable[[], Awaitable[AbstractAuth]],
    messages_received: list[Message],
    callback_exception: Exception | None,
) -> Generator[Callable[[], Awaitable[StreamingManager]], None, None]:
    async def create() -> StreamingManager:
        auth = await auth_client()

        async def callback(message: Message) -> None:
            if callback_exception:
                raise callback_exception
            _LOGGER.debug("Received message %s", message)
            messages_received.append(message)

        return StreamingManager(auth, SUBSCRIPTION_NAME, callback)

    with patch(
        "google_nest_sdm.streaming_manager.MIN_BACKOFF_INTERVAL",
        datetime.timedelta(seconds=0),
    ):
        yield create


async def test_subscribe_no_events(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
) -> None:
    streaming_manager = await factory()
    await streaming_manager.start()
    assert object_is(streaming_manager.healthy, True)
    streaming_manager.stop()
    assert object_is(streaming_manager.healthy, False)


async def test_events_received_at_start(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
) -> None:
    streaming_manager = await factory()

    await message_queue.async_push_events(
        [
            {"eventId": "1"},
            {"eventId": "2"},
        ]
    )
    await streaming_manager.start()
    await asyncio.sleep(0)  # yield to background task

    assert len(messages_received) == 2
    assert messages_received[0].payload == {"eventId": "1"}
    assert messages_received[1].payload == {"eventId": "2"}
    assert object_is(streaming_manager.healthy, True)
    streaming_manager.stop()
    assert object_is(streaming_manager.healthy, False)

    assert streaming_manager.pending_ack_ids() == ["ack-0", "ack-1"]
    assert not streaming_manager.pending_ack_ids()


async def test_events_received_after_start(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
) -> None:
    streaming_manager = await factory()
    await streaming_manager.start()

    await message_queue.async_push_events([{"eventId": "1"}])

    assert len(messages_received) == 1
    assert messages_received[0].payload == {"eventId": "1"}
    streaming_manager.stop()

    assert streaming_manager.pending_ack_ids() == ["ack-0"]
    assert not streaming_manager.pending_ack_ids()


async def test_cancel_after_message_received(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
) -> None:
    streaming_manager = await factory()
    await streaming_manager.start()

    await message_queue.async_push_events([{"eventId": "1"}], sleep=False)
    streaming_manager.stop()
    await asyncio.sleep(0)

    assert len(messages_received) == 0
    assert not streaming_manager.pending_ack_ids()
    streaming_manager.stop()


@pytest.mark.parametrize(
    ("pull_exception", "expected", "metrics"),
    [
        (
            Unauthenticated("Error"),  # type: ignore[no-untyped-call]
            AuthException,
            {"streaming_pull.unauthenticated": 1},
        ),
        (
            GoogleAPIError("Error"),  # type: ignore[no-untyped-call]
            SubscriberException,
            {"streaming_pull.api_error": 1},
        ),
        (
            ClientError("Error"),  # type: ignore[no-untyped-call]
            SubscriberException,
            {"streaming_pull.api_error": 1},
        ),
    ],
)
async def test_start_exception(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    expected: type[Exception],
    metrics: dict[str, int],
) -> None:
    streaming_manager = await factory()

    with pytest.raises(expected):
        await streaming_manager.start()
        assert object_is(streaming_manager.healthy, False)

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "connect": 1,
                "start": 1,
            },
            "subscriber": {
                **metrics,
            },
        },
    )

    streaming_manager.stop()


async def test_run_loop_exception(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
) -> None:
    streaming_manager = await factory()
    await message_queue.async_push_errors([Unauthenticated("Auth error")])  # type: ignore[no-untyped-call]

    await streaming_manager.start()
    await asyncio.sleep(0)  # yield to wake background task
    await asyncio.sleep(0)  # yield to sleep on retry

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "exception": 1,
                "connect": 2,
                "run": 1,
                "start": 1,
            },
            "subscriber": {"streaming_iterator.unauthenticated": 1},
        },
    )

    # Stream recovers and is still healthy
    assert object_is(streaming_manager.healthy, True)
    streaming_manager.stop()
    assert object_is(streaming_manager.healthy, False)


@pytest.mark.parametrize(
    ("callback_exception", "metrics"),
    [
        (AuthException(), {"process_message_exception": 1}),
        (TimeoutError(), {"process_message_timeout": 1}),
    ],
)
async def test_callback_exception(
    device_handler: DeviceHandler,
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
    metrics: dict[str, int],
) -> None:
    streaming_manager = await factory()
    await message_queue.async_push_events([{"eventId": "1"}])

    await streaming_manager.start()
    await asyncio.sleep(0)  # yield to background task

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "connect": 1,
                "run": 1,
                "start": 1,
                "process_message": 1,
                **metrics,
            }
        },
    )
    assert object_is(streaming_manager.healthy, True)
    assert not streaming_manager.pending_ack_ids()

    streaming_manager.stop()


@pytest.mark.parametrize(
    ("pull_exception"),
    [
        ([None, GoogleAPIError("Error"), None]),
    ],
)
async def test_reconnect_exception(
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
    messages_received: list[Message],
) -> None:
    streaming_manager = await factory()

    await streaming_manager.start()
    await message_queue.async_push_events([{"eventId": "1"}])
    assert object_is(streaming_manager.healthy, True)

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "connect": 1,
                "run": 1,
                "start": 1,
                "process_message": 1,
            }
        },
    )

    # Fail the active streaming pull. The next attempt to connect will also
    # fail because of the pull_exceptiopn fixture above.
    await message_queue.async_push_errors([SubscriberException("Error")])

    assert object_is(streaming_manager.healthy, False)
    await asyncio.sleep(0)  # yield to sleep on retry

    # Track next attempt to connect
    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "backoff": 1,
                "connect": 2,
                "exception": 1,
                "run": 1,
                "start": 1,
                "process_message": 1,
            },
            "subscriber": {
                "streaming_iterator.api_error": 1,
                "streaming_pull.api_error": 1,
            },
        },
    )

    # Verify that new messages can be processed after reconnect
    await message_queue.async_push_events([{"eventId": "2"}])
    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "backoff": 1,
                "connect": 3,
                "exception": 1,
                "run": 1,
                "start": 1,
                "process_message": 2,
            },
            "subscriber": {
                "streaming_iterator.api_error": 1,
                "streaming_pull.api_error": 1,
            },
        },
    )
    assert object_is(streaming_manager.healthy, True)

    streaming_manager.stop()
    assert object_is(streaming_manager.healthy, False)

    assert len(messages_received) == 2
    assert messages_received[0].payload == {"eventId": "1"}
    assert messages_received[1].payload == {"eventId": "2"}


async def test_uncaught_streaming_pull_exception(
    factory: Callable[[], Awaitable[StreamingManager]],
    message_queue: MessageQueue,
) -> None:
    streaming_manager = await factory()

    await streaming_manager.start()
    assert object_is(streaming_manager.healthy, True)
    await message_queue.async_push_errors([Exception("Error")])
    assert object_is(streaming_manager.healthy, False)

    assert_diagnostics(
        diagnostics.get_diagnostics(),
        {
            "streaming_manager": {
                "connect": 1,
                "run": 1,
                "start": 1,
                "exception": 1,
            },
            "subscriber": {
                "streaming_iterator.api_error": 1,
            },
        },
    )

    streaming_manager.stop()
