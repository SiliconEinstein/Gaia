"""Factor potential functions — theory 06-factor-graphs.md + IR infer CPT."""

from __future__ import annotations

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorType

__all__ = [
    "implication_potential",
    "conjunction_potential",
    "disjunction_potential",
    "equivalence_potential",
    "contradiction_potential",
    "complement_potential",
    "soft_entailment_potential",
    "conditional_potential",
    "evaluate_potential",
]

Assignment = dict[str, int]

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


def implication_potential(
    assignment: Assignment, antecedent: str, consequent: str, helper: str
) -> float:
    """Ternary implication with helper claim H.

    H=1 (implication holds): standard A=>B — forbid A=1,B=0.
    H=0 (implication fails): complement — forbid A=1,B=0 being HIGH.
    """
    a, b, h = assignment[antecedent], assignment[consequent], assignment[helper]
    if h == 1:
        # Standard implication: A=1,B=0 forbidden
        return _LOW if (a == 1 and b == 0) else _HIGH
    else:
        # Complement: A=1,B=0 is the only HIGH row
        return _HIGH if (a == 1 and b == 0) else _LOW


def conjunction_potential(assignment: Assignment, inputs: list[str], conclusion: str) -> float:
    """M = AND(inputs)."""
    all_one = all(assignment[v] == 1 for v in inputs)
    m = assignment[conclusion]
    ok = (all_one and m == 1) or ((not all_one) and m == 0)
    return _HIGH if ok else _LOW


def disjunction_potential(assignment: Assignment, inputs: list[str], conclusion: str) -> float:
    """D = OR(inputs)."""
    any_one = any(assignment[v] == 1 for v in inputs)
    d = assignment[conclusion]
    ok = (any_one and d == 1) or ((not any_one) and d == 0)
    return _HIGH if ok else _LOW


def equivalence_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Helper = (A == B)."""
    target = 1 if assignment[a] == assignment[b] else 0
    return _HIGH if assignment[conclusion] == target else _LOW


def contradiction_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Helper = NOT(A AND B) as binary: 0 iff both true."""
    both_one = assignment[a] == 1 and assignment[b] == 1
    target = 0 if both_one else 1
    return _HIGH if assignment[conclusion] == target else _LOW


def complement_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Helper = (A XOR B)."""
    target = 1 if assignment[a] != assignment[b] else 0
    return _HIGH if assignment[conclusion] == target else _LOW


def soft_entailment_potential(
    assignment: Assignment,
    premise: str,
    conclusion: str,
    p1: float,
    p2: float,
) -> float:
    """Theory §3.7: ψ on (M,C). Rows normalized per row for M."""
    m = assignment[premise]
    c = assignment[conclusion]
    if m == 1:
        return p1 if c == 1 else (1.0 - p1)
    return p2 if c == 0 else (1.0 - p2)


def conditional_potential(
    assignment: Assignment,
    premises: list[str],
    conclusion: str,
    cpt: tuple[float, ...],
) -> float:
    """P(C=1|parents) from CPT; idx = binary encoding in premise order."""
    idx = 0
    for i, v in enumerate(premises):
        if assignment[v] == 1:
            idx |= 1 << i
    p = cpt[idx]
    return p if assignment[conclusion] == 1 else (1.0 - p)


def evaluate_potential(factor: Factor, assignment: Assignment) -> float:
    ft = factor.factor_type
    v = factor.variables
    c = factor.conclusion

    if ft == FactorType.IMPLICATION:
        return implication_potential(assignment, v[0], v[1], c)

    if ft == FactorType.CONJUNCTION:
        return conjunction_potential(assignment, v, c)

    if ft == FactorType.DISJUNCTION:
        return disjunction_potential(assignment, v, c)

    if ft == FactorType.EQUIVALENCE:
        return equivalence_potential(assignment, v[0], v[1], c)

    if ft == FactorType.CONTRADICTION:
        return contradiction_potential(assignment, v[0], v[1], c)

    if ft == FactorType.COMPLEMENT:
        return complement_potential(assignment, v[0], v[1], c)

    if ft == FactorType.SOFT_ENTAILMENT:
        if factor.p1 is None or factor.p2 is None:
            raise ValueError(f"SOFT_ENTAILMENT '{factor.factor_id}' missing p1/p2.")
        return soft_entailment_potential(assignment, v[0], c, factor.p1, factor.p2)

    if ft == FactorType.CONDITIONAL:
        if factor.cpt is None:
            raise ValueError(f"CONDITIONAL '{factor.factor_id}' missing cpt.")
        return conditional_potential(assignment, v, c, factor.cpt)

    raise ValueError(f"Unknown FactorType: {ft!r}")
