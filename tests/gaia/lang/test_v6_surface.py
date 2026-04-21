"""Tests for v6 Lang surface scaffolding."""

import pytest

from gaia.ir import ComputeMethod, DeductionMethod, ModuleUseMethod
from gaia.lang import (
    LikelihoodScore,
    ParameterizedClaim,
    SUPPORTED_BY_PATTERNS,
    claim,
    claim_class,
    compute,
    context,
    equivalence,
    induction_from_comparisons,
    likelihood_from,
    setting,
    supported_by,
)
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime import ComputeResult
from gaia.lang.runtime.package import CollectedPackage


def test_context_compiles_to_context_knowledge():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        ctx = context("Control A had 10 users and 1 conversion.")
        ctx.label = "dashboard_excerpt"

    compiled = compile_package_artifact(pkg)
    ir_ctx = compiled.graph.knowledges[0]
    assert ir_ctx.type == "context"
    assert ir_ctx.id == "github:v6_pkg::dashboard_excerpt"


def test_parameterized_claim_template_and_values_compile():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        exp = setting("AB test exp_123.")
        exp.label = "exp_123"
        counts = claim(
            "AB test exp_123 recorded 500/10000 control conversions.",
            content_template="[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions.",
            rendered_content="AB test exp_123 recorded 500/10000 control conversions.",
            parameters=[
                {"name": "experiment", "type": "Setting", "value": "github:v6_pkg::exp_123"},
                {"name": "ctrl_k", "type": "int", "value": 500},
                {"name": "ctrl_n", "type": "int", "value": 10_000},
            ],
        )
        counts.label = "counts"

    compiled = compile_package_artifact(pkg)
    ir_counts = next(k for k in compiled.graph.knowledges if k.label == "counts")
    assert ir_counts.content_template == "[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions."
    assert ir_counts.rendered_content == "AB test exp_123 recorded 500/10000 control conversions."
    assert {p.name: p.value for p in ir_counts.parameters}["ctrl_k"] == 500


def test_parameterized_claim_class_compiles_human_text_and_values():
    class GaussianLogLR(ParameterizedClaim):
        template = (
            "The Gaussian log-likelihood ratio is {value}, comparing candidate "
            "{candidate_mean} against baseline {baseline_mean} for observed {observed}."
        )

        observed: float
        candidate_mean: float
        baseline_mean: float
        value: float

    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        score = GaussianLogLR(
            observed=1.2,
            candidate_mean=0.96,
            baseline_mean=1.9,
            value=2.4,
        )
        score.label = "al_score"

    compiled = compile_package_artifact(pkg)
    ir_score = next(k for k in compiled.graph.knowledges if k.label == "al_score")
    assert ir_score.content_template == GaussianLogLR.template
    assert ir_score.rendered_content == (
        "The Gaussian log-likelihood ratio is 2.4, comparing candidate "
        "0.96 against baseline 1.9 for observed 1.2."
    )
    assert {p.name: p.value for p in ir_score.parameters}["value"] == 2.4
    assert ir_score.metadata["claim_class"].endswith(".GaussianLogLR")


def test_claim_class_decorator_converts_knowledge_parameters_to_qids():
    @claim_class(kind="observation")
    class CountReported:
        template = "{experiment} reported {count} observations."

        experiment: object
        count: int

    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        exp = setting("Experiment exp_123.")
        exp.label = "exp_123"
        CountReported(experiment=exp, count=10, label="counted")

    compiled = compile_package_artifact(pkg)
    ir_counted = next(k for k in compiled.graph.knowledges if k.label == "counted")
    values = {p.name: p.value for p in ir_counted.parameters}
    assert values["experiment"] == "github:v6_pkg::exp_123"
    assert values["count"] == 10
    assert ir_counted.rendered_content == "Experiment exp_123. reported 10 observations."
    assert ir_counted.metadata["kind"] == "observation"


def test_supported_by_compiles_as_v6_deduction_surface():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        observation = claim("The observed transition temperature is close to 1.2 K.")
        observation.label = "observation"
        model_fit = claim("The candidate theory predicts 0.96 K for this material.")
        model_fit.label = "model_fit"
        conclusion = claim("The candidate theory is predictively supported for this case.")
        conclusion.label = "conclusion"
        conclusion.supported_by(
            inputs=[observation, model_fit],
            pattern="abduction",
            reason="The candidate prediction is closer than the baseline prediction.",
        )

    compiled = compile_package_artifact(pkg)
    ir_strategy = next(
        s
        for s in compiled.graph.strategies
        if (s.metadata or {}).get("surface_construct") == "supported_by"
    )
    assert ir_strategy.type == "deduction"
    assert ir_strategy.premises == ["github:v6_pkg::observation", "github:v6_pkg::model_fit"]
    assert ir_strategy.conclusion == "github:v6_pkg::conclusion"
    assert ir_strategy.metadata["pattern"] == "abduction"
    assert isinstance(ir_strategy.method, DeductionMethod)


def test_supported_by_preserves_minimal_pattern_taxonomy():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        for index, pattern in enumerate(SUPPORTED_BY_PATTERNS):
            premise = claim(f"Input claim {index}.")
            premise.label = f"input_{index}"
            conclusion = claim(f"Conclusion claim {index}.")
            conclusion.label = f"conclusion_{index}"
            supported_by(
                conclusion,
                inputs=[premise],
                pattern=pattern,
                reason=f"Exercise minimal pattern {pattern}.",
            )

    compiled = compile_package_artifact(pkg)
    strategies = [
        s
        for s in compiled.graph.strategies
        if (s.metadata or {}).get("surface_construct") == "supported_by"
    ]
    assert [s.metadata["pattern"] for s in strategies] == list(SUPPORTED_BY_PATTERNS)
    assert {s.type for s in strategies} == {"deduction"}
    assert all(isinstance(s.method, DeductionMethod) for s in strategies)


def test_supported_by_defaults_to_deduction_pattern():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        premise = claim("A premise claim.")
        premise.label = "premise"
        conclusion = claim("A conclusion claim.")
        conclusion.label = "conclusion"

        supported_by(conclusion, inputs=[premise], reason="The premise entails the conclusion.")

    compiled = compile_package_artifact(pkg)
    ir_strategy = next(
        s
        for s in compiled.graph.strategies
        if (s.metadata or {}).get("surface_construct") == "supported_by"
    )
    assert ir_strategy.metadata["pattern"] == "deduction"


def test_supported_by_rejects_unknown_pattern():
    target = claim("A target claim.")
    input_claim = claim("An input claim.")
    with pytest.raises(ValueError, match="unsupported supported_by\\(\\) pattern"):
        supported_by(target, inputs=[input_claim], pattern="custom-pattern")


def test_supported_by_rejects_context_inputs():
    target = claim("A target claim.")
    excerpt = context("Raw source text.")
    with pytest.raises(TypeError, match="inputs must be Claim objects"):
        supported_by(target, inputs=[excerpt], pattern="deduction")


def test_supported_by_rejects_empty_inputs():
    target = claim("A target claim.")
    with pytest.raises(ValueError, match="requires at least 1 input"):
        supported_by(target, inputs=[], pattern="induction")


def test_induction_from_comparisons_supports_law_from_prediction_matches():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        law = claim("All tested metals expand when heated.")
        law.label = "law"
        pred_iron = claim("The law predicts that iron expands when heated.")
        pred_iron.label = "pred_iron"
        obs_iron = claim("Iron expands when heated.")
        obs_iron.label = "obs_iron"
        pred_copper = claim("The law predicts that copper expands when heated.")
        pred_copper.label = "pred_copper"
        obs_copper = claim("Copper expands when heated.")
        obs_copper.label = "obs_copper"

        iron_match = equivalence(pred_iron, obs_iron)
        copper_match = equivalence(pred_copper, obs_copper)
        induction_from_comparisons(
            law,
            comparisons=[iron_match, copper_match],
            reason="Two prediction-observation matches support the proposed law.",
        )

    compiled = compile_package_artifact(pkg)
    ir_strategy = next(
        s
        for s in compiled.graph.strategies
        if (s.metadata or {}).get("surface_construct") == "supported_by"
    )
    assert ir_strategy.type == "deduction"
    assert ir_strategy.conclusion == "github:v6_pkg::law"
    assert ir_strategy.metadata["pattern"] == "induction"
    assert len(ir_strategy.premises) == 2
    knowledges = {k.id: k for k in compiled.graph.knowledges}
    assert {knowledges[p].metadata["helper_kind"] for p in ir_strategy.premises} == {
        "equivalence_result"
    }


def test_claim_induced_by_uses_induction_pattern():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        law = claim("A proposed law.")
        law.label = "law"
        match_1 = claim("Prediction one matches observation one.")
        match_1.label = "match_1"
        match_2 = claim("Prediction two matches observation two.")
        match_2.label = "match_2"

        law.induced_by(comparisons=[match_1, match_2], reason="Two matches support the law.")

    compiled = compile_package_artifact(pkg)
    ir_strategy = next(
        s
        for s in compiled.graph.strategies
        if (s.metadata or {}).get("surface_construct") == "supported_by"
    )
    assert ir_strategy.metadata["pattern"] == "induction"
    assert ir_strategy.premises == ["github:v6_pkg::match_1", "github:v6_pkg::match_2"]


def test_induction_from_comparisons_requires_two_comparisons():
    law = claim("A proposed law.")
    match = claim("One prediction matches one observation.")
    with pytest.raises(ValueError, match="requires at least 2 comparisons"):
        induction_from_comparisons(law, comparisons=[match])


def test_compute_and_likelihood_from_compile_to_v6_methods():
    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    module_ref = "gaia.std.likelihood.two_binomial_ab_test@v1"

    with pkg:
        counts = claim("AB counts are 500/10000 control and 550/10000 treatment.")
        counts.label = "counts"
        target = claim("Variant B has a higher true conversion rate than A.")
        target.label = "b_better"
        randomization_valid = claim("Users were randomly assigned between A and B.")
        randomization_valid.label = "randomization_valid"
        formula_correct = claim("The two-binomial log LR formula is correct.")
        formula_correct.label = "formula_correct"
        implementation_correct = claim("The reviewed code implements the formula.")
        implementation_correct.label = "implementation_correct"

        score = LikelihoodScore(
            target=target,
            module_ref=module_ref,
            score_type="log_lr",
            value=1.73,
            query="theta_B > theta_A",
            score_id="score:ab",
        )
        score_result = compute(
            "two_binomial_log_lr",
            inputs={"counts": counts},
            output=score,
            assumptions=[formula_correct, implementation_correct],
            output_binding={"value": "return_value"},
            reason="Compute the AB-test log likelihood ratio.",
        )
        assert isinstance(score_result, ComputeResult)

        likelihood_from(
            target=target,
            data=[counts],
            assumptions=[randomization_valid],
            score=score_result.output,
            score_correctness=score_result.correctness,
            module_ref=module_ref,
            input_bindings={"counts": counts, "target": target},
            query="theta_B > theta_A",
            reason="Apply the AB-test likelihood score.",
        )

    compiled = compile_package_artifact(pkg)
    strategies = {s.type: s for s in compiled.graph.strategies}

    compute_ir = strategies["compute"]
    assert isinstance(compute_ir.method, ComputeMethod)
    assert compute_ir.method.function_ref == "two_binomial_log_lr"
    assert compute_ir.method.input_bindings == {"counts": "github:v6_pkg::counts"}
    assert compute_ir.method.output == "score:ab"
    assert compute_ir.method.output_binding == {"value": "return_value"}

    correctness_id = compiled.knowledge_ids_by_object[id(score_result.correctness)]
    assert compute_ir.conclusion == correctness_id

    likelihood_ir = strategies["likelihood"]
    assert isinstance(likelihood_ir.method, ModuleUseMethod)
    assert likelihood_ir.conclusion == "github:v6_pkg::b_better"
    assert likelihood_ir.method.module_ref == module_ref
    assert likelihood_ir.method.input_bindings == {
        "counts": "github:v6_pkg::counts",
        "target": "github:v6_pkg::b_better",
    }
    assert likelihood_ir.method.output_bindings == {"score": "score:ab"}
    assert likelihood_ir.method.premise_bindings["score_correct"] == correctness_id
    assert correctness_id in likelihood_ir.premises


def test_compute_decorator_lifts_python_call_to_claim_and_strategy():
    class SumResult(ParameterizedClaim):
        template = "Adding {a} and {b} gives {value}."

        a: int
        b: int
        value: int

    @compute(output=SumResult, kind="computed_value")
    def add(a: int, b: int) -> int:
        return a + b

    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        result = add(2, b=3)
        result.label = "sum_result"

    compiled = compile_package_artifact(pkg)
    ir_result = next(k for k in compiled.graph.knowledges if k.label == "sum_result")
    assert ir_result.rendered_content == "Adding 2 and 3 gives 5."
    assert ir_result.metadata["kind"] == "computed_value"

    compute_ir = next(s for s in compiled.graph.strategies if s.type == "compute")
    assert compute_ir.conclusion == "github:v6_pkg::sum_result"
    assert isinstance(compute_ir.method, ComputeMethod)
    assert compute_ir.method.output == "github:v6_pkg::sum_result"
    assert set(compute_ir.method.input_bindings) == {"a", "b"}
    assert len(compute_ir.premises) == 2


def test_likelihood_from_accepts_parameterized_score_claim():
    class LogLRScore(ParameterizedClaim):
        template = "The log-likelihood ratio is {value}."
        metadata = {
            "kind": "likelihood_score",
            "module_ref": "gaia.std.likelihood.binomial_model@v1",
            "score_type": "log_lr",
        }

        value: float

    pkg = CollectedPackage("v6_pkg", namespace="github", version="1.0.0")
    with pkg:
        target = claim("The binomial model is adequate.")
        target.label = "target"
        data = claim("The experiment observed 295 successes out of 395 trials.")
        data.label = "counts"
        score = LogLRScore(value=-0.01)
        score.label = "score"

        likelihood_from(
            target=target,
            data=[data],
            score=score,
            query="p = 0.75",
            reason="Apply a score Claim directly.",
        )

    compiled = compile_package_artifact(pkg)
    assert len(compiled.graph.likelihood_scores) == 1
    score_record = compiled.graph.likelihood_scores[0]
    assert score_record.score_id == "github:v6_pkg::score"
    assert score_record.target == "github:v6_pkg::target"
    assert score_record.value == -0.01

    likelihood_ir = next(s for s in compiled.graph.strategies if s.type == "likelihood")
    assert likelihood_ir.method.output_bindings == {"score": "github:v6_pkg::score"}
    assert likelihood_ir.method.premise_bindings["score"] == "github:v6_pkg::score"
    assert "github:v6_pkg::score" in likelihood_ir.premises
