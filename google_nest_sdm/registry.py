"""Decorator for creating a registry of objects."""

from __future__ import annotations

from typing import Callable, TypeVar, Any

CALLABLE_T = TypeVar("CALLABLE_T", bound=Callable)  # pylint: disable=invalid-name


class Registry(dict[str, Any]):
    """Registry of items."""

    def register(self, name: str | None = None) -> Callable[[CALLABLE_T], CALLABLE_T]:
        """Return decorator to register item with a specific name."""

        def decorator(func: CALLABLE_T) -> CALLABLE_T:
            """Register decorated function."""
            nonlocal name
            if name is None:
                name = func.NAME  # type: ignore
            self[name] = func
            return func

        return decorator
