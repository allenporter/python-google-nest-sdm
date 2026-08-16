"""Traits for thermostats."""

import asyncio
import datetime
import logging
from dataclasses import dataclass, field
from typing import Any, ClassVar, Final, Self

import aiohttp
from mashumaro import field_options

from .traits import BaseTrait, CommandDataClass, TraitType

__all__ = [
    "ThermostatEcoTrait",
    "ThermostatHvacTrait",
    "ThermostatModeTrait",
    "ThermostatTemperatureSetpointTrait",
]

_LOGGER = logging.getLogger(__name__)

STATUS: Final = "status"
AVAILABLE_MODES: Final = "availableModes"
MODE: Final = "mode"
OPTIMISTIC_EXPIRY_SECONDS: Final = 30.0


@dataclass(frozen=True)
class PendingSetpoint:
    """Represents a setpoint modification waiting to be dispatched."""

    heat_celsius: float | None = None
    cool_celsius: float | None = None
    timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @property
    def is_expired(self) -> bool:
        """Return True if this setpoint has exceeded the optimistic expiry window."""
        now = datetime.datetime.now(datetime.UTC)
        return (now - self.timestamp).total_seconds() > OPTIMISTIC_EXPIRY_SECONDS

    def merge(self, other: Self) -> Self:
        """Merge a new setpoint request into this pending setpoint."""
        return self.__class__(
            heat_celsius=(
                other.heat_celsius
                if other.heat_celsius is not None
                else self.heat_celsius
            ),
            cool_celsius=(
                other.cool_celsius
                if other.cool_celsius is not None
                else self.cool_celsius
            ),
            timestamp=other.timestamp,
        )

    def as_command(self) -> dict[str, Any]:
        """Convert this pending setpoint into an SDM API command payload."""
        if self.heat_celsius is not None and self.cool_celsius is not None:
            return {
                "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetRange",
                "params": {
                    "heatCelsius": self.heat_celsius,
                    "coolCelsius": self.cool_celsius,
                },
            }

        if self.heat_celsius is not None:
            return {
                "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetHeat",
                "params": {"heatCelsius": self.heat_celsius},
            }

        if self.cool_celsius is not None:
            return {
                "command": "sdm.devices.commands.ThermostatTemperatureSetpoint.SetCool",
                "params": {"coolCelsius": self.cool_celsius},
            }

        raise ValueError("Invalid pending setpoint state: neither heat nor cool is set")


@dataclass
class ThermostatEcoTrait(CommandDataClass):
    """This trait belongs to any device that has a sensor to measure temperature."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_ECO

    available_modes: list[str] = field(
        metadata=field_options(alias="availableModes"), default_factory=list
    )
    """List of supported Eco modes."""

    mode: str = field(metadata=field_options(alias="mode"), default="OFF")
    """Eco mode of the thermostat."""

    heat_celsius: float | None = field(
        metadata=field_options(alias="heatCelsius"), default=None
    )
    """Lowest temperature where thermostat begins heating."""

    cool_celsius: float | None = field(
        metadata=field_options(alias="coolCelsius"), default=None
    )
    """Highest cooling temperature where thermostat begins cooling."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatEco.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@dataclass
class ThermostatHvacTrait(BaseTrait):
    """This trait belongs to devices that can report HVAC details."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_HVAC

    status: str
    """HVAC status of the thermostat."""


@dataclass
class ThermostatModeTrait(CommandDataClass):
    """This trait belongs to devices that support different thermostat modes."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_MODE

    available_modes: list[str] = field(metadata=field_options(alias="availableModes"))
    """List of supported thermostat modes."""

    mode: str = field(metadata=field_options(alias="mode"))
    """Mode of the thermostat."""

    async def set_mode(self, mode: str) -> aiohttp.ClientResponse:
        """Change the thermostat Eco mode."""
        data = {
            "command": "sdm.devices.commands.ThermostatMode.SetMode",
            "params": {"mode": mode},
        }
        return await self.cmd.execute(data)


@dataclass
class ThermostatTemperatureSetpointTrait(CommandDataClass):
    """This trait belongs to devices that support setting target temperature."""

    NAME: ClassVar[TraitType] = TraitType.THERMOSTAT_TEMPERATURE_SETPOINT

    _heat_celsius: float | None = field(
        metadata=field_options(alias="heatCelsius"), default=None
    )
    """Lowest temperature where thermostat begins heating."""

    _cool_celsius: float | None = field(
        metadata=field_options(alias="coolCelsius"), default=None
    )
    """Highest cooling temperature where thermostat begins cooling."""

    def __post_init__(self) -> None:
        self._cmd = None
        self._optimistic: PendingSetpoint | None = None
        self._pending_setpoint: PendingSetpoint | None = None
        self._pending_future: asyncio.Future[aiohttp.ClientResponse] | None = None
        self._lock: asyncio.Lock | None = None

    @property
    def heat_celsius(self) -> float | None:
        """Lowest temperature where thermostat begins heating."""
        if self._optimistic and not self._optimistic.is_expired:
            return self._optimistic.heat_celsius
        return self._heat_celsius

    @property
    def cool_celsius(self) -> float | None:
        """Highest cooling temperature where thermostat begins cooling."""
        if self._optimistic and not self._optimistic.is_expired:
            return self._optimistic.cool_celsius
        return self._cool_celsius

    def handle_trait_update(
        self, new_trait: BaseTrait, timestamp: datetime.datetime
    ) -> bool:
        """Update this trait from a newly parsed trait update."""
        if not super().handle_trait_update(new_trait, timestamp):
            return False
        self._optimistic = None
        return True

    def _update_optimistic(self, setpoint: PendingSetpoint) -> None:
        """Update optimistic values from pending setpoint."""
        self._optimistic = (
            self._optimistic.merge(setpoint) if self._optimistic else setpoint
        )

    async def _handle_setpoint_request(
        self, setpoint: PendingSetpoint
    ) -> aiohttp.ClientResponse:
        """Handle incoming setpoint change with coalescing and blocking dispatch."""
        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            self._update_optimistic(setpoint)
            self._pending_setpoint = (
                self._pending_setpoint.merge(setpoint)
                if self._pending_setpoint
                else setpoint
            )

            if self._pending_future and not self._pending_future.done():
                future = self._pending_future
                is_leader = False
            else:
                loop = asyncio.get_running_loop()
                future = loop.create_future()
                self._pending_future = future
                is_leader = True

        if not is_leader:
            return await future

        try:
            await self.cmd.rate_limiter.acquire()
            async with self._lock:
                to_send = self._pending_setpoint
                self._pending_setpoint = None
                self._pending_future = None

            assert to_send is not None
            response = await self.cmd.execute(to_send.as_command())
            future.set_result(response)
            return response
        except BaseException as err:
            self._optimistic = None
            if not future.done():
                future.set_exception(err)
            # Consume the exception on the future so asyncio GC doesn't warn
            # when only the leader was present, while followers still receive it on await.
            future.exception()
            raise

    async def set_heat(self, heat: float) -> aiohttp.ClientResponse:
        """Set the heat temperature setpoint."""
        return await self._handle_setpoint_request(PendingSetpoint(heat_celsius=heat))

    async def set_cool(self, cool: float) -> aiohttp.ClientResponse:
        """Set the cool temperature setpoint."""
        return await self._handle_setpoint_request(PendingSetpoint(cool_celsius=cool))

    async def set_range(self, heat: float, cool: float) -> aiohttp.ClientResponse:
        """Set the heat and cool temperature range setpoints."""
        return await self._handle_setpoint_request(
            PendingSetpoint(heat_celsius=heat, cool_celsius=cool)
        )
