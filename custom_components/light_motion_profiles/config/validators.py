from typing import Any, Set, Callable, TypeVar

import voluptuous as vol


T = TypeVar("T")


class InvalidConfigError(Exception):
    pass


def unique_list(inner: Callable[[Any], T]) -> Callable[[Any], Set[T]]:
    def validator(data: Any) -> Set[T]:
        if not isinstance(data, list):
            raise vol.Invalid(f"Expected list found '{type(data).__name__}'")

        out = set(inner(d) for d in data)
        if len(out) != len(data):
            raise vol.Invalid("Duplicate values found in set!")
        return out

    return validator
