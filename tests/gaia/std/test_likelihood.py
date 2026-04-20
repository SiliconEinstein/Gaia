"""Tests for standard v6 likelihood score modules."""

from gaia.lang import claim, compute, likelihood_from
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage
from gaia.std.likelihood import (
    BINOMIAL_MODEL_REF,
    TWO_BINOMIAL_AB_TEST_REF,
    binomial_model_score,
    two_binomial_ab_test_score,
)


def test_binomial_model_score_keeps_mendel_ratio_near_3_to_1():
    target = claim("The observed Mendel ratio is compatible with a 3:1 model.")

    score = binomial_model_score(
        target=target,
        successes=295,
        trials=395,
        probability=0.75,
        query="p = 0.75",
    )

    assert score.module_ref == BINOMIAL_MODEL_REF
    assert score.score_type == "log_lr"
    assert score.value < 0
    assert round(score.value, 6) == -0.010519


def test_two_binomial_ab_test_score_is_positive_when_treatment_rate_is_higher():
    target = claim("Treatment B has a higher conversion rate than control A.")

    score = two_binomial_ab_test_score(
        target=target,
        control_successes=500,
        control_trials=10_000,
        treatment_successes=550,
        treatment_trials=10_000,
        query="theta_B > theta_A",
    )

    assert score.module_ref == TWO_BINOMIAL_AB_TEST_REF
    assert score.score_type == "log_lr"
    assert score.value > 1.25
    assert score.query == "theta_B > theta_A"


def test_standard_score_flows_through_compute_and_likelihood_surface():
    pkg = CollectedPackage("v6_std_pkg", namespace="github", version="1.0.0")
    with pkg:
        counts = claim("AB counts are 500/10000 control and 550/10000 treatment.")
        counts.label = "counts"
        target = claim("Treatment B has a higher conversion rate than control A.")
        target.label = "b_better"

        score = two_binomial_ab_test_score(
            target=target,
            control_successes=500,
            control_trials=10_000,
            treatment_successes=550,
            treatment_trials=10_000,
            query="theta_B > theta_A",
        )
        score_result = compute(
            "gaia.std.likelihood.two_binomial_ab_test_score",
            inputs={"counts": counts},
            output=score,
        )

        likelihood_from(
            target=target,
            data=[counts],
            score=score_result,
        )

    compiled = compile_package_artifact(pkg)
    strategies = {s.type: s for s in compiled.graph.strategies}
    assert strategies["compute"].method.output == score.score_id
    assert strategies["likelihood"].method.module_ref == TWO_BINOMIAL_AB_TEST_REF
    assert strategies["likelihood"].method.output_bindings == {"score": score.score_id}
