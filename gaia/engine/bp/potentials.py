"""Factor potential functions — theory 06-factor-graphs.md + IR infer CPT.

Jaynes class I (logical assertion) potentials are STRICT delta {0, 1};
Cromwell ε is reserved for class IV (unary soft evidence) only.

This file exposes _HIGH / _LOW historical aliases for backwards
compatibility with downstream callers that import them, but deterministic
operator potentials below use strict 0.0 / 1.0 — no Cromwell softening.
Soft factors (SOFT_ENTAILMENT / CONDITIONAL / PAIRWISE_POTENTIAL) carry
their own author-supplied probabilities and are unaffected.
"""

from __future__ import annotations

from gaia.engine.bp.factor_graph import CROMWELL_EPS, Factor, FactorType

__all__ = [
    "complement_potential",
    "conditional_potential",
    "conjunction_potential",
    "contradiction_potential",
    "disjunction_potential",
    "equivalence_potential",
    "evaluate_potential",
    "implication_potential",
    "negation_potential",
    "pairwise_potential",
    "soft_entailment_potential",
]

Assignment = dict[str, int]

_DELTA_HIGH: float = 1.0
_DELTA_LOW: float = 0.0

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


def implication_potential(
    assignment: Assignment, antecedent: str, consequent: str, helper: str
) -> float:
    """Compute potential for implication factor: A → B."""
    a, b, h = assignment[antecedent], assignment[consequent], assignment[helper]
    if h == 1:
        return _DELTA_LOW if (a == 1 and b == 0) else _DELTA_HIGH
    return _DELTA_HIGH if (a == 1 and b == 0) else _DELTA_LOW


def conjunction_potential(assignment: Assignment, inputs: list[str], conclusion: str) -> float:
    """Compute potential for conjunction factor: A ∧ B ∧ ...."""
    all_one = all(assignment[v] == 1 for v in inputs)
    m = assignment[conclusion]
    ok = (all_one and m == 1) or ((not all_one) and m == 0)
    return _DELTA_HIGH if ok else _DELTA_LOW


def negation_potential(assignment: Assignment, a: str, conclusion: str) -> float:
    """Compute potential for negation factor: ¬A."""
    target = 0 if assignment[a] == 1 else 1
    return _DELTA_HIGH if assignment[conclusion] == target else _DELTA_LOW


def disjunction_potential(assignment: Assignment, inputs: list[str], conclusion: str) -> float:
    """Compute potential for disjunction factor: A ∨ B ∨ ...."""
    any_one = any(assignment[v] == 1 for v in inputs)
    d = assignment[conclusion]
    ok = (any_one and d == 1) or ((not any_one) and d == 0)
    return _DELTA_HIGH if ok else _DELTA_LOW


def equivalence_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Compute potential for equivalence factor: A ↔ B."""
    target = 1 if assignment[a] == assignment[b] else 0
    return _DELTA_HIGH if assignment[conclusion] == target else _DELTA_LOW


def contradiction_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Compute potential for contradiction factor: A ⊕ B (XOR)."""
    both_one = assignment[a] == 1 and assignment[b] == 1
    target = 0 if both_one else 1
    return _DELTA_HIGH if assignment[conclusion] == target else _DELTA_LOW


def complement_potential(assignment: Assignment, a: str, b: str, conclusion: str) -> float:
    """Compute potential for complement factor: A + B = 1."""
    target = 1 if assignment[a] != assignment[b] else 0
    return _DELTA_HIGH if assignment[conclusion] == target else _DELTA_LOW


def soft_entailment_potential(
    assignment: Assignment,
    premise: str,
    conclusion: str,
    p1: float,
    p2: float,
) -> float:
    """Compute soft entailment potential with confidence parameter."""
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
    """Compute conditional probability potential P(B|A)."""
    idx = 0
    for i, v in enumerate(premises):
        if assignment[v] == 1:
            idx |= 1 << i
    p = cpt[idx]
    return p if assignment[conclusion] == 1 else (1.0 - p)


def pairwise_potential(
    assignment: Assignment,
    a: str,
    b: str,
    weights: tuple[float, ...],
) -> float:
    """Compute pairwise potential between two variables."""
    idx = assignment[a] | (assignment[b] << 1)
    return weights[idx]


def evaluate_potential(factor: Factor, assignment: Assignment) -> float:  # noqa: C901
    """Evaluate potential function for given factor type and variable assignment."""
    ft = factor.factor_type
    v = factor.variables
    c = factor.conclusion

    if ft == FactorType.IMPLICATION:
        return implication_potential(assignment, v[0], v[1], c)
    if ft == FactorType.CONJUNCTION:
        return conjunction_potential(assignment, v, c)
    if ft == FactorType.NEGATION:
        return negation_potential(assignment, v[0], c)
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
    if ft == FactorType.PAIRWISE_POTENTIAL:
        if factor.cpt is None:
            raise ValueError(f"PAIRWISE_POTENTIAL '{factor.factor_id}' missing cpt.")
        return pairwise_potential(assignment, v[0], c, factor.cpt)

    raise ValueError(f"Unknown FactorType: {ft!r}")
