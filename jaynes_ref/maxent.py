"""MaxEnt prior reconstruction from moment constraints (PTLoS Ch. 11).

Given a finite sample space (we use the 2^n joint over an
InformationSet's universe) and a set of moment constraints
E_p[f_k] = mu_k, return the distribution

    p*(x) ~ exp(sum_k lam_k f_k(x))

that has maximum Shannon entropy subject to those constraints.

The Lagrange multipliers lam_k are found by minimizing the dual

    Psi(lam) = log Z(lam) - sum_k lam_k mu_k,
    Z(lam)   = sum_x exp(sum_k lam_k f_k(x)),

a smooth convex problem with gradient E_{p_lam}[f_k] - mu_k and
Hessian = Cov_{p_lam}(f). We use Newton with a damped step.

This is the Jaynes-correct way to **derive** a class-IV prior from
authored sufficient statistics, instead of having the author write pi
directly. Returns the full joint p* and the fitted lam.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from jaynes_ref.exact import _MAX_N, _enumerate_states
from jaynes_ref.information import InformationSet

# A moment constraint is described by (feature function on full state, target mu).
MomentFeature = Callable[[np.ndarray], np.ndarray]  # (N, n_vars) int8 -> (N,) float


@dataclass(frozen=True)
class MomentConstraint:
    """Moment constraint for maximum entropy problem."""

    label: str
    feature: MomentFeature
    target: float


@dataclass(frozen=True)
class MaxEntFit:
    """Maximum entropy distribution fit result."""

    p: np.ndarray  # length 2**n
    lam: np.ndarray  # length n_constraints
    log_Z: float
    iters: int
    grad_inf_norm: float


def marginal_constraint(var_idx: int, target: float) -> MomentConstraint:
    """E[x_i] = target, with x_i in {0,1}."""

    def f(states: np.ndarray) -> np.ndarray:
        return states[:, var_idx].astype(np.float64)

    return MomentConstraint(label=f"E[x_{var_idx}]={target}", feature=f, target=float(target))


def correlation_constraint(i: int, j: int, target: float) -> MomentConstraint:
    """E[x_i * x_j] = target."""

    def f(states: np.ndarray) -> np.ndarray:
        return (states[:, i] * states[:, j]).astype(np.float64)

    return MomentConstraint(label=f"E[x_{i}x_{j}]={target}", feature=f, target=float(target))


def fit_maxent(
    n: int,
    constraints: Sequence[MomentConstraint],
    *,
    tol: float = 1e-10,
    max_iter: int = 200,
    damping: float = 1.0,
) -> MaxEntFit:
    """Newton solve for lam minimizing Psi(lam) on the 2^n full sample space.

    Returns a MaxEntFit. Convergence criterion: ||E_p[f] - mu||_inf < tol.
    Raises RuntimeError if Newton fails to converge within max_iter.
    """
    if n < 0 or n > _MAX_N:
        raise ValueError(f"n={n} outside [0, {_MAX_N}]")
    states = _enumerate_states(n)
    K = len(constraints)
    F = np.stack([c.feature(states) for c in constraints], axis=1) if K else np.zeros((1 << n, 0))
    mu = np.array([c.target for c in constraints], dtype=np.float64)

    lam = np.zeros(K, dtype=np.float64)
    last_grad = np.inf
    for it in range(max_iter):
        scores = F @ lam if K else np.zeros(1 << n)
        m = scores.max()
        w = np.exp(scores - m)
        Z = w.sum()
        log_Z = float(m + np.log(Z))
        p = w / Z

        Ef = F.T @ p if K else np.zeros(0)
        grad = Ef - mu  # dPsi/dlam_k = E[f_k] - mu_k
        gnorm = float(np.linalg.norm(grad, ord=np.inf)) if K else 0.0
        if gnorm < tol or K == 0:
            return MaxEntFit(p=p, lam=lam, log_Z=log_Z, iters=it, grad_inf_norm=gnorm)

        # Hessian = Cov_p(f); add tiny ridge to guarantee SPD.
        FW = F * p[:, None]
        Cov = F.T @ FW - np.outer(Ef, Ef)
        Cov.flat[:: K + 1] += 1e-12
        try:
            step = np.linalg.solve(Cov, grad)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(Cov, grad, rcond=None)[0]
        lam = lam - damping * step
        last_grad = gnorm

    raise RuntimeError(
        f"MaxEnt Newton failed: last grad inf-norm = {last_grad}, target tol = {tol}"
    )


def maxent_from_info(
    info: InformationSet,
    constraints: Sequence[MomentConstraint],
    **kwargs,
) -> MaxEntFit:
    """Wrapper that pins n to info.variables. Constraint features must.

    consume a (N, n) int8 array indexed by sorted(info.variables).
    """
    info.validate()
    n = len(info.variables)
    return fit_maxent(n, constraints, **kwargs)


def marginal_from_fit(
    fit: MaxEntFit,
    n: int,
    var_idx: int,
) -> float:
    """Marginal P(x_{var_idx} = 1) under the fitted MaxEnt joint p*."""
    if not (0 <= var_idx < n):
        raise ValueError(f"var_idx={var_idx} outside [0, {n})")
    if fit.p.shape[0] != (1 << n):
        raise ValueError(f"fit.p has length {fit.p.shape[0]}, expected {1 << n}")
    states = _enumerate_states(n)
    mask = states[:, var_idx] == 1
    return float(fit.p[mask].sum())


def inject_marginal_priors(
    info: InformationSet,
    fit: MaxEntFit,
    *,
    targets: list[str] | None = None,
    eps: float = 1e-6,
) -> InformationSet:
    """Write MaxEnt-derived marginals back into info.unary_priors.

    For each variable v in 'targets' (defaults to info.free_variables()),
    compute pi_v = sum_{x : x_v = 1} p*(x) and add (v, pi_v) to a copy
    of 'info'. If pi_v falls within [eps, 1-eps] only — values at the
    boundary would violate the (0, 1) strict constraint on class IV and
    are rerouted to hard_evidence per D4.

    NOTE on lossy compression: if the MaxEnt fit captured correlations
    (e.g. via correlation_constraint), writing the marginals back as
    independent unary_priors discards that structure. Use this only
    when the moment constraints were strictly marginal in nature, OR
    accept the independence approximation deliberately.
    """
    import copy

    info.validate()
    sorted_vars = sorted(info.variables)
    n = len(sorted_vars)
    if fit.p.shape[0] != (1 << n):
        raise ValueError(
            f"fit.p length {fit.p.shape[0]} != 2^{n} = {1 << n}; "
            "fit must be over info's full variable set"
        )

    if targets is None:
        targets = sorted(info.free_variables())
    for v in targets:
        if v not in info.variables:
            raise ValueError(f"target {v!r} not in info.variables")

    new_info = copy.deepcopy(info)
    for v in targets:
        idx = sorted_vars.index(v)
        pi = marginal_from_fit(fit, n, idx)
        if pi <= eps:
            if v in new_info.unary_priors:
                del new_info.unary_priors[v]
            new_info.hard_evidence[v] = 0
        elif pi >= 1.0 - eps:
            if v in new_info.unary_priors:
                del new_info.unary_priors[v]
            new_info.hard_evidence[v] = 1
        else:
            if v in new_info.hard_evidence:
                raise ValueError(
                    f"inject_marginal_priors: cannot overwrite hard_evidence[{v!r}] "
                    "with a soft prior (D1)."
                )
            new_info.unary_priors[v] = float(pi)
    new_info.validate()
    return new_info
