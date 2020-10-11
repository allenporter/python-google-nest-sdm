from typing import List

from .auth import AbstractAuth
from .device import Device
from .structure import Structure


class GoogleNestAPI:
  """Class to communicate with the Google Nest SDM API."""

  def __init__(self, auth: AbstractAuth, project_id: str):
    """Initialize the API and store the auth so we can make requests."""
    self._auth = auth
    self._project_id = project_id

  @property
  def structures_url(self) -> str:
    return f'enterprises/{self._project_id}/structures'


  async def async_get_structures(self) -> List[Structure]:
    """Return the structures."""
    resp = await self._auth.request("get", self.structures_url)
    resp.raise_for_status()
    response_data = await resp.json()
    structures = response_data['structures']
    return [Structure.MakeStructure(structure_data)
                for structure_data in structures]

  async def async_get_structure(self, structure_id) -> Structure:
    """Return a structure device."""
    resp = await self._auth.request("get", structure_id)
    resp.raise_for_status()
    return Structure.MakeStructure(await resp.json())

  @property
  def devices_url(self) -> str:
    return f'enterprises/{self._project_id}/devices'

  async def async_get_devices(self) -> List[Device]:
    """Return the devices."""
    resp = await self._auth.request("get", self.devices_url)
    resp.raise_for_status()
    response_data = await resp.json()
    devices = response_data['devices']
    return [Device.MakeDevice(device_data, self._auth)
                for device_data in devices]

  async def async_get_device(self, device_id) -> Device:
    """Return a specific device."""
    resp = await self._auth.request("get", device_id)
    resp.raise_for_status()
    return Device.MakeDevice(await resp.json(), self._auth)
