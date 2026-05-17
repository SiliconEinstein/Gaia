import gaia.engine.bayes as bayes
from gaia.engine.lang import (
    Claim,
    Nat,
    Variable,
    associate,
    candidate_relation,
    compose,
    compute,
    derive,
    infer,
)
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.action import Associate, Compose, Compute, Infer
from gaia.engine.lang.runtime.package import CollectedPackage


class Probability(Claim):
    """Probability is {value}."""

    value: float


def _knowledge_by_label(compiled):
    return {k.label: k for k in compiled.graph.knowledges if k.label}


def _knowledge_by_id(compiled):
    return {k.id: k for k in compiled.graph.knowledges if k.id}


def _strategy_by_id(compiled):
    return {s.strategy_id: s for s in compiled.graph.strategies}


def test_compose_returns_conclusion_and_compiles_action_dag():
    @compose(name="test:evidence:toy_likelihood", version="1.0")
    def toy_likelihood(evidence: Claim, hypothesis: Claim) -> Claim:
        p_h = compute(Probability, fn=lambda: 0.8, label="compute_p_e_given_h")
        p_h.label = "p_e_given_h"
        p_not_h = compute(Probability, fn=lambda: 0.2, label="compute_p_e_given_not_h")
        p_not_h.label = "p_e_given_not_h"
        return infer(
            evidence,
            hypothesis=hypothesis,
            p_e_given_h=p_h,
            p_e_given_not_h=p_not_h,
            rationale="Computed toy likelihood.",
            label="infer_toy",
        )

    with CollectedPackage("v6_composition") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        conclusion = toy_likelihood(e, h)
        infer_action = next(action for action in pkg.actions if isinstance(action, Infer))
        assert infer_action.helper is not None
        infer_action.helper.label = "likelihood_helper"

    compose_actions = [action for action in pkg.actions if isinstance(action, Compose)]
    assert len(compose_actions) == 1
    compose_action = compose_actions[0]
    assert conclusion is e
    assert compose_action.conclusion is e
    assert compose_action in e.from_actions
    assert compose_action.inputs == (e, h)
    assert [type(action) for action in compose_action.actions] == [Compute, Compute, Infer]
    assert compose_action.warrants == []

    compiled = compile_package_artifact(pkg)
    by_label = _knowledge_by_label(compiled)
    assert not [k for k in compiled.graph.knowledges if k.type == "composition"]
    assert len(compiled.graph.composes) == 1
    node = compiled.graph.composes[0]
    assert node.name == "test:evidence:toy_likelihood"
    assert node.version == "1.0"
    assert node.inputs == ["github:v6_composition::e", "github:v6_composition::h"]
    assert node.conclusion == "github:v6_composition::e"
    assert node.actions == [
        compiled.action_label_map["github:v6_composition::action::compute_p_e_given_h"],
        compiled.action_label_map["github:v6_composition::action::compute_p_e_given_not_h"],
        compiled.action_label_map["github:v6_composition::action::infer_toy"],
    ]

    by_id = _knowledge_by_id(compiled)
    strategies = _strategy_by_id(compiled)
    compute_strategy = strategies[
        compiled.action_label_map["github:v6_composition::action::compute_p_e_given_h"]
    ]
    compute_warrant_id = compute_strategy.metadata["warrants"][0]
    assert by_id[compute_warrant_id].metadata["relation"]["type"] == "compute"
    assert by_label["likelihood_helper"].metadata["relation"]["type"] == "infer"


def test_compose_infers_closed_over_infer_given_as_input():
    with CollectedPackage("v6_composition") as pkg:
        h = Claim("H.")
        h.label = "h"
        e = Claim("E.")
        e.label = "e"
        gate = Claim("Gate.")
        gate.label = "gate"

        @compose(name="test:evidence:gated", version="1.0")
        def gated_likelihood(evidence: Claim, hypothesis: Claim) -> Claim:
            return infer(
                evidence,
                hypothesis=hypothesis,
                given=gate,
                p_e_given_h=0.8,
                label="infer_toy",
            )

        result = gated_likelihood(e, h)

    compose_action = next(action for action in pkg.actions if isinstance(action, Compose))
    assert result is e
    assert compose_action.inputs == (e, h, gate)


def test_compose_keeps_own_background_and_warrants_separate_from_child_warrants():
    with CollectedPackage("v6_composition") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        bg = Claim("Shared modeling background.")
        bg.label = "bg"
        compose_warrant = Claim(
            "The association is the right boundary object for this composition.",
            metadata={"generated": True, "helper_kind": "compose_warrant", "review": True},
        )
        compose_warrant.label = "compose_warrant"

        @compose(
            name="test:association:toy",
            version="1.0",
            background=[bg],
            warrants=[compose_warrant],
            label="assoc_workflow",
        )
        def workflow(left: Claim, right: Claim) -> Claim:
            return associate(
                left,
                right,
                p_a_given_b=0.75,
                p_b_given_a=0.25,
                label="assoc_ab",
            )

        helper = workflow(a, b)
        helper.label = "assoc_helper"

    compose_action = next(action for action in pkg.actions if isinstance(action, Compose))
    child_action = next(action for action in pkg.actions if isinstance(action, Associate))
    assert compose_action.background == [bg]
    assert compose_action.warrants == [compose_warrant]
    assert helper.from_actions == [child_action, compose_action]
    assert child_action.warrants == []
    assert helper not in compose_action.warrants

    compiled = compile_package_artifact(pkg)
    node = compiled.graph.composes[0]
    assert node.background == ["github:v6_composition::bg"]
    assert node.warrants == ["github:v6_composition::compose_warrant"]
    assert node.actions == [compiled.action_label_map["github:v6_composition::action::assoc_ab"]]
    assert (
        compiled.action_label_map["github:v6_composition::action::assoc_workflow"]
        == node.compose_id
    )


def test_compose_can_reference_bayes_model_and_likelihood_actions():
    with CollectedPackage("v6_bayes_composition") as pkg:
        k = Variable(symbol="k", domain=Nat, value=3)
        h = Claim(
            "theta = 0.5.",
            formula=None,
            prior=0.5,
        )
        h.label = "h"
        data = Claim("Observed k = 3.")
        data.label = "data"

        @compose(name="test:bayes:single", version="1.0")
        def workflow(hypothesis: Claim, observation: Claim) -> Claim:
            model = bayes.model(
                hypothesis,
                observable=k,
                distribution=bayes.Binomial(n=5, p=0.5),
                label="model_h",
            )
            return bayes.likelihood(
                observation,
                model=model,
                precomputed={hypothesis: -1.0},
                label="cmp_h",
            )

        comparison = workflow(h, data)

    compiled = compile_package_artifact(pkg)
    node = compiled.graph.composes[0]

    assert node.conclusion == "github:v6_bayes_composition::cmp_h"
    assert node.actions == [
        compiled.action_label_map["github:v6_bayes_composition::action::model_h"],
        compiled.action_label_map["github:v6_bayes_composition::action::cmp_h"],
    ]
    assert compiled.action_label_map["github:v6_bayes_composition::action::cmp_h"] == (
        "github:v6_bayes_composition::cmp_h"
    )
    assert comparison.label == "cmp_h"


def test_compose_identity_depends_on_ordered_actions():
    conclusion = Claim("C.")
    first = Compose(
        name="test:order",
        version="1.0",
        actions=("a", "b"),
        conclusion=conclusion,
    )
    second = Compose(
        name="test:order",
        version="1.0",
        actions=("b", "a"),
        conclusion=conclusion,
    )

    assert first.structure_hash(["in"], ["a", "b"], "c", []) != second.structure_hash(
        ["in"], ["b", "a"], "c", []
    )


def test_compose_does_not_capture_scaffold_records_as_child_reasoning():
    with CollectedPackage("v6_scaffold_composition") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        c = Claim("C.")
        c.label = "c"

        @compose(name="test:scaffold-free", version="1.0")
        def workflow() -> Claim:
            candidate_relation(claims=[a, b], label="open_relation")
            return derive(c, given=[a], rationale="C follows from A.", label="derive_c")

        workflow()

    compiled = compile_package_artifact(pkg)
    node = compiled.graph.composes[0]
    assert node.actions == [
        compiled.action_label_map["github:v6_scaffold_composition::action::derive_c"]
    ]
    assert compiled.formalization_manifest["dependencies"][0]["label"] == "open_relation"
