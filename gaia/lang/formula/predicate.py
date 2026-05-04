"""Predicate — atomic formulas (truth-valued expressions over Terms or Claims).

Spec §3 typed-AST discipline: UserPredicate carries a PredicateSymbol reference
and validates arity + arg domains. Equals/Greater/etc. validate that operands
are Terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Protocol, runtime_checkable

from gaia.lang.formula.symbols import PredicateSymbol
from gaia.lang.formula.term import _term_domain, is_term
from gaia.lang.runtime.knowledge import Claim


@runtime_checkable
class Formula(Protocol):
    """Marker protocol — a truth-valued AST node."""

    __gaia_formula__: bool = True


def is_formula(obj: object) -> bool:
    return getattr(obj, "__gaia_formula__", False) is True


def _check_term(name: str, value: object) -> None:
    if not is_term(value):
        raise TypeError(f"{name} is not a Term: {value!r}")


@dataclass(frozen=True)
class Equals:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class NotEquals:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Greater:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class GreaterEqual:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class Less:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class LessEqual:
    left: Any
    right: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("left", self.left)
        _check_term("right", self.right)


@dataclass(frozen=True)
class UserPredicate:
    """Application of a user-declared PredicateSymbol to typed Term arguments."""

    symbol: PredicateSymbol
    args: tuple[Any, ...]
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, PredicateSymbol):
            raise TypeError(f"symbol must be a PredicateSymbol, got {type(self.symbol).__name__}")
        expected_arity = len(self.symbol.arg_domains)
        if len(self.args) != expected_arity:
            raise ValueError(
                f"UserPredicate arity mismatch: {self.symbol.name} expects "
                f"{expected_arity} args, got {len(self.args)}"
            )
        for i, (arg, expected_domain) in enumerate(zip(self.args, self.symbol.arg_domains)):
            if not is_term(arg):
                raise TypeError(f"UserPredicate argument {i} is not a Term: {arg!r}")
            actual = _term_domain(arg)
            if actual is not None and actual is not expected_domain:
                raise TypeError(
                    f"UserPredicate argument {i} domain mismatch: {self.symbol.name} expects "
                    f"{expected_domain}, got {actual}"
                )


@dataclass(frozen=True)
class Causes:
    """Built-in causal predicate. v0.5: marker; v0.6: interventional factor."""

    cause: Any
    effect: Any
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        _check_term("cause", self.cause)
        _check_term("effect", self.effect)


@dataclass(frozen=True)
class ClaimAtom:
    """A reference to another Claim's truth — the bridge from formula land to claim graph."""

    claim: Claim
    __gaia_formula__: ClassVar[bool] = True

    def __post_init__(self) -> None:
        if not isinstance(self.claim, Claim):
            raise TypeError(f"ClaimAtom requires a Claim instance, got {type(self.claim).__name__}")
