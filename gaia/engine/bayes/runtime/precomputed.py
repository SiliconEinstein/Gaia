"""PrecomputedLikelihoods Claim — audit-bearing external-solver output.

A :class:`PrecomputedLikelihoods` Claim is the canonical v0.6 representation
of "log-likelihoods that came out of an external statistical solver"
(PyMC NUTS, Stan HMC, NumPyro SVI, custom MCMC, ...). It is what authors
return from a :func:`compute`-decorated wrapper that calls into an external
PPL, and it is what :func:`gaia.engine.bayes.compare` accepts via
``precomputed=`` when the computation deserves a citable record (as opposed
to the back-of-the-envelope ``dict[Claim, float]`` shortcut).

Design intent
-------------
The dict shortcut from v0.5 is preserved — passing
``precomputed={h1: -1.2, h2: -5.1}`` to ``compare()`` still works. The
``PrecomputedLikelihoods`` Claim adds two things on top of the bare dict:

1. **Audit trail.** As a Claim subclass it lives in the package
   ``knowledges`` list, can carry a label, and is naturally produced by a
   :class:`gaia.engine.lang.runtime.action.Compute` action that records
   ``fn`` and ``code_hash``. ``gaia review`` and ``gaia explain`` reach the
   computation through the standard action graph.

2. **Solver diagnostics.** Solver convergence statistics (r_hat, ESS,
   divergences, seed, model spec hash, ...) travel alongside the
   log-likelihoods themselves so ``gaia audit`` can grow rules that
   inspect them.

The Claim's ``content`` is auto-generated when not supplied, summarising
the solver and the hypothesis count. Authors who want a richer prose
record can pass ``content=...`` explicitly.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from gaia.engine.lang.runtime.knowledge import Claim


def _default_content(solver: str, n_hypotheses: int) -> str:
    """Auto-generate a content string when the author omits one."""
    label = solver or "external solver"
    if n_hypotheses == 0:
        return f"Precomputed log-likelihoods from {label}."
    plural = "hypothesis" if n_hypotheses == 1 else "hypotheses"
    return f"Precomputed log-likelihoods from {label} over {n_hypotheses} {plural}."


@dataclass(init=False, eq=False)
class PrecomputedLikelihoods(Claim):
    """Externally computed log-likelihoods packaged as a Claim.

    Attributes:
    ----------
    log_likelihoods:
        Mapping from hypothesis :class:`Claim` (the original objects passed
        to :func:`gaia.engine.bayes.model`) to ``log P(data | H_i)``. Same
        key shape as the legacy ``compare(precomputed=...)`` dict.
    diagnostics:
        Solver-specific convergence and provenance fields. Opaque to Gaia;
        consumed by ``gaia audit`` rules and reviewers. Recommended keys:
        ``r_hat_max``, ``ess_min``, ``divergences``, ``seed``,
        ``model_spec_hash``.
    solver:
        Free-form solver label, e.g. ``"pymc-nuts-4000"`` or ``"custom"``.
    """

    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)
    solver: str = ""

    def __init__(
        self,
        content: str | None = None,
        *,
        log_likelihoods: dict[Claim, float] | None = None,
        diagnostics: dict[str, Any] | None = None,
        solver: str = "",
        label: str | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialise the precomputed-likelihoods Claim."""
        likelihoods = dict(log_likelihoods or {})
        if any(not isinstance(k, Claim) for k in likelihoods):
            raise TypeError(
                "PrecomputedLikelihoods(log_likelihoods=...) keys must be "
                "the original hypothesis Claim objects."
            )
        for key, value in likelihoods.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise TypeError(
                    f"PrecomputedLikelihoods(log_likelihoods=...) value for "
                    f"{key.label or key.content[:40]!r} must be a numeric "
                    f"log-likelihood, got {type(value).__name__}: {value!r}."
                )
            float_value = float(value)
            # NaN is never a meaningful log-likelihood; +inf would later be
            # Cromwell-clamped to near-1 and silently dominate. -inf ("zero
            # likelihood under this hypothesis") is allowed; the comparison
            # lowering rejects the case where *all* hypotheses are -inf.
            if math.isnan(float_value):
                raise ValueError(
                    "PrecomputedLikelihoods log-likelihood for "
                    f"{key.label or key.content[:40]!r} is NaN. Fix the "
                    "wrapper to record a real log-likelihood, not a missing "
                    "sentinel."
                )
            if math.isinf(float_value) and float_value > 0:
                raise ValueError(
                    "PrecomputedLikelihoods log-likelihood for "
                    f"{key.label or key.content[:40]!r} is +inf. A finite "
                    "log-likelihood is required; +inf would silently dominate "
                    "the comparison."
                )

        resolved_content = content or _default_content(solver, len(likelihoods))
        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("kind", "precomputed_likelihoods")
        merged_metadata.setdefault("solver", solver)
        # Mirror diagnostics onto metadata so the IR / gaia build check / gaia
        # explain can introspect them without walking back to the runtime
        # PrecomputedLikelihoods instance. The dataclass-field
        # ``self.diagnostics`` remains the canonical runtime accessor; this
        # mirror is the IR-visible projection.
        merged_metadata.setdefault("diagnostics", dict(diagnostics or {}))

        super().__init__(
            content=resolved_content,
            metadata=merged_metadata,
            label=label,
            **kwargs,
        )
        self.log_likelihoods = {key: float(value) for key, value in likelihoods.items()}
        self.diagnostics = dict(diagnostics or {})
        self.solver = solver


__all__ = ["PrecomputedLikelihoods"]
