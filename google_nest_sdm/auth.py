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
from asyncio import TimeoutError
from typing import Any, Mapping

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.credentials import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials

from .exceptions import ApiException, AuthException

_LOGGER = logging.getLogger(__name__)

__all__ = ["AbstractAuth"]

HTTP_UNAUTHORIZED = 401
AUTHORIZATION_HEADER = "Authorization"
ERROR = "error"
STATUS = "status"
MESSAGE = "message"


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
        return OAuthCredentials(token=token)

    async def request(
        self,
        method: str,
        url: str,
        **kwargs: Mapping[str, Any] | None,
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
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        **kwargs: Mapping[str, Any] | None,
    ) -> aiohttp.ClientResponse:
        return await self._websession.request(method, url, **kwargs, headers=headers)

    async def get(
        self, url: str, **kwargs: Mapping[str, Any]
    ) -> aiohttp.ClientResponse:
        """Make a get request."""
        resp = await self.request("get", url, **kwargs)
        return await AbstractAuth._raise_for_status(resp)

    async def get_json(self, url: str, **kwargs: Mapping[str, Any]) -> dict[str, Any]:
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

    async def post(
        self, url: str, **kwargs: Mapping[str, Any]
    ) -> aiohttp.ClientResponse:
        """Make a post request."""
        resp = await self.request("post", url, **kwargs)
        return await AbstractAuth._raise_for_status(resp)

    async def post_json(self, url: str, **kwargs: Mapping[str, Any]) -> dict[str, Any]:
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

    @staticmethod
    async def _raise_for_status(resp: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        """Raise exceptions on failure methods."""
        detail = await AbstractAuth._error_detail(resp)
        try:
            resp.raise_for_status()
        except ClientResponseError as err:
            if err.status == HTTP_UNAUTHORIZED:
                raise AuthException(f"Unable to authenticate with API: {err}") from err
            detail.append(err.message)
            raise ApiException(": ".join(detail)) from err
        except ClientError as err:
            raise ApiException(f"Error from API: {err}") from err
        return resp

    @staticmethod
    async def _error_detail(resp: aiohttp.ClientResponse) -> list[str]:
        """Returns an error message string from the APi response."""
        if resp.status < 400:
            return []
        try:
            result = await resp.json()
            error = result.get(ERROR, {})
        except ClientError:
            return []
        message = ["Error from API", f"{resp.status}"]
        if STATUS in error:
            message.append(f"{error[STATUS]}")
        if MESSAGE in error:
            message.append(error[MESSAGE])
        return message
