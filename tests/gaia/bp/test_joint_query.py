import pytest

from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointQueryUnavailable,
    compare_joint_over,
    joint_over,
)

pytestmark = pytest.mark.pr_gate


def _two_variable_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.7)
    graph.add_variable("B", 0.2)
    return graph


def _entailment_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.5)
    graph.add_factor("f:a_to_b", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
    return graph


def test_joint_distribution_validates_bit_order_and_normalization():
    joint = JointDistribution(
        variables=["A", "B"],
        probabilities=[0.24, 0.56, 0.06, 0.14],
        method="exact",
        is_exact=True,
        basis="exact_joint_distribution",
    )

    assert joint.variables == ["A", "B"]
    assert joint.probabilities[3] == pytest.approx(0.14)


def test_exact_joint_over_preserves_existing_bit_order():
    joint = joint_over(_two_variable_graph(), ["A", "B"], method="exact")

    assert joint.method == "exact"
    assert joint.is_exact is True
    assert joint.basis == "exact_joint_distribution"
    assert joint.variables == ["A", "B"]
    assert joint.probabilities == pytest.approx([0.24, 0.56, 0.06, 0.14])


def test_mean_field_joint_is_variational_product_distribution():
    joint = joint_over(_two_variable_graph(), ["A", "B"], method="mean_field")

    assert joint.method == "mean_field"
    assert joint.is_exact is False
    assert joint.basis == "variational_joint_distribution"
    assert joint.probabilities == pytest.approx([0.24, 0.56, 0.06, 0.14])
    assert joint.diagnostics["converged"] is True


def test_compare_joint_over_collects_unavailable_methods():
    results = compare_joint_over(
        _two_variable_graph(),
        ["A", "B"],
        methods=("exact", "trw_bp", "mean_field"),
    )

    estimates = [result for result in results if isinstance(result, JointDistribution)]
    unavailable = [result for result in results if isinstance(result, JointQueryUnavailable)]

    assert {estimate.method for estimate in estimates} == {"exact", "mean_field"}
    assert {item.method for item in unavailable} == {"trw_bp"}
    assert all(item.variables == ["A", "B"] for item in unavailable)


def test_unknown_variable_is_collected_as_unavailable():
    results = compare_joint_over(_two_variable_graph(), ["A", "missing"], methods=("exact",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "exact"
    assert "unknown variables" in unavailable.reason


def test_mean_field_on_entailment_graph_returns_normalized_joint():
    joint = joint_over(_entailment_graph(), ["A", "B"], method="mean_field")

    assert sum(joint.probabilities) == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in joint.probabilities)
    assert joint.diagnostics["iterations_run"] >= 1
