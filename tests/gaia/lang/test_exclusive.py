from gaia.lang import exclusive
from gaia.lang.runtime.action import Exclusive
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.package import CollectedPackage


def test_exclusive_returns_reviewable_warrant_claim():
    a = Claim("Case A.")
    b = Claim("Case B.")
    helper = exclusive(a, b, rationale="The cases form a closed binary partition.")
    assert isinstance(helper, Claim)
    assert helper.metadata.get("generated") is True
    assert helper.metadata.get("helper_kind") == "complement_result"
    assert helper.metadata.get("review") is True


def test_exclusive_registers_action_and_warrant():
    with CollectedPackage("v6_test") as pkg:
        a = Claim("Case A.")
        b = Claim("Case B.")
        helper = exclusive(
            a,
            b,
            rationale="The cases form a closed binary partition.",
            label="binary_cases",
        )
    assert len(pkg.actions) == 1
    action = pkg.actions[0]
    assert isinstance(action, Exclusive)
    assert action.label == "binary_cases"
    assert action.a is a
    assert action.b is b
    assert action.helper is helper
    assert action.warrants == [helper]
