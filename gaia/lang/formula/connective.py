"""Connectives — compound formulas built from sub-formulas."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from gaia.lang.formula.predicate import is_formula


def _check_formula(name: str, value: object) -> None:
    if not is_formula(value):
        raise TypeError(f"{name} is not a Formula: {value!r}")


@dataclass(frozen=True)
class Land:
    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Land requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Land.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lor:
    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if len(self.operands) < 2:
            raise ValueError("Lor requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Lor.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lnot:
    operand: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_formula("operand", self.operand)


@dataclass(frozen=True)
class Implies:
    antecedent: Any
    consequent: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_formula("antecedent", self.antecedent)
        _check_formula("consequent", self.consequent)


@dataclass(frozen=True)
class Iff:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_formula("left", self.left)
        _check_formula("right", self.right)
