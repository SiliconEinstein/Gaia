"""Bayes predict / likelihood runtime and compiler lowering."""

from __future__ import annotations

import math

import pytest
import scipy.stats as stats

from gaia.bp.exact import exact_inference
from gaia.bp.factor_graph import FactorType
from gaia.bp.lowering import lower_local_graph
from gaia.ir.operator import OperatorType
from gaia.lang import Nat, Probability, Real, Variable, bayes, contradict, observation, parameter
from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.knowledge import ClaimKind, _current_package
from gaia.lang.runtime.package import CollectedPackage


def _compiled_mendel_bayes(*, exclusivity: str = "exhaustive_pairwise_complement"):
    pkg = CollectedPackage(name="bayes_mendel_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395

        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observation(count=k, content="Observed k = 295.", prior=0.999, label="data")
        model = bayes.predict(
            {h_31, h_null},
            k,
            distribution=bayes.Binomial(n=n, p=theta),
            label="f2_model",
        )
        cmp_result = bayes.likelihood(
            data,
            via=model,
            exclusivity=exclusivity,
            label="f2_likelihood",
        )
    finally:
        _current_package.reset(token)
    return pkg, h_31, h_null, data, model, cmp_result


def test_bayes_module_does_not_extend_factor_or_operator_enums():
    assert not any("bayes" in str(factor_type).lower() for factor_type in FactorType)
    assert not any("bayes" in str(operator_type).lower() for operator_type in OperatorType)


def test_predict_and_likelihood_are_claim_shaped_runtime_objects():
    pkg, h_31, h_null, data, model, cmp_result = _compiled_mendel_bayes()

    assert model.type == "claim"
    assert model.kind is ClaimKind.GENERAL
    assert model.metadata["bayes"]["role"] == "prediction"
    assert model.hypotheses == (h_31, h_null)
    assert model.observable.symbol == "k"
    assert cmp_result.type == "claim"
    assert cmp_result.metadata["bayes"]["role"] == "comparison"
    assert cmp_result.via is model
    assert cmp_result.data == (data,)
    assert model in pkg.knowledge
    assert cmp_result in pkg.knowledge


def test_observation_noise_metadata_serializes_distribution_literal():
    k = Variable(symbol="k", domain=Probability, value=0.7)

    obs = observation(measured=k, noise=bayes.Normal(mu=0.0, sigma=0.1))

    assert obs.metadata["bayes"]["noise"] == {
        "kind": "normal",
        "params": {"mu": 0.0, "sigma": 0.1},
    }


def test_likelihood_compiles_to_infer_strategies_and_exhaustive_complement():
    pkg, h_31, h_null, data, model, cmp_result = _compiled_mendel_bayes()
    cmp_result.precomputed = {h_31: -1.2, h_null: -5.1}

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
        s.conditional_probabilities and len(s.conditional_probabilities) == 2
        for s in infer_strategies
    )

    complement_ops = [
        op
        for op in graph.operators
        if op.operator == "complement"
        and (op.metadata or {}).get("bayes", {}).get("auto_generated_by")
    ]
    assert len(complement_ops) == 1
    assert set(complement_ops[0].variables) == {h_31_id, h_null_id}

    fg = lower_local_graph(graph)
    beliefs, _ = exact_inference(fg)
    odds = beliefs[h_31_id] / beliefs[h_null_id]
    assert odds == pytest.approx(46.942, rel=0.02)
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.03
    assert beliefs[cmp_id] > 0.99


def test_likelihood_precomputed_uses_runtime_claim_keys_not_qids():
    pkg, h_31, h_null, _data, _model, cmp_result = _compiled_mendel_bayes()
    cmp_result.precomputed = {h_31: -1.2, h_null: -5.1}

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    assert cmp_ir.metadata["bayes"]["likelihoods"] == {h_31_id: -1.2, h_null_id: -5.1}
    assert math.exp(
        cmp_ir.metadata["bayes"]["likelihoods"][h_31_id]
        - cmp_ir.metadata["bayes"]["likelihoods"][h_null_id]
    ) == pytest.approx(math.exp(3.9))


def test_continuous_normal_noise_likelihood_uses_convolution():
    pkg = CollectedPackage(name="bayes_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        mu = Variable(symbol="mu", domain=Real)
        y = Variable(symbol="y", domain=Real, value=3.0)
        h_near = parameter(mu, 2.5, content="mu = 2.5.", prior=0.5, label="h_near")
        h_far = parameter(mu, 0.0, content="mu = 0.", prior=0.5, label="h_far")
        data = observation(
            measured=y,
            content="Observed y = 3.0.",
            noise=bayes.Normal(mu=0.0, sigma=2.0),
            label="data",
        )
        model = bayes.predict(
            {h_near, h_far},
            y,
            distribution=bayes.Normal(mu=mu, sigma=1.0),
            label="model",
        )
        cmp_result = bayes.likelihood(data, via=model, label="cmp")
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
        data = observation(count=k, content="Observed impossible k = 3.", label="data")
        model = bayes.predict(
            {h_low, h_high},
            k,
            distribution=bayes.Binomial(n=1, p=theta),
            label="model",
        )
        bayes.likelihood(data, via=model, label="cmp")
    finally:
        _current_package.reset(token)

    with pytest.raises(ValueError, match="zero support"):
        compile_package_artifact(pkg)


def test_likelihood_does_not_duplicate_existing_pairwise_contradiction():
    pkg, h_31, h_null, _data, _model, _cmp_result = _compiled_mendel_bayes(
        exclusivity="pairwise_contradiction"
    )
    token = _current_package.set(pkg)
    try:
        contradict(h_31, h_null, label="manual_contradiction")
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
    assert (contradiction_ops[0].metadata or {}).get("bayes") is None


def test_multiple_likelihoods_reuse_auto_generated_pairwise_contradiction():
    pkg, h_31, h_null, _data, model, _cmp_result = _compiled_mendel_bayes(
        exclusivity="pairwise_contradiction"
    )
    token = _current_package.set(pkg)
    try:
        k2 = Variable(symbol="k", domain=Nat, value=300)
        data2 = observation(count=k2, content="Observed replicate k = 300.", label="data2")
        bayes.likelihood(data2, via=model, exclusivity="pairwise_contradiction", label="cmp2")
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
    assert (contradiction_ops[0].metadata or {}).get("bayes", {}).get("auto_generated_by")


def test_exhaustive_equal_prior_argmax_tracks_largest_log_likelihood():
    pkg = CollectedPackage(name="bayes_argmax_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h_low = parameter(theta, 0.2, content="theta = 0.2.", prior=1 / 3, label="h_low")
        h_mid = parameter(theta, 0.5, content="theta = 0.5.", prior=1 / 3, label="h_mid")
        h_high = parameter(theta, 0.8, content="theta = 0.8.", prior=1 / 3, label="h_high")
        data = observation(count=k, content="Observed k = 4.", label="data")
        model = bayes.predict(
            {h_low, h_mid, h_high},
            k,
            distribution=bayes.Binomial(n=5, p=theta),
            label="model",
        )
        comparison = bayes.likelihood(
            data,
            via=model,
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
