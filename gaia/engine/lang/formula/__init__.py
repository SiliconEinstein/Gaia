"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes."""

from gaia.engine.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.engine.lang.formula.predicate import (
    ClaimAtom,
    Equals,
    Formula,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
    is_formula,
)
from gaia.engine.lang.formula.primitives import Bool, Nat, PrimitiveType, Probability, Real
from gaia.engine.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.engine.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term


def __getattr__(name: str) -> object:
    if name in {"Exists", "Forall"}:
        from gaia.engine.lang.formula.quantifier import Exists, Forall

        exports = {"Exists": Exists, "Forall": Forall}
        globals().update(exports)
        return exports[name]
    raise AttributeError(f"module 'gaia.engine.lang.formula' has no attribute {name!r}")


__all__ = [
    "ArithOp",
    "Bool",
    "ClaimAtom",
    "Constant",
    "Equals",
    "Exists",
    "Forall",
    "Formula",
    "FunctionApp",
    "FunctionSymbol",
    "Greater",
    "GreaterEqual",
    "Iff",
    "Implies",
    "Land",
    "Less",
    "LessEqual",
    "Lnot",
    "Lor",
    "Nat",
    "NotEquals",
    "PredicateSymbol",
    "PrimitiveType",
    "Probability",
    "Real",
    "Term",
    "UserPredicate",
    "is_formula",
    "is_term",
]
