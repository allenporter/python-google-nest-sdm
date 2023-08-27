"""Base library for all traits."""

from __future__ import annotations

from typing import Any, Mapping

import aiohttp

try:
    from pydantic.v1 import BaseModel
except ImportError:
    from pydantic import BaseModel  # type: ignore

from .auth import AbstractAuth
from .diagnostics import Diagnostics

DEVICE_TRAITS = "traits"
TRAITS = "traits"


class Command:
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


class CommandModel(BaseModel):
    """Base model that supports commands."""

    _cmd: Command | None = None
    """Helper for executing commands"""

    @property
    def cmd(self) -> Command:
        """Helper for executing commands, used internally by the trait"""
        if not self._cmd:
            raise ValueError("Device trait in invalid state")
        return self._cmd

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True
        fields = {
            "_cmd": {
                "exclude": True,
            },
        }
