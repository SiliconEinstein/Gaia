"""Tests for v6 Lang surface scaffolding."""

from gaia.ir import ComputeMethod, ModuleUseMethod
from gaia.lang import (
    LikelihoodScore,
    claim,
    compute,
    context,
    likelihood_from,
    setting,
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
