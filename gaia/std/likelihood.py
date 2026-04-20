"""Small standard likelihood score modules for v6 experiments."""

from __future__ import annotations

import math

from gaia.ir import LikelihoodModuleSpec
from gaia.lang.runtime import Knowledge, LikelihoodScore

BINOMIAL_MODEL_REF = "gaia.std.likelihood.binomial_model@v1"
TWO_BINOMIAL_AB_TEST_REF = "gaia.std.likelihood.two_binomial_ab_test@v1"

BINOMIAL_MODEL_SPEC = LikelihoodModuleSpec(
    module_ref=BINOMIAL_MODEL_REF,
    input_schema={"counts": "BinomialCounts", "target": "Claim"},
    output_schema={"score": "LikelihoodScoreRecord"},
    premise_schema={"score_correct": "Claim"},
    target_role="target",
    score_role="score",
    score_type="log_lr",
    effect="add_log_odds",
)

TWO_BINOMIAL_AB_TEST_SPEC = LikelihoodModuleSpec(
    module_ref=TWO_BINOMIAL_AB_TEST_REF,
    input_schema={"counts": "TwoBinomialCounts", "target": "Claim"},
    output_schema={"score": "LikelihoodScoreRecord"},
    premise_schema={"score_correct": "Claim"},
    target_role="target",
    score_role="score",
    score_type="log_lr",
    effect="add_log_odds",
)


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
    if probability == 0.0:
        return 0.0 if successes == 0 else -math.inf
    if probability == 1.0:
        return 0.0 if successes == trials else -math.inf
    failures = trials - successes
    log_choose = (
        math.lgamma(trials + 1)
        - math.lgamma(successes + 1)
        - math.lgamma(failures + 1)
    )
    return log_choose + successes * math.log(probability) + failures * math.log1p(-probability)


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
