"""Gaia Lang v5 — Operator functions (deterministic logical constraints)."""

from gaia.lang.runtime import Knowledge, Operator


def contradiction(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """not(A and B). Creates Operator, returns helper claim."""
    helper = Knowledge(
        content=f"not_both_true({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata={"helper_kind": "contradiction_result"},
    )
    Operator(operator="contradiction", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def equivalence(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """A = B. Creates Operator, returns helper claim."""
    helper = Knowledge(
        content=f"same_truth({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata={"helper_kind": "equivalence_result"},
    )
    Operator(operator="equivalence", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def complement(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """A != B (XOR). Creates Operator, returns helper claim."""
    helper = Knowledge(
        content=f"opposite_truth({a.label or 'A'}, {b.label or 'B'})",
        type="claim",
        metadata={"helper_kind": "complement_result"},
    )
    Operator(operator="complement", variables=[a, b], conclusion=helper, reason=reason)
    return helper


def disjunction(*claims: Knowledge, reason: str = "") -> Knowledge:
    """At least one true. Creates Operator, returns helper claim."""
    labels = ", ".join(c.label or f"C{i}" for i, c in enumerate(claims))
    helper = Knowledge(
        content=f"any_true({labels})",
        type="claim",
        metadata={"helper_kind": "disjunction_result"},
    )
    Operator(operator="disjunction", variables=list(claims), conclusion=helper, reason=reason)
    return helper
