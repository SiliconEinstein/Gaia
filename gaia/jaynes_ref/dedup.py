"""L1 structural deduplication for D2 (information independence).

A constraint's 'canonical key' normalizes variable order so that
EQUIVALENCE(A,B) and EQUIVALENCE(B,A) map to the same key, while
IMPLICATION(A,B) and IMPLICATION(B,A) stay distinct (asymmetric).

Full semantic equivalence (e.g. A ∧ B vs B ∧ A under a wrapping operator)
is out of scope — that belongs to a SAT/BDD layer.
"""

from __future__ import annotations

from dataclasses import replace

from gaia.jaynes_ref.constraints import CPT, LogicalConstraint, WeightedFactor
from gaia.jaynes_ref.information import InformationSet


def canonical_constraint_key(c: LogicalConstraint) -> tuple:
    """Order-invariant key: sort variables lexicographically and.

    re-project the allowed set under that permutation.
    """
    order = sorted(range(len(c.variables)), key=lambda i: c.variables[i])
    sorted_vars = tuple(c.variables[i] for i in order)
    remapped = frozenset(tuple(a[i] for i in order) for a in c.allowed)
    return (sorted_vars, remapped)


def canonical_cpt_key(cpt: CPT) -> tuple:
    """CPT is parent-ordered (bit packing depends on order). We canonicalize.

    only (parents, child); conflicting tables at the same key are a D2
    violation and must raise.
    """
    return (tuple(cpt.parents), cpt.child)


def dedup_constraints(info: InformationSet) -> tuple[InformationSet, list[dict]]:
    """Return a new InformationSet with duplicate constraints removed.

    Same key → silently keep first, record in audit. No conflict is
    possible for constraints (no 'conclusion' field).
    """
    seen: dict = {}
    kept: list[LogicalConstraint] = []
    audit: list[dict] = []
    for c in info.constraints:
        key = canonical_constraint_key(c)
        if key in seen:
            audit.append({"kind": "constraint", "dropped_label": c.label, "key_vars": key[0]})
            continue
        seen[key] = True
        kept.append(c)
    return replace(info, constraints=kept), audit


def dedup_cpts(info: InformationSet) -> tuple[InformationSet, list[dict]]:
    """Same (parents, child) with identical table → dedup; conflicting.

    tables on the same key → raise (two different conditional
    distributions for the same fact, D2 violation).
    """
    seen: dict = {}
    kept: list[CPT] = []
    audit: list[dict] = []
    for cpt in info.cpts:
        key = canonical_cpt_key(cpt)
        if key in seen:
            if seen[key] != cpt.table:
                raise ValueError(
                    f"D2 violation: CPT for child={cpt.child!r} given parents={cpt.parents!r} "
                    f"is declared twice with different tables {seen[key]} vs {cpt.table}."
                )
            audit.append({"kind": "cpt", "child": cpt.child, "parents": cpt.parents})
            continue
        seen[key] = cpt.table
        kept.append(cpt)
    return replace(info, cpts=kept), audit


def canonical_weighted_factor_key(wf: WeightedFactor) -> tuple:
    """Order-invariant key over variables; weights are permuted to match.

    Two pairwise factors that disagree on weights under the same key are
    a D2 violation (two different soft factors for the same fact).
    """
    order = sorted(range(len(wf.variables)), key=lambda i: wf.variables[i])
    sorted_vars = tuple(wf.variables[i] for i in order)
    k = len(wf.variables)
    N = 1 << k
    new_weights = [0.0] * N
    # For each original index, derive new index after permutation.
    for old_idx in range(N):
        bits = [(old_idx >> i) & 1 for i in range(k)]
        new_idx = 0
        for new_pos, old_pos in enumerate(order):
            new_idx |= bits[old_pos] << new_pos
        new_weights[new_idx] = wf.weights[old_idx]
    return (sorted_vars, tuple(new_weights))


def dedup_weighted_factors(info: InformationSet) -> tuple[InformationSet, list[dict]]:
    """Same canonical key + identical permuted weights → dedup.

    conflicting weights → raise (D2).
    """
    seen: dict = {}
    kept: list[WeightedFactor] = []
    audit: list[dict] = []
    for wf in info.weighted_factors:
        key = canonical_weighted_factor_key(wf)
        if key[:1] in seen:
            if seen[key[:1]] != key[1]:
                raise ValueError(
                    f"D2 violation: weighted factor over {key[0]!r} is declared "
                    f"twice with different weights."
                )
            audit.append({"kind": "weighted_factor", "variables": key[0]})
            continue
        seen[key[:1]] = key[1]
        kept.append(wf)
    return replace(info, weighted_factors=kept), audit


def apply_d2_dedup(info: InformationSet) -> tuple[InformationSet, list[dict]]:
    """One-shot D2 L1 dedup over constraints, CPTs, and weighted factors."""
    info1, audit1 = dedup_constraints(info)
    info2, audit2 = dedup_cpts(info1)
    info3, audit3 = dedup_weighted_factors(info2)
    return info3, audit1 + audit2 + audit3
