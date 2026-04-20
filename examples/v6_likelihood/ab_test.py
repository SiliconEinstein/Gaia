"""Two-binomial AB test as a v6 likelihood example."""

from __future__ import annotations

from gaia.lang import claim, compute, context, likelihood_from
from gaia.lang.runtime.package import CollectedPackage
from gaia.std.likelihood import TWO_BINOMIAL_AB_TEST_REF, two_binomial_ab_test_score

from examples.v6_likelihood.common import ExampleResult, compile_and_infer


def build_ab_test_package() -> CollectedPackage:
    """Build a Gaia package for 500/10000 vs 550/10000 conversions."""
    package = CollectedPackage("v6_ab_test_likelihood", namespace="github", version="1.0.0")
    with package:
        source = context(
            "AB dashboard excerpt: control A had 500 conversions out of 10000 users; "
            "treatment B had 550 conversions out of 10000 users."
        )
        source.label = "ab_dashboard"

        counts = claim(
            "AB test counts are 500/10000 for control A and 550/10000 for treatment B.",
            content_template=(
                "[@experiment] recorded {control_successes}/{control_trials} for "
                "control and {treatment_successes}/{treatment_trials} for treatment."
            ),
            rendered_content=(
                "AB test exp_001 recorded 500/10000 for control and "
                "550/10000 for treatment."
            ),
            parameters=[
                {
                    "name": "experiment",
                    "type": "Context",
                    "value": "github:v6_ab_test_likelihood::ab_dashboard",
                },
                {"name": "control_successes", "type": "int", "value": 500},
                {"name": "control_trials", "type": "int", "value": 10_000},
                {"name": "treatment_successes", "type": "int", "value": 550},
                {"name": "treatment_trials", "type": "int", "value": 10_000},
            ],
            prior=0.999,
        )
        counts.label = "ab_counts"

        randomization_valid = claim(
            "Users were randomly assigned between control A and treatment B.",
            prior=0.999,
        )
        randomization_valid.label = "randomization_valid"

        target = claim("Treatment B has a higher true conversion rate than control A.", prior=0.5)
        target.label = "treatment_b_better"

        score_correct = claim(
            "The two-binomial AB-test log-likelihood score was computed correctly.",
            prior=0.999,
        )
        score_correct.label = "ab_score_correct"

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
            inputs={"counts": counts, "target": target},
            assumptions=[randomization_valid],
            output=score,
            correctness=score_correct,
            reason="Compute the signed two-binomial log likelihood ratio.",
        )

        likelihood_from(
            target=target,
            data=[counts],
            assumptions=[randomization_valid],
            score=score_result,
            reason="Use the AB-test score as a likelihood update.",
        )

    return package


def infer_ab_test() -> ExampleResult:
    return compile_and_infer(build_ab_test_package())


if __name__ == "__main__":
    result = infer_ab_test()
    score = result.compiled.graph.likelihood_scores[0]
    target_id = "github:v6_ab_test_likelihood::treatment_b_better"
    print(f"module_ref={TWO_BINOMIAL_AB_TEST_REF}")
    print(f"score_id={score.score_id}")
    print(f"log_lr={score.value:.6f}")
    print(f"belief={result.beliefs[target_id]:.6f}")
