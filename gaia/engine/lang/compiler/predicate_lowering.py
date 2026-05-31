"""Lower predicate / equation BoolExpr propositions to prior records.

When the author writes ``claim("k is fast", k > 1e-2)``, the resulting Claim
carries the BoolExpr in ``metadata['predicate']``. This module walks the
package, computes ``P(k > 1e-2)`` from the underlying Distribution's CDF,
Cromwell-clamps the result, and registers it as a compiler-generated
``prior_records`` entry with ``source_id="continuous_inference"``. The
package-level :class:`ResolutionPolicy` then decides whether that generated
value or an author/reviewer value wins.

Equation propositions are stored in ``metadata['equation']`` for audit and
future lowering. This module does not infer equation truth from the marginal
distributions of the equation operands; if the author does not provide a
prior, it registers a neutral 0.5 default that can be overridden by any
explicit prior source.

Observation-aware posterior CDF (Normal-Normal / LogNormal-Normal conjugate
updates triggered by ``observe(distribution, value, error)``) is intentionally
deferred to a follow-up PR. PR1 uses the prior CDF directly; observations
declared on a Distribution are stashed for the future update path but do not
yet shift the predicate prior.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any

from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang.dsl.bool_expr import BoolExpr
from gaia.engine.lang.dsl.register_prior import PRIOR_RECORDS_METADATA_KEY, register_prior
from gaia.engine.lang.runtime.distribution import Distribution
from gaia.engine.lang.runtime.knowledge import Claim

if TYPE_CHECKING:
    from gaia.engine.lang.runtime.package import CollectedPackage


PREDICATE_LOWERING_SOURCE_ID: str = "continuous_inference"
"""``source_id`` for CDF-derived predicate priors.

The default ResolutionPolicy ranks this source above the low-friction
``claim_inline`` shortcut and below explicit author/reviewer sources.
"""

EQUATION_DEFAULT_SOURCE_ID: str = "equation_default"
"""Low-priority ``source_id`` for neutral equation defaults."""

PREDICATE_PRIOR_GENERATED_ATTR = "_gaia_predicate_prior_generated"
"""Private runtime marker distinguishing compiler-generated priors from author overrides."""


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))


def _resolve_threshold(value: Any, distribution: Distribution) -> float:
    """Coerce a literal threshold to a finite float in the distribution's unit.

    Accepts either a bare numeric scalar or a :class:`gaia.unit.Quantity`. When
    the LHS distribution carries a ``metadata['unit']``, the threshold MUST be
    a Quantity with a dimensionally-compatible unit (it is converted via
    Pint's ``.to()`` to the distribution's unit before extraction). When the
    distribution is unitless, the threshold MUST be a bare scalar — passing a
    Quantity in that case is a type error since the comparison would be
    ill-defined.

    Distributions on the right-hand side of an inequality are not yet
    supported — those would require a joint distribution over ``(lhs, rhs)``.
    """
    from gaia.unit import is_quantity, ureg

    distribution_unit: str | None = (distribution.metadata or {}).get("unit")

    if isinstance(value, Distribution):
        raise NotImplementedError(
            "Predicate with a Distribution on both sides is not yet supported. "
            "Express the predicate against a numeric threshold (e.g. "
            "k > 1e-3); a Distribution-vs-Distribution comparison would "
            "require joint marginalisation, which is deferred to a "
            "follow-up release."
        )
    if is_quantity(value):
        if distribution_unit is None:
            raise TypeError(
                "Predicate threshold is a unit-typed Quantity but the LHS "
                f"distribution {distribution.label or distribution.content[:40]!r} "
                "is unitless. Pass a bare scalar threshold or attach a unit "
                "to the distribution by passing Quantity-typed parameters."
            )
        try:
            converted = value.to(ureg.parse_units(distribution_unit))
        except Exception as err:  # pint raises a variety of subclasses
            raise ValueError(
                f"Predicate threshold unit {value.units!s} is not compatible "
                f"with the LHS distribution unit {distribution_unit!r}: {err}"
            ) from err
        threshold = float(converted.magnitude)
    else:
        if distribution_unit is not None:
            raise TypeError(
                f"Predicate threshold must be a Quantity in {distribution_unit!r} "
                f"because the LHS distribution "
                f"{distribution.label or distribution.content[:40]!r} carries "
                f"that unit; got bare scalar {value!r}."
            )
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(
                "Predicate threshold must be a numeric scalar; "
                f"got {type(value).__name__}: {value!r}."
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
    if distribution.kind in {"binomial", "poisson"}:
        if op == ">":
            cdf_threshold = math.floor(threshold)
            prior = 1.0 - distribution.cdf(cdf_threshold)
        elif op == ">=":
            cdf_threshold = math.ceil(threshold) - 1
            prior = 1.0 - distribution.cdf(cdf_threshold)
        elif op == "<":
            cdf_threshold = math.ceil(threshold) - 1
            prior = distribution.cdf(cdf_threshold)
        elif op == "<=":
            cdf_threshold = math.floor(threshold)
            prior = distribution.cdf(cdf_threshold)
        else:
            raise NotImplementedError(
                f"Predicate operator {op!r} is not yet supported for prior "
                "lowering. Use one of '>', '>=', '<', '<=' for inequality "
                "predicates, or attach the proposition as an equation via "
                "the '==' operator (which lowers to metadata['equation'] and "
                "expects an explicit `prior=` for the equation's truth claim)."
            )
        return _clamp(float(prior))

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


def _prior_records(claim: Claim) -> list[dict[str, Any]]:
    """Return claim prior records when the reserved metadata key is well-formed."""
    records = claim.metadata.get(PRIOR_RECORDS_METADATA_KEY, [])
    if not records:
        return []
    if not isinstance(records, list):
        raise TypeError(
            f"Claim {claim.label or claim.content[:40]!r} has "
            f"metadata[{PRIOR_RECORDS_METADATA_KEY!r}] of type "
            f"{type(records).__name__}, expected list."
        )
    return [record for record in records if isinstance(record, dict)]


def _has_non_generated_prior_record(claim: Claim) -> bool:
    """Whether a claim has any prior record not produced by this lowering pass."""
    return any(
        record.get("source_id") != PREDICATE_LOWERING_SOURCE_ID for record in _prior_records(claim)
    )


def _upsert_generated_prior_record(
    claim: Claim,
    value: float,
    *,
    justification: str,
    source_id: str = PREDICATE_LOWERING_SOURCE_ID,
) -> None:
    """Register or update this pass's generated prior without duplicating records."""
    records = claim.metadata.get(PRIOR_RECORDS_METADATA_KEY)
    if records is not None and not isinstance(records, list):
        raise TypeError(
            f"Claim {claim.label or claim.content[:40]!r} has "
            f"metadata[{PRIOR_RECORDS_METADATA_KEY!r}] of type "
            f"{type(records).__name__}, expected list."
        )
    if isinstance(records, list):
        for record in records:
            if isinstance(record, dict) and record.get("source_id") == source_id:
                record["value"] = value
                record["justification"] = justification
                setattr(claim, PREDICATE_PRIOR_GENERATED_ATTR, True)
                return
    register_prior(
        claim,
        value,
        source_id=source_id,
        justification=justification,
    )
    setattr(claim, PREDICATE_PRIOR_GENERATED_ATTR, True)


def _cdf_derived_prior(expr: BoolExpr) -> float:
    if not isinstance(expr.left, Distribution):
        raise TypeError(
            "Predicate claim left-hand side must be a Distribution; "
            f"got {type(expr.left).__name__}. The proposition is "
            f"`{expr.left!r} {expr.op} {expr.right!r}`."
        )
    threshold = _resolve_threshold(expr.right, expr.left)
    return _predicate_prior(expr.left, expr.op, threshold)


def _audit_cdf_prior(claim: Claim, cdf_derived: float | None) -> None:
    meta = dict(claim.metadata)
    audit = dict(meta.get("predicate_audit") or {})
    audit["cdf_derived_prior"] = cdf_derived
    meta["predicate_audit"] = audit
    claim.metadata = meta


def _lower_predicate_claim(claim: Claim) -> None:
    """Compute and register the generated prior for a single predicate claim."""
    expr = claim.metadata.get("predicate")
    if not isinstance(expr, BoolExpr):
        return
    cdf_derived = _cdf_derived_prior(expr)
    _upsert_generated_prior_record(
        claim,
        cdf_derived,
        justification="CDF-derived predicate prior from distribution CDF.",
    )
    if claim.prior is not None or _has_non_generated_prior_record(claim):
        _audit_cdf_prior(claim, cdf_derived)


def _has_direct_or_registered_prior(claim: Claim) -> bool:
    prior_was_generated = bool(getattr(claim, PREDICATE_PRIOR_GENERATED_ATTR, False))
    return (claim.prior is not None and not prior_was_generated) or bool(_prior_records(claim))


def _register_neutral_equation_prior(claim: Claim) -> None:
    _upsert_generated_prior_record(
        claim,
        0.5,
        justification=(
            "Neutral default for equation truth claim; equation constraint "
            "lowering is not implemented yet."
        ),
        source_id=EQUATION_DEFAULT_SOURCE_ID,
    )


def _lower_equation_claim(claim: Claim) -> None:
    """Validate an equation claim; defer prior derivation to follow-up PR.

    PR1 stores the equation expression and uses prior records for the
    equation's truth claim. That truth prior is methodologically separate from
    the involved distributions — for example "this calibration equation
    holds" has a prior reflecting the author's confidence in the law/model,
    which is not derivable from the marginal distributions of the operands
    alone.
    """
    expr = claim.metadata.get("equation")
    if not isinstance(expr, BoolExpr):
        return
    if not _has_direct_or_registered_prior(claim):
        # Author asserted an equation but didn't say how much they believe in
        # it. Default to the neutral 0.5 — the author can override.
        _register_neutral_equation_prior(claim)


def lower_predicate_priors(package: CollectedPackage) -> None:
    """Walk the package and compute predicate-derived priors in place.

    Mutates each Claim that carries ``metadata['predicate']`` (an inequality
    BoolExpr) by registering the CDF-derived prior in ``prior_records``.
    Equation claims (``metadata['equation']``) keep author priors or receive
    a neutral generated default of 0.5.

    This is invoked at the start of :func:`compile_package_artifact` so the
    ResolutionPolicy can collapse all prior records to one resolved
    ``metadata['prior']`` before IR emission.
    """
    for knowledge in package.knowledge:
        if not isinstance(knowledge, Claim):
            continue
        if "predicate" in knowledge.metadata:
            _lower_predicate_claim(knowledge)
        elif "equation" in knowledge.metadata:
            _lower_equation_claim(knowledge)
