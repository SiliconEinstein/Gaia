import pytest

from gaia.lang import evidence
from gaia.lang.runtime.action import Evidence
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.package import CollectedPackage
from gaia.stats import Binomial


def test_evidence_returns_data_and_keeps_model_warrant_on_action():
    with CollectedPackage("evidence_test") as pkg:
        h = Claim("The coin has success probability 0.8.", prior=0.5)
        d = Claim("Eight successes were observed in ten trials.", prior=0.95)
        gate = Claim("Trials are independent.", prior=0.9)
        result = evidence(
            d,
            hypothesis=h,
            model=Binomial(n=10, p=0.8),
            observed=8,
            p_data_given_not_h=0.05,
            given=gate,
            rationale="Under H, the observed count is Binomial(n=10, p=0.8).",
            label="count_evidence",
        )

    action = pkg.actions[0]
    assert result is d
    assert isinstance(action, Evidence)
    assert action.data is d
    assert action.hypothesis is h
    assert action.given == (gate,)
    assert action.p_data_given_h == pytest.approx(0.301989888)
    assert action.p_data_given_not_h == 0.05
    assert action in d.supports
    assert action.helper is not None
    assert action.helper is not d
    assert action.warrants == [action.helper]
    assert action.helper.metadata["helper_kind"] == "evidence"
    assert action.helper.metadata["review"] is True
    assert action.helper.metadata["relation"]["type"] == "evidence"
    assert action.helper.metadata["relation"]["hypothesis"] is h
    assert action.helper.metadata["relation"]["data"] is d
    assert action.helper.metadata["relation"]["given"] == (gate,)
    assert action.helper.metadata["relation"]["model"]["kind"] == "binomial"
    assert action.helper.metadata["relation"]["observed"] == 8
    assert action.helper.metadata["relation"]["p_data_given_h"] == pytest.approx(0.301989888)
    assert action.helper.metadata["relation"]["p_data_given_not_h"] == 0.05


def test_evidence_defaults_not_h_to_neutral():
    with CollectedPackage("evidence_test") as pkg:
        h = Claim("H.")
        d = Claim("D.")
        result = evidence(d, hypothesis=h, model=Binomial(n=2, p=0.5), observed=1)

    action = pkg.actions[0]
    assert result is d
    assert action.p_data_given_h == 0.5
    assert action.p_data_given_not_h == 0.5
    assert action.helper.metadata["relation"]["p_data_given_not_h"] == 0.5


def test_evidence_requires_binomial_model_for_initial_release():
    h = Claim("H.")
    d = Claim("D.")
    with pytest.raises(TypeError, match="currently supports Binomial"):
        evidence(d, hypothesis=h, model={"kind": "normal"}, observed=1)
