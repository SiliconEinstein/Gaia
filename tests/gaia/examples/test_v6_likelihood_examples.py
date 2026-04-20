"""End-to-end tests for runnable v6 likelihood examples."""

from gaia.bp import lower_local_graph
from gaia.ir import ModuleUseMethod
from gaia.ir.validator import validate_local_graph

from examples.v6_likelihood.ab_test import infer_ab_test
from examples.v6_likelihood.mendel import infer_mendel


def test_mendel_example_compiles_and_infers():
    result = infer_mendel()
    graph = result.compiled.graph
    validation = validate_local_graph(graph)
    assert validation.valid, validation.errors

    assert len(graph.likelihood_scores) == 1
    score = graph.likelihood_scores[0]
    assert score.module_ref == "gaia.std.likelihood.binomial_model@v1"
    assert round(score.value, 6) == -0.010519

    target_id = "github:v6_mendel_likelihood::three_to_one_not_disconfirmed"
    assert target_id in result.beliefs
    assert 0.49 < result.beliefs[target_id] < 0.51

    factor_graph = lower_local_graph(graph)
    assert any(f.factor_id.startswith("like_loglr") for f in factor_graph.factors)


def test_ab_test_example_compiles_and_infers():
    result = infer_ab_test()
    graph = result.compiled.graph
    validation = validate_local_graph(graph)
    assert validation.valid, validation.errors

    strategies = {strategy.type: strategy for strategy in graph.strategies}
    likelihood = strategies["likelihood"]
    assert isinstance(likelihood.method, ModuleUseMethod)
    assert likelihood.method.output_bindings["score"] == graph.likelihood_scores[0].score_id

    score = graph.likelihood_scores[0]
    assert score.module_ref == "gaia.std.likelihood.two_binomial_ab_test@v1"
    assert score.value > 1.25

    target_id = "github:v6_ab_test_likelihood::treatment_b_better"
    assert result.beliefs[target_id] > 0.75
