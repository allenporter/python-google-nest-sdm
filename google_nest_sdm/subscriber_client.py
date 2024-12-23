"""Pub/sub subscriber client library."""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, AsyncIterable, Any
from collections.abc import AsyncIterator

from aiohttp.client_exceptions import ClientError
from google.api_core.exceptions import GoogleAPIError, NotFound, Unauthenticated
from google.auth.exceptions import RefreshError, GoogleAuthError, TransportError
from google.auth.transport.requests import Request
from google import pubsub_v1
from google.oauth2.credentials import Credentials

from .auth import AbstractAuth
from .diagnostics import SUBSCRIBER_DIAGNOSTICS as DIAGNOSTICS
from .exceptions import (
    AuthException,
    ConfigurationException,
    SubscriberException,
)

_LOGGER = logging.getLogger(__name__)


RPC_TIMEOUT_SECONDS = 10.0
STREAM_ACK_TIMEOUT_SECONDS = 30.0


def refresh_creds(creds: Credentials) -> Credentials:
    """Refresh credentials.

    This is not part of the subscriber API, exposed only to facilitate testing.
    """
    try:
        creds.refresh(Request())
    except RefreshError as err:
        raise AuthException(f"Authentication refresh failure: {err}") from err
    except TransportError as err:
        raise SubscriberException(
            f"Connectivity error during authentication refresh: {err}"
        ) from err
    except GoogleAuthError as err:
        raise SubscriberException(
            f"Error during authentication refresh: {err}"
        ) from err
    return creds


def exception_handler[
    _T: Any
](func_name: str) -> Callable[..., Callable[..., Awaitable[_T]]]:
    """Wrap a function with exception handling."""

    def wrapped(func: Callable[..., Awaitable[_T]]) -> Callable[..., Awaitable[_T]]:

        async def wrapped_func(*args: Any, **kwargs: Any) -> _T:
            try:
                async with asyncio.timeout(RPC_TIMEOUT_SECONDS):
                    return await func(*args, **kwargs)
            except asyncio.TimeoutError as err:
                _LOGGER.debug("Timeout in %s: %s", func_name, err)
                DIAGNOSTICS.increment(f"{func_name}.timeout")
                raise SubscriberException(f"Timeout in {func_name}") from err
            except NotFound as err:
                _LOGGER.debug("NotFound error in %s: %s", func_name, err)
                DIAGNOSTICS.increment(f"{func_name}.not_found_error")
                raise ConfigurationException(
                    f"NotFound error calling {func_name}: {err}"
                ) from err
            except Unauthenticated as err:
                _LOGGER.debug(
                    "Failed to authenticate subscriber in %s: %s", func_name, err
                )
                DIAGNOSTICS.increment(f"{func_name}.unauthenticated")
                raise AuthException(f"Failed to authenticate {func_name}: {err}") from err
            except GoogleAPIError as err:
                _LOGGER.debug("API error in %s: %s", func_name, err)
                DIAGNOSTICS.increment(f"{func_name}.api_error")
                raise SubscriberException(
                    f"API error when calling {func_name}: {err}"
                ) from err
            except Exception as err:
                _LOGGER.debug("Uncaught error in %s: %s", func_name, err)
                DIAGNOSTICS.increment(f"{func_name}.api_error")
                raise SubscriberException(
                    f"Unexpected error when calling {func_name}: {err}"
                ) from err

        return wrapped_func

    return wrapped


class SubscriberClient:
    """Pub/sub subscriber client library."""

    def __init__(
        self,
        auth: AbstractAuth,
        subscription_name: str,
    ) -> None:
        """Initialize the SubscriberClient."""
        self._auth = auth
        self._subscription_name = subscription_name
        self._client: pubsub_v1.SubscriberAsyncClient | None = None
        self._creds: Credentials | None = None

    async def _async_get_client(self) -> pubsub_v1.SubscriberAsyncClient:
        """Create the Pub/Sub client library."""
        if self._client is None or self._creds is None or self._creds.expired:
            try:
                creds = await self._auth.async_get_creds()
            except ClientError as err:
                DIAGNOSTICS.increment("create_subscription.creds_error")
                raise AuthException(f"Access token failure: {err}") from err
            self._creds = creds
            self._client = pubsub_v1.SubscriberAsyncClient(credentials=self._creds)
        return self._client

    @exception_handler(func_name="streaming_pull")
    async def streaming_pull(
        self,
    ) -> AsyncIterable[pubsub_v1.types.StreamingPullResponse]:
        """Start the streaming pull."""

        async def _request_generator() -> AsyncIterator[pubsub_v1.StreamingPullRequest]:
            while True:
                yield pubsub_v1.StreamingPullRequest(
                    subscription=self._subscription_name,
                    stream_ack_deadline_seconds=STREAM_ACK_TIMEOUT_SECONDS,
                )

        client = await self._async_get_client()
        _LOGGER.debug("Sending streaming pull request for %s", self._subscription_name)
        return await client.streaming_pull(requests=_request_generator())

    @exception_handler("acknowledge")
    async def ack_messages(self, ack_ids: list[str]) -> None:
        """Acknowledge messages."""
        if not ack_ids:
            return
        client = await self._async_get_client()
        _LOGGER.debug("Acking %s messages", len(ack_ids))
        await client.acknowledge(
            subscription=self._subscription_name,
            ack_ids=ack_ids,
        )
