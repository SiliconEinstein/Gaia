"""Factor potential functions for BP v2 — strictly per theory.

Theory reference: docs/foundations/theory/belief-propagation.md §2

This module implements the potential families that cover all five operator
types defined in reasoning-hypergraph.md §7.3.

Potential functions take a full joint assignment {var_id: 0|1} and return a
non-negative weight encoding the compatibility of that assignment with the
factor's constraint. Potentials are NOT normalized — only ratios matter.

The four potential functions (bp.md §2.1, §2.5, §2.6):

1. entailment_potential — for ENTAILMENT only
   Implements bp.md §2.6: entailment's C4 is "通常沉默" (typically silent).
   When premises are false the factor contributes nothing (potential = 1.0).
   Reason: ¬∀x.P(x) ⊬ ¬P(a) — a universal being false does not make each
   instance false. This is the Popper/Jaynes stance on instantiation.

   Potential table:
       all premises true,  conclusion = 1  ->  p
       all premises true,  conclusion = 0  ->  1 - p
       any premise false,  any conclusion  ->  1.0   (silent)

2. noisy_and_potential — for INDUCTION / ABDUCTION
   Implements noisy-AND + leak (bp.md §2.1), satisfying all four weak
   syllogisms including C4: premise false → conclusion belief decreases.
   Used for induction and abduction because those operators make a genuine
   probabilistic claim that "given the evidence, the hypothesis is more or
   less likely" — the absence of evidence is informative.

   Potential table:
       all premises true,  conclusion = 1  ->  p
       all premises true,  conclusion = 0  ->  1 - p
       any premise false,  conclusion = 1  ->  eps    (leak)
       any premise false,  conclusion = 0  ->  1 - eps

3. contradiction_potential — for CONTRADICTION (bp.md §2.5)
   Constraint: relation active + all claims true is almost impossible.

4. equivalence_potential — for EQUIVALENCE (bp.md §2.5)
   Constraint: when relation active, agreement rewarded (1-eps), disagreement
   penalized (eps).

The dispatcher `evaluate_potential` is the single call-site used by the BP
and JT engines, routing by FactorType.
"""

from __future__ import annotations

from libs.inference_v2.factor_graph import CROMWELL_EPS, Factor, FactorType

__all__ = [
    "entailment_potential",
    "noisy_and_potential",
    "contradiction_potential",
    "equivalence_potential",
    "evaluate_potential",
]

# Type alias: a complete joint assignment of all variables in a factor
Assignment = dict[str, int]  # var_id -> 0 or 1


# ---------------------------------------------------------------------------
# 1. Entailment (silence when premises false)  — bp.md §2.6
# ---------------------------------------------------------------------------


def entailment_potential(
    assignment: Assignment,
    premises: list[str],
    conclusions: list[str],
    p: float,
) -> float:
    """Compute the entailment potential (silent C4 model).

    Implements bp.md §2.6: ENTAILMENT satisfies C4 only "通常沉默" — when
    premises are false the factor is silent (potential = 1.0 for all
    conclusion values), contributing nothing to the BP messages.

    Rationale: from ¬∀x.P(x) we cannot infer ¬P(a). A universal law being
    false does not make every instance false (Popper/Jaynes). Therefore the
    factor should not penalise the conclusion when the antecedent is absent.

    Potential table (bp.md §2.6):

        all premises true,  conclusion = 1  ->  p
        all premises true,  conclusion = 0  ->  1 - p
        any premise false,  any conclusion  ->  1.0   (silent, no constraint)

    Parameters
    ----------
    assignment:
        Full joint assignment {var_id: 0|1} for all variables in this factor.
    premises:
        Variable IDs that are the joint necessary conditions.
    conclusions:
        Variable IDs that are jointly entailed.
    p:
        P(all conclusions=1 | all premises=1). Cromwell-clamped by caller.
    """
    if not all(assignment[v] == 1 for v in premises):
        return 1.0  # silent: premises absent → factor imposes no constraint

    pot = 1.0
    for c in conclusions:
        pot *= p if assignment[c] == 1 else (1.0 - p)
    return pot


# ---------------------------------------------------------------------------
# 2. Noisy-AND + Leak  (INDUCTION / ABDUCTION)
# ---------------------------------------------------------------------------


def noisy_and_potential(
    assignment: Assignment,
    premises: list[str],
    conclusions: list[str],
    p: float,
    eps: float = CROMWELL_EPS,
) -> float:
    """Compute the noisy-AND + leak potential for induction/abduction factors.

    Used for INDUCTION and ABDUCTION only (not ENTAILMENT — see
    entailment_potential above).

    Implements bp.md §2.1 table:

        all premises true,  conclusion = 1  ->  p
        all premises true,  conclusion = 0  ->  1 - p
        any premise false,  conclusion = 1  ->  eps    (leak — C4 satisfied)
        any premise false,  conclusion = 0  ->  1 - eps

    The leak probability eps encodes that even when the evidence (premises)
    is absent, the hypothesis can still be true with small background
    probability. For induction and abduction this is correct: the absence of
    confirming instances does weakly disconfirm the hypothesis (C4 ✓).

    Parameters
    ----------
    assignment:
        Full joint assignment {var_id: 0|1} for all variables in this factor.
    premises:
        Variable IDs that are the joint necessary conditions.
    conclusions:
        Variable IDs that are jointly supported.
    p:
        P(all conclusions=1 | all premises=1). Cromwell-clamped by caller.
    eps:
        Cromwell lower bound, also used as the leak probability.

    Returns
    -------
    float
        Non-negative potential weight.
    """
    all_premises_true = all(assignment[v] == 1 for v in premises)

    pot = 1.0
    for c in conclusions:
        c_val = assignment[c]
        if all_premises_true:
            # Standard conditional: C4 via noisy-AND
            pot *= p if c_val == 1 else (1.0 - p)
        else:
            # Leak: premise false -> conclusion actively suppressed (C4)
            pot *= eps if c_val == 1 else (1.0 - eps)

    return pot


# ---------------------------------------------------------------------------
# 3. Contradiction  (CONTRADICTION)
# ---------------------------------------------------------------------------


def contradiction_potential(
    assignment: Assignment,
    relation_var: str,
    claim_vars: list[str],
    eps: float = CROMWELL_EPS,
) -> float:
    """Compute the contradiction constraint potential.

    Implements bp.md §2.5 table:

        relation = 1, all claims = 1  ->  eps    (almost impossible)
        all other combinations        ->  1.0    (unconstrained)

    The relation variable is a full BP participant. When both claims have
    strong evidence (high beliefs), BP will *lower the relation variable's
    belief* rather than forcing one claim down — "questioning the contradiction
    itself" (bp.md §2.5). This emerges naturally from the potential when both
    claim beliefs are high.

    Parameters
    ----------
    assignment:
        Full joint assignment including relation_var and all claim_vars.
    relation_var:
        Variable ID for the relation node (active when value = 1).
    claim_vars:
        Variable IDs of the mutually exclusive claims.
    eps:
        Cromwell lower bound. Fixed — constraint strength is NOT a free param.
    """
    r_val = assignment[relation_var]
    if r_val == 1 and all(assignment[c] == 1 for c in claim_vars):
        return eps
    return 1.0


# ---------------------------------------------------------------------------
# 4. Equivalence  (EQUIVALENCE)
# ---------------------------------------------------------------------------


def equivalence_potential(
    assignment: Assignment,
    relation_var: str,
    claim_a: str,
    claim_b: str,
    eps: float = CROMWELL_EPS,
) -> float:
    """Compute the equivalence constraint potential.

    Implements bp.md §2.5 table:

        relation = 1, A == B  ->  1 - eps  (agreement rewarded)
        relation = 1, A != B  ->  eps      (disagreement penalized)
        relation = 0, any     ->  1.0      (relation inactive, unconstrained)

    The relation variable participates fully in BP:
    - When A and B agree, the factor sends a positive message to the relation
      node, raising its belief.
    - When A and B disagree strongly, the factor lowers the relation node's
      belief — "the equivalence itself is being questioned."

    Parameters
    ----------
    assignment:
        Full joint assignment including relation_var, claim_a, claim_b.
    relation_var:
        Variable ID for the relation node.
    claim_a, claim_b:
        Variable IDs of the two equivalent claims.
    eps:
        Cromwell lower bound. Fixed — constraint strength is NOT a free param.
    """
    r_val = assignment[relation_var]
    if r_val == 0:
        return 1.0  # Relation inactive: factor imposes no constraint

    a_val = assignment[claim_a]
    b_val = assignment[claim_b]
    return (1.0 - eps) if a_val == b_val else eps


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def evaluate_potential(factor: Factor, assignment: Assignment) -> float:
    """Dispatch to the correct potential function based on factor type.

    This is the single entry point used by the BP engine. All routing by
    FactorType is done here so the BP loop stays clean.

    Parameters
    ----------
    factor:
        The Factor object whose potential is being evaluated.
    assignment:
        Complete joint assignment for all variables in factor.all_vars.
        Must include every variable ID in the factor.

    Returns
    -------
    float
        Non-negative potential weight.

    Raises
    ------
    ValueError
        If the factor type is unknown or the factor lacks required fields.
    """
    ft = factor.factor_type

    if ft == FactorType.ENTAILMENT:
        # bp.md §2.6: entailment is silent when premises are false.
        # ¬∀x.P(x) ⊬ ¬P(a) — a universal being false ≠ each instance false.
        return entailment_potential(
            assignment=assignment,
            premises=factor.premises,
            conclusions=factor.conclusions,
            p=factor.p,
        )

    if ft in (FactorType.INDUCTION, FactorType.ABDUCTION):
        # bp.md §2.1: noisy-AND + leak. C4 satisfied via eps.
        return noisy_and_potential(
            assignment=assignment,
            premises=factor.premises,
            conclusions=factor.conclusions,
            p=factor.p,
        )

    if ft == FactorType.CONTRADICTION:
        if factor.relation_var is None:
            raise ValueError(f"CONTRADICTION factor '{factor.factor_id}' missing relation_var.")
        return contradiction_potential(
            assignment=assignment,
            relation_var=factor.relation_var,
            claim_vars=factor.premises,
        )

    if ft == FactorType.EQUIVALENCE:
        if factor.relation_var is None:
            raise ValueError(f"EQUIVALENCE factor '{factor.factor_id}' missing relation_var.")
        if len(factor.premises) != 2:
            raise ValueError(
                f"EQUIVALENCE factor '{factor.factor_id}' needs exactly 2 premises, "
                f"got {len(factor.premises)}."
            )
        return equivalence_potential(
            assignment=assignment,
            relation_var=factor.relation_var,
            claim_a=factor.premises[0],
            claim_b=factor.premises[1],
        )

    raise ValueError(f"Unknown FactorType: {ft!r}")
