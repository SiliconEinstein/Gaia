"""Registry for standard likelihood modules known to the IR validator."""

from __future__ import annotations

from gaia.ir.strategy import LikelihoodModuleSpec

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

STANDARD_LIKELIHOOD_MODULES: dict[str, LikelihoodModuleSpec] = {
    BINOMIAL_MODEL_REF: BINOMIAL_MODEL_SPEC,
    TWO_BINOMIAL_AB_TEST_REF: TWO_BINOMIAL_AB_TEST_SPEC,
}


def get_likelihood_module_spec(module_ref: str) -> LikelihoodModuleSpec | None:
    """Return the registered likelihood module spec for ``module_ref``."""
    return STANDARD_LIKELIHOOD_MODULES.get(module_ref)
