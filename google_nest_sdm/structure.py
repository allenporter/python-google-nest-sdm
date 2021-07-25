"""Traits for structures / rooms."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Optional, cast

from .registry import Registry
from .typing import cast_optional

STRUCTURE_NAME = "name"
STRUCTURE_TRAITS = "traits"
CUSTOM_NAME = "customName"

STRUCTURE_TRAITS_MAP = Registry()


class StructureTrait(ABC):
    """This trait belongs to any structure for structure-related information."""

    @property
    @abstractmethod
    def custom_name(self) -> Optional[str]:
        """Name of the structure."""


@STRUCTURE_TRAITS_MAP.register()
class InfoTrait(StructureTrait):
    """This trait belongs to any structure for structure-related information."""

    NAME = "sdm.structures.traits.Info"

    def __init__(self, data: Mapping[str, Any]):
        """Initialize InfoTrait."""
        self._data = data

    @property
    def custom_name(self) -> Optional[str]:
        """Name of the structure."""
        return cast_optional(str, self._data[CUSTOM_NAME])


@STRUCTURE_TRAITS_MAP.register()
class RoomInfoTrait(StructureTrait):
    """This trait belongs to any structure for room-related information."""

    NAME = "sdm.structures.traits.RoomInfo"

    def __init__(self, data: Mapping[str, Any]) -> None:
        """Initialize RoomInfoTrait."""
        self._data = data

    @property
    def custom_name(self) -> Optional[str]:
        """Name of the room."""
        return cast_optional(str, self._data[CUSTOM_NAME])


def _TraitsDict(
    traits: Mapping[str, Any], trait_map: Mapping[str, Any]
) -> Dict[str, StructureTrait]:
    result: Dict[str, StructureTrait] = {}
    for (trait, trait_data) in traits.items():
        if trait not in trait_map:
            continue
        cls = trait_map[trait]
        result[trait] = cls(trait_data)
    return result


class Structure:
    """Class that represents a structure object in the Google Nest SDM API."""

    def __init__(
        self, raw_data: Mapping[str, Any], traits: Mapping[str, StructureTrait]
    ) -> None:
        """Initialize a structure."""
        self._raw_data = raw_data
        self._traits = traits

    @staticmethod
    def MakeStructure(raw_data: Mapping[str, Any]) -> Structure:
        """Create a structure with the appropriate traits."""
        traits = raw_data.get(STRUCTURE_TRAITS, {})
        traits_dict = _TraitsDict(traits, STRUCTURE_TRAITS_MAP)
        return Structure(raw_data, traits_dict)

    @property
    def name(self) -> Optional[str]:
        """Resource name of the structure e.g. 'enterprises/XYZ/structures/123'."""
        return cast_optional(str, self._raw_data[STRUCTURE_NAME])

    @property
    def traits(self) -> Dict[str, StructureTrait]:
        """Return a trait mixin on None."""
        return dict(self._traits)

    def _traits_data(self, trait: Mapping[str, Any]) -> Dict[str, Any]:
        """Return the raw dictionary for the specified trait."""
        traits_dict = self._raw_data.get(STRUCTURE_TRAITS, {})
        return cast(Dict[str, Any], traits_dict.get(trait, {}))

    @property
    def raw_data(self) -> Dict[str, Any]:
        """Return raw data for the structure."""
        return dict(self._raw_data)
