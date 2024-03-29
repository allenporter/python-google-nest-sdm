"""Base model for all nest trait based classes."""

from __future__ import annotations

from dataclasses import dataclass, fields
from mashumaro import DataClassDictMixin
from typing import Any, Mapping

try:
    from pydantic.v1 import BaseModel, root_validator
except ImportError:
    from pydantic import BaseModel, root_validator  # type: ignore


TRAITS = "traits"
SDM_PREFIX = "sdm."


class TraitModel(BaseModel):
    """Base model for API objects that are trait based.

    This is meant to be subclasses by the model definitions.
    """

    _EXCLUDE_FIELDS = set(
        {
            "_trait_event_ts",
        }
    )

    def __init__(self, **data: Any):
        """Initialize TraitModel."""
        super().__init__(**data)

    @property
    def traits(self) -> dict[str, Any]:
        """Return a trait mixin on None."""
        return {
            field.alias: getattr(self, field.name)
            for field in self.__fields__.values()
            if getattr(self, field.name) is not None
            and field.alias.startswith(SDM_PREFIX)
        }

    @root_validator(pre=True)
    def _parse_traits(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse traits as primary members of this class."""
        if traits := values.get(TRAITS):
            values.update(traits)
        return values

    @property
    def raw_data(self) -> dict[str, Any]:
        """Return raw data for the object."""
        return self.dict(
            by_alias=True,
            exclude=self._EXCLUDE_FIELDS,
            exclude_unset=True,
            exclude_defaults=True,
        )

    class Config:
        extra = "allow"


@dataclass
class TraitDataClass(DataClassDictMixin):
    """Base model for API objects that are trait based.

    This is meant to be subclasses by the model definitions.
    """

    _EXCLUDE_FIELDS = set(
        {
            "_trait_event_ts",
        }
    )

    @classmethod
    def parse_trait_object(cls, raw_data: Mapping[str, Any]) -> TraitDataClass:
        """Parse a new dataclass"""
        data = {
            **raw_data,
        }
        data.update(raw_data.get(TRAITS, {}))
        return cls.from_dict(data)

    @property
    def traits(self) -> dict[str, Any]:
        """Return a trait mixin on None."""
        return {
            alias: value
            for field in fields(self)
            if (alias := field.metadata.get("alias")) is not None
            and (value := getattr(self, field.name)) is not None
            and alias.startswith(SDM_PREFIX)
        }

    @property
    def raw_data(self) -> dict[str, Any]:
        """Return raw data for the object."""
        return {
            k: v
            for k, v in self.to_dict(by_alias=True, omit_none=True)
            if k not in self._EXCLUDE_FIELDS
        }
