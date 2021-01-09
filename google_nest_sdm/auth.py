"""Authentication library, implemented by users of the API."""
import logging
from abc import ABC, abstractmethod

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError
from google.auth.credentials import Credentials
from google.oauth2.credentials import Credentials as OAuthCredentials

from .exceptions import ApiException, AuthException

HTTP_UNAUTHORIZED = 401
AUTHORIZATION_HEADER = "Authorization"


class AbstractAuth(ABC):
    """Abstract class to make authenticated requests."""

    def __init__(self, websession: aiohttp.ClientSession, host: str):
        """Initialize the auth."""
        self._websession = websession
        self._host = host

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def async_get_creds(self) -> Credentials:
        """Return creds for subscriber API."""
        token = await self.async_get_access_token()
        return OAuthCredentials(token=token)

    async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
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
            except ClientError as err:
                raise AuthException(f"Access token failure: {err}") from err
            headers[AUTHORIZATION_HEADER] = f"Bearer {access_token}"
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self._host}/{url}"
        logging.debug("request[%s]=%s", method, url)
        return await self._websession.request(method, url, **kwargs, headers=headers)

    async def get(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a get request."""
        try:
            resp = await self.request("get", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return AbstractAuth.raise_for_status(resp)

    async def post(self, url: str, **kwargs) -> aiohttp.ClientResponse:
        """Make a post request."""
        try:
            resp = await self.request("post", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return AbstractAuth.raise_for_status(resp)

    @staticmethod
    def raise_for_status(resp: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        """Raise exceptions on failure methods."""
        try:
            resp.raise_for_status()
        except ClientResponseError as err:
            if err.status == HTTP_UNAUTHORIZED:
                raise AuthException(f"Unable to authenticate with API: {err}") from err
            raise ApiException(f"Error from API: {err}") from err
        except ClientError as err:
            raise ApiException(f"Error from API: {err}") from err
        return resp
