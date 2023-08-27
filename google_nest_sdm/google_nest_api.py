"""Library to access the Smart Device Management API."""

from .auth import AbstractAuth
from .device import Device
from .structure import Structure

__all__ = ["GoogleNestAPI"]

STRUCTURES = "structures"
DEVICES = "devices"
NAME = "name"


class GoogleNestAPI:
    """Client library to communicate with the Google Nest SDM API."""

    def __init__(self, auth: AbstractAuth, project_id: str):
        """Initialize the API and store the auth so we can make requests."""
        self._auth = auth
        self._project_id = project_id

    @property
    def _structures_url(self) -> str:
        return f"enterprises/{self._project_id}/structures"

    async def async_get_structures(self) -> list[Structure]:
        """Return the structures."""
        response_data = await self._auth.get_json(self._structures_url)
        if STRUCTURES not in response_data:
            return []
        structures = response_data[STRUCTURES]
        return [
            Structure.MakeStructure(structure_data) for structure_data in structures
        ]

    async def async_get_structure(self, structure_id: str) -> Structure | None:
        """Return a structure device."""
        data = await self._auth.get_json(f"{self._structures_url}/{structure_id}")
        if NAME not in data:
            return None
        return Structure.MakeStructure(data)

    @property
    def _devices_url(self) -> str:
        return f"enterprises/{self._project_id}/devices"

    async def async_get_devices(self) -> list[Device]:
        """Return the devices."""
        response_data = await self._auth.get_json(self._devices_url)
        if DEVICES not in response_data:
            return []
        devices = response_data[DEVICES]
        return [Device.MakeDevice(device_data, self._auth) for device_data in devices]

    async def async_get_device(self, device_id: str) -> Device | None:
        """Return a specific device."""
        data = await self._auth.get_json(f"{self._devices_url}/{device_id}")
        if NAME not in data:
            return None
        return Device.MakeDevice(data, self._auth)
