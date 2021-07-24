"""Libraries for helping with typing API responses."""

from typing import TypeVar, Any, cast, Type, Optional


T = TypeVar("T")


def cast_assert(t: Type[T], data: Any) -> T:
    """Function to aid in extracting type values from API responses."""
    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
    return cast(T, data)


def cast_optional(t: Type[T], data: Any) -> Optional[T]:
    """Function to aid in extracting type values from API responses."""
    if data is None:
        return None
    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
    return data


# def cast_assert_generic(t: Type[T], data: Any) -> T:
#    """Function to aid in extracting type values from API responses."""
#    if isinstace(data,
#    assert isinstance(data, t), f"Expected data with type {t} but was {type(data)}"
#    return cast(T, data)
