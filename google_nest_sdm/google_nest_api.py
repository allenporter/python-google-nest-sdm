from typing import List

from .auth import AbstractAuth
from .device import Device


class GoogleNestAPI:
  """Class to communicate with the Google Nest SDM API."""

  def __init__(self, auth: AbstractAuth):
    """Initialize the API and store the auth so we can make requests."""
    self._auth = auth

  async def async_get_devices(self) -> List[Device]:
    """Return the devices."""
    resp = await self._auth.request("get", "devices")
    resp.raise_for_status()
    response_data = await resp.json()
    devices = response_data['devices']
    return [Device.MakeDevice(device_data, self._auth) for device_data in devices]

  async def async_get_device(self, device_id) -> Device:
    """Return a specific device."""
    resp = await self._auth.request("get", f"devices/{device_id}")
    resp.raise_for_status()
    return Device.MakeDevice(await resp.json(), self.auth)
