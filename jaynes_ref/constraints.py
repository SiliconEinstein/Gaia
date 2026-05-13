"""Constraint value types: class II likelihood, class III CPT, and
deterministic logical potentials.

All three are frozen dataclasses so they can be hashed and compared —
this is what makes the D2 structural dedup tractable.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from itertools import product


@dataclass(frozen=True)
class Likelihood:
    """Class II (soft evidence) — a single-variable likelihood ratio.

    ratio = P(E | variable=1) / P(E | variable=0) > 0.
    Folded into class-IV unary via Bayes during exact inference.
    """

    variable: str
    ratio: float

    def __post_init__(self) -> None:
        if not isinstance(self.variable, str) or not self.variable:
            raise ValueError(f"Likelihood.variable must be a non-empty str, got {self.variable!r}")
        if self.ratio <= 0:
            raise ValueError(f"Likelihood.ratio must be > 0, got {self.ratio}")


@dataclass(frozen=True)
class CPT:
    """Class III — conditional probability table P(child=1 | parents).

    table has length 2**len(parents). Index is
    sum(v_i << i for i, v_i in enumerate(parent_assignment))
    (LSB-first bit packing, matching gaia.bp.exact).
    Entries lie in [0, 1]. Values of exactly 0 or 1 are allowed
    (Jaynes does not require Cromwell clamp on CPT entries).
    """

    parents: tuple[str, ...]
    child: str
    table: tuple[float, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.child, str) or not self.child:
            raise ValueError(f"CPT.child must be a non-empty str, got {self.child!r}")
        if self.child in self.parents:
            raise ValueError(
                f"CPT.child {self.child!r} must not appear in parents {self.parents!r}"
            )
        for p in self.parents:
            if not isinstance(p, str) or not p:
                raise ValueError(f"CPT.parents must be non-empty strs, got {p!r}")
        expected = 1 << len(self.parents)
        if len(self.table) != expected:
            raise ValueError(
                f"CPT({self.child}|{self.parents}).table has {len(self.table)} "
                f"entries, expected 2**{len(self.parents)} = {expected}"
            )
        for p in self.table:
            if not (0.0 <= p <= 1.0):
                raise ValueError(f"CPT entry out of [0,1]: {p}")


@dataclass(frozen=True)
class LogicalConstraint:
    """Deterministic logical potential ψ: {0,1}^k → {0,1}.

    Jaynes-strict: information I cuts the sample space into an allowed
    subset. We store exactly that subset.

    variables is the ordered tuple of variable ids; allowed is the
    frozenset of tuples (one per allowed assignment, same order as
    variables). An assignment is forbidden ↔ not in allowed.
    """

    variables: tuple[str, ...]
    allowed: frozenset[tuple[int, ...]]
    label: str = ""

    def __post_init__(self) -> None:
        for v in self.variables:
            if not isinstance(v, str) or not v:
                raise ValueError(f"LogicalConstraint.variables must be non-empty strs, got {v!r}")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError(f"LogicalConstraint.variables must be unique, got {self.variables!r}")
        k = len(self.variables)
        if not self.allowed:
            raise ValueError("LogicalConstraint with empty allowed set forbids everything (Z=0)")
        for a in self.allowed:
            if len(a) != k:
                raise ValueError(f"Allowed tuple {a!r} has length {len(a)}, expected {k}")
            for b in a:
                if b not in (0, 1):
                    raise ValueError(f"Allowed tuple {a!r} contains non-binary value {b}")


# ---------------------------------------------------------------------------
# Standard factories — Jaynes-pure (no helper variables, no Cromwell ε,
# no soft approximation). Each returns a LogicalConstraint over ONLY the
# actual propositional variables involved.
# ---------------------------------------------------------------------------


def _all_assignments(k: int) -> Iterable[tuple[int, ...]]:
    return product((0, 1), repeat=k)


def implication(a: str, b: str) -> LogicalConstraint:
    """A → B: forbid (A=1, B=0); allow the other three."""
    return LogicalConstraint(
        variables=(a, b),
        allowed=frozenset(x for x in _all_assignments(2) if not (x[0] == 1 and x[1] == 0)),
        label=f"{a} -> {b}",
    )


def negation(a: str, b: str) -> LogicalConstraint:
    """B = ¬A."""
    return LogicalConstraint(
        variables=(a, b),
        allowed=frozenset((x0, 1 - x0) for x0 in (0, 1)),
        label=f"{b} = !{a}",
    )


def equivalence(a: str, b: str) -> LogicalConstraint:
    """A ≡ B."""
    return LogicalConstraint(
        variables=(a, b),
        allowed=frozenset(((0, 0), (1, 1))),
        label=f"{a} == {b}",
    )


def contradiction(a: str, b: str) -> LogicalConstraint:
    """¬(A ∧ B): forbid (1, 1) only."""
    return LogicalConstraint(
        variables=(a, b),
        allowed=frozenset(x for x in _all_assignments(2) if not (x[0] == 1 and x[1] == 1)),
        label=f"!({a} & {b})",
    )


def complement(a: str, b: str) -> LogicalConstraint:
    """A XOR B (exactly one of them is true)."""
    return LogicalConstraint(
        variables=(a, b),
        allowed=frozenset(((0, 1), (1, 0))),
        label=f"{a} ^ {b}",
    )


def conjunction(xs: Iterable[str], out: str) -> LogicalConstraint:
    """Out = AND(xs): allow assignments where out matches ∧xs."""
    xs_t = tuple(xs)
    vars_ = (*xs_t, out)
    n = len(xs_t)
    allowed = set()
    for assign in _all_assignments(n):
        target = 1 if all(a == 1 for a in assign) else 0
        allowed.add((*assign, target))
    return LogicalConstraint(
        variables=vars_, allowed=frozenset(allowed), label=f"{out} = AND({xs_t})"
    )


def disjunction(xs: Iterable[str], out: str) -> LogicalConstraint:
    """Out = OR(xs)."""
    xs_t = tuple(xs)
    vars_ = (*xs_t, out)
    n = len(xs_t)
    allowed = set()
    for assign in _all_assignments(n):
        target = 1 if any(a == 1 for a in assign) else 0
        allowed.add((*assign, target))
    return LogicalConstraint(
        variables=vars_, allowed=frozenset(allowed), label=f"{out} = OR({xs_t})"
    )


# ---------------------------------------------------------------------------
# WeightedFactor — class III' non-deterministic / non-normalised factor.
#
# Distinct from LogicalConstraint (allowed/forbidden indicator) and CPT
# (normalised conditional). Used for pairwise potentials and any factor
# whose entries are arbitrary non-negative weights with no per-row
# normalisation constraint. This is what gaia.bp.FactorType.PAIRWISE_POTENTIAL
# expresses.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WeightedFactor:
    """Arbitrary non-negative weighted factor over k variables.

    weights has length 2**k. The index for a binary assignment x is
    sum(x_i << i for i in range(k)) (LSB-first, matching gaia.bp).
    Entries must be non-negative; rows are NOT normalised (this is what
    distinguishes a weight from a conditional probability).
    """

    variables: tuple[str, ...]
    weights: tuple[float, ...]
    label: str = ""

    def __post_init__(self) -> None:
        for v in self.variables:
            if not isinstance(v, str) or not v:
                raise ValueError(f"WeightedFactor.variables must be non-empty strs, got {v!r}")
        if len(set(self.variables)) != len(self.variables):
            raise ValueError(f"WeightedFactor.variables must be unique, got {self.variables!r}")
        expected = 1 << len(self.variables)
        if len(self.weights) != expected:
            raise ValueError(
                f"WeightedFactor({self.variables}).weights has {len(self.weights)} "
                f"entries, expected 2**{len(self.variables)} = {expected}"
            )
        if all(w == 0.0 for w in self.weights):
            raise ValueError("WeightedFactor with all-zero weights forbids everything (Z=0)")
        for w in self.weights:
            if w < 0.0:
                raise ValueError(f"WeightedFactor weight must be >= 0, got {w}")


def pairwise_weight(a: str, b: str, weights: tuple[float, ...]) -> WeightedFactor:
    """Build a pairwise WeightedFactor over (a, b).

    weights is length 4, indexed by a + 2*b:
        [w(a=0,b=0), w(a=1,b=0), w(a=0,b=1), w(a=1,b=1)]
    Matches gaia.bp.FactorType.PAIRWISE_POTENTIAL convention.
    """
    if len(weights) != 4:
        raise ValueError(f"pairwise_weight requires 4 weights, got {len(weights)}")
    return WeightedFactor(
        variables=(a, b), weights=tuple(float(w) for w in weights), label=f"pair({a},{b})"
    )
