"""Gaia unit facade built on Pint."""

from __future__ import annotations

from typing import Any, TypeGuard

from pint import UnitRegistry

from gaia.ir import QuantityLiteral

ureg = UnitRegistry()
Quantity = type(ureg.Quantity(1, "dimensionless"))


def is_quantity(value: Any) -> TypeGuard[Quantity]:
    """Return True when value is a Quantity from Gaia's shared registry."""
    return isinstance(value, Quantity) and getattr(value, "_REGISTRY", None) is ureg


def q(value: float, unit: str) -> Quantity:
    """Create a Pint quantity using Gaia's shared unit registry."""
    return ureg.Quantity(value, unit)


def to_literal(quantity: Quantity) -> QuantityLiteral:
    """Convert a Gaia runtime quantity to the IR literal carrier."""
    if not is_quantity(quantity):
        raise TypeError("Expected a gaia.unit.Quantity from the shared registry")
    return QuantityLiteral(value=float(quantity.magnitude), unit=str(quantity.units))


def from_literal(literal: QuantityLiteral) -> Quantity:
    """Rehydrate an IR quantity literal into a runtime quantity."""
    return ureg.Quantity(literal.value, literal.unit)
