"""Quantifiers — universal and existential binding of a Variable inside a body Formula."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

from gaia.lang.formula.predicate import is_formula
from gaia.lang.runtime.variable import Variable


def _check(variable: object, body: object) -> None:
    if not isinstance(variable, Variable):
        raise TypeError(f"variable must be a Variable, got {type(variable).__name__}")
    if variable.value is not None:
        raise ValueError(
            f"variable {variable.symbol!r} is already bound to a value; "
            "quantifiers must bind FREE variables"
        )
    if not is_formula(body):
        raise TypeError(f"body is not a Formula: {body!r}")


@dataclass(frozen=True)
class Forall:
    """Universal quantifier binding a free Variable in a Formula body."""

    variable: Variable
    body: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate the bound variable and body Formula."""
        _check(self.variable, self.body)


@dataclass(frozen=True)
class Exists:
    """Existential quantifier binding a free Variable in a Formula body."""

    variable: Variable
    body: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        """Validate the bound variable and body Formula."""
        _check(self.variable, self.body)
