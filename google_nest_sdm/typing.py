"""Libraries for helping with typing API responses."""

from typing import Any, Type, TypeVar

T = TypeVar("T")


def cast_assert(t: Type[T], data: Any) -> T:
    """Function to aid in extracting type values from API responses."""
    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
    return data
