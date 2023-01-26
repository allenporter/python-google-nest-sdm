"""Base model for all nest trait based classes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, root_validator

TRAITS = "traits"


class TraitModel(BaseModel):
    """Base model for API objects that are trait based.

    This is meant to be subclasses by the model definitions.
    """

    @property
    def traits(self) -> dict[str, Any]:
        """Return a trait mixin on None."""
        return {
            field.alias: getattr(self, field.name)
            for field in self.__fields__.values()
            if getattr(self, field.name) is not None
        }

    @root_validator(pre=True)
    def _parse_traits(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Parse traits as primary members of this class."""
        if traits := values.get(TRAITS):
            values.update(traits)
        return values

    class Config:
        extra = "allow"
