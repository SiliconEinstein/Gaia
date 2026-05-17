import numpy as np
import pytest

import gaia.engine.bp.joint_query as joint_query_module
from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointQueryUnavailable,
    JointQueryUnavailableError,
    compare_joint_over,
    joint_over,
)
from gaia.engine.bp.trw_bp import (
    TRWBeliefPropagation,
    TRWDiagnostics,
    _compute_factor_joint_tables,
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


def _chain_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.5)
    graph.add_variable("C", 0.5)
    graph.add_factor("f:a_to_b", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
    graph.add_factor("f:b_to_c", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.85, p2=0.9)
    return graph


def _contradiction_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.25)
    graph.add_variable("H", 0.7)
    graph.add_factor("f:not_both", FactorType.CONTRADICTION, ["A", "B"], "H")
    return graph


def _nested_covering_factor_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.25)
    graph.add_variable("H", 0.7)
    graph.add_factor("f:larger", FactorType.CONTRADICTION, ["A", "B"], "H")
    graph.add_factor("f:smaller", FactorType.PAIRWISE_POTENTIAL, ["A"], "B", cpt=[1, 4, 2, 8])
    return graph


def test_bp_package_exports_joint_query_api():
    import gaia.engine.bp as bp_package
    from gaia.engine.bp import (
        JointDistribution as ExportedJointDistribution,
    )
    from gaia.engine.bp import (
        JointDistributionBasis as ExportedJointDistributionBasis,
    )
    from gaia.engine.bp import (
        JointQueryMethod as ExportedJointQueryMethod,
    )
    from gaia.engine.bp import (
        JointQueryUnavailable as ExportedJointQueryUnavailable,
    )
    from gaia.engine.bp import (
        JointQueryUnavailableError as ExportedJointQueryUnavailableError,
    )
    from gaia.engine.bp import (
        compare_joint_over as exported_compare_joint_over,
    )
    from gaia.engine.bp import (
        joint_over as exported_joint_over,
    )

    exported_names = {
        "JointDistribution",
        "JointDistributionBasis",
        "JointQueryMethod",
        "JointQueryUnavailable",
        "JointQueryUnavailableError",
        "compare_joint_over",
        "joint_over",
    }
    assert exported_names <= set(bp_package.__all__)
    assert ExportedJointDistribution is joint_query_module.JointDistribution
    assert ExportedJointDistributionBasis is joint_query_module.JointDistributionBasis
    assert ExportedJointQueryMethod is joint_query_module.JointQueryMethod
    assert ExportedJointQueryUnavailable is joint_query_module.JointQueryUnavailable
    assert ExportedJointQueryUnavailableError is joint_query_module.JointQueryUnavailableError
    assert exported_compare_joint_over is joint_query_module.compare_joint_over
    assert exported_joint_over is joint_query_module.joint_over


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

    with pytest.raises(ValueError, match="must sum to 1"):
        JointDistribution(
            variables=["A", "B"],
            probabilities=[0.25, 0.25, 0.25, 0.30],
            method="exact",
            is_exact=True,
            basis="exact_joint_distribution",
        )

    with pytest.raises(ValueError, match="must be finite"):
        JointDistribution(
            variables=["A"],
            probabilities=[float("nan"), 1.0],
            method="exact",
            is_exact=True,
            basis="exact_joint_distribution",
        )

    with pytest.raises(ValueError, match="must be unique"):
        JointDistribution(
            variables=["A", "A"],
            probabilities=[0.25, 0.25, 0.25, 0.25],
            method="exact",
            is_exact=True,
            basis="exact_joint_distribution",
        )


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
        methods=("exact", "junction_tree", "trw_bp", "mean_field"),
    )

    estimates = [result for result in results if isinstance(result, JointDistribution)]
    unavailable = [result for result in results if isinstance(result, JointQueryUnavailable)]

    assert {estimate.method for estimate in estimates} == {"exact", "junction_tree", "mean_field"}
    assert {item.method for item in unavailable} == {"trw_bp"}
    assert all(item.variables == ["A", "B"] for item in unavailable)
    assert unavailable[0].diagnostics["converged"] is True
    assert unavailable[0].diagnostics["available_scopes"] == []
    exact = next(estimate for estimate in estimates if estimate.method == "exact")
    junction_tree = next(estimate for estimate in estimates if estimate.method == "junction_tree")
    assert junction_tree.probabilities == pytest.approx(exact.probabilities)


def test_trw_no_factor_diagnostics_are_converged_with_empty_factor_tables():
    result = TRWBeliefPropagation().run(_two_variable_graph())

    assert result.diagnostics.converged is True
    assert result.diagnostics.factor_joint_tables == []


def test_trw_diagnostics_positional_constructor_keeps_rho_and_treewidth_order():
    diagnostics = TRWDiagnostics(False, 3, 0.25, {}, {}, 0.5, 7)

    assert diagnostics.rho == pytest.approx(0.5)
    assert diagnostics.treewidth == 7
    assert diagnostics.factor_joint_tables == []


def test_junction_tree_no_factor_singleton_query_uses_singleton_scope():
    joint = joint_over(_two_variable_graph(), ["A"], method="junction_tree")

    assert joint.method == "junction_tree"
    assert joint.is_exact is True
    assert joint.probabilities == pytest.approx([0.3, 0.7])
    assert joint.diagnostics["treewidth"] == 0
    assert joint.diagnostics["clique_size"] == 1
    assert joint.diagnostics["source_clique"] == ["A"]


def test_junction_tree_no_factor_joint_uses_independent_singleton_scopes():
    graph = FactorGraph()
    variables = [f"V{i}" for i in range(12)]
    for variable in variables:
        graph.add_variable(variable, 0.5)

    joint = joint_over(graph, ["V0", "V11"], method="junction_tree")

    assert joint.probabilities == pytest.approx([0.25, 0.25, 0.25, 0.25])
    assert joint.diagnostics["treewidth"] == 0
    assert joint.diagnostics["clique_size"] == 1
    assert joint.diagnostics["source_cliques"] == [["V0"], ["V11"]]
    assert "source_clique" not in joint.diagnostics


def test_unknown_variable_is_collected_as_unavailable():
    results = compare_joint_over(_two_variable_graph(), ["A", "missing"], methods=("exact",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "exact"
    assert "unknown variables" in unavailable.reason


def test_exact_too_many_variables_is_collected_as_unavailable():
    graph = FactorGraph()
    variables = [f"V{i}" for i in range(27)]
    for variable in variables:
        graph.add_variable(variable, 0.5)

    results = compare_joint_over(graph, variables, methods=("exact",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "exact"
    assert "Exact inference requires 2^n enumeration" in unavailable.reason


def test_unexpected_exact_provider_errors_propagate(monkeypatch):
    def raise_unexpected_value_error(_graph, _variables):
        raise ValueError("internal exact provider bug")

    monkeypatch.setattr(
        "gaia.engine.bp.joint_query.exact_joint_over",
        raise_unexpected_value_error,
    )

    with pytest.raises(ValueError, match="internal exact provider bug"):
        joint_over(_two_variable_graph(), ["A", "B"], method="exact")


def test_unexpected_junction_tree_provider_errors_propagate(monkeypatch):
    def raise_unexpected_value_error(_graph):
        raise ValueError("internal calibration bug")

    monkeypatch.setattr(
        "gaia.engine.bp.joint_query.calibrate_junction_tree",
        raise_unexpected_value_error,
    )

    with pytest.raises(ValueError, match="internal calibration bug"):
        joint_over(_two_variable_graph(), ["A"], method="junction_tree")


def test_mean_field_on_entailment_graph_returns_normalized_joint():
    joint = joint_over(_entailment_graph(), ["A", "B"], method="mean_field")

    assert sum(joint.probabilities) == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in joint.probabilities)
    assert joint.diagnostics["iterations_run"] >= 1


def test_junction_tree_joint_matches_exact_when_clique_contains_query():
    graph = _chain_graph()

    exact = joint_over(graph, ["A", "B"], method="exact")
    jt = joint_over(graph, ["A", "B"], method="junction_tree")

    assert jt.method == "junction_tree"
    assert jt.is_exact is True
    assert jt.basis == "calibrated_clique_marginal"
    assert jt.variables == ["A", "B"]
    assert jt.probabilities == pytest.approx(exact.probabilities, abs=1e-9)
    assert jt.diagnostics["treewidth"] >= 1


def test_junction_tree_returns_unavailable_without_covering_clique():
    results = compare_joint_over(_chain_graph(), ["A", "C"], methods=("junction_tree",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "junction_tree"
    assert "single calibrated clique" in unavailable.reason


def test_trw_bp_returns_factor_scope_pseudo_joint():
    joint = joint_over(_contradiction_graph(), ["A", "B"], method="trw_bp")

    assert joint.method == "trw_bp"
    assert joint.is_exact is False
    assert joint.basis == "approximate_joint_distribution"
    assert joint.variables == ["A", "B"]
    assert sum(joint.probabilities) == pytest.approx(1.0)

    expected = [0.105 / 0.62, 0.42 / 0.62, 0.035 / 0.62, 0.06 / 0.62]
    assert joint.probabilities == pytest.approx(expected, abs=1e-5)
    assert joint.probabilities[1] > joint.probabilities[2]

    assert joint.diagnostics["source_factor_id"] == "f:not_both"
    assert joint.diagnostics["source_factor_variables"] == ["A", "B", "H"]
    assert joint.diagnostics["source_factor_rho"] == pytest.approx(1.0)
    assert joint.diagnostics["converged"] is True
    assert joint.diagnostics["iterations_run"] >= 1


def test_trw_bp_chooses_smallest_covering_factor_scope():
    joint = joint_over(_nested_covering_factor_graph(), ["A", "B"], method="trw_bp")

    assert joint.diagnostics["source_factor_id"] == "f:smaller"
    assert joint.diagnostics["source_factor_index"] == 1
    assert joint.diagnostics["source_factor_variables"] == ["A", "B"]


def test_trw_bp_returns_unavailable_without_factor_scope_joint():
    with pytest.raises(JointQueryUnavailableError, match="factor-scope pseudo-joint") as exc_info:
        joint_over(_chain_graph(), ["A", "C"], method="trw_bp")

    error = exc_info.value
    assert error.method == "trw_bp"
    assert error.variables == ["A", "C"]
    assert error.diagnostics["available_scopes"] == [["A", "B"], ["B", "C"]]


def test_trw_factor_joint_tables_do_not_raise_potential_to_rho():
    graph = FactorGraph()
    graph.add_variable("A", 0.5)
    graph.add_variable("B", 0.5)
    graph.add_factor(
        "f:weighted",
        FactorType.PAIRWISE_POTENTIAL,
        ["A"],
        "B",
        cpt=[1.0, 4.0, 2.0, 8.0],
    )
    uniform_messages = {
        ("A", 0): np.array([0.5, 0.5]),
        ("B", 0): np.array([0.5, 0.5]),
    }

    tables = _compute_factor_joint_tables(graph, uniform_messages, {0: 0.5})

    assert len(tables) == 1
    assert tables[0]["rho"] == pytest.approx(0.5)
    assert tables[0]["probabilities"] == pytest.approx([1 / 15, 4 / 15, 2 / 15, 8 / 15])
