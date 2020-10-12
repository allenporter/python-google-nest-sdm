"""Traits for structures / rooms."""

STRUCTURE_NAME = "name"
STRUCTURE_TRAITS = "traits"
CUSTOM_NAME = "customName"


class InfoTrait:
    """This trait belongs to any structure for structure-related information."""

    NAME = "sdm.structures.traits.Info"

    def __init__(self, data: dict):
        self._data = data

    @property
    def custom_name(self) -> str:
        """Custom name of the structure."""
        return self._data[CUSTOM_NAME]


class RoomInfoTrait:
    """This trait belongs to any structure for room-related information."""

    NAME = "sdm.structures.traits.RoomInfo"

    def __init__(self, data: dict):
        self._data = data

    @property
    def custom_name(self) -> str:
        """Custom name of the room."""
        return self._data[CUSTOM_NAME]


_ALL_TRAITS = [
    InfoTrait,
    RoomInfoTrait,
]
_ALL_TRAIT_MAP = {cls.NAME: cls for cls in _ALL_TRAITS}


def _TraitsDict(traits: dict, trait_map: dict):
    result = {}
    for (trait, trait_data) in traits.items():
        if not trait in trait_map:
            continue
        cls = trait_map[trait]
        result[trait] = cls(trait_data)
    return result


class Structure:
    """Class that represents a structure object in the Google Nest SDM API."""

    def __init__(self, raw_data: dict, traits: dict):
        """Initialize a structure."""
        self._raw_data = raw_data
        self._traits = traits

    @staticmethod
    def MakeStructure(raw_data: dict):
        """Creates a structure with the appropriate traits."""
        traits = raw_data.get(STRUCTURE_TRAITS, {})
        traits_dict = _TraitsDict(traits, _ALL_TRAIT_MAP)
        return Structure(raw_data, traits_dict)

    @property
    def name(self) -> str:
        """The resource name of the structure such as 'enterprises/XYZ/structures/123'."""
        return self._raw_data[STRUCTURE_NAME]

    @property
    def traits(self) -> dict:
        """Return a trait mixin on None."""
        return self._traits

    def _traits_data(self, trait) -> dict:
        """Return the raw dictionary for the specified trait."""
        traits_dict = self._raw_data.get(STRUCTURE_TRAITS, {})
        return traits_dict.get(trait, {})
