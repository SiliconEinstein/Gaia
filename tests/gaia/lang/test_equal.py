from gaia.engine.lang import derive, equal
from gaia.engine.lang.runtime.action import Equal
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.package import CollectedPackage


def test_equal_returns_helper_claim():
    a = Claim("Prediction matches.")
    b = Claim("Observation matches.")
    helper = equal(a, b, rationale="Theory agrees with data.")
    assert isinstance(helper, Claim)
    assert helper.metadata.get("generated") is True
    assert helper.metadata.get("helper_kind") == "equivalence_result"
    assert helper.metadata.get("review") is True


def test_equal_registers_action_and_helper_attachment():
    with CollectedPackage("v6_test") as pkg:
        a = Claim("Prediction matches.")
        b = Claim("Observation matches.")
        helper = equal(a, b, rationale="Theory agrees with data.", label="match")
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Equal)
    assert action.label == "match"
    assert action.a is a
    assert action.b is b
    assert action.helper is helper
    assert helper.from_actions == [action]
    assert action.warrants == []


def test_equal_records_background_information():
    with CollectedPackage("v6_test") as pkg:
        a = Claim("Prediction matches.")
        b = Claim("Observation matches.")
        bg = Claim("Same calibration frame.")
        equal(a, b, background=[bg], rationale="Theory agrees with data.")
    action = pkg.actions[0]
    assert action.background == [bg]


def test_equal_helper_usable_as_premise():
    a = Claim("Pred.")
    b = Claim("Obs.")
    helper = equal(a, b, rationale="Match.")
    c = derive("Theory valid.", given=helper, rationale="Matches imply valid.")
    assert c.from_actions[0].given == (helper,)
