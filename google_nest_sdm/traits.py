"""Base library for all traits."""

from __future__ import annotations

from abc import ABC
from enum import StrEnum
from typing import Any, Mapping

import aiohttp
from mashumaro.types import SerializableType

from .auth import AbstractAuth
from .diagnostics import Diagnostics

DEVICE_TRAITS = "traits"
TRAITS = "traits"


class TraitType(StrEnum):
    """Traits for SDM devices."""

    CAMERA_IMAGE = "sdm.devices.traits.CameraImage"
    CAMERA_LIVE_STREAM = "sdm.devices.traits.CameraLiveStream"
    CAMERA_EVENT_IMAGE = "sdm.devices.traits.CameraEventImage"
    CAMERA_MOTION = "sdm.devices.traits.CameraMotion"
    CAMERA_PERSON = "sdm.devices.traits.CameraPerson"
    CAMERA_SOUND = "sdm.devices.traits.CameraSound"
    CAMERA_CLIP_PREVIEW = "sdm.devices.traits.CameraClipPreview"
    CONNECTIVITY = "sdm.devices.traits.Connectivity"
    FAN = "sdm.devices.traits.Fan"
    INFO = "sdm.devices.traits.Info"
    HUMIDITY = "sdm.devices.traits.Humidity"
    TEMPERATURE = "sdm.devices.traits.Temperature"
    DOORBELL_CHIME = "sdm.devices.traits.DoorbellChime"
    THERMOSTAT_ECO = "sdm.devices.traits.ThermostatEco"
    THERMOSTAT_HVAC = "sdm.devices.traits.ThermostatHvac"
    THERMOSTAT_MODE = "sdm.devices.traits.ThermostatMode"
    THERMOSTAT_TEMPERATURE_SETPOINT = "sdm.devices.traits.ThermostatTemperatureSetpoint"


class Command(SerializableType):
    """Base class for executing commands."""

    def __init__(self, device_id: str, auth: AbstractAuth, diagnostics: Diagnostics):
        """Initialize Command."""
        self._device_id = device_id
        self._auth = auth
        self._diagnostics = diagnostics

    async def execute(self, data: Mapping[str, Any]) -> aiohttp.ClientResponse:
        """Run the command."""
        assert self._auth
        cmd = data.get("command", "execute")
        with self._diagnostics.timer(cmd):
            return await self._auth.post(f"{self._device_id}:executeCommand", json=data)

    async def execute_json(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Run the command and return a json result."""
        assert self._auth
        cmd = data.get("command", "execute")
        with self._diagnostics.timer(cmd):
            return await self._auth.post_json(
                f"{self._device_id}:executeCommand", json=data
            )

    async def fetch_image(self, url: str, basic_auth: str | None = None) -> bytes:
        """Fetch an image at the specified url."""
        headers: dict[str, Any] = {}
        if basic_auth:
            headers = {"Authorization": f"Basic {basic_auth}"}
        with self._diagnostics.timer("fetch_image"):
            resp = await self._auth.get(url, headers=headers)
            return await resp.read()


class CommandDataClass(ABC):
    """Base model that supports commands."""

    def __post_init__(self) -> None:
        self._cmd: Command | None = None

    @property
    def cmd(self) -> Command:
        """Helper for executing commands, used internally by the trait"""
        if not self._cmd:
            raise ValueError("Device trait in invalid state")
        return self._cmd
