import aiohttp
import logging
from abc import ABC, abstractmethod
from google.auth.credentials import Credentials

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
    return None

  async def request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
    """Make a request."""
    headers = kwargs.get("headers")

    if headers is None:
      headers = {}
    else:
      headers = dict(headers)
      del kwargs['headers']

    access_token = await self.async_get_access_token()
    headers["authorization"] = f"Bearer {access_token}"
    url = f"{self._host}/{url}"
    logging.debug(f'request[{method}]={url}')
    return await self._websession.request(method, url, **kwargs,
        headers=headers)
