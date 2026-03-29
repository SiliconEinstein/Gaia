"""Sum-product loopy Belief Propagation — BP v2, strictly per theory.

Theory reference: docs/foundations/theory/belief-propagation.md §3–4

Implements the exact algorithm from bp.md §3:

    Initialize:
        all messages = [0.5, 0.5]  (uniform, MaxEnt prior)
        priors = {var_id: [1-π, π]}

    Repeat (up to max_iterations):
      1. Compute all variable→factor messages (exclude-self rule):
             msg(v→f) = prior(v) * prod_{f'≠f} msg(f'→v)
             normalize.
      2. Compute all factor→variable messages (marginalize):
             msg(f→v) = Σ_{other vars} potential(assignment) * prod_{v'≠v} msg(v'→f)
             normalize.
      3. Damp and normalize:
             msg = α * new_msg + (1-α) * old_msg  (α=0.5 default per bp.md §4)
      4. Compute beliefs:
             b(v) = normalize(prior(v) * prod_f msg(f→v))
             output belief = b(v)[1]  i.e. P(x=1)
      5. Check convergence:
             if max|new_belief - old_belief| < threshold: stop.

Key properties (vs old libs/inference/bp.py):
- NO gate_var mechanism: relation variables for CONTRADICTION/EQUIVALENCE are
  full participants, receiving and sending messages bidirectionally.
- Potential dispatch via potentials.evaluate_potential() routes by FactorType:
  ENTAILMENT → silence (bp.md §2.6), INDUCTION/ABDUCTION → noisy-AND (§2.1),
  CONTRADICTION/EQUIVALENCE → fixed-eps constraints (§2.5).
- String variable IDs throughout.
- BPDiagnostics records full per-variable belief history per iteration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product as cartesian_product

import numpy as np
from numpy.typing import NDArray

from gaia.bp.factor_graph import FactorGraph
from gaia.bp.potentials import evaluate_potential

__all__ = ["BeliefPropagation", "BPDiagnostics", "BPResult"]

# 2-vector: [P(x=0), P(x=1)], always normalized to sum=1
Msg = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uniform_msg() -> Msg:
    """Return uniform [0.5, 0.5] message (MaxEnt initial state)."""
    return np.array([0.5, 0.5])


def _prior_to_msg(pi: float) -> Msg:
    """Convert scalar prior π=P(x=1) to normalized 2-vector."""
    return np.array([1.0 - pi, pi])


def _normalize(msg: Msg) -> Msg:
    """Normalize a 2-vector so entries sum to 1.

    If both entries are zero (or negative due to floating point), the graph
    has no valid state — we raise an explicit error with context rather than
    silently producing NaN.
    """
    s = float(msg[0] + msg[1])
    if s < 1e-300:
        raise RuntimeError(
            "BP encountered a zero-sum message vector. "
            "The factor graph has an internally inconsistent assignment — "
            "no valid probability distribution exists. "
            "Check that all Cromwell constraints (eps > 0) are satisfied "
            "and that no factor enforces a logically impossible state."
        )
    return msg / s


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass
class BPDiagnostics:
    """Diagnostic information collected during a BP run.

    Attributes
    ----------
    converged:
        True if the run stopped due to belief change < convergence_threshold.
    iterations_run:
        Number of complete sweep iterations executed.
    max_change_at_stop:
        Maximum absolute belief change in the final iteration.
    belief_history:
        {var_id: [belief_at_iter_0, belief_at_iter_1, ...]}
        where iter_0 is the initial belief (from prior) before any messages.
    message_history:
        Optional detailed record of f2v messages per iteration.
        Only populated when trace=True is passed to run().
    direction_changes:
        {var_id: count} — how many times the belief's direction of change
        reversed (sign flip). High counts indicate oscillation / conflict.
    """

    converged: bool = False
    iterations_run: int = 0
    max_change_at_stop: float = 0.0
    treewidth: int = -1  # Set by JT; -1 means not computed / not applicable
    belief_history: dict[str, list[float]] = field(default_factory=dict)
    direction_changes: dict[str, int] = field(default_factory=dict)

    def compute_direction_changes(self) -> None:
        """Populate direction_changes from belief_history (call after run)."""
        for vid, history in self.belief_history.items():
            changes = 0
            for k in range(2, len(history)):
                d_prev = history[k - 1] - history[k - 2]
                d_curr = history[k] - history[k - 1]
                if d_prev * d_curr < 0:
                    changes += 1
            self.direction_changes[vid] = changes

    def belief_table(self, variables: list[str] | None = None) -> str:
        """Return a formatted table of belief history across iterations.

        Parameters
        ----------
        variables:
            Variable IDs to include. Defaults to all recorded variables.
        """
        vids = variables if variables is not None else sorted(self.belief_history)
        if not vids:
            return "(no belief history)"

        max_iters = max(len(self.belief_history[v]) for v in vids)
        header = f"{'Variable':30s}" + "".join(f" iter{i:3d}" for i in range(max_iters))
        lines = [header, "-" * len(header)]
        for vid in vids:
            row = f"{vid:30s}"
            for b in self.belief_history[vid]:
                row += f"  {b:6.4f}"
            lines.append(row)
        return "\n".join(lines)


@dataclass
class BPResult:
    """Return value of BeliefPropagation.run().

    Attributes
    ----------
    beliefs:
        {var_id: posterior_belief} where belief = P(x=1) after BP.
    diagnostics:
        Full diagnostic record. Always present (never None in v2).
    """

    beliefs: dict[str, float]
    diagnostics: BPDiagnostics


# ---------------------------------------------------------------------------
# Variable→Factor message
# ---------------------------------------------------------------------------


def _compute_v2f(
    var: str,
    factor_idx: int,
    prior_msg: Msg,
    var_to_factors: dict[str, list[int]],
    f2v_msgs: dict[tuple[int, str], Msg],
) -> Msg:
    """Compute a single variable→factor message using the exclude-self rule.

    msg(v→f) = prior(v) * prod_{f'≠f} msg(f'→v)
    then normalize.

    This is step 1 of the bp.md §3 algorithm.
    """
    msg = prior_msg.copy()
    for fi in var_to_factors[var]:
        if fi == factor_idx:
            continue  # exclude-self rule
        incoming = f2v_msgs.get((fi, var))
        if incoming is not None:
            msg = msg * incoming
    return _normalize(msg)


# ---------------------------------------------------------------------------
# Factor→Variable message
# ---------------------------------------------------------------------------


def _compute_f2v(
    factor_idx: int,
    target_var: str,
    factor,  # Factor object
    v2f_msgs: dict[tuple[str, int], Msg],
) -> Msg:
    """Compute a single factor→variable message by marginalizing.

    msg(f→v) = Σ_{all assignments of other vars}
                   potential(assignment) * prod_{v'≠v} msg(v'→f)
    then normalize.

    This is step 2 of the bp.md §3 algorithm.

    Enumerates 2^(n-1) assignments where n = |factor.all_vars|.
    For factors with many variables this is exponential; in practice
    Gaia's factors have ≤5 premises + 1 conclusion = ≤6 variables,
    so 2^5 = 32 assignments at most.
    """
    all_vars = factor.all_vars
    other_vars = [v for v in all_vars if v != target_var]

    msg_out = np.zeros(2)

    for target_val in (0, 1):
        total = 0.0
        for other_vals in cartesian_product((0, 1), repeat=len(other_vars)):
            # Build full assignment
            assignment: dict[str, int] = {}
            for v, val in zip(other_vars, other_vals):
                assignment[v] = val
            assignment[target_var] = target_val

            # Factor potential
            pot = evaluate_potential(factor, assignment)

            # Product of incoming v2f messages from other variables
            weight = 1.0
            for v, val in zip(other_vars, other_vals):
                v2f = v2f_msgs.get((v, factor_idx))
                if v2f is not None:
                    weight *= float(v2f[val])
                else:
                    weight *= 0.5  # uniform if message not yet initialized

            total += pot * weight

        msg_out[target_val] = total

    return _normalize(msg_out)


# ---------------------------------------------------------------------------
# BeliefPropagation
# ---------------------------------------------------------------------------


class BeliefPropagation:
    """Sum-product loopy Belief Propagation on a FactorGraph (v2).

    Implements bp.md §3 exactly, with the following design principles:
    - All messages are 2-vectors [P(x=0), P(x=1)], always normalized.
    - Synchronous schedule: all new messages computed from old, then swapped.
    - Damping per bp.md §4 prevents oscillation in loopy graphs.
    - Relation variables (CONTRADICTION/EQUIVALENCE) participate fully.
    - BPDiagnostics always collected (full belief history).

    Parameters
    ----------
    damping:
        α in bp.md §4. Default 0.5. Range (0, 1].
        1.0 = fully replace old message (fast, may oscillate).
        0.5 = half-step (default, balanced stability).
        Lower values increase stability but slow convergence.
    max_iterations:
        Upper bound on sweep iterations.
    convergence_threshold:
        Stop early when max|Δbelief| < threshold across all variables.
    """

    def __init__(
        self,
        damping: float = 0.5,
        max_iterations: int = 100,
        convergence_threshold: float = 1e-6,
    ) -> None:
        if not (0.0 < damping <= 1.0):
            raise ValueError(f"damping must be in (0, 1], got {damping}")
        self._damping = damping
        self._max_iter = max_iterations
        self._threshold = convergence_threshold

    def run(self, graph: FactorGraph) -> BPResult:
        """Run loopy BP on *graph* and return beliefs + diagnostics.

        Always returns a BPResult with full diagnostics (never None).

        Parameters
        ----------
        graph:
            A validated FactorGraph. Variables referenced by factors must
            be registered. Cromwell clamping is enforced at graph construction.

        Returns
        -------
        BPResult
            .beliefs: dict[str, float] — posterior P(x=1) per variable.
            .diagnostics: BPDiagnostics — full run record.
        """
        diag = BPDiagnostics()

        # --- Edge case: empty graph ---
        if not graph.variables:
            diag.converged = True
            return BPResult(beliefs={}, diagnostics=diag)

        # --- Edge case: no factors — beliefs = priors ---
        if not graph.factors:
            diag.converged = True
            beliefs = dict(graph.variables)
            for vid, p in beliefs.items():
                diag.belief_history[vid] = [p]
            return BPResult(beliefs=beliefs, diagnostics=diag)

        # --- Build reverse index: var -> list of factor indices ---
        var_to_factors = graph.get_var_to_factors()

        # --- Initialize priors as 2-vectors ---
        priors: dict[str, Msg] = {vid: _prior_to_msg(pi) for vid, pi in graph.variables.items()}

        # --- Initialize all messages to uniform [0.5, 0.5] ---
        # f2v_msgs[(fi, vid)] = message from factor fi to variable vid
        # v2f_msgs[(vid, fi)] = message from variable vid to factor fi
        f2v_msgs: dict[tuple[int, str], Msg] = {}
        v2f_msgs: dict[tuple[str, int], Msg] = {}

        for fi, factor in enumerate(graph.factors):
            for vid in factor.all_vars:
                if vid in graph.variables:
                    f2v_msgs[(fi, vid)] = _uniform_msg()
                    v2f_msgs[(vid, fi)] = _uniform_msg()

        # --- Compute initial beliefs from priors only ---
        prev_beliefs: dict[str, float] = {}
        for vid, pi in graph.variables.items():
            prev_beliefs[vid] = pi
            diag.belief_history[vid] = [pi]

        max_change = 0.0

        # --- Main BP loop ---
        for iteration in range(self._max_iter):
            # Step 1: Compute all variable→factor messages (synchronous)
            new_v2f: dict[tuple[str, int], Msg] = {}
            for vid, fi in v2f_msgs:
                new_v2f[(vid, fi)] = _compute_v2f(
                    var=vid,
                    factor_idx=fi,
                    prior_msg=priors[vid],
                    var_to_factors=var_to_factors,
                    f2v_msgs=f2v_msgs,
                )

            # Step 2: Compute all factor→variable messages (synchronous)
            new_f2v: dict[tuple[int, str], Msg] = {}
            for fi, vid in f2v_msgs:
                new_f2v[(fi, vid)] = _compute_f2v(
                    factor_idx=fi,
                    target_var=vid,
                    factor=graph.factors[fi],
                    v2f_msgs=new_v2f,  # use freshly computed v2f
                )

            # Step 3: Damp and normalize both sets of messages
            for key in f2v_msgs:
                blended = self._damping * new_f2v[key] + (1.0 - self._damping) * f2v_msgs[key]
                f2v_msgs[key] = _normalize(blended)

            for key in v2f_msgs:
                blended = self._damping * new_v2f[key] + (1.0 - self._damping) * v2f_msgs[key]
                v2f_msgs[key] = _normalize(blended)

            # Step 4: Compute beliefs
            beliefs: dict[str, float] = {}
            for vid in graph.variables:
                b = priors[vid].copy()
                for fi in var_to_factors[vid]:
                    incoming = f2v_msgs.get((fi, vid))
                    if incoming is not None:
                        b = b * incoming
                b = _normalize(b)
                beliefs[vid] = float(b[1])
                diag.belief_history[vid].append(beliefs[vid])

            # Step 5: Check convergence
            max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
            prev_beliefs = beliefs

            if max_change < self._threshold:
                diag.converged = True
                diag.iterations_run = iteration + 1
                diag.max_change_at_stop = max_change
                diag.compute_direction_changes()
                return BPResult(beliefs=beliefs, diagnostics=diag)

        # Did not converge within max_iterations
        diag.converged = False
        diag.iterations_run = self._max_iter
        diag.max_change_at_stop = max_change
        diag.compute_direction_changes()
        return BPResult(beliefs=prev_beliefs, diagnostics=diag)
