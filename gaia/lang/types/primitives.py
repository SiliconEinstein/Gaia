"""Built-in primitive type tokens for Gaia Lang.

A primitive type is a runtime singleton that knows its name and how to validate
a candidate value. Authors reference the four built-ins (Nat, Real, Probability,
Bool); they do not construct PrimitiveType instances directly.
"""

from __future__ import annotations

from collections.abc import Callable

_SEALED = False


class PrimitiveType:
    """A built-in typed sort. Construction is sealed once the module finishes loading."""

    __slots__ = ("name", "_accept")

    def __init__(self, name: str, accept: Callable[[object], bool]) -> None:
        if _SEALED:
            raise TypeError(
                "PrimitiveType is sealed. Use the four built-ins: Nat, Real, Probability, Bool."
            )
        self.name = name
        self._accept = accept

    def accepts(self, value: object) -> bool:
        return self._accept(value)

    def __repr__(self) -> str:
        return self.name

    def __reduce__(self) -> tuple[Callable[[str], PrimitiveType], tuple[str]]:
        return (_lookup_primitive, (self.name,))


def _is_nat(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _is_real(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _is_probability(v: object) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool) and 0.0 <= v <= 1.0


def _is_bool(v: object) -> bool:
    return isinstance(v, bool)


Nat = PrimitiveType("Nat", _is_nat)
Real = PrimitiveType("Real", _is_real)
Probability = PrimitiveType("Probability", _is_probability)
Bool = PrimitiveType("Bool", _is_bool)


_BY_NAME = {p.name: p for p in (Nat, Real, Probability, Bool)}


def _lookup_primitive(name: str) -> PrimitiveType:
    return _BY_NAME[name]


_SEALED = True
