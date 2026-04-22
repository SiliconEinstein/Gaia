from gaia.lang import Claim, compute, contradict, derive, equal, infer, observe
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage


class IntClaim(Claim):
    """Value is {value}."""

    value: int


class SumResult(Claim):
    """Sum is {value}."""

    value: int


def _knowledge_by_label(compiled):
    return {k.label: k for k in compiled.graph.knowledges if k.label}


def test_compile_derive_action_to_deduction_formal_strategy():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = derive("C.", given=(a, b), rationale="A and B imply C.", label="derive_c")
        c.label = "c"

    compiled = compile_package_artifact(pkg)
    assert compiled.action_label_map["github:v6_actions::action::derive_c"].startswith("lcs_")
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "deduction"
    assert strategy.metadata["action_label"] == "github:v6_actions::action::derive_c"
    assert strategy.metadata["pattern"] == "derivation"
    assert strategy.steps[0].reasoning == "A and B imply C."

    implication_helpers = [
        k
        for k in compiled.graph.knowledges
        if (k.metadata or {}).get("helper_kind") == "implication_result"
    ]
    conjunction_helpers = [
        k
        for k in compiled.graph.knowledges
        if (k.metadata or {}).get("helper_kind") == "conjunction_result"
    ]
    assert implication_helpers[0].metadata["review"] is True
    assert conjunction_helpers[0].metadata["review"] is False


def test_compile_root_observe_action_to_reviewable_grounding():
    with CollectedPackage("v6_actions") as pkg:
        data = observe("UV spectrum data.", rationale="Measured.", label="observe_uv")
        data.label = "uv"

    compiled = compile_package_artifact(pkg)
    assert compiled.graph.strategies == []
    assert compiled.action_label_map["github:v6_actions::action::observe_uv"] == (
        "github:v6_actions::uv"
    )

    uv = _knowledge_by_label(compiled)["uv"]
    assert uv.metadata["grounding"]["kind"] == "source_fact"
    assert uv.metadata["grounding"]["action_label"] == "github:v6_actions::action::observe_uv"


def test_compile_compute_action_to_deduction_with_compute_metadata():
    with CollectedPackage("v6_actions") as pkg:
        a = IntClaim(value=3)
        a.label = "a"
        b = IntClaim(value=4)
        b.label = "b"
        result = compute(
            SumResult,
            fn=lambda a, b: a.value + b.value,
            given=(a, b),
            rationale="Addition.",
            label="sum",
        )
        result.label = "sum_result"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "deduction"
    assert strategy.metadata["pattern"] == "computation"
    assert strategy.metadata["action_label"] == "github:v6_actions::action::sum"
    assert "compute" in strategy.metadata
    assert strategy.metadata["compute"]["function_ref"]


def test_compile_equal_and_contradict_actions_to_operators():
    with CollectedPackage("v6_actions") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        eq = equal(a, b, rationale="Same.", label="same")
        eq.label = "same_helper"
        conflict = contradict(a, b, rationale="Conflict.", label="conflict")
        conflict.label = "conflict_helper"

    compiled = compile_package_artifact(pkg)
    by_operator = {op.operator: op for op in compiled.graph.operators}
    assert by_operator["equivalence"].metadata["action_label"] == "github:v6_actions::action::same"
    assert by_operator["equivalence"].conclusion == "github:v6_actions::same_helper"
    assert by_operator["contradiction"].metadata["action_label"] == (
        "github:v6_actions::action::conflict"
    )
    assert by_operator["contradiction"].conclusion == "github:v6_actions::conflict_helper"


def test_compile_infer_action_to_strategy_cpt():
    with CollectedPackage("v6_actions") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        bg = Claim("Measurement reliable.")
        bg.label = "reliable"
        result = infer(
            e,
            hypothesis=h,
            background=[bg],
            p_e_given_h=0.8,
            p_e_given_not_h=0.2,
            rationale="Bayes.",
            label="bayes_update",
        )
        assert result is e
        helper = pkg.actions[0].helper
        assert helper is not None
        helper.label = "stat_support"

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.type == "infer"
    assert strategy.premises == ["github:v6_actions::h"]
    assert strategy.conclusion == "github:v6_actions::e"
    assert strategy.background == ["github:v6_actions::reliable"]
    assert strategy.metadata["action_label"] == "github:v6_actions::action::bayes_update"
    assert strategy.steps[0].reasoning == "Bayes."
    assert strategy.conditional_probabilities == [0.2, 0.8]
    assert not hasattr(compiled, "strategy_param_records")

    stat_support = _knowledge_by_label(compiled)["stat_support"]
    assert stat_support.metadata["helper_kind"] == "statistical_support"
    assert stat_support.metadata["review"] is True
