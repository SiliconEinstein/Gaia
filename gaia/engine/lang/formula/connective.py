"""Connectives — compound formulas built from sub-formulas.

Propositional connectives (``Land``, ``Lor``, ``Lnot``, ``Implies``, ``Iff``)
accept either Formula operands or raw ``Claim`` objects; the latter are
auto-wrapped as ``ClaimAtom(claim)`` to remove the boilerplate of writing
``ClaimAtom(...)`` explicitly at every reference site. Term-level predicates
(``Equals``, ``Greater``, ``UserPredicate``, ...) stay strict and accept Terms
only — coercion is intentionally scoped to propositional connectives where
``Claim`` operands are unambiguous.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from gaia.engine.lang.formula.predicate import is_formula


def _coerce_formula(name: str, value: object) -> Any:
    """Return a Formula node for ``value``.

    Already-formula inputs pass through unchanged. ``Claim`` operands are
    wrapped as ``ClaimAtom(value)`` so callers can write
    ``land(claim_a, claim_b)`` instead of
    ``land(ClaimAtom(claim_a), ClaimAtom(claim_b))``. Anything else raises
    ``TypeError`` — including ``Note``/``Question``/``Setting`` which lack
    well-defined propositional truth.
    """
    if is_formula(value):
        return value

    from gaia.engine.lang.formula.predicate import ClaimAtom
    from gaia.engine.lang.runtime.knowledge import Claim

    if isinstance(value, Claim):
        return ClaimAtom(value)
    raise TypeError(f"{name} is not a Formula: {value!r}")


@dataclass(frozen=True)
class Land:
    """Logical conjunction over two or more Formula operands."""

    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate conjunction arity and coerce/validate operand formulas."""
        if len(self.operands) < 2:
            raise ValueError("Land requires at least two operands")
        coerced = tuple(
            _coerce_formula(f"Land.operands[{i}]", op) for i, op in enumerate(self.operands)
        )
        if coerced != self.operands:
            object.__setattr__(self, "operands", coerced)


@dataclass(frozen=True)
class Lor:
    """Logical disjunction over two or more Formula operands."""

    operands: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate disjunction arity and coerce/validate operand formulas."""
        if len(self.operands) < 2:
            raise ValueError("Lor requires at least two operands")
        coerced = tuple(
            _coerce_formula(f"Lor.operands[{i}]", op) for i, op in enumerate(self.operands)
        )
        if coerced != self.operands:
            object.__setattr__(self, "operands", coerced)


@dataclass(frozen=True)
class Lnot:
    """Logical negation of a Formula operand."""

    operand: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Coerce/validate the operand as a Formula."""
        coerced = _coerce_formula("operand", self.operand)
        if coerced is not self.operand:
            object.__setattr__(self, "operand", coerced)


@dataclass(frozen=True)
class Implies:
    """Logical implication from antecedent Formula to consequent Formula."""

    antecedent: Any
    consequent: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Coerce/validate implication operands as Formula nodes."""
        coerced_antecedent = _coerce_formula("antecedent", self.antecedent)
        coerced_consequent = _coerce_formula("consequent", self.consequent)
        if coerced_antecedent is not self.antecedent:
            object.__setattr__(self, "antecedent", coerced_antecedent)
        if coerced_consequent is not self.consequent:
            object.__setattr__(self, "consequent", coerced_consequent)


@dataclass(frozen=True)
class Iff:
    """Logical equivalence between two Formula operands."""

    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Coerce/validate equivalence operands as Formula nodes."""
        coerced_left = _coerce_formula("left", self.left)
        coerced_right = _coerce_formula("right", self.right)
        if coerced_left is not self.left:
            object.__setattr__(self, "left", coerced_left)
        if coerced_right is not self.right:
            object.__setattr__(self, "right", coerced_right)
