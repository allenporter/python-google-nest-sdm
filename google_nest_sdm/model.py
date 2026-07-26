"""Base model for all nest trait based classes."""

from __future__ import annotations

from dataclasses import dataclass, fields
from mashumaro import DataClassDictMixin
from mashumaro.config import BaseConfig
from typing import Any, Mapping, Self


TRAITS = "traits"
SDM_PREFIX = "sdm."


@dataclass
class TraitDataClass(DataClassDictMixin):
    """Base model for API objects that are trait based.

    This is meant to be subclasses by the model definitions.
    """

    @classmethod
    def parse_trait_object(cls, raw_data: Mapping[str, Any]) -> Self:
        """Parse a new dataclass"""
        return cls.from_dict(
            {
                **raw_data,
                **raw_data.get(TRAITS, {}),
            }
        )

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
        result: dict[str, Any] = {}
        for k, v in self.to_dict(by_alias=True, omit_none=True).items():
            if k.startswith(SDM_PREFIX):
                if "traits" not in result:
                    result["traits"] = {}
                result["traits"][k] = v
            else:
                result[k] = v
        return result

    class Config(BaseConfig):
        code_generation_options = [
            "TO_DICT_ADD_BY_ALIAS_FLAG",
            "TO_DICT_ADD_OMIT_NONE_FLAG",
        ]
        serialize_by_alias = True
