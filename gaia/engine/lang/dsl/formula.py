"""Milestone B formula helper functions.

These helpers are intentionally thin: they construct the typed Formula AST
nodes introduced in Milestone A. Compiler lowering decides how those formulas
become IR.
"""

from __future__ import annotations

from typing import Any

from gaia.engine.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.engine.lang.formula.predicate import Equals
from gaia.engine.lang.formula.quantifier import Exists, Forall
from gaia.engine.lang.runtime.variable import Variable


def forall(variable: Variable, body: Any) -> Forall:
    """Create a universal quantifier over a free variable."""
    return Forall(variable=variable, body=body)


def exists(variable: Variable, body: Any) -> Exists:
    """Create an existential quantifier over a free variable."""
    return Exists(variable=variable, body=body)


def land(*operands: Any) -> Land:
    """Create a logical conjunction formula."""
    return Land(operands=tuple(operands))


def lor(*operands: Any) -> Lor:
    """Create a logical disjunction formula."""
    return Lor(operands=tuple(operands))


def lnot(operand: Any) -> Lnot:
    """Create a logical negation formula."""
    return Lnot(operand=operand)


def implies(antecedent: Any, consequent: Any) -> Implies:
    """Create an implication formula."""
    return Implies(antecedent=antecedent, consequent=consequent)


def iff(left: Any, right: Any) -> Iff:
    """Create an equivalence formula."""
    return Iff(left=left, right=right)


def equals(left: Any, right: Any) -> Equals:
    """Create an equality formula."""
    return Equals(left=left, right=right)
