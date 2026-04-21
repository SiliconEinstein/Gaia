import pytest

from gaia.lang import infer
from gaia.lang.runtime.action import Infer
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.package import CollectedPackage


def test_infer_returns_statistical_support():
    h = Claim("Quantum theory is correct.", prior=0.5)
    e = Claim("Planck spectrum observed.", prior=0.95)
    support = infer(
        hypothesis=h,
        evidence=e,
        p_e_given_h=0.9,
        p_e_given_not_h=0.05,
        rationale="Strong evidence.",
    )
    assert isinstance(support, Claim)
    assert support.metadata.get("generated") is True
    assert support.metadata.get("helper_kind") == "statistical_support"
    assert support.metadata.get("review") is True


def test_infer_all_keyword_only_for_v6_shape():
    h = Claim("H.")
    e = Claim("E.")
    with pytest.raises(TypeError):
        infer(h, e, 0.9, 0.1)


def test_infer_registers_action_and_warrant():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        bg = Setting("Experiment conditions.")
        helper = infer(
            hypothesis=h,
            evidence=e,
            background=[bg],
            p_e_given_h=0.8,
            p_e_given_not_h=0.2,
            rationale="Test.",
            label="bayes_update",
        )
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Infer)
    assert action.label == "bayes_update"
    assert action.hypothesis is h
    assert action.evidence is e
    assert action.background == [bg]
    assert action.p_e_given_h == 0.8
    assert action.p_e_given_not_h == 0.2
    assert action.helper is helper
    assert action.warrants == [helper]


def test_infer_preserves_v5_positional_shape():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")
    strategy = infer([a, b], c, reason="custom CPT")
    assert strategy.type == "infer"
    assert strategy.premises == [a, b]
    assert strategy.conclusion is c
