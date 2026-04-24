"""Propositional logic backend for Gaia IR operator graphs."""

from __future__ import annotations

from typing import Any

from sympy import Symbol
from sympy.logic.boolalg import And, Equivalent, Implies, Not, Or, Xor
from sympy.logic.boolalg import simplify_logic as _sympy_simplify_logic
from sympy.logic.boolalg import to_cnf, to_dnf, to_nnf
from sympy.logic.inference import satisfiable

from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.operator import Operator, OperatorType
from gaia.ir.strategy import FormalStrategy


def _operator_value(operator: OperatorType | str) -> str:
    return str(operator)


def _operator_by_conclusion(graph: LocalCanonicalGraph) -> dict[str, Operator]:
    operators: dict[str, Operator] = {}

    def add(op: Operator) -> None:
        existing = operators.get(op.conclusion)
        if existing is not None and existing != op:
            raise ValueError(
                f"Multiple propositional operators conclude {op.conclusion!r}; "
                "cannot expand an unambiguous Boolean expression"
            )
        operators[op.conclusion] = op

    for op in graph.operators:
        add(op)
    for strategy in graph.strategies:
        if isinstance(strategy, FormalStrategy):
            for op in strategy.formal_expr.operators:
                add(op)
    return operators


def _knowledge_ids(graph: LocalCanonicalGraph) -> set[str]:
    return {k.id for k in graph.knowledges if k.id is not None}


def _to_sympy(
    graph: LocalCanonicalGraph,
    knowledge_id: str,
    *,
    operators: dict[str, Operator],
    known_ids: set[str],
    cache: dict[str, Any],
    stack: set[str],
) -> Any:
    if knowledge_id in cache:
        return cache[knowledge_id]

    if knowledge_id in stack:
        cycle = " -> ".join([*stack, knowledge_id])
        raise ValueError(f"Cycle while expanding propositional operator graph: {cycle}")

    op = operators.get(knowledge_id)
    if op is None:
        if knowledge_id not in known_ids:
            raise KeyError(f"Knowledge id not found in graph: {knowledge_id}")
        expr = Symbol(knowledge_id)
        cache[knowledge_id] = expr
        return expr

    stack.add(knowledge_id)
    args = [
        _to_sympy(
            graph,
            variable,
            operators=operators,
            known_ids=known_ids,
            cache=cache,
            stack=stack,
        )
        for variable in op.variables
    ]
    stack.remove(knowledge_id)

    match _operator_value(op.operator):
        case OperatorType.NEGATION:
            expr = Not(args[0])
        case OperatorType.CONJUNCTION:
            expr = And(*args)
        case OperatorType.DISJUNCTION:
            expr = Or(*args)
        case OperatorType.IMPLICATION:
            expr = Implies(args[0], args[1])
        case OperatorType.EQUIVALENCE:
            expr = Equivalent(args[0], args[1])
        case OperatorType.CONTRADICTION:
            expr = Not(And(args[0], args[1]))
        case OperatorType.COMPLEMENT:
            expr = Xor(args[0], args[1])
        case _:
            raise ValueError(f"Unsupported propositional operator: {op.operator!r}")

    cache[knowledge_id] = expr
    return expr


def to_sympy_proposition(graph: LocalCanonicalGraph, knowledge_id: str) -> Any:
    """Expand a Gaia knowledge id into a SymPy Boolean expression.

    Knowledge nodes that are not operator conclusions become atomic symbols. Operator
    conclusions are recursively expanded through Gaia's deterministic propositional
    operators. The returned SymPy object is a backend representation only; callers
    should not persist it in Gaia IR.
    """

    return _to_sympy(
        graph,
        knowledge_id,
        operators=_operator_by_conclusion(graph),
        known_ids=_knowledge_ids(graph),
        cache={},
        stack=set(),
    )


def simplify_proposition(
    graph: LocalCanonicalGraph, knowledge_id: str, *, force: bool = False
) -> Any:
    """Return SymPy's simplified Boolean form for a Gaia proposition."""

    return _sympy_simplify_logic(to_sympy_proposition(graph, knowledge_id), force=force)


def to_cnf_proposition(
    graph: LocalCanonicalGraph,
    knowledge_id: str,
    *,
    simplify: bool = False,
    force: bool = False,
) -> Any:
    """Return a CNF SymPy expression for a Gaia proposition."""

    return to_cnf(to_sympy_proposition(graph, knowledge_id), simplify=simplify, force=force)


def to_dnf_proposition(
    graph: LocalCanonicalGraph,
    knowledge_id: str,
    *,
    simplify: bool = False,
    force: bool = False,
) -> Any:
    """Return a DNF SymPy expression for a Gaia proposition."""

    return to_dnf(to_sympy_proposition(graph, knowledge_id), simplify=simplify, force=force)


def to_nnf_proposition(
    graph: LocalCanonicalGraph, knowledge_id: str, *, simplify: bool = True
) -> Any:
    """Return a negation-normal-form SymPy expression for a Gaia proposition."""

    return to_nnf(to_sympy_proposition(graph, knowledge_id), simplify=simplify)


def are_equivalent(
    graph: LocalCanonicalGraph,
    left_knowledge_id: str,
    right_knowledge_id: str,
) -> bool:
    """Return whether two Gaia propositions are logically equivalent."""

    left = to_sympy_proposition(graph, left_knowledge_id)
    right = to_sympy_proposition(graph, right_knowledge_id)
    return satisfiable(Xor(left, right)) is False


def is_satisfiable(graph: LocalCanonicalGraph, knowledge_id: str) -> bool:
    """Return whether a Gaia proposition has at least one satisfying assignment."""

    return satisfiable(to_sympy_proposition(graph, knowledge_id)) is not False
