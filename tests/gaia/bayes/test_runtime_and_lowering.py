"""Bayes model / likelihood runtime actions and compiler lowering."""

from __future__ import annotations

import math

import pytest
import scipy.stats as stats

import gaia.engine.bayes as bayes
from gaia.engine.bayes.runtime import Likelihood, PredictiveModel
from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.factor_graph import FactorType
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.ir.operator import OperatorType
from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang import (
    Constant,
    Nat,
    Probability,
    Real,
    Variable,
    claim,
    contradict,
    equals,
    observe,
    parameter,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.action import Observe
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang.runtime.roles import roles_for_package


def _observed_value(
    variable: Variable,
    *,
    content: str,
    label: str,
    noise=None,
):
    metadata = {}
    if noise is not None:
        metadata["bayes"] = {"noise": noise.model_dump()}
    data = claim(
        content,
        formula=equals(variable, Constant(variable.value, variable.domain)),
        metadata=metadata,
    )
    observe(data, rationale=content, label=f"observe_{label}")
    data.label = label
    return data


def _compiled_mendel_bayes(
    *,
    exclusivity: str = "exhaustive_pairwise_complement",
    precomputed: dict | None = None,
):
    pkg = CollectedPackage(name="bayes_mendel_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395

        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = _observed_value(k, content="Observed k = 295.", label="data")
        model_31 = bayes.model(
            h_31,
            observable=k,
            distribution=bayes.Binomial(n=n, p=theta),
            label="f2_model_3_1",
        )
        model_null = bayes.model(
            h_null,
            observable=k,
            distribution=bayes.Binomial(n=n, p=theta),
            label="f2_model_null",
        )
        cmp_result = bayes.likelihood(
            data,
            model=model_31,
            against=[model_null],
            exclusivity=exclusivity,
            precomputed=precomputed,
            label="f2_likelihood",
        )
    finally:
        _current_package.reset(token)
    return pkg, h_31, h_null, data, model_31, model_null, cmp_result


def test_bayes_module_does_not_extend_factor_or_operator_enums():
    assert not any("bayes" in str(factor_type).lower() for factor_type in FactorType)
    assert not any("bayes" in str(operator_type).lower() for operator_type in OperatorType)


def test_model_and_likelihood_are_action_backed_helper_claims():
    pkg, h_31, _h_null, data, model_31, model_null, cmp_result = _compiled_mendel_bayes()

    model_action = model_31.from_actions[0]
    assert isinstance(model_action, PredictiveModel)
    assert model_action.hypothesis is h_31
    assert model_action.observable.symbol == "k"
    assert model_action.helper is model_31
    assert model_31.metadata["helper_kind"] == "predictive_model"
    assert model_31.metadata["bayes"]["role"] == "prediction"

    cmp_action = cmp_result.from_actions[0]
    assert isinstance(cmp_action, Likelihood)
    assert cmp_action.model is model_31
    assert cmp_action.against == (model_null,)
    assert cmp_action.data == (data,)
    assert cmp_action.helper is cmp_result
    assert cmp_result.metadata["helper_kind"] == "model_preference"
    assert cmp_result.metadata["bayes"]["role"] == "comparison"

    assert model_31 in pkg.knowledge
    assert cmp_result in pkg.knowledge
    assert model_action in pkg.actions
    assert cmp_action in pkg.actions

    roles = roles_for_package(pkg)
    assert "hypothesis" in [occ.role for occ in roles[h_31]]
    assert "model_helper" in [occ.role for occ in roles[model_31]]
    assert "compared_model" in [occ.role for occ in roles[model_31]]
    assert "compared_alternative" in [occ.role for occ in roles[model_null]]
    assert "likelihood_data" in [occ.role for occ in roles[data]]
    assert "model_preference_helper" in [occ.role for occ in roles[cmp_result]]


def test_observation_noise_metadata_serializes_distribution_literal():
    k = Variable(symbol="k", domain=Probability, value=0.7)

    obs = _observed_value(
        k,
        content="Observed measured = 0.7.",
        label="obs",
        noise=bayes.Normal(mu=0.0, sigma=0.1),
    )

    assert obs.metadata["bayes"]["noise"] == {
        "kind": "normal",
        "params": {"mu": 0.0, "sigma": 0.1},
    }


def test_data_helper_builds_observed_formula_claim_for_likelihood():
    pkg = CollectedPackage(name="bayes_data_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        y = Variable(symbol="log_rr", domain=Real)
        data = bayes.data(y, value=-0.151, error=0.05, label="measured_log_rr")
    finally:
        _current_package.reset(token)

    assert data.label == "measured_log_rr"
    assert data.formula == equals(y, Constant(-0.151, Real))
    assert data.prior == pytest.approx(1.0 - CROMWELL_EPS)
    assert data.metadata["bayes"]["noise"] == {
        "kind": "normal",
        "params": {"mu": 0.0, "sigma": 0.05},
    }
    assert data in pkg.knowledge

    observe_action = data.from_actions[0]
    assert isinstance(observe_action, Observe)
    assert observe_action.label == "observe_measured_log_rr"
    assert observe_action.conclusion is data
    assert observe_action.given == ()
    assert observe_action in pkg.actions


def test_likelihood_compiles_to_reviewable_infer_strategies_and_exhaustive_complement():
    pkg, h_31, h_null, _data, _model_31, _model_null, cmp_result = _compiled_mendel_bayes()
    cmp_result.from_actions[0].precomputed = {h_31: -1.2, h_null: -5.1}

    compiled = compile_package_artifact(pkg)
    graph = compiled.graph
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]

    cmp_ir = next(k for k in graph.knowledges if k.id == cmp_id)
    likelihoods = cmp_ir.metadata["bayes"]["likelihoods"]
    assert set(likelihoods) == {h_31_id, h_null_id}
    assert likelihoods[h_31_id] == pytest.approx(-1.2)
    assert likelihoods[h_null_id] == pytest.approx(-5.1)

    infer_strategies = [
        s
        for s in graph.strategies
        if (s.metadata or {}).get("bayes", {}).get("role") == "likelihood_factor"
    ]
    assert len(infer_strategies) == 2
    assert {tuple(s.premises) for s in infer_strategies} == {(h_31_id,), (h_null_id,)}
    assert {s.conclusion for s in infer_strategies} == {cmp_id}
    assert all(
        s.metadata["action_label"] == "t:bayes_mendel_pkg::action::f2_likelihood"
        for s in infer_strategies
    )

    complement_ops = [
        op
        for op in graph.operators
        if op.operator == "complement"
        and (op.metadata or {})
        .get("action_label", "")
        .endswith("::action::f2_likelihood_exclusive_h_3_1_h_null")
    ]
    assert len(complement_ops) == 1
    assert set(complement_ops[0].variables) == {h_31_id, h_null_id}

    manifest_actions = {review.action_label for review in compiled.review.reviews}
    assert "t:bayes_mendel_pkg::action::f2_model_3_1" in manifest_actions
    assert "t:bayes_mendel_pkg::action::f2_model_null" in manifest_actions
    assert "t:bayes_mendel_pkg::action::f2_likelihood" in manifest_actions
    assert "t:bayes_mendel_pkg::action::f2_likelihood_exclusive_h_3_1_h_null" in manifest_actions

    fg = lower_local_graph(graph)
    beliefs, _ = exact_inference(fg)
    odds = beliefs[h_31_id] / beliefs[h_null_id]
    assert odds == pytest.approx(46.942, rel=0.02)
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.03
    assert beliefs[cmp_id] > 0.99


def test_likelihood_precomputed_uses_hypothesis_claim_keys_not_model_helpers():
    pkg, h_31, h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihood keys"):
            bayes.likelihood(
                data,
                model=model_31,
                against=[model_null],
                precomputed={model_31: -1.0, h_null: -2.0},
                label="bad_cmp",
            )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    cmp_id = compiled.knowledge_ids_by_object[id(_cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    assert set(cmp_ir.metadata["bayes"]["likelihoods"]) == {h_31_id, h_null_id}


def test_likelihood_precomputed_requires_every_model_hypothesis():
    pkg, h_31, _h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihoods must cover"):
            bayes.likelihood(
                data,
                model=model_31,
                against=[model_null],
                precomputed={h_31: -1.0},
                label="missing_precomputed",
            )
    finally:
        _current_package.reset(token)

    _cmp_result.from_actions[0].precomputed = {h_31: -1.0}
    with pytest.raises(ValueError, match="precomputed likelihoods must cover"):
        compile_package_artifact(pkg)


def test_likelihood_precomputed_rejects_non_claim_keys_cleanly():
    pkg, _h_31, _h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihood keys"):
            bayes.likelihood(
                data,
                model=model_31,
                against=[model_null],
                precomputed={"h_3_1": -1.0},
                label="bad_key",
            )
    finally:
        _current_package.reset(token)


def test_continuous_normal_noise_likelihood_uses_convolution():
    pkg = CollectedPackage(name="bayes_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        mu = Variable(symbol="mu", domain=Real)
        y = Variable(symbol="y", domain=Real, value=3.0)
        h_near = parameter(mu, 2.5, content="mu = 2.5.", prior=0.5, label="h_near")
        h_far = parameter(mu, 0.0, content="mu = 0.", prior=0.5, label="h_far")
        data = _observed_value(
            y,
            content="Observed y = 3.0.",
            noise=bayes.Normal(mu=0.0, sigma=2.0),
            label="data",
        )
        model_near = bayes.model(
            h_near,
            observable=y,
            distribution=bayes.Normal(mu=mu, sigma=1.0),
            label="model_near",
        )
        model_far = bayes.model(
            h_far,
            observable=y,
            distribution=bayes.Normal(mu=mu, sigma=1.0),
            label="model_far",
        )
        cmp_result = bayes.likelihood(data, model=model_near, against=[model_far], label="cmp")
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_near_id = compiled.knowledge_ids_by_object[id(h_near)]
    h_far_id = compiled.knowledge_ids_by_object[id(h_far)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    likelihoods = cmp_ir.metadata["bayes"]["likelihoods"]
    convolved_sigma = math.sqrt(1.0**2 + 2.0**2)
    assert likelihoods[h_near_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=2.5, scale=convolved_sigma),
        rel=1e-5,
    )
    assert likelihoods[h_far_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=0.0, scale=convolved_sigma),
        rel=1e-5,
    )


def test_data_helper_noise_is_consumed_by_likelihood_lowering():
    pkg = CollectedPackage(name="bayes_data_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        mu = Variable(symbol="mu", domain=Real)
        y = Variable(symbol="y", domain=Real)
        h_near = parameter(mu, 2.5, content="mu = 2.5.", prior=0.5, label="h_near")
        h_far = parameter(mu, 0.0, content="mu = 0.", prior=0.5, label="h_far")
        data = bayes.data(y, value=3.0, error=2.0, label="data")
        model_near = bayes.model(
            h_near,
            observable=y,
            distribution=bayes.Normal(mu=mu, sigma=1.0),
            label="model_near",
        )
        model_far = bayes.model(
            h_far,
            observable=y,
            distribution=bayes.Normal(mu=mu, sigma=1.0),
            label="model_far",
        )
        cmp_result = bayes.likelihood(data, model=model_near, against=[model_far], label="cmp")
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_near_id = compiled.knowledge_ids_by_object[id(h_near)]
    h_far_id = compiled.knowledge_ids_by_object[id(h_far)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    likelihoods = cmp_ir.metadata["bayes"]["likelihoods"]
    convolved_sigma = math.sqrt(1.0**2 + 2.0**2)
    assert likelihoods[h_near_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=2.5, scale=convolved_sigma),
        rel=1e-5,
    )
    assert likelihoods[h_far_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=0.0, scale=convolved_sigma),
        rel=1e-5,
    )


def test_likelihood_errors_when_all_hypotheses_have_zero_support():
    pkg = CollectedPackage(name="bayes_zero_support_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=3)
        h_low = parameter(theta, 0.2, content="theta = 0.2.", prior=0.5, label="h_low")
        h_high = parameter(theta, 0.8, content="theta = 0.8.", prior=0.5, label="h_high")
        data = _observed_value(k, content="Observed impossible k = 3.", label="data")
        model_low = bayes.model(
            h_low,
            observable=k,
            distribution=bayes.Binomial(n=1, p=theta),
            label="model_low",
        )
        model_high = bayes.model(
            h_high,
            observable=k,
            distribution=bayes.Binomial(n=1, p=theta),
            label="model_high",
        )
        bayes.likelihood(data, model=model_low, against=[model_high], label="cmp")
    finally:
        _current_package.reset(token)

    with pytest.raises(ValueError, match="zero support"):
        compile_package_artifact(pkg)


def test_likelihood_does_not_duplicate_existing_pairwise_contradiction():
    pkg = CollectedPackage(name="bayes_mendel_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = _observed_value(k, content="Observed k = 295.", label="data")
        model_31 = bayes.model(
            h_31, observable=k, distribution=bayes.Binomial(n=395, p=theta), label="model_31"
        )
        model_null = bayes.model(
            h_null, observable=k, distribution=bayes.Binomial(n=395, p=theta), label="model_null"
        )
        contradict(h_31, h_null, label="manual_contradiction")
        bayes.likelihood(
            data,
            model=model_31,
            against=[model_null],
            exclusivity="pairwise_contradiction",
            label="cmp",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    contradiction_ops = [
        op
        for op in compiled.graph.operators
        if op.operator == "contradiction" and set(op.variables) == {h_31_id, h_null_id}
    ]

    assert len(contradiction_ops) == 1
    assert contradiction_ops[0].metadata["action_label"].endswith("::action::manual_contradiction")


def test_multiple_likelihoods_reuse_auto_generated_pairwise_contradiction():
    pkg, h_31, h_null, _data, model_31, model_null, _cmp_result = _compiled_mendel_bayes(
        exclusivity="pairwise_contradiction"
    )
    token = _current_package.set(pkg)
    try:
        k2 = Variable(symbol="k", domain=Nat, value=300)
        data2 = _observed_value(k2, content="Observed replicate k = 300.", label="data2")
        bayes.likelihood(
            data2,
            model=model_31,
            against=[model_null],
            exclusivity="pairwise_contradiction",
            label="cmp2",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    contradiction_ops = [
        op
        for op in compiled.graph.operators
        if op.operator == "contradiction" and set(op.variables) == {h_31_id, h_null_id}
    ]

    assert len(contradiction_ops) == 1
    assert (
        contradiction_ops[0]
        .metadata["action_label"]
        .endswith("::action::f2_likelihood_contradict_h_3_1_h_null")
    )


def test_exhaustive_equal_prior_argmax_tracks_largest_log_likelihood():
    pkg = CollectedPackage(name="bayes_argmax_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h_low = parameter(theta, 0.2, content="theta = 0.2.", prior=1 / 3, label="h_low")
        h_mid = parameter(theta, 0.5, content="theta = 0.5.", prior=1 / 3, label="h_mid")
        h_high = parameter(theta, 0.8, content="theta = 0.8.", prior=1 / 3, label="h_high")
        data = _observed_value(k, content="Observed k = 4.", label="data")
        model_low = bayes.model(
            h_low, observable=k, distribution=bayes.Binomial(n=5, p=theta), label="model_low"
        )
        model_mid = bayes.model(
            h_mid, observable=k, distribution=bayes.Binomial(n=5, p=theta), label="model_mid"
        )
        model_high = bayes.model(
            h_high, observable=k, distribution=bayes.Binomial(n=5, p=theta), label="model_high"
        )
        comparison = bayes.likelihood(
            data,
            model=model_low,
            against=[model_mid, model_high],
            exclusivity="exhaustive_pairwise_complement",
            precomputed={h_low: -4.0, h_mid: -2.0, h_high: -1.0},
            label="cmp",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    hypothesis_ids = {
        h_low: compiled.knowledge_ids_by_object[id(h_low)],
        h_mid: compiled.knowledge_ids_by_object[id(h_mid)],
        h_high: compiled.knowledge_ids_by_object[id(h_high)],
    }
    posterior_winner = max(hypothesis_ids, key=lambda h: beliefs[hypothesis_ids[h]])

    assert posterior_winner is h_high
    assert beliefs[compiled.knowledge_ids_by_object[id(comparison)]] > 0.99


def test_full_pipeline_mendel_with_real_binomial_no_precomputed():
    pkg, h_31, h_null, _data, _model_31, _model_null, cmp_result = _compiled_mendel_bayes(
        exclusivity="exhaustive_pairwise_complement"
    )

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]

    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)
    likelihoods = cmp_ir.metadata["bayes"]["likelihoods"]
    assert likelihoods[h_31_id] == pytest.approx(stats.binom(n=395, p=0.75).logpmf(295), rel=1e-6)
    assert likelihoods[h_null_id] == pytest.approx(stats.binom(n=395, p=0.5).logpmf(295), rel=1e-6)

    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    odds = beliefs[h_31_id] / beliefs[h_null_id]
    assert odds > 100.0
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.03
    assert beliefs[cmp_id] > 0.99
