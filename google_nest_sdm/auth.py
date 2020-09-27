import aiohttp
from abc import ABC, abstractmethod

class AbstractAuth(ABC):
  """Abstract class to make authenticated requests."""

  def __init__(self, websession: aiohttp.ClientSession, host: str):
    """Initialize the auth."""
    self._websession = websession
    self._host = host

  @abstractmethod
  async def async_get_access_token(self) -> str:
    """Return a valid access token."""

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

    return await self._websession.request(
      method, f"{self._host}/{url}", **kwargs, headers=headers)
