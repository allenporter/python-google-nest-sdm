"""Authentication library, implemented by users of the API.

This library is a simple `aiohttp` that handles authentication when talking
to the API. Users are expected to provide their own implementation that provides
credentials obtained using the standard Google authentication approaches
described at https://developers.google.com/nest/device-access/api/authorization

An implementation of `AbstractAuth` implements `async_get_access_token`
to provide authentication credentials to the SDM library. The implementation is
responsible for managing the lifecycle of the token (any persistence needed,
or refresh to deal with expiration, etc).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from asyncio import TimeoutError
from typing import Any
from http import HTTPStatus

import aiohttp
from aiohttp.client_exceptions import ClientError
from google.auth.credentials import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials
from mashumaro.mixins.json import DataClassJSONMixin

from .exceptions import (
    ApiException,
    AuthException,
    ApiForbiddenException,
    NotFoundException,
)

_LOGGER = logging.getLogger(__name__)

__all__ = ["AbstractAuth"]

HTTP_UNAUTHORIZED = 401
AUTHORIZATION_HEADER = "Authorization"
ERROR = "error"
STATUS = "status"
MESSAGE = "message"


@dataclass
class Status(DataClassJSONMixin):
    """Status of the media item."""

    code: int = field(default=HTTPStatus.OK)
    """The status code, which should be an enum value of google.rpc.Code"""

    message: str | None = None
    """A developer-facing error message, which should be in English"""

    details: list[dict[str, Any]] = field(default_factory=list)
    """A list of messages that carry the error details"""


@dataclass
class Error:
    """Error details from the API response."""

    status: str | None = None
    code: int | None = None
    message: str | None = None
    details: list[dict[str, Any]] | None = field(default_factory=list)

    def __str__(self) -> str:
        """Return a string representation of the error details."""
        error_message = ""
        if self.status:
            error_message += self.status
        if self.code:
            if error_message:
                error_message += f" ({self.code})"
            else:
                error_message += str(self.code)
        if self.message:
            if error_message:
                error_message += ": "
            error_message += self.message
        if self.details:
            error_message += f"\nError details: ({self.details})"
        return error_message


@dataclass
class ErrorResponse(DataClassJSONMixin):
    """A response message that contains an error message."""

    error: Error | None = None


class AbstractAuth(ABC):
    """Abstract class to make authenticated requests."""

    def __init__(self, websession: aiohttp.ClientSession, host: str):
        """Initialize the AbstractAuth."""
        self._websession = websession
        self._host = host

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def async_get_creds(self) -> Credentials:
        """Return creds for subscriber API."""
        token = await self.async_get_access_token()
        return OAuthCredentials(token=token)  # type: ignore[no-untyped-call]

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> aiohttp.ClientResponse:
        """Make a request."""
        headers = kwargs.get("headers")

        if headers is None:
            headers = {}
        else:
            headers = dict(headers)
            del kwargs["headers"]
        if AUTHORIZATION_HEADER not in headers:
            try:
                access_token = await self.async_get_access_token()
            except TimeoutError as err:
                raise ApiException(f"Timeout requesting API token: {err}") from err
            except ClientError as err:
                raise AuthException(f"Access token failure: {err}") from err
            headers[AUTHORIZATION_HEADER] = f"Bearer {access_token}"
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self._host}/{url}"
        _LOGGER.debug("request[%s]=%s", method, url)
        if method == "post" and "json" in kwargs:
            _LOGGER.debug("request[post json]=%s", kwargs["json"])
        try:
            return await self._request(method, url, headers=headers, **kwargs)
        except (ClientError, TimeoutError) as err:
            raise ApiException(f"Error connecting to API: {err}") from err

    async def _request(
        self, method: str, url: str, headers: dict[str, str], **kwargs: Any
    ) -> aiohttp.ClientResponse:
        return await self._websession.request(method, url, **kwargs, headers=headers)

    async def get(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a get request."""
        response = await self.request("get", url, **kwargs)
        return await AbstractAuth._raise_for_status(response)

    async def get_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Make a get request and return json response."""
        resp = await self.get(url, **kwargs)
        try:
            result = await resp.json()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        if not isinstance(result, dict):
            raise ApiException("Server return malformed response: %s" % result)
        _LOGGER.debug("response=%s", result)
        return result

    async def post(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a post request."""
        response = await self.request("post", url, **kwargs)
        return await AbstractAuth._raise_for_status(response)

    async def post_json(self, url: str, **kwargs: Any) -> dict[str, Any]:
        """Make a post request and return a json response."""
        resp = await self.post(url, **kwargs)
        try:
            result = await resp.json()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        if not isinstance(result, dict):
            raise ApiException("Server returned malformed response: %s" % result)
        _LOGGER.debug("response=%s", result)
        return result

    async def put(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a put request."""
        response = await self.request("put", url, **kwargs)
        return await AbstractAuth._raise_for_status(response)

    async def delete(self, url: str, **kwargs: Any) -> aiohttp.ClientResponse:
        """Make a delete request."""
        response = await self.request("delete", url, **kwargs)
        return await AbstractAuth._raise_for_status(response)

    @classmethod
    async def _raise_for_status(
        cls, resp: aiohttp.ClientResponse
    ) -> aiohttp.ClientResponse:
        """Raise exceptions on failure methods."""
        error_detail = await cls._error_detail(resp)
        try:
            resp.raise_for_status()
        except aiohttp.ClientResponseError as err:
            error_message = f"{err.message} response from API ({resp.status})"
            if error_detail:
                error_message += f": {error_detail}"
            if err.status == HTTPStatus.FORBIDDEN:
                raise ApiForbiddenException(error_message)
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise AuthException(error_message)
            if err.status == HTTPStatus.NOT_FOUND:
                raise NotFoundException(error_message)
            raise ApiException(error_message) from err
        except aiohttp.ClientError as err:
            raise ApiException(f"Error from API: {err}") from err
        return resp

    @classmethod
    async def _error_detail(cls, resp: aiohttp.ClientResponse) -> Error | None:
        """Returns an error message string from the APi response."""
        if resp.status < 400:
            return None
        try:
            result = await resp.text()
        except ClientError:
            return None
        try:
            error_response = ErrorResponse.from_json(result)
        except (LookupError, ValueError):
            return None
        return error_response.error
