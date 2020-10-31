"""Traits belonging to doorbell devices."""

from .traits import TRAIT_MAP, Command


@TRAIT_MAP.register()
class DoorbellChimeTrait:
    """For any device that supports a doorbell chime and related press events."""

    NAME = "sdm.devices.traits.DoorbellChime"

    def __init__(self, data: dict, cmd: Command):
        """Initialize DoorbellChime."""
        self._data = data
        self._cmd = cmd
