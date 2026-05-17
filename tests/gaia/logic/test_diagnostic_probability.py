import subprocess
import sys

import pytest

import gaia.engine.ir.logic.probability as probability_module
from gaia.engine.bp import lower_local_graph
from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.joint_query import JointDistribution, JointQueryUnavailable
from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    inspect_formula_graphs,
)
from gaia.engine.ir.logic.probability import (
    ConditionProbabilityEstimate,
    DiagnosticProbability,
    event_probability,
    score_condition,
    score_diagnostic_conditions,
)
from gaia.engine.lang import ClaimAtom, associate, claim, land, lnot
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage

pytestmark = pytest.mark.pr_gate


def _joint_ab(method: str = "exact", *, is_exact: bool = True) -> JointDistribution:
    return JointDistribution(
        variables=["A", "B"],
        probabilities=[0.3, 0.2, 0.1, 0.4],
        method=method,
        is_exact=is_exact,
        basis="exact_joint_distribution" if is_exact else "approximate_joint_distribution",
    )


def _condition(expression: dict) -> DiagnosticCondition:
    return DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["A", "B"],
        expression=expression,
        confidence_basis="hard_logic",
    )


def test_logic_package_exports_diagnostic_probability_api():
    import gaia.engine.ir.logic as logic_package
    from gaia.engine.ir.logic import (
        ConditionProbabilityEstimate as ExportedConditionProbabilityEstimate,
    )
    from gaia.engine.ir.logic import (
        DiagnosticProbability as ExportedDiagnosticProbability,
    )
    from gaia.engine.ir.logic import (
        event_probability as exported_event_probability,
    )
    from gaia.engine.ir.logic import (
        score_condition as exported_score_condition,
    )
    from gaia.engine.ir.logic import (
        score_diagnostic_conditions as exported_score_diagnostic_conditions,
    )

    exported_names = {
        "ConditionProbabilityEstimate",
        "DiagnosticProbability",
        "event_probability",
        "score_condition",
        "score_diagnostic_conditions",
    }
    assert exported_names <= set(logic_package.__all__)
    assert ExportedConditionProbabilityEstimate is probability_module.ConditionProbabilityEstimate
    assert ExportedDiagnosticProbability is probability_module.DiagnosticProbability
    assert exported_event_probability is probability_module.event_probability
    assert exported_score_condition is probability_module.score_condition
    assert exported_score_diagnostic_conditions is probability_module.score_diagnostic_conditions


def test_logic_propositional_import_does_not_eagerly_load_bp_package():
    script = "\n".join(
        [
            "import sys",
            "from gaia.engine.ir.logic import is_satisfiable",
            "print('gaia.engine.bp' in sys.modules)",
            "print('gaia.engine.bp.joint_query' in sys.modules)",
            "print(callable(is_satisfiable))",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.splitlines() == ["False", "False", "True"]


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
    assert scored.diagnostic_code is None
    assert scored.condition_kind == "joint_incompatibility"
    assert scored.variables == ["A", "B"]
    assert scored.event_expression == {"var": "A"}
    assert scored.spread == pytest.approx(0.1)
    assert scored.exact_spread == pytest.approx(0.0)
    assert isinstance(scored.estimates[0], ConditionProbabilityEstimate)
    assert scored.estimates[0].probability == pytest.approx(0.6)
    assert isinstance(scored.estimates[1], ConditionProbabilityEstimate)
    assert scored.estimates[1].probability == pytest.approx(0.7)
    assert scored.unavailable == [unavailable]


def test_score_condition_accepts_diagnostic_code_and_all_unavailable_boundary():
    unavailable = JointQueryUnavailable(
        variables=["A", "B"],
        method="exact",
        reason="too large",
        diagnostics={"limit": 26},
    )
    condition = _condition({"var": "A"})

    scored = score_condition(condition, [unavailable], diagnostic_code="cross_claim")

    assert scored.diagnostic_code == "cross_claim"
    assert scored.condition_kind == "joint_incompatibility"
    assert scored.variables == ["A", "B"]
    assert scored.event_expression == {"var": "A"}
    assert scored.estimates == []
    assert scored.unavailable == [unavailable]
    assert scored.spread is None
    assert scored.exact_spread is None


def test_score_condition_approximate_only_has_zero_spread_and_no_exact_spread():
    approximate = _joint_ab("trw_bp", is_exact=False)
    condition = _condition({"var": "A"})

    scored = score_condition(condition, [approximate])

    assert len(scored.estimates) == 1
    assert scored.estimates[0].probability == pytest.approx(0.6)
    assert scored.spread == pytest.approx(0.0)
    assert scored.exact_spread is None


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

    scored = score_diagnostic_conditions([diagnostic, skipped], graph, methods=("exact",))

    assert len(scored) == 1
    assert scored[0].diagnostic_code == "cross_claim_entailment"
    assert scored[0].condition_kind == "joint_incompatibility"
    assert scored[0].variables == ["A", "B"]
    assert scored[0].event_expression == diagnostic.condition.expression
    assert scored[0].estimates[0].method == "exact"
    assert scored[0].estimates[0].probability == pytest.approx(0.08)
    assert scored[0].unavailable == []
    assert scored[0].spread == pytest.approx(0.0)
    assert scored[0].exact_spread == pytest.approx(0.0)


def test_score_diagnostic_conditions_from_physics_python_dsl_e2e():
    package = "cmb_bmode_logic_e2e"
    with CollectedPackage(package, namespace="physics", version="0.1.0") as pkg:
        bmode_excess = claim(
            "BICEP2 reports a degree-scale CMB B-mode excess, meaning an unexpectedly "
            "strong curl-like polarization pattern in the cosmic microwave background "
            "on degree angular scales.",
            prior=0.9,
        )
        bmode_excess.label = "bmode_excess"
        primordial_tensor = claim(
            "The B-mode excess is dominated by primordial tensor modes, meaning "
            "gravitational-wave fluctuations from early-universe inflation rather than "
            "later astrophysical foregrounds.",
            prior=0.4,
        )
        primordial_tensor.label = "primordial_tensor"
        bicep2_tensor_interpretation = claim(
            "BICEP2 interpretation: the observed B-mode excess is a primordial tensor "
            "signal, so the curl-like CMB polarization is mainly from inflationary "
            "gravitational waves.",
            formula=land(ClaimAtom(bmode_excess), ClaimAtom(primordial_tensor)),
            prior=0.4,
        )
        bicep2_tensor_interpretation.label = "bicep2_tensor_interpretation"
        planck_dust_interpretation = claim(
            "Planck foreground interpretation: the same B-mode excess is dominated by "
            "Galactic dust foreground, meaning polarized emission from dust in the "
            "Milky Way, not primordial tensor modes.",
            formula=land(ClaimAtom(bmode_excess), lnot(ClaimAtom(primordial_tensor))),
            prior=0.6,
        )
        planck_dust_interpretation.label = "planck_dust_interpretation"
        helper = associate(
            bicep2_tensor_interpretation,
            planck_dust_interpretation,
            p_a_given_b=0.5,
            p_b_given_a=0.75,
            pattern=None,
            rationale=(
                "Corpus/reviewer state still gives nontrivial belief to both historical "
                "interpretations, so the logic warning should be probability-scored."
            ),
            label="bmode_interpretation_tension",
        )
        helper.label = "bmode_tension_helper"

    artifact = compile_package_artifact(pkg)
    report = inspect_formula_graphs(artifact.graph)
    # Score the warning under the current belief graph, not under the formula
    # operators that generated the warning itself. Otherwise the hard logic
    # relation is conditioned on as evidence and Cromwell-clamps the event.
    belief_graph_ir = artifact.graph.model_copy(
        update={
            "operators": [
                op
                for op in artifact.graph.operators
                if not (op.metadata or {}).get("formula_lowering")
            ]
        }
    )
    graph = lower_local_graph(belief_graph_ir)

    left_id = f"physics:{package}::bicep2_tensor_interpretation"
    right_id = f"physics:{package}::planck_dust_interpretation"
    diagnostic = next(d for d in report.diagnostics if d.code == "cross_claim_incompatibility")
    assert diagnostic.severity == "warning"
    assert diagnostic.logic_strength == "hard"
    assert diagnostic.condition is not None
    assert diagnostic.condition.variables == [left_id, right_id]
    assert diagnostic.condition.expression == {
        "op": "and",
        "args": [{"var": left_id}, {"var": right_id}],
    }

    factor_types = {factor.factor_type for factor in graph.factors}
    assert factor_types == {FactorType.PAIRWISE_POTENTIAL}

    scored = score_diagnostic_conditions(
        [diagnostic],
        graph,
        methods=("exact", "junction_tree", "trw_bp", "mean_field"),
    )

    assert len(scored) == 1
    probability = scored[0]
    assert probability.diagnostic_code == "cross_claim_incompatibility"
    assert probability.condition_kind == "joint_incompatibility"
    assert probability.unavailable == []
    assert probability.exact_spread == pytest.approx(0.0)

    estimates = {estimate.method: estimate for estimate in probability.estimates}
    assert set(estimates) == {"exact", "junction_tree", "trw_bp", "mean_field"}
    assert estimates["exact"].is_exact is True
    assert estimates["junction_tree"].is_exact is True
    assert estimates["trw_bp"].is_exact is False
    assert estimates["mean_field"].is_exact is False
    assert estimates["junction_tree"].probability == pytest.approx(estimates["exact"].probability)
    assert estimates["exact"].probability == pytest.approx(0.3)
    assert estimates["trw_bp"].probability > 0.25
    assert estimates["mean_field"].probability > 0.2


def test_score_diagnostic_conditions_propagates_unexpected_provider_errors(monkeypatch):
    graph = FactorGraph()
    graph.add_variable("A", 0.5)
    graph.add_variable("B", 0.5)
    diagnostic = FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="A",
        related_claims=["B"],
        formula_nodes=["fg:a", "fg:b"],
        condition=_condition({"op": "and", "args": [{"var": "A"}, {"var": "B"}]}),
        message="A and B conflict.",
    )

    def raise_unexpected_provider_bug(_graph, _variables, *, methods):
        raise RuntimeError(f"provider bug for {methods!r}")

    monkeypatch.setattr(
        probability_module,
        "compare_joint_over",
        raise_unexpected_provider_bug,
    )

    with pytest.raises(RuntimeError, match="provider bug"):
        score_diagnostic_conditions([diagnostic], graph, methods=("exact",))
