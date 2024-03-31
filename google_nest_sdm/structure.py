"""Traits for structures / rooms."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from mashumaro import field_options

from .model import TraitDataClass


@dataclass
class InfoTrait:
    """This trait belongs to any structure for structure-related information."""

    custom_name: str | None = field(
        metadata=field_options(alias="customName"), default=None
    )
    """Name of the structure."""


@dataclass
class RoomInfoTrait:
    """This trait belongs to any structure for room-related information."""

    custom_name: str = field(metadata=field_options(alias="customName"))
    """Name of the structure."""


@dataclass
class Structure(TraitDataClass):
    """Class that represents a structure object in the Google Nest SDM API."""

    name: str
    """Resource name of the structure e.g. 'enterprises/XYZ/structures/123'."""

    info: InfoTrait | None = field(
        metadata=field_options(alias="sdm.structures.traits.Info"), default=None
    )
    room_info: RoomInfoTrait | None = field(
        metadata=field_options(alias="sdm.structures.traits.RoomInfo"), default=None
    )

    @classmethod
    def MakeStructure(cls, raw_data: Mapping[str, Any]) -> Structure:
        """Create a structure with the appropriate traits."""
        return cls.parse_trait_object(raw_data)
