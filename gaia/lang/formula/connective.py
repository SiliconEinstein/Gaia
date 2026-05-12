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
    """Logical conjunction over two or more Formula operands."""

    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate conjunction arity and operand formula markers."""
        if len(self.operands) < 2:
            raise ValueError("Land requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Land.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lor:
    """Logical disjunction over two or more Formula operands."""

    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate disjunction arity and operand formula markers."""
        if len(self.operands) < 2:
            raise ValueError("Lor requires at least two operands")
        for i, op in enumerate(self.operands):
            if not is_formula(op):
                raise TypeError(f"Lor.operands[{i}] is not a Formula: {op!r}")


@dataclass(frozen=True)
class Lnot:
    """Logical negation of a Formula operand."""

    operand: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate that the operand is a Formula."""
        _check_formula("operand", self.operand)


@dataclass(frozen=True)
class Implies:
    """Logical implication from antecedent Formula to consequent Formula."""

    antecedent: Any
    consequent: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate implication operands as Formula nodes."""
        _check_formula("antecedent", self.antecedent)
        _check_formula("consequent", self.consequent)


@dataclass(frozen=True)
class Iff:
    """Logical equivalence between two Formula operands."""

    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate equivalence operands as Formula nodes."""
        _check_formula("left", self.left)
        _check_formula("right", self.right)
