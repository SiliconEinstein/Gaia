"""Tree-Reweighted Belief Propagation (TRW-BP) — factor-level formulation.

Reference: Wainwright, Jaakkola & Willsky (2003/2005).
  "Tree-reweighted belief propagation algorithms and approximate ML
   estimation by pseudo-moment matching." AISTATS 2003.
  "A new class of upper bounds on the log partition function."
   IEEE Trans. Inf. Theory 51(7), 2005.

Factor-level TRW for higher-order factor graphs
------------------------------------------------
Standard TRW is defined for pairwise MRFs. For Gaia's higher-order factor
graph (factors can connect k variables), we use the factor-level extension:

  Each factor f has weight rho_f in (0, 1].
  rho_f = min(1, (n_soft - 1) / F_soft)
  where n_soft = non-hard-evidence variables, F_soft = soft factors.

Message updates:
  msg(v->f) = prior(v) * prod_{f'!=f} msg(f'->v)          [standard]
  msg(f->v)[x_v] ∝ exp(rho_f * log Σ_{x_{-v}}
      exp[log psi(x) + Σ_{v'!=v} log msg(v'->f)[x_{v'}]])  [TRW-weighted]
  b(v) ∝ prior(v) * prod_f msg(f->v)                       [standard]

The rho_f weighting is equivalent to raising the factor potential to the
power rho_f, which shrinks the influence of each factor and prevents the
double-counting that causes loopy BP bias on cyclic graphs.

Hard evidence (Class I, Jaynes):
  Variables in graph.hard_evidence are clamped delta-distributions.
  Their v->f messages are always [0,1] or [1,0] and bypass damping.
  Factors containing only hard-evidence variables get rho_f = 1.0.

Schedules:
  "synchronous"  -- standard parallel sweep (default)
  "residual"     -- priority-queue residual BP (Murphy 1999)
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from itertools import product as cartesian_product

import numpy as np
from numpy.typing import NDArray

from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph
from gaia.bp.potentials import evaluate_potential

__all__ = ["TRWBeliefPropagation", "TRWDiagnostics", "TRWResult"]

Msg = NDArray[np.float64]

_LOG_EPS = np.log(1e-300)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uniform_msg() -> Msg:
    return np.array([0.5, 0.5], dtype=np.float64)


def _prior_to_msg(pi: float) -> Msg:
    return np.array([1.0 - pi, pi], dtype=np.float64)


def _normalize(msg: Msg) -> Msg:
    s = float(msg[0] + msg[1])
    if s < 1e-300:
        raise RuntimeError(
            "TRW-BP: zero-sum message -- factor graph has no valid assignment. "
            "Check Cromwell constraints and hard_evidence consistency."
        )
    return msg / s


def _safe_log(msg: Msg) -> Msg:
    return np.log(np.maximum(msg, 1e-300))


def _log_normalize(log_msg: Msg) -> Msg:
    log_msg = log_msg - log_msg.max()
    msg = np.exp(log_msg)
    return msg / msg.sum()


# ---------------------------------------------------------------------------
# Factor weights
# ---------------------------------------------------------------------------


def _compute_factor_weights(
    graph: FactorGraph,
    _var_to_factors: dict[str, list[int]],
) -> dict[int, float]:
    """Compute TRW factor appearance probabilities rho_f.

    Uses the uniform hypertree distribution:
        rho_f = min(1, (n_soft - 1) / F_soft)
    where n_soft = non-hard-evidence variables,
          F_soft = factors with at least one soft variable.

    Hard-evidence-only factors get rho_f = 1.0.
    On trees (F_soft = n_soft - 1) all rho_f = 1 and TRW = exact BP.
    """
    hard = set(graph.hard_evidence.keys())
    n_soft = sum(1 for v in graph.variables if v not in hard)

    soft_factor_ids = [
        fi
        for fi, factor in enumerate(graph.factors)
        if any(v not in hard for v in factor.all_vars if v in graph.variables)
    ]
    F_soft = len(soft_factor_ids)

    rho_soft = 1.0 if F_soft == 0 or n_soft <= 1 else min(1.0, (n_soft - 1) / F_soft)

    weights: dict[int, float] = {}
    for fi in range(len(graph.factors)):
        factor = graph.factors[fi]
        all_hard = all(v in hard for v in factor.all_vars if v in graph.variables)
        weights[fi] = 1.0 if all_hard else rho_soft

    return weights


# ---------------------------------------------------------------------------
# Message computations
# ---------------------------------------------------------------------------


def _compute_v2f_trw(
    var: str,
    factor_idx: int,
    prior_msg: Msg,
    var_to_factors: dict[str, list[int]],
    f2v_msgs: dict[tuple[int, str], Msg],
    _rho: dict[int, float],
) -> Msg:
    """Variable->factor message (standard sum-product, no rho in v->f).

    In factor-level TRW the v->f message is the standard form:
        msg(v->f) = prior(v) * prod_{f'!=f} msg(f'->v)
    The rho weighting only enters in the f->v direction.
    """
    log_msg = _safe_log(prior_msg)
    for fi in var_to_factors[var]:
        if fi == factor_idx:
            continue
        incoming = f2v_msgs.get((fi, var))
        if incoming is not None:
            log_msg = log_msg + _safe_log(incoming)
    return _log_normalize(log_msg)


def _compute_f2v_trw(
    factor_idx: int,
    target_var: str,
    factor,
    v2f_msgs: dict[tuple[str, int], Msg],
    rho: dict[int, float],
) -> Msg:
    """Factor->variable message with factor-level TRW reweighting.

    log msg(f->v)[x_v] ∝ rho_f * log Σ_{x_{-v}}
        exp[ log psi(x) + Σ_{v'!=v} log msg(v'->f)[x_{v'}] ]

    Raising the log-sum-exp by rho_f is equivalent to raising the factor
    potential to the power rho_f, reducing double-counting on cyclic graphs.
    """
    all_vars = factor.all_vars
    other_vars = [v for v in all_vars if v != target_var]
    rho_f = rho.get(factor_idx, 1.0)

    log_msg_out = np.zeros(2, dtype=np.float64)

    for target_val in (0, 1):
        log_terms = []
        for other_vals in cartesian_product((0, 1), repeat=len(other_vars)):
            assignment: dict[str, int] = dict(zip(other_vars, other_vals, strict=True))
            assignment[target_var] = target_val

            pot = evaluate_potential(factor, assignment)
            if pot <= 0.0:
                continue

            log_term = np.log(pot)
            for v, val in zip(other_vars, other_vals, strict=True):
                v2f = v2f_msgs.get((v, factor_idx))
                if v2f is not None:
                    log_term += float(_safe_log(v2f)[val])

            log_terms.append(log_term)

        if log_terms:
            max_lt = max(log_terms)
            log_msg_out[target_val] = rho_f * (
                max_lt + np.log(sum(np.exp(lt - max_lt) for lt in log_terms))
            )
        else:
            log_msg_out[target_val] = _LOG_EPS

    return _log_normalize(log_msg_out)


def _compute_beliefs_trw(
    graph: FactorGraph,
    priors: dict[str, Msg],
    var_to_factors: dict[str, list[int]],
    f2v_msgs: dict[tuple[int, str], Msg],
    _rho: dict[int, float],
) -> dict[str, float]:
    """Compute beliefs: b(v) ∝ prior(v) * prod_f msg(f->v).

    The rho weighting is baked into f->v messages, so beliefs use the
    standard sum-product formula.
    """
    beliefs: dict[str, float] = {}
    for vid in graph.variables:
        log_b = _safe_log(priors[vid])
        for fi in var_to_factors[vid]:
            incoming = f2v_msgs.get((fi, vid))
            if incoming is not None:
                log_b = log_b + _safe_log(incoming)
        b = _log_normalize(log_b)
        beliefs[vid] = float(b[1])
    return beliefs


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


@dataclass
class TRWDiagnostics:
    """Diagnostics from a TRW-BP run."""

    converged: bool = False
    iterations_run: int = 0
    max_change_at_stop: float = 0.0
    belief_history: dict[str, list[float]] = field(default_factory=dict)
    direction_changes: dict[str, int] = field(default_factory=dict)
    rho: float = 1.0  # factor weight used (uniform scheme)

    def compute_direction_changes(self) -> None:
        for vid, history in self.belief_history.items():
            changes = 0
            for k in range(2, len(history)):
                d_prev = history[k - 1] - history[k - 2]
                d_curr = history[k] - history[k - 1]
                if d_prev * d_curr < 0:
                    changes += 1
            self.direction_changes[vid] = changes

    def belief_table(self, variables: list[str] | None = None) -> str:
        """返回 belief history 的格式化表格。."""
        vids = variables if variables is not None else sorted(self.belief_history)
        if not vids:
            return "(no belief history)"
        max_iters = max(len(self.belief_history[v]) for v in vids)
        header = "Variable".ljust(30) + "".join(f" iter{i:3d}" for i in range(max_iters))
        lines = [header, "-" * len(header)]
        for vid in vids:
            row = f"{vid:30s}"
            for b in self.belief_history[vid]:
                row += f"  {b:6.4f}"
            lines.append(row)
        return "\n".join(lines)


@dataclass
class TRWResult:
    """Return value of TRWBeliefPropagation.run()."""

    beliefs: dict[str, float]
    diagnostics: TRWDiagnostics


# ---------------------------------------------------------------------------
# TRWBeliefPropagation
# ---------------------------------------------------------------------------


class TRWBeliefPropagation:
    """Tree-Reweighted Belief Propagation (Wainwright et al. 2003/2005).

    Replaces loopy BP as the default approximate inference algorithm.
    Uses factor-level reweighting for higher-order factor graphs.

    Parameters
    ----------
    damping:
        Message mixing coefficient alpha in (0, 1]. Default 0.5.
    max_iterations:
        Maximum number of full sweeps.
    convergence_threshold:
        Stop when max|delta_belief| < threshold.
    schedule:
        "synchronous" -- standard parallel sweep (default).
        "residual"    -- priority-queue residual schedule (Murphy 1999).
    """

    def __init__(
        self,
        damping: float = 0.5,
        max_iterations: int = 200,
        convergence_threshold: float = 1e-6,
        schedule: str = "synchronous",
    ) -> None:
        if not (0.0 < damping <= 1.0):
            raise ValueError(f"damping must be in (0, 1], got {damping}")
        if schedule not in ("synchronous",):
            raise ValueError(
                f"schedule must be 'synchronous', got {schedule!r}. Residual schedule for TRW-BP is not yet stable."
            )
        if schedule not in ("synchronous",):
            raise ValueError(
                f"schedule must be 'synchronous', got {schedule!r}. Residual schedule for TRW-BP is not yet stable."
            )
        self._damping = damping
        self._max_iter = max_iterations
        self._threshold = convergence_threshold
        self._schedule = schedule

    def run(self, graph: FactorGraph) -> TRWResult:
        """Run TRW-BP on graph and return beliefs + diagnostics."""
        diag = TRWDiagnostics()

        if not graph.variables:
            diag.converged = True
            return TRWResult(beliefs={}, diagnostics=diag)

        if not graph.factors:
            beliefs = {}
            for vid in graph.variables:
                if vid in graph.hard_evidence:
                    beliefs[vid] = (
                        (1.0 - CROMWELL_EPS) if graph.hard_evidence[vid] == 1 else CROMWELL_EPS
                    )
                else:
                    beliefs[vid] = graph.unary_factors.get(vid, 0.5)
            for vid, b in beliefs.items():
                diag.belief_history[vid] = [b]
            return TRWResult(beliefs=beliefs, diagnostics=diag)

        var_to_factors = graph.get_var_to_factors()
        rho = _compute_factor_weights(graph, var_to_factors)
        if rho:
            diag.rho = (
                next(v for v in rho.values() if v < 1.0)
                if any(v < 1.0 for v in rho.values())
                else 1.0
            )

        def _prior_for(vid: str) -> Msg:
            if vid in graph.hard_evidence:
                v = graph.hard_evidence[vid]
                # Cromwell-clamped {ε, 1-ε} per Gaia's adjusted Jaynes Class I
                if v == 0:
                    return np.array([1.0 - CROMWELL_EPS, CROMWELL_EPS], dtype=np.float64)
                return np.array([CROMWELL_EPS, 1.0 - CROMWELL_EPS], dtype=np.float64)
            if vid in graph.unary_factors:
                return _prior_to_msg(graph.unary_factors[vid])
            return _uniform_msg()

        priors: dict[str, Msg] = {vid: _prior_for(vid) for vid in graph.variables}

        f2v_msgs: dict[tuple[int, str], Msg] = {}
        v2f_msgs: dict[tuple[str, int], Msg] = {}
        for fi, factor in enumerate(graph.factors):
            for vid in factor.all_vars:
                if vid in graph.variables:
                    f2v_msgs[(fi, vid)] = _uniform_msg()
                    v2f_msgs[(vid, fi)] = _uniform_msg()

        prev_beliefs: dict[str, float] = {}
        for vid in graph.variables:
            if vid in graph.hard_evidence:
                pi = (1.0 - CROMWELL_EPS) if graph.hard_evidence[vid] == 1 else CROMWELL_EPS
            else:
                pi = graph.unary_factors.get(vid, 0.5)
            prev_beliefs[vid] = pi
            diag.belief_history[vid] = [pi]

        if self._schedule == "synchronous":
            return self._run_synchronous(
                graph, diag, priors, var_to_factors, f2v_msgs, v2f_msgs, prev_beliefs, rho
            )
        return self._run_residual(
            graph, diag, priors, var_to_factors, f2v_msgs, v2f_msgs, prev_beliefs, rho
        )

    def _run_synchronous(
        self,
        graph: FactorGraph,
        diag: TRWDiagnostics,
        priors: dict[str, Msg],
        var_to_factors: dict[str, list[int]],
        f2v_msgs: dict[tuple[int, str], Msg],
        v2f_msgs: dict[tuple[str, int], Msg],
        prev_beliefs: dict[str, float],
        rho: dict[int, float],
    ) -> TRWResult:
        max_change = 0.0

        for iteration in range(self._max_iter):
            # v2f messages
            new_v2f: dict[tuple[str, int], Msg] = {}
            for vid, fi in v2f_msgs:
                if vid in graph.hard_evidence:
                    v = graph.hard_evidence[vid]
                    # Cromwell-clamped Class I message
                    if v == 0:
                        new_v2f[(vid, fi)] = np.array([1.0 - CROMWELL_EPS, CROMWELL_EPS])
                    else:
                        new_v2f[(vid, fi)] = np.array([CROMWELL_EPS, 1.0 - CROMWELL_EPS])
                else:
                    new_v2f[(vid, fi)] = _compute_v2f_trw(
                        vid, fi, priors[vid], var_to_factors, f2v_msgs, rho
                    )

            # f2v messages (use fresh v2f)
            new_f2v: dict[tuple[int, str], Msg] = {}
            for fi, vid in f2v_msgs:
                factor = graph.factors[fi]
                new_f2v[(fi, vid)] = _compute_f2v_trw(fi, vid, factor, new_v2f, rho)

            # Damp
            for key in f2v_msgs:
                blended = self._damping * new_f2v[key] + (1.0 - self._damping) * f2v_msgs[key]
                f2v_msgs[key] = _normalize(blended)

            for key in v2f_msgs:
                vid = key[0]
                if vid in graph.hard_evidence:
                    v2f_msgs[key] = new_v2f[key]
                else:
                    blended = self._damping * new_v2f[key] + (1.0 - self._damping) * v2f_msgs[key]
                    v2f_msgs[key] = _normalize(blended)

            # Beliefs + convergence
            beliefs = _compute_beliefs_trw(graph, priors, var_to_factors, f2v_msgs, rho)
            for vid in beliefs:
                diag.belief_history[vid].append(beliefs[vid])

            max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
            prev_beliefs = beliefs

            if max_change < self._threshold:
                diag.converged = True
                diag.iterations_run = iteration + 1
                diag.max_change_at_stop = max_change
                diag.compute_direction_changes()
                return TRWResult(beliefs=beliefs, diagnostics=diag)

        diag.converged = False
        diag.iterations_run = self._max_iter
        diag.max_change_at_stop = max_change
        diag.compute_direction_changes()
        return TRWResult(beliefs=prev_beliefs, diagnostics=diag)

    def _run_residual(
        self,
        graph: FactorGraph,
        diag: TRWDiagnostics,
        priors: dict[str, Msg],
        var_to_factors: dict[str, list[int]],
        f2v_msgs: dict[tuple[int, str], Msg],
        v2f_msgs: dict[tuple[str, int], Msg],
        prev_beliefs: dict[str, float],
        rho: dict[int, float],
    ) -> TRWResult:
        heap: list[tuple[float, str, tuple]] = []

        # Bootstrap sweep
        new_v2f_init: dict[tuple[str, int], Msg] = {}
        for vid, fi in v2f_msgs:
            if vid in graph.hard_evidence:
                v = graph.hard_evidence[vid]
                # Cromwell-clamped Class I message
                if v == 0:
                    new_v2f_init[(vid, fi)] = np.array([1.0 - CROMWELL_EPS, CROMWELL_EPS])
                else:
                    new_v2f_init[(vid, fi)] = np.array([CROMWELL_EPS, 1.0 - CROMWELL_EPS])
            else:
                new_v2f_init[(vid, fi)] = _compute_v2f_trw(
                    vid, fi, priors[vid], var_to_factors, f2v_msgs, rho
                )

        new_f2v_init: dict[tuple[int, str], Msg] = {}
        for fi, vid in f2v_msgs:
            factor = graph.factors[fi]
            new_f2v_init[(fi, vid)] = _compute_f2v_trw(fi, vid, factor, new_v2f_init, rho)

        for key in list(v2f_msgs.keys()):
            vid = key[0]
            if vid in graph.hard_evidence:
                v2f_msgs[key] = new_v2f_init[key]
                heapq.heappush(heap, (-1.0, "v2f", key))
            else:
                old = v2f_msgs[key]
                blended = self._damping * new_v2f_init[key] + (1.0 - self._damping) * old
                v2f_msgs[key] = _normalize(blended)
                residual = float(np.abs(v2f_msgs[key] - old).max())
                heapq.heappush(heap, (-max(residual, 1e-10), "v2f", key))

        for key in list(f2v_msgs.keys()):
            old = f2v_msgs[key]
            blended = self._damping * new_f2v_init[key] + (1.0 - self._damping) * old
            f2v_msgs[key] = _normalize(blended)
            residual = float(np.abs(f2v_msgs[key] - old).max())
            heapq.heappush(heap, (-max(residual, 1e-10), "f2v", key))

        total_updates = 0
        check_interval = max(1, len(f2v_msgs) + len(v2f_msgs))
        max_updates = self._max_iter * check_interval
        max_change = 0.0

        # Update prev_beliefs after bootstrap so first check_interval comparison is valid
        prev_beliefs = _compute_beliefs_trw(graph, priors, var_to_factors, f2v_msgs, rho)
        for vid in prev_beliefs:
            diag.belief_history[vid].append(prev_beliefs[vid])

        while total_updates < max_updates and heap:
            neg_residual, msg_type, key = heapq.heappop(heap)
            residual = -neg_residual

            if residual < self._threshold:
                diag.converged = True
                break

            if msg_type == "f2v":
                fi, vid = key
                factor = graph.factors[fi]
                new_msg = _compute_f2v_trw(fi, vid, factor, v2f_msgs, rho)
                old_msg = f2v_msgs[key]
                blended = self._damping * new_msg + (1.0 - self._damping) * old_msg
                f2v_msgs[key] = _normalize(blended)
                new_residual = float(np.abs(f2v_msgs[key] - old_msg).max())
                for fi2 in var_to_factors[vid]:
                    affected = (vid, fi2)
                    if affected in v2f_msgs and vid not in graph.hard_evidence:
                        heapq.heappush(heap, (-max(new_residual, 1e-10), "v2f", affected))
            else:
                vid, fi = key
                if vid in graph.hard_evidence:
                    total_updates += 1
                    continue
                new_msg = _compute_v2f_trw(vid, fi, priors[vid], var_to_factors, f2v_msgs, rho)
                old_msg = v2f_msgs[key]
                blended = self._damping * new_msg + (1.0 - self._damping) * old_msg
                v2f_msgs[key] = _normalize(blended)
                new_residual = float(np.abs(v2f_msgs[key] - old_msg).max())
                factor = graph.factors[fi]
                for v in factor.all_vars:
                    if v in graph.variables:
                        affected = (fi, v)
                        if affected in f2v_msgs:
                            heapq.heappush(heap, (-max(new_residual, 1e-10), "f2v", affected))

            total_updates += 1

            if total_updates % check_interval == 0:
                beliefs = _compute_beliefs_trw(graph, priors, var_to_factors, f2v_msgs, rho)
                max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
                for vid in beliefs:
                    diag.belief_history[vid].append(beliefs[vid])
                prev_beliefs = beliefs
                if max_change < self._threshold:
                    diag.converged = True
                    break

        if not diag.converged:
            beliefs = _compute_beliefs_trw(graph, priors, var_to_factors, f2v_msgs, rho)
            max_change = max(abs(beliefs[vid] - prev_beliefs[vid]) for vid in beliefs)
        else:
            beliefs = prev_beliefs

        diag.iterations_run = total_updates // check_interval
        diag.max_change_at_stop = max_change
        diag.compute_direction_changes()
        return TRWResult(beliefs=beliefs, diagnostics=diag)
