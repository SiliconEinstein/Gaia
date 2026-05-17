import pytest

from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.joint_query import JointDistribution, JointQueryUnavailable
from gaia.engine.ir.logic.diagnostics import DiagnosticCondition, FormulaDiagnostic
from gaia.engine.ir.logic.probability import (
    ConditionProbabilityEstimate,
    DiagnosticProbability,
    event_probability,
    score_condition,
    score_diagnostic_conditions,
)

pytestmark = pytest.mark.pr_gate


def _joint_ab(method: str = "exact", *, is_exact: bool = True) -> JointDistribution:
    return JointDistribution(
        variables=["A", "B"],
        probabilities=[0.3, 0.2, 0.1, 0.4],
        method=method,
        is_exact=is_exact,
        basis="exact_joint_distribution"
        if is_exact
        else "approximate_joint_distribution",
    )


def _condition(expression: dict) -> DiagnosticCondition:
    return DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["A", "B"],
        expression=expression,
        confidence_basis="hard_logic",
    )


def test_event_probability_sums_joint_assignments_in_bit_index_order():
    joint = _joint_ab()

    both_true = {"op": "and", "args": [{"var": "A"}, {"var": "B"}]}
    a_without_b = {
        "op": "and",
        "args": [{"var": "A"}, {"op": "not", "arg": {"var": "B"}}],
    }
    mismatch = {
        "op": "or",
        "args": [
            a_without_b,
            {
                "op": "and",
                "args": [{"op": "not", "arg": {"var": "A"}}, {"var": "B"}],
            },
        ],
    }

    assert event_probability(both_true, joint) == pytest.approx(0.4)
    assert event_probability(a_without_b, joint) == pytest.approx(0.2)
    assert event_probability(mismatch, joint) == pytest.approx(0.3)


def test_event_probability_does_not_use_marginals_or_independence():
    joint = _joint_ab()

    marginal_a = 0.2 + 0.4
    marginal_b = 0.1 + 0.4
    assert marginal_a * marginal_b == pytest.approx(0.3)
    assert event_probability(
        {"op": "and", "args": [{"var": "A"}, {"var": "B"}]},
        joint,
    ) == pytest.approx(0.4)


def test_event_probability_rejects_missing_variables_and_malformed_expressions():
    joint = _joint_ab()

    with pytest.raises(ValueError, match="unknown variable"):
        event_probability({"var": "missing"}, joint)

    with pytest.raises(ValueError, match="not expression requires"):
        event_probability({"op": "not", "args": [{"var": "A"}]}, joint)

    with pytest.raises(ValueError, match="unsupported diagnostic condition operator"):
        event_probability({"op": "xor", "args": [{"var": "A"}, {"var": "B"}]}, joint)


def test_score_condition_preserves_unavailable_items_and_computes_spreads():
    exact = _joint_ab("exact", is_exact=True)
    approximate = JointDistribution(
        variables=["A", "B"],
        probabilities=[0.2, 0.3, 0.1, 0.4],
        method="trw_bp",
        is_exact=False,
        basis="approximate_joint_distribution",
    )
    unavailable = JointQueryUnavailable(
        variables=["A", "B"],
        method="junction_tree",
        reason="not in one clique",
        diagnostics={"treewidth": 3},
    )
    condition = _condition({"var": "A"})

    scored = score_condition(condition, [exact, unavailable, approximate])

    assert isinstance(scored, DiagnosticProbability)
    assert scored.condition == condition
    assert scored.diagnostic is None
    assert scored.spread == pytest.approx(0.1)
    assert scored.exact_spread == pytest.approx(0.0)
    assert isinstance(scored.estimates[0], ConditionProbabilityEstimate)
    assert scored.estimates[0].probability == pytest.approx(0.6)
    assert scored.estimates[1] == unavailable
    assert isinstance(scored.estimates[2], ConditionProbabilityEstimate)
    assert scored.estimates[2].probability == pytest.approx(0.7)


def test_score_diagnostic_conditions_queries_graph_and_skips_diagnostics_without_condition():
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.5)
    graph.add_factor("f:a_to_b", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)

    diagnostic = FormulaDiagnostic(
        code="cross_claim_entailment",
        severity="info",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="A",
        related_claims=["B"],
        formula_nodes=["fg:a", "fg:b"],
        condition=_condition(
            {
                "op": "and",
                "args": [{"var": "A"}, {"op": "not", "arg": {"var": "B"}}],
            }
        ),
        message="A entails B.",
    )
    skipped = FormulaDiagnostic(
        code="formula_projection_unsupported",
        severity="info",
        scope="claim",
        logic_strength="unknown",
        source_claim="C",
        message="No condition.",
    )

    scored = score_diagnostic_conditions(graph, [diagnostic, skipped], methods=("exact",))

    assert len(scored) == 1
    assert scored[0].diagnostic == diagnostic
    assert scored[0].condition == diagnostic.condition
    assert scored[0].estimates[0].method == "exact"
    assert scored[0].estimates[0].probability == pytest.approx(0.08)
    assert scored[0].spread == pytest.approx(0.0)
    assert scored[0].exact_spread == pytest.approx(0.0)
