"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes."""

from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import (
    Causes,
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
from gaia.lang.formula.quantifier import Exists, Forall
from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    "ArithOp",
    "Causes",
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
    "NotEquals",
    "PredicateSymbol",
    "Term",
    "UserPredicate",
    "is_formula",
    "is_term",
]
