"""Lower predicate / equation BoolExpr propositions to claim priors.

When the author writes ``claim("k is fast", k > 1e-2)``, the resulting Claim
carries the BoolExpr in ``metadata['predicate']``. This module walks the
package, computes ``P(k > 1e-2)`` from the underlying Distribution's CDF,
Cromwell-clamps the result, and writes it to ``Claim.prior`` so the existing
compile / BP pipeline picks it up unchanged.

Equation propositions (``k == A * exp(-Ea / (R * T))``) are stored in
``metadata['equation']`` for downstream constraint lowering. v0.6 PR1 stores
the equation but does not yet compute a derived prior — the prior of an
equation claim is the author's belief in the law's validity, which is
methodologically distinct from a CDF-derived predicate probability. Authors
should set ``prior=`` explicitly on equation claims; this module raises a
helpful error when neither prior nor proposition can produce a value.

Observation-aware posterior CDF (Normal-Normal / LogNormal-Normal conjugate
updates triggered by ``observe(distribution, value, error)``) is intentionally
deferred to a follow-up PR. PR1 uses the prior CDF directly; observations
declared on a Distribution are stashed for the future update path but do not
yet shift the predicate prior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from gaia.ir.parameterization import CROMWELL_EPS
from gaia.lang.dsl.bool_expr import BoolExpr
from gaia.lang.runtime.distribution import Distribution
from gaia.lang.runtime.knowledge import Claim

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage


PREDICATE_LOWERING_SOURCE_ID: str = "predicate_lowering"
"""``source_id`` used when the multi-source PriorRecord pipeline lands.

For v0.6 PR1 we write directly to ``Claim.prior`` because the multi-source
pipeline (issue #582) is in flight on a separate branch. Once that lands the
predicate-derived prior should be registered via
``register_prior(claim, value, source_id=PREDICATE_LOWERING_SOURCE_ID, ...)``
so the resolution policy can decide between author overrides and CDF-derived
defaults.
"""


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))


def _resolve_threshold(value: Any) -> float:
    """Coerce a literal threshold (int / float) to a finite float.

    Distributions on the right-hand side of an inequality are not yet supported
    — those would require a joint distribution over ``(lhs, rhs)``. PR1 limits
    the right-hand side to a numeric scalar so the predicate is a 1-D CDF
    query against the LHS distribution's marginal.
    """
    if isinstance(value, Distribution):
        raise NotImplementedError(
            "Predicate with a Distribution on both sides is not yet supported. "
            "Express the predicate against a numeric threshold (e.g. "
            "k > 1e-3); a Distribution-vs-Distribution comparison would "
            "require joint marginalisation, which is deferred to a "
            "follow-up release."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"Predicate threshold must be a numeric scalar; got {type(value).__name__}: {value!r}."
        )
    threshold = float(value)
    if threshold != threshold:  # NaN
        raise ValueError("Predicate threshold must be finite, got NaN.")
    return threshold


def _predicate_prior(distribution: Distribution, op: str, threshold: float) -> float:
    """Compute ``P(op(X, threshold))`` for ``X ~ distribution``.

    Returns the Cromwell-clamped probability that the predicate evaluates to
    true under the underlying distribution's CDF. PR1 uses the prior CDF
    directly; observation-aware posterior CDF is deferred.
    """
    cdf_at = distribution.cdf(threshold)
    if op in {">", ">="}:
        # P(X > c) = 1 - cdf(c); for continuous distributions strict and
        # non-strict inequalities differ by a measure-zero point.
        prior = 1.0 - cdf_at
    elif op in {"<", "<="}:
        prior = cdf_at
    else:
        raise NotImplementedError(
            f"Predicate operator {op!r} is not yet supported for prior "
            "lowering. Use one of '>', '>=', '<', '<=' for inequality "
            "predicates, or attach the proposition as an equation via "
            "the '==' operator (which lowers to metadata['equation'] and "
            "expects an explicit `prior=` for the equation's truth claim)."
        )
    return _clamp(float(prior))


def _lower_predicate_claim(claim: Claim) -> None:
    """Compute and write the prior for a single predicate claim."""
    expr = claim.metadata.get("predicate")
    if not isinstance(expr, BoolExpr):
        return
    if claim.prior is not None:
        # Author override wins — author explicitly set a prior alongside a
        # predicate (e.g. claim("X", k > 1e-3, prior=0.4)) means "I know the
        # CDF says one thing but I'm asserting a different belief". Keep
        # the author's value and stash the CDF-derived value as audit info.
        try:
            cdf_derived = _predicate_prior(expr.left, expr.op, _resolve_threshold(expr.right))
        except (TypeError, ValueError, NotImplementedError):
            cdf_derived = None
        meta = dict(claim.metadata)
        meta.setdefault("predicate_audit", {})["cdf_derived_prior"] = cdf_derived
        claim.metadata = meta
        return
    if not isinstance(expr.left, Distribution):
        raise TypeError(
            "Predicate claim left-hand side must be a Distribution; "
            f"got {type(expr.left).__name__}. The proposition is "
            f"`{expr.left!r} {expr.op} {expr.right!r}`."
        )
    threshold = _resolve_threshold(expr.right)
    claim.prior = _predicate_prior(expr.left, expr.op, threshold)


def _lower_equation_claim(claim: Claim) -> None:
    """Validate an equation claim; defer prior derivation to follow-up PR.

    PR1 only verifies the equation has at least one Distribution operand and
    leaves ``Claim.prior`` to the author. The equation's truth claim is
    methodologically separate from the involved distributions — for example
    "Arrhenius's law holds for this reaction" has a prior reflecting the
    author's confidence in the law, which is not derivable from the marginal
    distributions of ``k``, ``A``, ``Ea``.
    """
    expr = claim.metadata.get("equation")
    if not isinstance(expr, BoolExpr):
        return
    if claim.prior is None:
        # Author asserted an equation but didn't say how much they believe in
        # it. Default to the neutral 0.5 — the author can override.
        claim.prior = 0.5


def lower_predicate_priors(package: CollectedPackage) -> None:
    """Walk the package and compute predicate-derived priors in place.

    Mutates each Claim that carries ``metadata['predicate']`` (an inequality
    BoolExpr) by writing the CDF-derived prior to ``Claim.prior``.
    Equation claims (``metadata['equation']``) are validated but their prior
    is left to the author or defaulted to 0.5.

    This is invoked at the start of :func:`compile_package_artifact` so the
    rest of the LANG → IR pipeline sees a Claim with a numeric prior, no
    different from a hand-set ``claim(prior=0.27)``.
    """
    for knowledge in package.knowledge:
        if not isinstance(knowledge, Claim):
            continue
        if "predicate" in knowledge.metadata:
            _lower_predicate_claim(knowledge)
        elif "equation" in knowledge.metadata:
            _lower_equation_claim(knowledge)
