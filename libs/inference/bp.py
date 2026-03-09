"""Sum-product loopy Belief Propagation for knowledge hypergraphs.

Implements proper loopy BP on binary variables with:
- 2-vector messages [p(x=0), p(x=1)] per message, always normalized
- Explicit message storage for both var→factor and factor→var directions
- Synchronous schedule: all new messages computed from old, then swapped + damped
- Factor potentials encoding edge-type semantics (deduction, retraction, contradiction)
"""

from __future__ import annotations

from itertools import product as cartesian_product
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from libs.inference.factor_graph import FactorGraph

__all__ = ["BeliefPropagation", "InconsistentGraphError"]

Msg = NDArray[np.float64]  # shape (2,): [p(x=0), p(x=1)]


class InconsistentGraphError(Exception):
    """Raised when BP encounters a zero partition (no valid state)."""


def _normalize(msg: Msg) -> Msg:
    """Normalize a 2-vector to sum to 1.

    Raises :class:`InconsistentGraphError` if both components are zero,
    which means the graph has no valid probability distribution.
    """
    s = msg[0] + msg[1]
    if s < 1e-30:
        raise InconsistentGraphError(
            "Zero partition: message sums to 0. "
            "The factor graph is internally inconsistent — "
            "no valid state exists for some variable."
        )
    return msg / s


def _prior_msg(prior: float) -> Msg:
    """Convert scalar prior p(x=1) to 2-vector [p(x=0), p(x=1)].

    Assumes *prior* is already Cromwell-clamped by :class:`FactorGraph`.
    """
    return np.array([1.0 - prior, prior])


def _evaluate_potential(
    edge_type: str,
    premise_ids: list[int],
    conclusion_ids: list[int],
    assignment: dict[int, int],
    prob: float,
) -> float:
    """Evaluate factor potential for a full variable assignment.

    Gated structure: if ALL premises are 1, behavior depends on edge type:

    - **deduction/induction**: conclusion=1 with prob p (standard conditional)
    - **retraction**: conclusion=1 with prob 1-p (inverted)
    - **contradiction** (Jaynes): the all-premises-true configuration is penalized.
      pot = (1-p) overall, with conclusion=1 favored over conclusion=0 to
      acknowledge the contradiction exists. This encodes P(A∧B|I) ≈ 0.

    Otherwise (not all premises true): unconstrained (potential = 1).

    Assumes *prob* is already Cromwell-clamped by :class:`FactorGraph`.

    .. note:: **Contradiction conclusions are non-participating**

       Conclusion variables in a contradiction factor exist for structural and
       review purposes only — they do not participate in BP inference.
       The potential is independent of conclusion values, so the
       factor-to-conclusion message is uniform and conclusion beliefs stay
       at their priors. This avoids the non-monotonicity that arises when
       premise inhibition and conclusion confirmation share the same
       potential.
    """
    all_premises_true = all(assignment[t] == 1 for t in premise_ids)

    if not all_premises_true:
        return 1.0

    if edge_type == "contradiction":
        # Jaynes: all-premises-true is implausible. Penalize the entire configuration.
        # Base penalty: (1-p). Strong contradiction (high p) → stronger penalty.
        # Conclusion variables are ignored — potential depends only on premises.
        # This makes f2v messages to conclusions uniform, so conclusions stay at prior.
        return 1.0 - prob

    # All premises true — compute gated potential for conclusions
    pot = 1.0
    for h in conclusion_ids:
        h_val = assignment[h]
        if edge_type == "retraction":
            pot *= (1.0 - prob) if h_val == 1 else prob
        else:
            # deduction, induction, paper-extract, abstraction, etc.
            pot *= prob if h_val == 1 else (1.0 - prob)
    return pot


def _compute_var_to_factor(
    var: int,
    factor_idx: int,
    prior: Msg,
    var_factors: dict[int, list[int]],
    f2v_msgs: dict[tuple[int, int], Msg],
) -> Msg:
    """Compute variable→factor message: prior * product of all incoming f2v except this factor."""
    msg = prior.copy()
    for fi in var_factors[var]:
        if fi != factor_idx:
            incoming = f2v_msgs.get((fi, var))
            if incoming is not None:
                msg = msg * incoming
    return _normalize(msg)


def _compute_factor_to_var(
    factor_idx: int,
    target_var: int,
    factor: dict,
    v2f_msgs: dict[tuple[int, int], Msg],
) -> Msg:
    """Compute factor→variable message by marginalizing over all other variables.

    Enumerates 2^(n-1) assignments of other variables, weights by potential and
    incoming v2f messages, then marginalizes to get message for target_var.
    """
    premise_ids: list[int] = factor["premises"]
    conclusion_ids: list[int] = factor["conclusions"]
    prob: float = factor["probability"]
    edge_type: str = factor.get("edge_type", "deduction")

    all_vars = premise_ids + conclusion_ids
    other_vars = [v for v in all_vars if v != target_var]

    msg = np.zeros(2)

    # Enumerate target_var ∈ {0, 1}
    for target_val in (0, 1):
        total = 0.0
        # Enumerate all assignments of other variables
        for other_vals in cartesian_product([0, 1], repeat=len(other_vars)):
            assignment = {v: val for v, val in zip(other_vars, other_vals)}
            assignment[target_var] = target_val

            # Factor potential
            pot = _evaluate_potential(edge_type, premise_ids, conclusion_ids, assignment, prob)

            # Product of incoming v2f messages from other variables
            weight = 1.0
            for v, val in zip(other_vars, other_vals):
                v2f = v2f_msgs.get((v, factor_idx))
                if v2f is not None:
                    weight *= v2f[val]
                else:
                    weight *= 0.5  # uniform if no message yet
            total += pot * weight
        msg[target_val] = total

    return _normalize(msg)


class BeliefPropagation:
    """Sum-product loopy Belief Propagation on a :class:`FactorGraph`.

    Parameters
    ----------
    damping:
        Controls how aggressively messages are updated each iteration.
        ``1.0`` means fully replace old message; ``0.0`` means keep old message.
    max_iterations:
        Upper bound on the number of message-passing sweeps.
    convergence_threshold:
        Stop early when the maximum absolute change in any belief
        falls below this value.
    """

    def __init__(
        self,
        damping: float = 0.5,
        max_iterations: int = 50,
        convergence_threshold: float = 1e-6,
    ) -> None:
        self._damping = damping
        self._max_iter = max_iterations
        self._threshold = convergence_threshold

    def run(self, graph: FactorGraph) -> dict[int, float]:
        """Run loopy BP on *graph* and return posterior beliefs.

        Returns
        -------
        dict[int, float]
            Mapping from variable (node) id to its posterior belief in ``[0, 1]``.
        """
        if not graph.variables:
            return {}

        if not graph.factors:
            return dict(graph.variables)

        var_factors = graph.get_var_factors()
        priors = {vid: _prior_msg(p) for vid, p in graph.variables.items()}

        # Initialize messages to uniform
        f2v_msgs: dict[tuple[int, int], Msg] = {}
        v2f_msgs: dict[tuple[int, int], Msg] = {}
        uniform = np.array([0.5, 0.5])

        for fi, factor in enumerate(graph.factors):
            for vid in factor["premises"] + factor["conclusions"]:
                if vid in graph.variables:
                    f2v_msgs[(fi, vid)] = uniform.copy()
                    v2f_msgs[(vid, fi)] = uniform.copy()

        prev_beliefs = {vid: p for vid, p in graph.variables.items()}

        for _iteration in range(self._max_iter):
            # 1. Compute all var→factor messages
            new_v2f: dict[tuple[int, int], Msg] = {}
            for (vid, fi), _ in v2f_msgs.items():
                new_v2f[(vid, fi)] = _compute_var_to_factor(
                    vid, fi, priors[vid], var_factors, f2v_msgs
                )

            # 2. Compute all factor→var messages
            new_f2v: dict[tuple[int, int], Msg] = {}
            for (fi, vid), _ in f2v_msgs.items():
                new_f2v[(fi, vid)] = _compute_factor_to_var(fi, vid, graph.factors[fi], new_v2f)

            # 3. Damp and normalize
            for key in f2v_msgs:
                f2v_msgs[key] = _normalize(
                    self._damping * new_f2v[key] + (1 - self._damping) * f2v_msgs[key]
                )
            for key in v2f_msgs:
                v2f_msgs[key] = _normalize(
                    self._damping * new_v2f[key] + (1 - self._damping) * v2f_msgs[key]
                )

            # 4. Compute beliefs
            beliefs: dict[int, float] = {}
            for vid in graph.variables:
                b = priors[vid].copy()
                for fi in var_factors[vid]:
                    b = b * f2v_msgs[(fi, vid)]
                b = _normalize(b)
                beliefs[vid] = float(b[1])  # p(x=1)

            # 5. Check convergence
            max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
            if max_change < self._threshold:
                return beliefs
            prev_beliefs = beliefs

        return beliefs
