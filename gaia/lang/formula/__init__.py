"""Gaia Lang Formula AST — typed term, predicate, connective, quantifier nodes.

Type discipline (spec §3): AST nodes carry references to PrimitiveType /
FunctionSymbol / PredicateSymbol — not name strings — and validate at construction.
"""

from gaia.lang.formula.symbols import FunctionSymbol, PredicateSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp, Term, is_term

__all__ = [
    # symbols
    "FunctionSymbol",
    "PredicateSymbol",
    # term
    "Term",
    "Constant",
    "FunctionApp",
    "ArithOp",
    "is_term",
]
