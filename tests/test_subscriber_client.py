from __future__ import annotations

from typing import Any
from unittest.mock import Mock, AsyncMock, patch

import pytest
from google.auth.exceptions import RefreshError, GoogleAuthError, TransportError
from google.api_core.exceptions import GoogleAPIError, NotFound, Unauthenticated

from google_nest_sdm.exceptions import (
    AuthException,
    SubscriberException,
    ConfigurationException,
)
from google_nest_sdm.subscriber_client import (
    refresh_creds,
    SubscriberClient,
    pull_request_generator,
)


async def test_refresh_creds() -> None:
    """Test low level refresh errors."""
    mock_refresh = Mock()
    mock_creds = Mock()
    mock_creds.refresh = mock_refresh
    refresh_creds(mock_creds)
    assert mock_refresh.call_count == 1


@pytest.mark.parametrize(
    ("raised", "expected"),
    [
        (RefreshError(), AuthException),  # type: ignore[no-untyped-call]
        (TransportError(), SubscriberException),  # type: ignore[no-untyped-call]
        (GoogleAuthError(), SubscriberException),  # type: ignore[no-untyped-call]
    ],
)
async def test_refresh_creds_error(raised: Exception, expected: Any) -> None:
    """Test low level refresh errors."""
    mock_refresh = Mock()
    mock_refresh.side_effect = raised
    mock_creds = Mock()
    mock_creds.refresh = mock_refresh
    with pytest.raises(expected):
        refresh_creds(mock_creds)


async def test_ack_no_messages() -> None:
    """Test ack with no messages to ack is a no-op."""

    client = SubscriberClient(auth=AsyncMock(), subscription_name="test")
    await client.ack_messages([])


async def test_ack_messages() -> None:
    """Test ack messages."""

    client = SubscriberClient(auth=AsyncMock(), subscription_name="test")
    with patch(
        "google_nest_sdm.subscriber_client.pubsub_v1.SubscriberAsyncClient"
    ) as mock_client:
        mock_acknowledge = AsyncMock()
        mock_acknowledge.return_value = None
        mock_client.return_value.acknowledge = mock_acknowledge
        await client.ack_messages(["message1", "message2"])

    # Verify that acknowledge was called with the correct arguments
    mock_acknowledge.assert_awaited_once_with(
        subscription="test", ack_ids=["message1", "message2"]
    )


async def test_streaming_pull() -> None:
    """Test streaming pull call."""

    client = SubscriberClient(auth=AsyncMock(), subscription_name="test")
    with patch(
        "google_nest_sdm.subscriber_client.pubsub_v1.SubscriberAsyncClient"
    ) as mock_client:
        mock_streaming_pull = AsyncMock()
        mock_streaming_pull.return_value = None
        mock_client.return_value.streaming_pull = mock_streaming_pull
        await client.streaming_pull(lambda: [])

    # Verify the call was invoked with the correct arguments
    mock_streaming_pull.assert_awaited_once()


@pytest.mark.parametrize(
    ("raised", "expected", "message"),
    [
        (
            NotFound("my error"),  # type: ignore[no-untyped-call]
            ConfigurationException,
            "NotFound error calling streaming_pull: 404 my error",
        ),
        (
            GoogleAPIError("my error"),
            SubscriberException,
            "API error when calling streaming_pull: my error",
        ),
        (
            Unauthenticated("auth error"),  # type: ignore[no-untyped-call]
            AuthException,
            "Failed to authenticate streaming_pull: 401 auth error",
        ),
        (
            Exception("my error"),
            SubscriberException,
            "Unexpected error when calling streaming_pull: my error",
        ),
    ],
)
async def test_streaming_pull_failure(
    raised: Exception, expected: Any, message: str
) -> None:
    """Test ack messages."""

    client = SubscriberClient(auth=AsyncMock(), subscription_name="test")
    with patch(
        "google_nest_sdm.subscriber_client.pubsub_v1.SubscriberAsyncClient"
    ) as mock_client:
        mock_streaming_pull = AsyncMock()
        mock_streaming_pull.side_effect = raised
        mock_client.return_value.streaming_pull = mock_streaming_pull

        with pytest.raises(expected, match=message):
            await client.streaming_pull(lambda: [])


async def test_request_generator() -> None:
    """Test the streaming pull request generator."""
    ack_ids = [
        ["ack-id-1", "ack-id-2"],
        ["ack-id-3", "ack-id-4"],
        [],
    ]
    with patch("asyncio.sleep", return_value=None):
        stream = pull_request_generator(
            "projects/some-project-id/subscriptions/sub-1", lambda: ack_ids.pop(0)
        )
        stream_iter = aiter(stream)
        request = await anext(stream_iter)
        assert request.subscription == "projects/some-project-id/subscriptions/sub-1"
        assert request.stream_ack_deadline_seconds == 180
        assert not request.ack_ids

        request = await anext(stream_iter)
        assert request.subscription == ""
        assert request.stream_ack_deadline_seconds == 180
        assert request.ack_ids == ["ack-id-1", "ack-id-2"]

        request = await anext(stream_iter)
        assert request.subscription == ""
        assert request.stream_ack_deadline_seconds == 180
        assert request.ack_ids == ["ack-id-3", "ack-id-4"]

        await stream.aclose()
