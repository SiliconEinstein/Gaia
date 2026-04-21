"""Tests for standard v6 likelihood score modules."""

import importlib
import sys
import textwrap
from collections import Counter

from gaia.lang import ParameterizedClaim, claim, compute, likelihood_from
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.package import (
    CollectedPackage,
    get_inferred_package,
    reset_inferred_package,
)
from gaia.std.likelihood import (
    BINOMIAL_MODEL_REF,
    GAUSSIAN_MODEL_COMPARISON_REF,
    TWO_BINOMIAL_AB_TEST_REF,
    binomial_test,
    binomial_model_score,
    gaussian_model_comparison,
    gaussian_model_comparison_from_claims,
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
    assert len(compiled.graph.likelihood_scores) == 1
    assert compiled.graph.likelihood_scores[0].score_id == score.score_id
    assert compiled.graph.likelihood_scores[0].value == score.value

    strategies = {s.type: s for s in compiled.graph.strategies}
    assert strategies["compute"].method.output == score.score_id
    assert strategies["likelihood"].method.module_ref == TWO_BINOMIAL_AB_TEST_REF
    assert strategies["likelihood"].method.output_bindings == {"score": score.score_id}


def test_gaussian_model_comparison_helper_uses_score_claim():
    pkg = CollectedPackage("v6_std_pkg", namespace="github", version="1.0.0")
    with pkg:
        target = claim("The candidate model is favored over the baseline.")
        target.label = "candidate_favored"
        data = claim("Observed value is 1.2; candidate predicts 0.96; baseline predicts 1.9.")
        data.label = "comparison_data"

        gaussian_model_comparison(
            target=target,
            observed=1.2,
            candidate_mean=0.96,
            baseline_mean=1.9,
            sigma=0.2,
            data=data,
        )

    compiled = compile_package_artifact(pkg)
    assert len(compiled.graph.likelihood_scores) == 1
    score = compiled.graph.likelihood_scores[0]
    assert score.module_ref == GAUSSIAN_MODEL_COMPARISON_REF
    assert score.value > 0
    assert score.score_id.startswith("github:v6_std_pkg::")
    assert score.query == {
        "type": "gaussian_model_comparison",
        "direction": "candidate_over_baseline",
    }

    likelihood = next(s for s in compiled.graph.strategies if s.type == "likelihood")
    assert likelihood.method.output_bindings == {"score": score.score_id}
    assert score.score_id in likelihood.premises


def test_gaussian_model_comparison_from_claims_reads_parameters():
    class ScalarValue(ParameterizedClaim):
        template = "The {kind} value for {material} is {value_K} K."

        kind: str
        material: str
        value_K: float

    pkg = CollectedPackage("v6_std_pkg", namespace="github", version="1.0.0")
    with pkg:
        observed = ScalarValue(kind="observed", material="Li", value_K=4e-4)
        observed.label = "observed"
        candidate = ScalarValue(kind="candidate", material="Li", value_K=5e-3)
        candidate.label = "candidate"
        baseline = ScalarValue(kind="baseline", material="Li", value_K=0.35)
        baseline.label = "baseline"
        valid = claim("The Li log-scale comparison is well posed.")
        valid.label = "valid"
        target = claim("The candidate model is favored over the baseline for Li.")
        target.label = "target"

        gaussian_model_comparison_from_claims(
            target=target,
            observed=observed,
            candidate=candidate,
            baseline=baseline,
            value_field="value_K",
            transform="log10",
            sigma=1.0,
            assumptions=[valid],
        )

    compiled = compile_package_artifact(pkg)
    score = compiled.graph.likelihood_scores[0]
    assert round(score.value, 6) == 3.7261
    assert score.query == {
        "type": "gaussian_model_comparison",
        "direction": "candidate_over_baseline",
        "value_field": "value_K",
        "transform": "log10",
    }

    likelihood = next(s for s in compiled.graph.strategies if s.type == "likelihood")
    assert likelihood.premises == [
        "github:v6_std_pkg::observed",
        "github:v6_std_pkg::candidate",
        "github:v6_std_pkg::baseline",
        "github:v6_std_pkg::valid",
        score.score_id,
    ]


def test_binomial_test_helper_creates_compute_and_likelihood():
    pkg = CollectedPackage("v6_std_pkg", namespace="github", version="1.0.0")
    with pkg:
        target = claim("The observed count is compatible with p=0.75.")
        target.label = "target"
        binomial_test(target=target, successes=295, trials=395, probability=0.75)

    compiled = compile_package_artifact(pkg)
    strategies = {s.type: s for s in compiled.graph.strategies}
    assert "compute" in strategies
    assert "likelihood" in strategies
    assert compiled.graph.likelihood_scores[0].module_ref == BINOMIAL_MODEL_REF


def test_standard_helpers_register_when_called_from_inferred_package(tmp_path, monkeypatch):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """
            [project]
            name = "std-helper-pkg-gaia"
            version = "1.0.0"

            [tool.gaia]
            namespace = "github"
            type = "knowledge-package"
            """
        ),
        encoding="utf-8",
    )
    package_dir = tmp_path / "src" / "std_helper_pkg"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text(
        textwrap.dedent(
            """
            from gaia.lang import claim
            from gaia.std.likelihood import gaussian_model_comparison

            target = claim("The candidate model is favored.")
            data = claim("Observed value is 1.2.")

            gaussian_model_comparison(
                target=target,
                observed=1.2,
                candidate_mean=0.96,
                baseline_mean=1.9,
                sigma=0.3,
                data=data,
            )
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path / "src"))
    reset_inferred_package(pyproject, module_name="std_helper_pkg")
    sys.modules.pop("std_helper_pkg", None)
    importlib.invalidate_caches()
    importlib.import_module("std_helper_pkg")

    pkg = get_inferred_package(pyproject)
    assert pkg is not None
    assert Counter(strategy.type for strategy in pkg.strategies) == {
        "compute": 1,
        "likelihood": 1,
    }

    compiled = compile_package_artifact(pkg)
    assert len(compiled.graph.likelihood_scores) == 1
    assert next(s for s in compiled.graph.strategies if s.type == "likelihood").conclusion
