"""Mendel 2.95:1 vs 3:1 as a v6 likelihood example."""

from __future__ import annotations

from gaia.lang import claim, compute, context, likelihood_from
from gaia.lang.runtime.package import CollectedPackage
from gaia.std.likelihood import BINOMIAL_MODEL_REF, binomial_model_score

from examples.v6_likelihood.common import ExampleResult, compile_and_infer


def build_mendel_package() -> CollectedPackage:
    """Build a Gaia package for an observed 295:100 ratio under a 3:1 model."""
    package = CollectedPackage("v6_mendel_likelihood", namespace="github", version="1.0.0")
    with package:
        source = context(
            "Mendel-style dominant/recessive count: 295 dominant and 100 recessive plants."
        )
        source.label = "mendel_table"

        counts = claim(
            "The experiment observed 295 dominant plants out of 395 total plants.",
            content_template=(
                "[@experiment] observed {dominant_count} dominant plants out of "
                "{total_count} total plants."
            ),
            rendered_content=(
                "The Mendel-style experiment observed 295 dominant plants out of "
                "395 total plants."
            ),
            parameters=[
                {
                    "name": "experiment",
                    "type": "Context",
                    "value": "github:v6_mendel_likelihood::mendel_table",
                },
                {"name": "dominant_count", "type": "int", "value": 295},
                {"name": "total_count", "type": "int", "value": 395},
            ],
            prior=0.999,
        )
        counts.label = "mendel_counts"

        target = claim(
            "The 3:1 binomial model is not strongly disconfirmed by the observed count.",
            prior=0.5,
        )
        target.label = "three_to_one_not_disconfirmed"

        statistical_model_valid = claim(
            "A binomial count model is appropriate for this segregating-trait count.",
            prior=0.999,
        )
        statistical_model_valid.label = "binomial_model_valid"

        score_correct = claim(
            "The binomial log-likelihood score was computed correctly.",
            prior=0.999,
        )
        score_correct.label = "mendel_score_correct"

        score = binomial_model_score(
            target=target,
            successes=295,
            trials=395,
            probability=0.75,
            query="p = 0.75",
        )
        score_result = compute(
            "gaia.std.likelihood.binomial_model_score",
            inputs={"counts": counts, "target": target},
            assumptions=[statistical_model_valid],
            output=score,
            correctness=score_correct,
            reason="Compute log L(p=0.75) - log L(p_hat) for the observed count.",
        )

        likelihood_from(
            target=target,
            data=[counts],
            assumptions=[statistical_model_valid],
            score=score_result,
            reason="Use the binomial-model score as a likelihood update.",
        )

    return package


def infer_mendel() -> ExampleResult:
    return compile_and_infer(build_mendel_package())


if __name__ == "__main__":
    result = infer_mendel()
    score = result.compiled.graph.likelihood_scores[0]
    target_id = "github:v6_mendel_likelihood::three_to_one_not_disconfirmed"
    print(f"module_ref={BINOMIAL_MODEL_REF}")
    print(f"score_id={score.score_id}")
    print(f"log_lr={score.value:.6f}")
    print(f"belief={result.beliefs[target_id]:.6f}")
