"""Traits for structures / rooms."""

from __future__ import annotations

from typing import Any, Final, Mapping

try:
    from pydantic.v1 import BaseModel, Field
except ImportError:
    from pydantic import BaseModel, Field  # type: ignore

from .model import TraitModel


class StructureTrait(BaseModel):
    """This trait belongs to any structure for structure-related information."""

    custom_name: str = Field(alias="customName")
    """Name of the structure."""


class InfoTrait(StructureTrait):
    """This trait belongs to any structure for structure-related information."""

    NAME: Final = "sdm.structures.traits.Info"


class RoomInfoTrait(StructureTrait):
    """This trait belongs to any structure for room-related information."""

    NAME: Final = "sdm.structures.traits.RoomInfo"


class Structure(TraitModel):
    """Class that represents a structure object in the Google Nest SDM API."""

    name: str
    """Resource name of the structure e.g. 'enterprises/XYZ/structures/123'."""

    info: InfoTrait | None = Field(alias="sdm.structures.traits.Info")
    room_info: RoomInfoTrait | None = Field(alias="sdm.structures.traits.RoomInfo")

    @staticmethod
    def MakeStructure(raw_data: Mapping[str, Any]) -> Structure:
        """Create a structure with the appropriate traits."""
        return Structure.parse_obj(raw_data)
