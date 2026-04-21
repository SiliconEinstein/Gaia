"""Small standard likelihood score modules for v6 experiments."""

from __future__ import annotations

import math
from collections.abc import Callable

from gaia.ir.likelihood_registry import (
    BINOMIAL_MODEL_REF,
    BINOMIAL_MODEL_SPEC,
    GAUSSIAN_MODEL_COMPARISON_REF,
    GAUSSIAN_MODEL_COMPARISON_SPEC,
    TWO_BINOMIAL_AB_TEST_REF,
    TWO_BINOMIAL_AB_TEST_SPEC,
)
from gaia.lang import ParameterizedClaim, compute, likelihood_from
from gaia.lang.runtime import Knowledge, LikelihoodScore, Strategy
from scipy.stats import binom, norm

__all__ = [
    "BINOMIAL_MODEL_REF",
    "BINOMIAL_MODEL_SPEC",
    "GAUSSIAN_MODEL_COMPARISON_REF",
    "GAUSSIAN_MODEL_COMPARISON_SPEC",
    "TWO_BINOMIAL_AB_TEST_REF",
    "TWO_BINOMIAL_AB_TEST_SPEC",
    "BinomialModelLogLR",
    "GaussianModelComparisonLogLR",
    "TwoBinomialABLogLR",
    "ab_test",
    "binomial_log_likelihood",
    "binomial_model_log_lr",
    "binomial_model_log_lr_claim",
    "binomial_model_score",
    "binomial_test",
    "gaussian_model_comparison",
    "gaussian_model_comparison_from_claims",
    "gaussian_model_comparison_log_lr",
    "gaussian_model_comparison_log_lr_claim",
    "two_binomial_ab_log_lr_claim",
    "two_binomial_ab_test_score",
    "two_binomial_signed_log_lr",
]


def _validate_count(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _validate_probability(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be between 0 and 1")


def _mle_probability(successes: int, trials: int) -> float:
    if trials == 0:
        raise ValueError("trials must be positive")
    return successes / trials


def binomial_log_likelihood(successes: int, trials: int, probability: float) -> float:
    """Return log P(K=successes | trials, probability)."""
    _validate_count("successes", successes)
    _validate_count("trials", trials)
    _validate_probability("probability", probability)
    if successes > trials:
        raise ValueError("successes cannot exceed trials")
    if trials == 0:
        raise ValueError("trials must be positive")
    return float(binom.logpmf(successes, trials, probability))


def binomial_model_log_lr(successes: int, trials: int, probability: float) -> float:
    """Compare an explicit binomial model against the saturated MLE model.

    The result is log L(model) - log L(MLE), so it is always <= 0. Values near
    zero mean the explicit model explains the observed count almost as well as
    the best-fitting binomial probability.
    """
    p_hat = _mle_probability(successes, trials)
    return binomial_log_likelihood(successes, trials, probability) - binomial_log_likelihood(
        successes, trials, p_hat
    )


def binomial_model_score(
    *,
    target: Knowledge,
    successes: int,
    trials: int,
    probability: float,
    query: str | dict | None = None,
) -> LikelihoodScore:
    """Score whether binomial counts fit an explicit probability model."""
    log_lr = binomial_model_log_lr(successes, trials, probability)
    p_hat = _mle_probability(successes, trials)
    if query is None:
        query = {"distribution": "binomial", "success_probability": probability}
    return LikelihoodScore(
        target=target,
        module_ref=BINOMIAL_MODEL_REF,
        score_type="log_lr",
        value=log_lr,
        query=query,
        rationale=(
            f"log L(p={probability:g}) - log L(p_hat={p_hat:g}) for "
            f"k={successes}, n={trials}"
        ),
    )


class BinomialModelLogLR(ParameterizedClaim):
    template = (
        "The binomial-model log-likelihood ratio is {value} for {successes} "
        "successes out of {trials} trials under probability {probability}."
    )
    kind = "likelihood_score"
    metadata = {
        "generated": True,
        "helper_kind": "likelihood_score",
        "module_ref": BINOMIAL_MODEL_REF,
        "score_type": "log_lr",
    }

    successes: int
    trials: int
    probability: float
    value: float


@compute(
    output=BinomialModelLogLR,
    kind="likelihood_score",
    metadata={"module_ref": BINOMIAL_MODEL_REF, "score_type": "log_lr"},
)
def binomial_model_log_lr_claim(successes: int, trials: int, probability: float) -> float:
    """Compute a binomial log-LR as a Gaia score Claim."""
    return binomial_model_log_lr(successes, trials, probability)


def binomial_test(
    *,
    target: Knowledge,
    successes: int,
    trials: int,
    probability: float,
    data: Knowledge | None = None,
    assumptions: list[Knowledge] | None = None,
    query: str | dict | None = None,
) -> Strategy:
    """Standard binomial-model likelihood helper backed by SciPy."""
    score = binomial_model_log_lr_claim(
        successes=successes,
        trials=trials,
        probability=probability,
    )
    return likelihood_from(
        target=target,
        data=[data] if data is not None else [],
        assumptions=assumptions or [],
        score=score,
        module_ref=BINOMIAL_MODEL_REF,
        query=query or {"distribution": "binomial", "success_probability": probability},
        reason="Use the SciPy-backed binomial log-likelihood score.",
    )


def two_binomial_signed_log_lr(
    *,
    control_successes: int,
    control_trials: int,
    treatment_successes: int,
    treatment_trials: int,
) -> float:
    """Return a signed log LR for theta_treatment > theta_control.

    Magnitude is the log-likelihood gain of separate binomial rates over a
    pooled rate. Sign follows the observed treatment-control rate difference.
    """
    _validate_count("control_successes", control_successes)
    _validate_count("control_trials", control_trials)
    _validate_count("treatment_successes", treatment_successes)
    _validate_count("treatment_trials", treatment_trials)
    if control_trials == 0 or treatment_trials == 0:
        raise ValueError("trials must be positive")
    if control_successes > control_trials:
        raise ValueError("control_successes cannot exceed control_trials")
    if treatment_successes > treatment_trials:
        raise ValueError("treatment_successes cannot exceed treatment_trials")

    control_rate = control_successes / control_trials
    treatment_rate = treatment_successes / treatment_trials
    pooled_rate = (control_successes + treatment_successes) / (
        control_trials + treatment_trials
    )
    separate_log_likelihood = binomial_log_likelihood(
        control_successes, control_trials, control_rate
    ) + binomial_log_likelihood(treatment_successes, treatment_trials, treatment_rate)
    pooled_log_likelihood = binomial_log_likelihood(
        control_successes, control_trials, pooled_rate
    ) + binomial_log_likelihood(treatment_successes, treatment_trials, pooled_rate)
    magnitude = separate_log_likelihood - pooled_log_likelihood
    sign = 1.0 if treatment_rate >= control_rate else -1.0
    return sign * magnitude


def two_binomial_ab_test_score(
    *,
    target: Knowledge,
    control_successes: int,
    control_trials: int,
    treatment_successes: int,
    treatment_trials: int,
    query: str | dict = "theta_treatment > theta_control",
) -> LikelihoodScore:
    """Score an AB-test direction query using two binomial samples."""
    log_lr = two_binomial_signed_log_lr(
        control_successes=control_successes,
        control_trials=control_trials,
        treatment_successes=treatment_successes,
        treatment_trials=treatment_trials,
    )
    return LikelihoodScore(
        target=target,
        module_ref=TWO_BINOMIAL_AB_TEST_REF,
        score_type="log_lr",
        value=log_lr,
        query=query,
        rationale=(
            "signed log-likelihood gain of separate binomial rates over "
            "a pooled-rate model"
        ),
    )


class TwoBinomialABLogLR(ParameterizedClaim):
    template = (
        "The two-binomial AB-test log-likelihood ratio is {value} for control "
        "{control_successes}/{control_trials} and treatment "
        "{treatment_successes}/{treatment_trials}."
    )
    kind = "likelihood_score"
    metadata = {
        "generated": True,
        "helper_kind": "likelihood_score",
        "module_ref": TWO_BINOMIAL_AB_TEST_REF,
        "score_type": "log_lr",
    }

    control_successes: int
    control_trials: int
    treatment_successes: int
    treatment_trials: int
    value: float


@compute(
    output=TwoBinomialABLogLR,
    kind="likelihood_score",
    metadata={"module_ref": TWO_BINOMIAL_AB_TEST_REF, "score_type": "log_lr"},
)
def two_binomial_ab_log_lr_claim(
    control_successes: int,
    control_trials: int,
    treatment_successes: int,
    treatment_trials: int,
) -> float:
    """Compute a two-binomial AB-test log-LR as a Gaia score Claim."""
    return two_binomial_signed_log_lr(
        control_successes=control_successes,
        control_trials=control_trials,
        treatment_successes=treatment_successes,
        treatment_trials=treatment_trials,
    )


def ab_test(
    *,
    target: Knowledge,
    control_successes: int,
    control_trials: int,
    treatment_successes: int,
    treatment_trials: int,
    data: Knowledge | None = None,
    assumptions: list[Knowledge] | None = None,
    query: str | dict = "theta_treatment > theta_control",
) -> Strategy:
    """Standard two-binomial AB-test likelihood helper."""
    score = two_binomial_ab_log_lr_claim(
        control_successes=control_successes,
        control_trials=control_trials,
        treatment_successes=treatment_successes,
        treatment_trials=treatment_trials,
    )
    return likelihood_from(
        target=target,
        data=[data] if data is not None else [],
        assumptions=assumptions or [],
        score=score,
        module_ref=TWO_BINOMIAL_AB_TEST_REF,
        query=query,
        reason="Use the SciPy-backed two-binomial AB-test likelihood score.",
    )


def gaussian_model_comparison_log_lr(
    *,
    observed: float,
    candidate_mean: float,
    baseline_mean: float,
    sigma: float,
) -> float:
    """Return log p(observed | candidate) - log p(observed | baseline)."""
    if not all(math.isfinite(v) for v in [observed, candidate_mean, baseline_mean, sigma]):
        raise ValueError("observed, means, and sigma must be finite")
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return float(
        norm.logpdf(observed, loc=candidate_mean, scale=sigma)
        - norm.logpdf(observed, loc=baseline_mean, scale=sigma)
    )


class GaussianModelComparisonLogLR(ParameterizedClaim):
    template = (
        "The Gaussian model-comparison log-likelihood ratio is {value} for "
        "observed value {observed}, candidate mean {candidate_mean}, baseline "
        "mean {baseline_mean}, and sigma {sigma}."
    )
    kind = "likelihood_score"
    metadata = {
        "generated": True,
        "helper_kind": "likelihood_score",
        "module_ref": GAUSSIAN_MODEL_COMPARISON_REF,
        "score_type": "log_lr",
    }

    observed: float
    candidate_mean: float
    baseline_mean: float
    sigma: float
    value: float


@compute(
    output=GaussianModelComparisonLogLR,
    kind="likelihood_score",
    metadata={"module_ref": GAUSSIAN_MODEL_COMPARISON_REF, "score_type": "log_lr"},
)
def gaussian_model_comparison_log_lr_claim(
    observed: float,
    candidate_mean: float,
    baseline_mean: float,
    sigma: float,
) -> float:
    """Compute a Gaussian model-comparison log-LR as a Gaia score Claim."""
    return gaussian_model_comparison_log_lr(
        observed=observed,
        candidate_mean=candidate_mean,
        baseline_mean=baseline_mean,
        sigma=sigma,
    )


def _gaussian_model_comparison_query() -> dict[str, str]:
    return {
        "type": "gaussian_model_comparison",
        "direction": "candidate_over_baseline",
    }


def gaussian_model_comparison(
    *,
    target: Knowledge,
    observed: float,
    candidate_mean: float,
    baseline_mean: float,
    sigma: float,
    data: Knowledge | None = None,
    assumptions: list[Knowledge] | None = None,
    query: str | dict | None = None,
) -> Strategy:
    """Likelihood helper for comparing two Gaussian predictive models."""
    score = gaussian_model_comparison_log_lr_claim(
        observed=observed,
        candidate_mean=candidate_mean,
        baseline_mean=baseline_mean,
        sigma=sigma,
    )
    return likelihood_from(
        target=target,
        data=[data] if data is not None else [],
        assumptions=assumptions or [],
        score=score,
        module_ref=GAUSSIAN_MODEL_COMPARISON_REF,
        query=query if query is not None else _gaussian_model_comparison_query(),
        reason="Use the SciPy-backed Gaussian model-comparison likelihood score.",
    )


def _parameter_value(source: Knowledge, field: str):
    for parameter in source.parameters:
        if parameter.get("name") == field:
            return parameter.get("value")
    label = source.label or source.title or source.content[:40]
    raise ValueError(f"Claim {label!r} has no parameter named {field!r}")


def _numeric_parameter(source: Knowledge, field: str) -> float:
    value = _parameter_value(source, field)
    if isinstance(value, bool) or not isinstance(value, int | float):
        label = source.label or source.title or source.content[:40]
        raise TypeError(f"Claim {label!r} parameter {field!r} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        label = source.label or source.title or source.content[:40]
        raise ValueError(f"Claim {label!r} parameter {field!r} must be finite")
    return result


def _apply_transform(value: float, transform: str | Callable[[float], float] | None) -> float:
    if transform is None or transform == "identity":
        result = value
    elif transform == "log":
        result = math.log(value)
    elif transform == "log10":
        result = math.log10(value)
    elif callable(transform):
        result = float(transform(value))
    else:
        raise ValueError("transform must be None, 'identity', 'log', 'log10', or callable")
    if not math.isfinite(result):
        raise ValueError("transformed parameter value must be finite")
    return float(result)


def _transform_query_name(transform: str | Callable[[float], float] | None) -> str:
    if transform is None:
        return "identity"
    if isinstance(transform, str):
        return transform
    name = getattr(transform, "__qualname__", None) or getattr(transform, "__name__", None)
    if name is None:
        name = transform.__class__.__name__
    return f"callable:{name}"


def _gaussian_claims_comparison_query(
    *,
    value_field: str,
    observed_field: str,
    candidate_field: str,
    baseline_field: str,
    transform: str | Callable[[float], float] | None,
) -> dict[str, object]:
    query: dict[str, object] = _gaussian_model_comparison_query()
    if observed_field == candidate_field == baseline_field:
        query["value_field"] = observed_field
    else:
        query["fields"] = {
            "observed": observed_field,
            "candidate": candidate_field,
            "baseline": baseline_field,
        }
    transform_name = _transform_query_name(transform)
    if transform_name != "identity":
        query["transform"] = transform_name
    return query


def gaussian_model_comparison_from_claims(
    *,
    target: Knowledge,
    observed: Knowledge,
    candidate: Knowledge,
    baseline: Knowledge,
    sigma: float,
    value_field: str = "value",
    observed_field: str | None = None,
    candidate_field: str | None = None,
    baseline_field: str | None = None,
    transform: str | Callable[[float], float] | None = None,
    assumptions: list[Knowledge] | None = None,
    query: str | dict | None = None,
) -> Strategy:
    """Compare Gaussian predictions using numeric parameters from Claims."""
    observed_field_name = observed_field or value_field
    candidate_field_name = candidate_field or value_field
    baseline_field_name = baseline_field or value_field
    observed_value = _apply_transform(
        _numeric_parameter(observed, observed_field_name),
        transform,
    )
    candidate_value = _apply_transform(
        _numeric_parameter(candidate, candidate_field_name),
        transform,
    )
    baseline_value = _apply_transform(
        _numeric_parameter(baseline, baseline_field_name),
        transform,
    )
    return gaussian_model_comparison(
        target=target,
        observed=observed_value,
        candidate_mean=candidate_value,
        baseline_mean=baseline_value,
        sigma=sigma,
        data=observed,
        assumptions=[candidate, baseline, *(assumptions or [])],
        query=query
        if query is not None
        else _gaussian_claims_comparison_query(
            value_field=value_field,
            observed_field=observed_field_name,
            candidate_field=candidate_field_name,
            baseline_field=baseline_field_name,
            transform=transform,
        ),
    )
