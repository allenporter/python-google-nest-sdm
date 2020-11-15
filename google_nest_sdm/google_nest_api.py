"""Library to access the Smart Device Management API."""
from typing import List

from aiohttp.client_exceptions import ClientError

from .auth import AbstractAuth
from .device import Device
from .exceptions import ApiException
from .structure import Structure


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
        resp = await self._auth.request("get", self._structures_url)
        try:
            resp.raise_for_status()
        except ClientError as err:
            raise ApiException("Error fetching structures") from err
        response_data = await resp.json()
        structures = response_data["structures"]
        return [
            Structure.MakeStructure(structure_data) for structure_data in structures
        ]

    async def async_get_structure(self, structure_id) -> Structure:
        """Return a structure device."""
        resp = await self._auth.request("get", structure_id)
        try:
            resp.raise_for_status()
        except ClientError as err:
            raise ApiException("Error fetching structure") from err
        return Structure.MakeStructure(await resp.json())

    @property
    def _devices_url(self) -> str:
        return f"enterprises/{self._project_id}/devices"

    async def async_get_devices(self) -> List[Device]:
        """Return the devices."""
        resp = await self._auth.request("get", self._devices_url)
        try:
            resp.raise_for_status()
        except ClientError as err:
            raise ApiException("Error fetching devices") from err
        response_data = await resp.json()
        devices = response_data["devices"]
        return [Device.MakeDevice(device_data, self._auth) for device_data in devices]

    async def async_get_device(self, device_id) -> Device:
        """Return a specific device."""
        resp = await self._auth.request("get", device_id)
        try:
            resp.raise_for_status()
        except ClientError as err:
            raise ApiException("Error fetching device") from err
        return Device.MakeDevice(await resp.json(), self._auth)
