from __future__ import annotations

import pytest

import gaia.engine.bayes as bayes
from gaia.engine.lang import (
    Probability,
    Variable,
    associate,
    claim,
    contradict,
    depends_on,
    equal,
)
from gaia.engine.lang.runtime.action import (
    Associate,
    CandidateRelation,
    DependsOn,
    Equal,
    attach_reasoning,
    validate_no_self_warrant,
)
from gaia.engine.lang.runtime.package import CollectedPackage


def test_relation_helpers_are_primary_attachments_not_self_warrants() -> None:
    with CollectedPackage("reference_boundary") as pkg:
        a = claim("A.")
        b = claim("B.")
        helper = equal(a, b, label="same")

    action = next(action for action in pkg.actions if isinstance(action, Equal))
    assert action.helper is helper
    assert helper.from_actions == [action]
    assert action.warrants == []


def test_associate_helper_is_primary_attachment_not_self_warrant() -> None:
    with CollectedPackage("reference_boundary") as pkg:
        a = claim("A.")
        b = claim("B.")
        helper = associate(
            a,
            b,
            p_a_given_b=0.7,
            p_b_given_a=0.6,
            label="association",
        )

    action = next(action for action in pkg.actions if isinstance(action, Associate))
    assert action.helper is helper
    assert helper.from_actions == [action]
    assert action.warrants == []


def test_bayes_helpers_are_primary_attachments_not_self_warrants() -> None:
    with CollectedPackage("reference_boundary") as pkg:
        theta = Variable(symbol="theta", domain=Probability)
        h = claim("Hypothesis.", prior=0.5)
        data = claim("Data.")
        model = bayes.model(
            h,
            observable=theta,
            distribution=bayes.Beta(alpha=3, beta=1),
            label="model",
        )
        comparison = bayes.likelihood(data, model=model, label="comparison")

    model_action = model.from_actions[0]
    comparison_action = comparison.from_actions[0]
    assert model_action in pkg.actions
    assert comparison_action in pkg.actions
    assert model_action.warrants == []
    assert comparison_action.warrants == []


def test_scaffold_verbs_return_scaffold_records_without_claim_backrefs() -> None:
    with CollectedPackage("reference_boundary"):
        conclusion = claim("Conclusion.")
        premise = claim("Premise.")
        dependency = depends_on(conclusion, given=[premise], label="gap")
        relation = contradict(conclusion, premise, label="formal_relation")
        scaffold = depends_on(conclusion, given=premise, label="gap_2")

    assert isinstance(dependency, DependsOn)
    assert isinstance(scaffold, DependsOn)
    assert dependency.conclusion is conclusion
    assert dependency.given == (premise,)
    assert dependency not in conclusion.from_actions
    assert scaffold not in conclusion.from_actions
    assert relation.from_actions
    assert all(
        not isinstance(action, CandidateRelation | DependsOn) for action in conclusion.from_actions
    )


def test_attach_reasoning_is_idempotent() -> None:
    primary = claim("Primary.")
    helper = claim("Helper.")
    action = Equal(helper=helper)

    attach_reasoning(primary, action)
    attach_reasoning(primary, action)

    assert primary.from_actions == [action]


def test_validate_no_self_warrant_rejects_primary_claim() -> None:
    helper = claim("Helper.")
    action = Equal(helper=helper, warrants=[helper])

    with pytest.raises(ValueError, match="must not also be its warrant"):
        validate_no_self_warrant(action, helper)
