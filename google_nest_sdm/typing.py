"""Libraries for helping with typing API responses."""

from typing import Any, Optional, Type, TypeVar

T = TypeVar("T")


def cast_assert(t: Type[T], data: Any) -> T:
    """Function to aid in extracting type values from API responses."""
    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
    return data


def cast_optional(t: Type[T], data: Any) -> Optional[T]:
    """Function to aid in extracting type values from API responses."""
    if data is None:
        return None
    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
    return data
