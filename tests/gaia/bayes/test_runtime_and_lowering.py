"""Bayes ``model`` / ``compare`` runtime actions and compiler lowering."""

from __future__ import annotations

import math
import textwrap

import pytest
import scipy.stats as stats

import gaia.engine.bayes as bayes
from gaia.engine.bayes.runtime import Model, ModelCompare
from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.factor_graph import FactorType
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.ir.operator import OperatorType
from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang import (
    BetaBinomial,
    Binomial,
    Constant,
    Domain,
    Nat,
    Normal,
    Probability,
    Real,
    Variable,
    claim,
    contradict,
    equals,
    land,
    observe,
    parameter,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.action import Contradict, Exclusive, Observe
from gaia.engine.lang.runtime.knowledge import _current_package
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang.runtime.roles import roles_for_package
from gaia.unit import q as gaia_q


def _compiled_mendel_bayes(
    *,
    exclusivity: str = "exhaustive_pairwise_complement",
    precomputed: dict | None = None,
):
    """Build the canonical Mendel 3:1 vs Null 1:1 comparison."""
    pkg = CollectedPackage(name="bayes_mendel_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395

        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k, value=295, label="data", rationale="Observed k = 295.")
        model_31 = bayes.model(
            h_31,
            observable=k,
            distribution=Binomial("k under 3:1", n=n, p=theta),
            label="f2_model_3_1",
        )
        model_null = bayes.model(
            h_null,
            observable=k,
            distribution=Binomial("k under null", n=n, p=theta),
            label="f2_model_null",
        )
        cmp_result = bayes.compare(
            data,
            models=[model_31, model_null],
            exclusivity=exclusivity,
            precomputed=precomputed,
            label="f2_likelihood",
        )
    finally:
        _current_package.reset(token)
    return pkg, h_31, h_null, data, model_31, model_null, cmp_result


def test_bayes_module_does_not_extend_factor_or_operator_enums():
    """The unified surface lowers into existing IR / BP primitives."""
    assert not any("bayes" in str(factor_type).lower() for factor_type in FactorType)
    assert not any("bayes" in str(operator_type).lower() for operator_type in OperatorType)


def test_model_and_compare_are_action_backed_helper_claims():
    pkg, h_31, _h_null, data, model_31, model_null, cmp_result = _compiled_mendel_bayes()

    model_action = model_31.from_actions[0]
    assert isinstance(model_action, Model)
    assert model_action.hypothesis is h_31
    assert isinstance(model_action.observable, Variable)
    assert model_action.observable.symbol == "k"
    assert model_action.helper is model_31
    assert model_31.metadata["helper_kind"] == "model"
    assert model_31.metadata["model"]["kind"] == "model"

    cmp_action = cmp_result.from_actions[0]
    assert isinstance(cmp_action, ModelCompare)
    assert cmp_action.models == (model_31, model_null)
    assert cmp_action.data == (data,)
    assert cmp_action.helper is cmp_result
    assert cmp_result.metadata["helper_kind"] == "model_preference"
    assert cmp_result.metadata["comparison"]["kind"] == "comparison"

    assert model_31 in pkg.knowledge
    assert cmp_result in pkg.knowledge
    assert model_action in pkg.actions
    assert cmp_action in pkg.actions

    roles = roles_for_package(pkg)
    assert "hypothesis" in [occ.role for occ in roles[h_31]]
    assert "model_helper" in [occ.role for occ in roles[model_31]]
    assert "compared_model" in [occ.role for occ in roles[model_31]]
    assert "compared_model" in [occ.role for occ in roles[model_null]]
    assert "likelihood_data" in [occ.role for occ in roles[data]]
    assert "model_preference_helper" in [occ.role for occ in roles[cmp_result]]


def test_compare_requires_at_least_two_models() -> None:
    theta = Variable(symbol="theta", domain=Probability)
    k = Variable(symbol="k", domain=Nat)
    h = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h")
    data = observe(k, value=3, label="data")
    model = bayes.model(
        h,
        observable=k,
        distribution=Binomial("k under h", n=5, p=theta),
        label="model_h",
    )

    with pytest.raises(ValueError, match="at least two models"):
        bayes.compare(data, models=[model], label="cmp")


def test_model_rejects_distribution_observable() -> None:
    h = parameter(Variable(symbol="theta", domain=Probability), 0.5, prior=0.5, label="h")
    y = Normal("observed y", mu=0, sigma=1)
    with pytest.raises(TypeError, match="observable must be a Variable"):
        bayes.model(
            h,
            observable=y,  # type: ignore[arg-type]
            distribution=Normal("y under H", mu=0, sigma=1),
            label="bad_model",
        )


def test_model_accepts_unit_typed_variable_and_distribution() -> None:
    h = parameter(Variable(symbol="theta", domain=Probability), 0.5, prior=0.5, label="h")
    y = Variable(symbol="y", domain=Real, unit="K")
    model = bayes.model(
        h,
        observable=y,
        distribution=Normal("y under H", mu=gaia_q(200, "K"), sigma=gaia_q(50, "K")),
        label="model_h",
    )
    action = next(a for a in model.from_actions if isinstance(a, Model))
    assert action.observable is y
    assert action.distribution is not None
    assert action.distribution.metadata["unit"] == "kelvin"


def test_model_rejects_unit_mismatch_between_observable_and_distribution() -> None:
    h = parameter(Variable(symbol="theta", domain=Probability), 0.5, prior=0.5, label="h")
    y = Variable(symbol="y", domain=Real, unit="K")
    with pytest.raises(ValueError, match="not compatible"):
        bayes.model(
            h,
            observable=y,
            distribution=Normal("length under H", mu=gaia_q(0, "m"), sigma=gaia_q(1, "m")),
            label="bad_model",
        )


def test_compare_rejects_same_symbol_observation_with_different_unit() -> None:
    pkg = CollectedPackage(name="bayes_same_symbol_unit_mismatch_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        model_y = Variable(symbol="y", domain=Real, unit="m")
        data_y = Variable(symbol="y", domain=Real, unit="cm")
        theta = Variable(symbol="theta", domain=Probability)
        h = parameter(theta, 0.5, prior=0.5, label="h")
        h_alt = parameter(theta, 0.6, prior=0.5, label="h_alt")
        data = observe(data_y, value=gaia_q(20, "cm"), label="data")
        model = bayes.model(
            h,
            observable=model_y,
            distribution=Normal("y under h", mu=gaia_q(1, "m"), sigma=gaia_q(0.1, "m")),
            label="model_h",
        )
        model_alt = bayes.model(
            h_alt,
            observable=model_y,
            distribution=Normal("y under h_alt", mu=gaia_q(2, "m"), sigma=gaia_q(0.1, "m")),
            label="model_h_alt",
        )
        bayes.compare(
            data, models=[model, model_alt], exclusivity="pairwise_contradiction", label="cmp"
        )
    finally:
        _current_package.reset(token)

    with pytest.raises(ValueError, match=r"unit.*model observable.*data observable"):
        compile_package_artifact(pkg)


def test_compare_allows_same_symbol_observation_with_same_unit() -> None:
    pkg = CollectedPackage(name="bayes_same_symbol_same_unit_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        model_y = Variable(symbol="y", domain=Real, unit="m")
        data_y = Variable(symbol="y", domain=Real, unit="m")
        theta = Variable(symbol="theta", domain=Probability)
        h = parameter(theta, 0.5, prior=0.5, label="h")
        h_alt = parameter(theta, 0.6, prior=0.5, label="h_alt")
        data = observe(data_y, value=gaia_q(1.2, "m"), label="data")
        model = bayes.model(
            h,
            observable=model_y,
            distribution=Normal("y under h", mu=gaia_q(1, "m"), sigma=gaia_q(0.1, "m")),
            label="model_h",
        )
        model_alt = bayes.model(
            h_alt,
            observable=model_y,
            distribution=Normal("y under h_alt", mu=gaia_q(2, "m"), sigma=gaia_q(0.1, "m")),
            label="model_h_alt",
        )
        cmp_result = bayes.compare(
            data,
            models=[model, model_alt],
            exclusivity="pairwise_contradiction",
            label="cmp",
        )
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)
    assert "comparison" in (cmp_ir.metadata or {})


def test_compare_rejects_same_symbol_same_label_custom_domains_with_different_members() -> None:
    pkg = CollectedPackage(name="bayes_same_symbol_domain_mismatch_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        model_domain = Domain("model states", members=[1, 2], label="State")
        data_domain = Domain("model states", members=[1, 3], label="State")
        model_x = Variable(symbol="x", domain=model_domain)
        data_x = Variable(symbol="x", domain=data_domain)
        theta = Variable(symbol="theta", domain=Probability)
        h = parameter(theta, 0.5, prior=0.5, label="h")
        h_alt = parameter(theta, 0.6, prior=0.5, label="h_alt")
        data = observe(data_x, value=1, label="data")
        model = bayes.model(
            h,
            observable=model_x,
            distribution=Normal("x under h", mu=0, sigma=1),
            label="model_h",
        )
        model_alt = bayes.model(
            h_alt,
            observable=model_x,
            distribution=Normal("x under h_alt", mu=1, sigma=1),
            label="model_h_alt",
        )
        bayes.compare(
            data, models=[model, model_alt], exclusivity="pairwise_contradiction", label="cmp"
        )
    finally:
        _current_package.reset(token)

    with pytest.raises(ValueError, match=r"data observable .* does not match model observable"):
        compile_package_artifact(pkg)


def test_observe_variable_with_distribution_noise_stores_knowledge_object():
    pkg = CollectedPackage(name="bayes_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        k = Variable(symbol="k", domain=Probability, value=0.7)
        noise = Normal("measurement noise", mu=0.0, sigma=0.1)
        obs = observe(k, value=0.7, error=noise, label="obs")
    finally:
        _current_package.reset(token)

    observation = obs.metadata["observation"]
    assert observation["kind"] == "observation"
    assert observation["value"] == 0.7
    assert observation["target"] is k
    assert observation["noise"] is noise


def test_observe_variable_with_scalar_error_sugars_into_anonymous_normal():
    """Scalar error becomes a Distribution Knowledge node, not a dict payload."""
    pkg = CollectedPackage(name="bayes_data_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        y = Variable(symbol="log_rr", domain=Real)
        data = observe(y, value=-0.151, error=0.05, label="measured_log_rr")
    finally:
        _current_package.reset(token)

    assert data.label == "measured_log_rr"
    observation = data.metadata["observation"]
    assert observation["target"] is y
    assert observation["value"] == -0.151
    # Noise is always a Distribution Knowledge object — never a dict payload.
    noise = observation["noise"]
    assert isinstance(noise, Normal.__call__.__class__) or noise.kind == "normal"
    assert noise.params["mu"] == 0.0
    assert noise.params["sigma"] == 0.05
    assert data.prior == pytest.approx(1.0 - CROMWELL_EPS)
    assert data in pkg.knowledge

    observe_action = data.from_actions[0]
    assert isinstance(observe_action, Observe)
    assert observe_action.conclusion is data
    assert observe_action.given == ()
    assert observe_action in pkg.actions


def test_compare_compiles_to_reviewable_infer_strategies_and_exhaustive_complement():
    pkg, h_31, h_null, _data, _model_31, _model_null, cmp_result = _compiled_mendel_bayes()
    cmp_result.from_actions[0].precomputed = {h_31: -1.2, h_null: -5.1}
    cmp_result.from_actions[0].log_likelihoods = {h_31: -1.2, h_null: -5.1}

    compiled = compile_package_artifact(pkg)
    graph = compiled.graph
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]

    cmp_ir = next(k for k in graph.knowledges if k.id == cmp_id)
    likelihoods = cmp_ir.metadata["comparison"]["likelihoods"]
    assert set(likelihoods) == {h_31_id, h_null_id}
    assert likelihoods[h_31_id] == pytest.approx(-1.2)
    assert likelihoods[h_null_id] == pytest.approx(-5.1)

    infer_strategies = [
        s
        for s in graph.strategies
        if (s.metadata or {}).get("comparison_factor", {}).get("kind") == "comparison_factor"
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


def test_compare_precomputed_uses_hypothesis_claim_keys_not_model_helpers():
    pkg, _h_31, h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihood keys"):
            bayes.compare(
                data,
                models=[model_31, model_null],
                precomputed={model_31: -1.0, h_null: -2.0},
                label="bad_cmp",
            )
    finally:
        _current_package.reset(token)


def test_compare_precomputed_requires_every_model_hypothesis():
    pkg, h_31, _h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihoods must cover"):
            bayes.compare(
                data,
                models=[model_31, model_null],
                precomputed={h_31: -1.0},
                label="missing_precomputed",
            )
    finally:
        _current_package.reset(token)


def test_compare_precomputed_rejects_non_claim_keys_cleanly():
    pkg, _h_31, _h_null, data, model_31, model_null, _cmp_result = _compiled_mendel_bayes()
    token = _current_package.set(pkg)
    try:
        with pytest.raises(ValueError, match="precomputed likelihood keys"):
            bayes.compare(
                data,
                models=[model_31, model_null],
                precomputed={"h_3_1": -1.0},
                label="bad_key",
            )
    finally:
        _current_package.reset(token)


def test_continuous_normal_noise_likelihood_uses_convolution():
    """Distribution-typed noise on observe() flows through the convolution lowering."""
    pkg = CollectedPackage(name="bayes_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        mu = Variable(symbol="mu", domain=Real)
        y = Variable(symbol="y", domain=Real, value=3.0)
        h_near = parameter(mu, 2.5, content="mu = 2.5.", prior=0.5, label="h_near")
        h_far = parameter(mu, 0.0, content="mu = 0.", prior=0.5, label="h_far")
        data = observe(
            y,
            value=3.0,
            error=Normal("measurement noise", mu=0.0, sigma=2.0),
            label="data",
        )
        model_near = bayes.model(
            h_near,
            observable=y,
            distribution=Normal("y under near", mu=mu, sigma=1.0),
            label="model_near",
        )
        model_far = bayes.model(
            h_far,
            observable=y,
            distribution=Normal("y under far", mu=mu, sigma=1.0),
            label="model_far",
        )
        cmp_result = bayes.compare(data, models=[model_near, model_far], label="cmp")
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_near_id = compiled.knowledge_ids_by_object[id(h_near)]
    h_far_id = compiled.knowledge_ids_by_object[id(h_far)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    likelihoods = cmp_ir.metadata["comparison"]["likelihoods"]
    convolved_sigma = math.sqrt(1.0**2 + 2.0**2)
    assert likelihoods[h_near_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=2.5, scale=convolved_sigma),
        rel=1e-5,
    )
    assert likelihoods[h_far_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=0.0, scale=convolved_sigma),
        rel=1e-5,
    )


def test_observe_with_scalar_error_consumed_by_compare_lowering():
    """Scalar ``error=σ`` on observe() reaches compare()'s convolution path."""
    pkg = CollectedPackage(name="bayes_data_noise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        mu = Variable(symbol="mu", domain=Real)
        y = Variable(symbol="y", domain=Real)
        h_near = parameter(mu, 2.5, content="mu = 2.5.", prior=0.5, label="h_near")
        h_far = parameter(mu, 0.0, content="mu = 0.", prior=0.5, label="h_far")
        data = observe(y, value=3.0, error=2.0, label="data")
        model_near = bayes.model(
            h_near,
            observable=y,
            distribution=Normal("y under near", mu=mu, sigma=1.0),
            label="model_near",
        )
        model_far = bayes.model(
            h_far,
            observable=y,
            distribution=Normal("y under far", mu=mu, sigma=1.0),
            label="model_far",
        )
        cmp_result = bayes.compare(data, models=[model_near, model_far], label="cmp")
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_near_id = compiled.knowledge_ids_by_object[id(h_near)]
    h_far_id = compiled.knowledge_ids_by_object[id(h_far)]
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)

    likelihoods = cmp_ir.metadata["comparison"]["likelihoods"]
    convolved_sigma = math.sqrt(1.0**2 + 2.0**2)
    assert likelihoods[h_near_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=2.5, scale=convolved_sigma),
        rel=1e-5,
    )
    assert likelihoods[h_far_id] == pytest.approx(
        stats.norm.logpdf(3.0, loc=0.0, scale=convolved_sigma),
        rel=1e-5,
    )


def test_compare_errors_when_all_hypotheses_have_zero_support():
    pkg = CollectedPackage(name="bayes_zero_support_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=3)
        h_low = parameter(theta, 0.2, content="theta = 0.2.", prior=0.5, label="h_low")
        h_high = parameter(theta, 0.8, content="theta = 0.8.", prior=0.5, label="h_high")
        data = observe(k, value=3, label="data", rationale="Observed impossible k = 3.")
        model_low = bayes.model(
            h_low,
            observable=k,
            distribution=Binomial("k under low", n=1, p=theta),
            label="model_low",
        )
        model_high = bayes.model(
            h_high,
            observable=k,
            distribution=Binomial("k under high", n=1, p=theta),
            label="model_high",
        )
        bayes.compare(data, models=[model_low, model_high], label="cmp")
    finally:
        _current_package.reset(token)

    with pytest.raises(ValueError, match="zero support"):
        compile_package_artifact(pkg)


def test_compare_does_not_duplicate_existing_pairwise_contradiction():
    pkg = CollectedPackage(name="bayes_mendel_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k, value=295, label="data", rationale="Observed k = 295.")
        model_31 = bayes.model(
            h_31,
            observable=k,
            distribution=Binomial("k under 3:1", n=395, p=theta),
            label="model_31",
        )
        model_null = bayes.model(
            h_null,
            observable=k,
            distribution=Binomial("k under null", n=395, p=theta),
            label="model_null",
        )
        contradict(h_31, h_null, label="manual_contradiction")
        bayes.compare(
            data,
            models=[model_31, model_null],
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


def test_multiple_compares_reuse_auto_generated_pairwise_contradiction():
    pkg, h_31, h_null, _data, model_31, model_null, _cmp_result = _compiled_mendel_bayes(
        exclusivity="pairwise_contradiction"
    )
    token = _current_package.set(pkg)
    try:
        k2 = Variable(symbol="k", domain=Nat, value=300)
        data2 = observe(k2, value=300, label="data2", rationale="Observed replicate k = 300.")
        bayes.compare(
            data2,
            models=[model_31, model_null],
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


def test_three_model_pairwise_contradiction_argmax_tracks_largest_log_likelihood():
    """3-hypothesis comparison: argmax of BP beliefs tracks the largest log-likelihood.

    Uses ``pairwise_contradiction`` because the new default
    ``exhaustive_pairwise_complement`` is currently restricted to
    2-hypothesis comparisons. Once an N-ary Exclusive operator lands
    (see the follow-up issue), this fixture should be re-pointed at
    ``exhaustive_pairwise_complement`` and the assertion on
    ``beliefs[h_high]`` can be tightened past the dilution caused by
    the at-most-one ``(F,F,F)`` joint state.
    """
    pkg = CollectedPackage(name="bayes_argmax_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h_low = parameter(theta, 0.2, content="theta = 0.2.", prior=1 / 3, label="h_low")
        h_mid = parameter(theta, 0.5, content="theta = 0.5.", prior=1 / 3, label="h_mid")
        h_high = parameter(theta, 0.8, content="theta = 0.8.", prior=1 / 3, label="h_high")
        data = observe(k, value=4, label="data", rationale="Observed k = 4.")
        model_low = bayes.model(
            h_low,
            observable=k,
            distribution=Binomial("k under low", n=5, p=theta),
            label="model_low",
        )
        model_mid = bayes.model(
            h_mid,
            observable=k,
            distribution=Binomial("k under mid", n=5, p=theta),
            label="model_mid",
        )
        model_high = bayes.model(
            h_high,
            observable=k,
            distribution=Binomial("k under high", n=5, p=theta),
            label="model_high",
        )
        comparison = bayes.compare(
            data,
            models=[model_low, model_mid, model_high],
            exclusivity="pairwise_contradiction",
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
    likelihoods = cmp_ir.metadata["comparison"]["likelihoods"]
    assert likelihoods[h_31_id] == pytest.approx(stats.binom(n=395, p=0.75).logpmf(295), rel=1e-6)
    assert likelihoods[h_null_id] == pytest.approx(stats.binom(n=395, p=0.5).logpmf(295), rel=1e-6)

    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    odds = beliefs[h_31_id] / beliefs[h_null_id]
    assert odds > 100.0
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.03
    assert beliefs[cmp_id] > 0.99


# ---------------------------------------------------------------------------
# Default-exclusivity contract (regression for the bayes-unified default fix)
# ---------------------------------------------------------------------------


def test_default_exclusivity_emits_exclusive_for_two_models():
    """Calling ``compare()`` without ``exclusivity=`` auto-generates Exclusive.

    The default was changed from ``"pairwise_contradiction"`` (at-most-one,
    which silently diluted Bayesian model-selection posteriors via the
    "(F,F)" joint state) to ``"exhaustive_pairwise_complement"``
    (exactly-one for 2 models). The auto-generated structural action must
    therefore be ``Exclusive``, not ``Contradict``.
    """
    pkg = CollectedPackage(name="bayes_default_exclusivity_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
        h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
        data = observe(k, value=4, label="data")
        m1 = bayes.model(
            h1, observable=k, distribution=Binomial("k under h1", n=5, p=theta), label="m1"
        )
        m2 = bayes.model(
            h2, observable=k, distribution=Binomial("k under h2", n=5, p=theta), label="m2"
        )
        cmp_result = bayes.compare(data, models=[m1, m2], label="cmp")
    finally:
        _current_package.reset(token)

    exclusives = [
        a
        for a in pkg.actions
        if isinstance(a, Exclusive) and {id(a.a), id(a.b)} == {id(h1), id(h2)}
    ]
    contradicts = [
        a
        for a in pkg.actions
        if isinstance(a, Contradict) and {id(a.a), id(a.b)} == {id(h1), id(h2)}
    ]
    assert len(exclusives) == 1, (
        f"default compare() should auto-generate one Exclusive(h1, h2); "
        f"got exclusives={len(exclusives)}, contradicts={len(contradicts)}"
    )
    assert contradicts == [], (
        "default compare() must not fall back to Contradict — that would "
        "be the old at-most-one semantics."
    )

    metadata = cmp_result.metadata["comparison"]
    assert metadata["exclusivity"] == "exhaustive_pairwise_complement"


def test_default_exclusivity_yields_bayes_factor_posterior():
    """Default 2-model ``compare()`` produces strict Bayes-factor posterior odds.

    Builds the fixture inline (no helper) so the assertion really
    exercises ``bayes.compare()``'s own default. Under
    ``exhaustive_pairwise_complement`` and equal priors, posterior odds
    equal the (Cromwell-clamped) likelihood ratio. This is the property
    that the old default — ``pairwise_contradiction`` plus α=0.5 —
    did **not** preserve: an "all-false" joint state used to carry
    substantial mass and dilute the comparison.
    """
    pkg = CollectedPackage(name="bayes_default_posterior_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=295)
        n = 395
        h_31 = parameter(theta, 0.75, content="theta = 0.75.", prior=0.5, label="h_3_1")
        h_null = parameter(theta, 0.5, content="theta = 0.5.", prior=0.5, label="h_null")
        data = observe(k, value=295, label="data")
        m_31 = bayes.model(
            h_31,
            observable=k,
            distribution=Binomial("k under 3:1", n=n, p=theta),
            label="m_31",
        )
        m_null = bayes.model(
            h_null,
            observable=k,
            distribution=Binomial("k under null", n=n, p=theta),
            label="m_null",
        )
        # No explicit ``exclusivity=`` — we want the verb's own default.
        bayes.compare(data, models=[m_31, m_null], label="cmp")
    finally:
        _current_package.reset(token)

    compiled = compile_package_artifact(pkg)
    h_31_id = compiled.knowledge_ids_by_object[id(h_31)]
    h_null_id = compiled.knowledge_ids_by_object[id(h_null)]

    beliefs, _ = exact_inference(lower_local_graph(compiled.graph))
    odds = beliefs[h_31_id] / beliefs[h_null_id]
    assert odds > 100.0, (
        "Bayesian model selection should put Mendel posterior >100x "
        f"above null under k=295/n=395; got odds={odds:.2f}"
    )
    assert beliefs[h_31_id] > 0.95
    assert beliefs[h_null_id] < 0.03


def test_three_model_exhaustive_raises_not_implemented():
    """``exhaustive_pairwise_complement`` with 3 models raises NotImplementedError.

    The N-ary Exclusive operator does not yet exist in the IR; the
    previous code silently fell back to pairwise Contradict, which is
    at-most-one and not the requested "exactly one of N" semantics.
    Until the N-ary operator lands, compare() must refuse loudly.
    """
    pkg = CollectedPackage(name="bayes_three_exhaustive_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h_a = parameter(theta, 0.2, content="theta = 0.2.", prior=1 / 3, label="h_a")
        h_b = parameter(theta, 0.5, content="theta = 0.5.", prior=1 / 3, label="h_b")
        h_c = parameter(theta, 0.8, content="theta = 0.8.", prior=1 / 3, label="h_c")
        data = observe(k, value=4, label="data")
        m_a = bayes.model(
            h_a, observable=k, distribution=Binomial("k under a", n=5, p=theta), label="m_a"
        )
        m_b = bayes.model(
            h_b, observable=k, distribution=Binomial("k under b", n=5, p=theta), label="m_b"
        )
        m_c = bayes.model(
            h_c, observable=k, distribution=Binomial("k under c", n=5, p=theta), label="m_c"
        )
        with pytest.raises(NotImplementedError, match="N-ary Exclusive"):
            bayes.compare(
                data,
                models=[m_a, m_b, m_c],
                exclusivity="exhaustive_pairwise_complement",
                label="cmp",
            )
    finally:
        _current_package.reset(token)


def test_compare_rejects_exclusivity_none():
    """``exclusivity='none'`` is no longer accepted; remediation hint surfaced."""
    pkg = CollectedPackage(name="bayes_none_rejection_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
        h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
        data = observe(k, value=4, label="data")
        m1 = bayes.model(
            h1, observable=k, distribution=Binomial("k under h1", n=5, p=theta), label="m1"
        )
        m2 = bayes.model(
            h2, observable=k, distribution=Binomial("k under h2", n=5, p=theta), label="m2"
        )
        with pytest.raises(ValueError, match="exclusivity='none'"):
            bayes.compare(data, models=[m1, m2], exclusivity="none", label="cmp")
    finally:
        _current_package.reset(token)


def test_compare_dedups_against_external_exclusive():
    """An external ``exclusive(h1, h2)`` prevents compare() from emitting a duplicate.

    The external author's helper Claim, label, and rationale are preserved;
    compare() reuses them rather than auto-generating a second ``Exclusive``
    with an anonymous helper that would later trip the IR's D2 check on
    distinct conclusions for the same complement operator.
    """
    from gaia.engine.lang.dsl.relate import exclusive

    pkg = CollectedPackage(name="bayes_external_exclusive_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
        h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
        competing = exclusive(h1, h2, rationale="external rationale", label="competing")
        data = observe(k, value=4, label="data")
        m1 = bayes.model(
            h1, observable=k, distribution=Binomial("k under h1", n=5, p=theta), label="m1"
        )
        m2 = bayes.model(
            h2, observable=k, distribution=Binomial("k under h2", n=5, p=theta), label="m2"
        )
        bayes.compare(data, models=[m1, m2], label="cmp")
    finally:
        _current_package.reset(token)

    exclusives = [a for a in pkg.actions if isinstance(a, Exclusive)]
    assert len(exclusives) == 1, "dedup should leave only the external Exclusive"
    assert exclusives[0].helper is competing
    # Also: compiling the package should not trip the IR D2 check.
    compile_package_artifact(pkg)


def test_compare_dedups_external_exclusive_even_after_contradict():
    """Same-type dedup must not depend on the order of cross-type relations.

    Authors may first declare an at-most-one relation, then refine it to a
    closed binary partition. ``compare()`` must still reuse the external
    Exclusive instead of creating a second complement helper.
    """
    from gaia.engine.lang.dsl.relate import exclusive

    pkg = CollectedPackage(name="bayes_external_exclusive_after_contradict_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
        h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
        manual_conflict = contradict(h1, h2, rationale="manual", label="manual_conflict")
        competing = exclusive(h1, h2, rationale="external rationale", label="competing")
        data = observe(k, value=4, label="data")
        m1 = bayes.model(
            h1, observable=k, distribution=Binomial("k under h1", n=5, p=theta), label="m1"
        )
        m2 = bayes.model(
            h2, observable=k, distribution=Binomial("k under h2", n=5, p=theta), label="m2"
        )
        bayes.compare(data, models=[m1, m2], label="cmp")
    finally:
        _current_package.reset(token)

    exclusives = [a for a in pkg.actions if isinstance(a, Exclusive)]
    contradicts = [a for a in pkg.actions if isinstance(a, Contradict)]
    assert len(exclusives) == 1, "dedup should reuse the external Exclusive"
    assert exclusives[0].helper is competing
    assert manual_conflict in (a.helper for a in contradicts)
    compiled = compile_package_artifact(pkg)
    lower_local_graph(compiled.graph)


def test_compare_dedups_through_callstack_inferred_package(tmp_path):
    """Dedup works even when ``_current_package`` is unset.

    The ``gaia build compile`` pipeline registers actions into the
    inferred package (looked up via ``infer_package_from_callstack``)
    without ever binding ``_current_package``. ``compare()`` must therefore
    fall back to the same lookup when checking for an existing structural
    action. This regression test exercises the inferred-package path by
    invoking the loader directly.
    """
    from gaia.engine.lang.runtime.action import Exclusive as ExclusiveAction
    from gaia.engine.packaging import (
        compile_loaded_package_artifact,
        load_gaia_package,
    )

    pkg_dir = tmp_path / "mini-mendel-gaia"
    src_dir = pkg_dir / "src" / "mini_mendel"
    src_dir.mkdir(parents=True)
    (pkg_dir / "pyproject.toml").write_text(
        textwrap.dedent(
            """
            [project]
            name = "mini-mendel-gaia"
            version = "0.1.0"

            [tool.gaia]
            type = "knowledge-package"
            namespace = "t"
            """
        ).strip(),
        encoding="utf-8",
    )
    (src_dir / "__init__.py").write_text(
        textwrap.dedent(
            """
            import gaia.engine.bayes as bayes
            from gaia.engine.lang import (
                Binomial,
                Nat,
                Probability,
                Variable,
                exclusive,
                observe,
                parameter,
            )

            theta = Variable(symbol="theta", domain=Probability)
            k = Variable(symbol="k", domain=Nat, value=4)
            h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
            h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
            competing_models = exclusive(h1, h2, label="competing_models")
            data = observe(k, value=4, label="data")
            m1 = bayes.model(
                h1,
                observable=k,
                distribution=Binomial("k under h1", n=5, p=theta),
                label="m1",
            )
            m2 = bayes.model(
                h2,
                observable=k,
                distribution=Binomial("k under h2", n=5, p=theta),
                label="m2",
            )
            cmp = bayes.compare(data, models=[m1, m2], label="cmp")
            __all__ = ["h1", "h2", "competing_models", "data", "m1", "m2", "cmp"]
            """
        ).strip(),
        encoding="utf-8",
    )

    loaded = load_gaia_package(pkg_dir)
    pkg = loaded.package

    pair_ids = None
    for action in pkg.actions:
        if isinstance(action, ExclusiveAction) and (action.label or "").startswith(
            "competing_models"
        ):
            pair_ids = {id(action.a), id(action.b)}
            break
    assert pair_ids is not None, "Mendel example must declare competing_models externally"

    matching = [
        action
        for action in pkg.actions
        if isinstance(action, ExclusiveAction) and {id(action.a), id(action.b)} == pair_ids
    ]
    assert len(matching) == 1, (
        "compare() must dedup against external Exclusive(mendel, blending) "
        f"even when actions are registered via inferred package; "
        f"found {len(matching)} duplicates"
    )

    # IR compile must also succeed without the D2 "two complement conclusions" violation.
    compile_loaded_package_artifact(loaded)


def test_compare_coexists_with_external_contradict_of_different_type():
    """External ``contradict(h1, h2)`` does not block compare() from emitting Exclusive.

    The two structural-action types are logically consistent (``Exclusive``
    implies ``Contradict``), so cross-type coexistence is allowed at the
    DSL layer. The IR's own consistency checks govern whether the combined
    graph is legal.
    """
    pkg = CollectedPackage(name="bayes_cross_type_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h1 = parameter(theta, 0.3, content="theta = 0.3.", prior=0.5, label="h1")
        h2 = parameter(theta, 0.7, content="theta = 0.7.", prior=0.5, label="h2")
        manual_conflict = contradict(h1, h2, rationale="manual", label="manual_conflict")
        data = observe(k, value=4, label="data")
        m1 = bayes.model(
            h1, observable=k, distribution=Binomial("k under h1", n=5, p=theta), label="m1"
        )
        m2 = bayes.model(
            h2, observable=k, distribution=Binomial("k under h2", n=5, p=theta), label="m2"
        )
        bayes.compare(data, models=[m1, m2], label="cmp")
    finally:
        _current_package.reset(token)

    exclusives = [a for a in pkg.actions if isinstance(a, Exclusive)]
    contradicts = [a for a in pkg.actions if isinstance(a, Contradict)]
    assert len(exclusives) == 1, (
        "compare() must still auto-emit Exclusive when only a Contradict is external"
    )
    assert manual_conflict in (a.helper for a in contradicts), (
        "the external manual_conflict Contradict must remain in the package"
    )


def test_three_model_pairwise_contradiction_remains_supported():
    """``pairwise_contradiction`` with 3 models is still accepted.

    The N>=3 raise is specific to ``exhaustive_pairwise_complement``;
    authors who genuinely want at-most-one semantics over 3+ models
    (open-world comparisons) can still get there explicitly.
    """
    pkg = CollectedPackage(name="bayes_three_pairwise_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=4)
        h_a = parameter(theta, 0.2, content="theta = 0.2.", prior=1 / 3, label="h_a")
        h_b = parameter(theta, 0.5, content="theta = 0.5.", prior=1 / 3, label="h_b")
        h_c = parameter(theta, 0.8, content="theta = 0.8.", prior=1 / 3, label="h_c")
        data = observe(k, value=4, label="data")
        m_a = bayes.model(
            h_a, observable=k, distribution=Binomial("k under a", n=5, p=theta), label="m_a"
        )
        m_b = bayes.model(
            h_b, observable=k, distribution=Binomial("k under b", n=5, p=theta), label="m_b"
        )
        m_c = bayes.model(
            h_c, observable=k, distribution=Binomial("k under c", n=5, p=theta), label="m_c"
        )
        cmp_result = bayes.compare(
            data,
            models=[m_a, m_b, m_c],
            exclusivity="pairwise_contradiction",
            label="cmp",
        )
    finally:
        _current_package.reset(token)

    contradict_pairs = {
        frozenset((id(a.a), id(a.b))) for a in pkg.actions if isinstance(a, Contradict)
    }
    expected_pairs = {
        frozenset((id(h_a), id(h_b))),
        frozenset((id(h_a), id(h_c))),
        frozenset((id(h_b), id(h_c))),
    }
    assert contradict_pairs == expected_pairs
    assert cmp_result.metadata["comparison"]["exclusivity"] == "pairwise_contradiction"


# -----------------------------------------------------------------------------
# Lindley-Jeffreys diagnostic
# -----------------------------------------------------------------------------


def _compile_lindley_setup(*, k_observed: int, alpha: float, beta: float):
    """Build a point-Binomial(p=0.10) vs BetaBinomial(α, β) comparison."""
    pkg = CollectedPackage(name="bayes_lindley_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=k_observed)
        n = 244

        h_path = parameter(theta, 0.10, content="theta = 0.10.", prior=0.5, label="h_path")
        h_alt = parameter(theta, 0.5, content="theta diffuse.", prior=0.5, label="h_alt")
        data = observe(k, value=k_observed, label="data", rationale=f"k = {k_observed}.")
        model_path = bayes.model(
            h_path,
            observable=k,
            distribution=Binomial("k under p=0.10", n=n, p=theta),
            label="model_path",
        )
        model_alt = bayes.model(
            h_alt,
            observable=k,
            distribution=BetaBinomial("k under diffuse", n=n, alpha=alpha, beta=beta),
            label="model_alt",
        )
        cmp_result = bayes.compare(
            data,
            models=[model_path, model_alt],
            label="cmp_lindley",
        )
    finally:
        _current_package.reset(token)
    return pkg, cmp_result


def _ir_comparison_metadata(compiled, cmp_result):
    """Pull the comparison helper's IR-side metadata."""
    cmp_id = compiled.knowledge_ids_by_object[id(cmp_result)]
    cmp_ir = next(k for k in compiled.graph.knowledges if k.id == cmp_id)
    return cmp_ir.metadata["comparison"]


def test_compare_emits_lindley_diagnostic_for_point_vs_diffuse_uniform_extreme():
    """k=4 vs Binomial(244, 0.10) (mean 24.4) hits the Lindley trap; warning fires."""
    pkg, cmp_result = _compile_lindley_setup(k_observed=4, alpha=1, beta=1)

    with pytest.warns(UserWarning, match="Lindley-Jeffreys trap"):
        compiled = compile_package_artifact(pkg)

    cmp_md = _ir_comparison_metadata(compiled, cmp_result)
    assert cmp_md["lindley_signature"] is True
    assert cmp_md["lindley_warning"] is True
    assert cmp_md["per_observation_log_lr"] > 5.0
    assert cmp_md["lindley_threshold"] == 5.0
    assert cmp_md["max_pairwise_log_lr"] == pytest.approx(
        cmp_md["per_observation_log_lr"], rel=1e-9
    )


def test_compare_lindley_diagnostic_resolves_deferred_betabinomial_parameters():
    """A deferred BetaBinomial(alpha=1, beta=1) still carries the Lindley signature."""
    pkg = CollectedPackage(name="bayes_lindley_deferred_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        alpha = Variable(symbol="alpha", domain=Real)
        beta = Variable(symbol="beta", domain=Real)
        k = Variable(symbol="k", domain=Nat, value=4)
        n = 244

        h_path = parameter(theta, 0.10, content="theta = 0.10.", prior=0.5, label="h_path")
        h_alt = claim(
            "Diffuse alternative sets alpha = 1 and beta = 1.",
            formula=land(equals(alpha, Constant(1.0, Real)), equals(beta, Constant(1.0, Real))),
            prior=0.5,
        )
        h_alt.label = "h_alt"
        data = observe(k, value=4, label="data", rationale="k = 4.")
        model_path = bayes.model(
            h_path,
            observable=k,
            distribution=Binomial("k under p=0.10", n=n, p=theta),
            label="model_path",
        )
        model_alt = bayes.model(
            h_alt,
            observable=k,
            distribution=BetaBinomial("k under diffuse", n=n, alpha=alpha, beta=beta),
            label="model_alt",
        )
        cmp_result = bayes.compare(
            data,
            models=[model_path, model_alt],
            label="cmp_lindley_deferred",
        )
    finally:
        _current_package.reset(token)

    with pytest.warns(UserWarning, match="Lindley-Jeffreys trap"):
        compiled = compile_package_artifact(pkg)

    cmp_md = _ir_comparison_metadata(compiled, cmp_result)
    assert cmp_md["lindley_signature"] is True
    assert cmp_md["lindley_warning"] is True


def test_compare_lindley_quiet_for_point_vs_point_extreme():
    """Mendel-style point-vs-point comparison with extreme LR: no Lindley warning."""
    import warnings as _w

    pkg, _h_31, _h_null, _data, _model_31, _model_null, cmp_result = _compiled_mendel_bayes()
    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        compiled = compile_package_artifact(pkg)

    lindley = [w for w in caught if "Lindley" in str(w.message)]
    assert lindley == [], f"unexpected Lindley warning(s): {[str(w.message) for w in lindley]}"

    cmp_md = _ir_comparison_metadata(compiled, cmp_result)
    assert cmp_md["lindley_signature"] is False
    assert cmp_md["lindley_warning"] is False
    # Per-obs log-LR can still be large; only the structural signature
    # gates the warning.
    assert cmp_md["per_observation_log_lr"] > 5.0


def test_compare_lindley_quiet_for_composite_vs_composite():
    """Two non-degenerate BetaBinomials (no uniform diffuse): no Lindley warning."""
    import warnings as _w

    pkg = CollectedPackage(name="bayes_composite_pkg", namespace="t")
    token = _current_package.set(pkg)
    try:
        theta = Variable(symbol="theta", domain=Probability)
        k = Variable(symbol="k", domain=Nat, value=10)
        n = 100

        h_elev = parameter(theta, 0.20, content="elevated.", prior=0.5, label="h_elev")
        h_base = parameter(theta, 0.05, content="baseline.", prior=0.5, label="h_base")
        data = observe(k, value=10, label="data", rationale="k = 10.")
        model_elev = bayes.model(
            h_elev,
            observable=k,
            distribution=BetaBinomial("elevated", n=n, alpha=10, beta=40),
            label="model_elev",
        )
        model_base = bayes.model(
            h_base,
            observable=k,
            distribution=BetaBinomial("baseline", n=n, alpha=1, beta=20),
            label="model_base",
        )
        cmp_result = bayes.compare(
            data,
            models=[model_elev, model_base],
            label="cmp_composite",
        )
    finally:
        _current_package.reset(token)

    with _w.catch_warnings(record=True) as caught:
        _w.simplefilter("always")
        compiled = compile_package_artifact(pkg)

    lindley = [w for w in caught if "Lindley" in str(w.message)]
    assert lindley == [], f"unexpected Lindley warning(s): {[str(w.message) for w in lindley]}"

    cmp_md = _ir_comparison_metadata(compiled, cmp_result)
    assert cmp_md["lindley_signature"] is False
    assert cmp_md["lindley_warning"] is False


def test_compare_metadata_always_exposes_diagnostic_fields():
    """The diagnostic numbers are present on every comparison."""
    pkg, cmp_result = _compile_lindley_setup(k_observed=24, alpha=1, beta=1)
    # k=24 is at the Binomial mode: log-LR is small; no warning, but fields exist
    compiled = compile_package_artifact(pkg)

    cmp_md = _ir_comparison_metadata(compiled, cmp_result)
    assert "max_pairwise_log_lr" in cmp_md
    assert "per_observation_log_lr" in cmp_md
    assert "lindley_threshold" in cmp_md
    assert "lindley_signature" in cmp_md
    assert "lindley_warning" in cmp_md
    assert cmp_md["lindley_warning"] is False
