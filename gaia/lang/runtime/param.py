"""Parameterization primitives for Gaia Lang v6."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class _Unbound:
    """Sentinel for unbound parameters. Not None."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNBOUND"

    def __bool__(self) -> bool:
        return False


UNBOUND = _Unbound()


@dataclass
class Param:
    """A single parameter in a parameterized Knowledge type."""

    name: str
    type: type
    value: Any = field(default_factory=lambda: UNBOUND)
