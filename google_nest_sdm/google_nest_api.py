"""Library to access the Smart Device Management API."""
from typing import List, Optional

from .auth import AbstractAuth
from .device import Device
from .structure import Structure

STRUCTURES = "structures"
DEVICES = "devices"
NAME = "name"


class GoogleNestAPI:
    """Class to communicate with the Google Nest SDM API."""

    def __init__(self, auth: AbstractAuth, project_id: str):
        """Initialize the API and store the auth so we can make requests."""
        self._auth = auth
        self._project_id = project_id

    @property
    def _structures_url(self) -> str:
        return f"enterprises/{self._project_id}/structures"

    async def async_get_structures(self) -> List[Structure]:
        """Return the structures."""
        resp = await self._auth.get(self._structures_url)
        response_data = await resp.json()
        if STRUCTURES not in response_data:
            return []
        structures = response_data[STRUCTURES]
        return [
            Structure.MakeStructure(structure_data) for structure_data in structures
        ]

    async def async_get_structure(self, structure_id: str) -> Optional[Structure]:
        """Return a structure device."""
        resp = await self._auth.get(f"{self._structures_url}/{structure_id}")
        data = await resp.json()
        if NAME not in data:
            return None
        return Structure.MakeStructure(data)

    @property
    def _devices_url(self) -> str:
        return f"enterprises/{self._project_id}/devices"

    async def async_get_devices(self) -> List[Device]:
        """Return the devices."""
        resp = await self._auth.get(self._devices_url)
        response_data = await resp.json()
        if DEVICES not in response_data:
            return []
        devices = response_data[DEVICES]
        return [Device.MakeDevice(device_data, self._auth) for device_data in devices]

    async def async_get_device(self, device_id: str) -> Optional[Device]:
        """Return a specific device."""
        resp = await self._auth.get(f"{self._devices_url}/{device_id}")
        data = await resp.json()
        if NAME not in data:
            return None
        return Device.MakeDevice(data, self._auth)
