from gaia.lang import contradict
from gaia.lang.runtime.action import Contradict
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.package import CollectedPackage


def test_contradict_returns_helper_claim():
    a = Claim("Classical prediction.")
    b = Claim("Observation.")
    helper = contradict(a, b, rationale="Classical theory fails.")
    assert isinstance(helper, Claim)
    assert helper.metadata.get("generated") is True
    assert helper.metadata.get("helper_kind") == "contradiction_result"
    assert helper.metadata.get("review") is True


def test_contradict_registers_action_and_warrant():
    with CollectedPackage("v6_test") as pkg:
        a = Claim("Classical prediction.")
        b = Claim("Observation.")
        helper = contradict(a, b, rationale="Classical theory fails.", label="conflict")
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Contradict)
    assert action.label == "conflict"
    assert action.a is a
    assert action.b is b
    assert action.helper is helper
    assert action.warrants == [helper]
