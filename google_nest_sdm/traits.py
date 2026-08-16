"""Base library for all traits."""

import datetime
import logging
from abc import ABC
from collections.abc import Mapping
from dataclasses import dataclass, field, fields
from enum import StrEnum
from typing import Any

import aiohttp
from mashumaro import DataClassDictMixin
from mashumaro.types import SerializableType

from .auth import AbstractAuth
from .diagnostics import Diagnostics
from .rate_limiter import RateLimiter

_LOGGER = logging.getLogger(__name__)

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

    def __init__(
        self,
        device_id: str,
        auth: AbstractAuth,
        diagnostics: Diagnostics,
        rate_limiter: RateLimiter | None = None,
    ):
        """Initialize Command."""
        self._device_id = device_id
        self._auth = auth
        self._diagnostics = diagnostics
        self._rate_limiter = rate_limiter or RateLimiter()

    @property
    def rate_limiter(self) -> RateLimiter:
        """Return the rate limiter for this command executor."""
        return self._rate_limiter

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


@dataclass
class BaseTrait(DataClassDictMixin):
    """Base class for all SDM traits."""

    _last_event_ts: datetime.datetime | None = field(
        init=False, default=None, metadata={"serialize": "omit"}
    )

    def handle_trait_update(
        self, new_trait: "BaseTrait", timestamp: datetime.datetime
    ) -> bool:
        """Update this trait from a newly parsed trait update."""
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=datetime.UTC)
        if self._last_event_ts and self._last_event_ts > timestamp:
            _LOGGER.debug("Discarding stale update (%s)", timestamp)
            return False
        for trait_field in fields(self):
            if (val := getattr(new_trait, trait_field.name)) is not None:
                setattr(self, trait_field.name, val)
        self._last_event_ts = timestamp
        return True

    @property
    def last_event_ts(self) -> datetime.datetime | None:
        """Timestamp of last event update."""
        if self._last_event_ts is None:
            return None
        if self._last_event_ts.tzinfo is None:
            return self._last_event_ts.replace(tzinfo=datetime.UTC)
        return self._last_event_ts


class CommandDataClass(BaseTrait, ABC):
    """Base model that supports commands."""

    def __post_init__(self) -> None:
        self._cmd: Command | None = None

    @property
    def cmd(self) -> Command:
        """Helper for executing commands, used internally by the trait"""
        if not self._cmd:
            raise ValueError("Device trait in invalid state")
        return self._cmd
