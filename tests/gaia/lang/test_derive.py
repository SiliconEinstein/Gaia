from gaia.lang import derive
from gaia.lang.runtime.action import Derive
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.package import CollectedPackage


def test_derive_returns_conclusion():
    a = Claim("Premise A.")
    b = Claim("Premise B.")
    c = Claim("Conclusion.")
    result = derive(c, given=(a, b), rationale="A and B imply C.")
    assert result is c


def test_derive_str_creates_claim():
    a = Claim("Premise.")
    c = derive("New conclusion.", given=a, rationale="Follows from A.")
    assert isinstance(c, Claim)
    assert c.content == "New conclusion."


def test_derive_attaches_to_supports():
    a = Claim("Premise.")
    c = Claim("Conclusion.")
    derive(c, given=a, rationale="Test.")
    assert len(c.supports) == 1
    assert isinstance(c.supports[0], Derive)


def test_derive_multiple_supports():
    a = Claim("A.")
    b = Claim("B.")
    c = Claim("C.")
    derive(c, given=a, rationale="From A.")
    derive(c, given=b, rationale="From B.")
    assert len(c.supports) == 2


def test_derive_single_given_not_tuple():
    a = Claim("Premise.")
    c = derive("Conclusion.", given=a, rationale="Test.")
    assert isinstance(c.supports[0].given, tuple)
    assert len(c.supports[0].given) == 1


def test_derive_with_label():
    a = Claim("Premise.")
    c = derive("Conclusion.", given=a, rationale="Test.", label="my_step")
    assert c.supports[0].label == "my_step"


def test_derive_with_background():
    a = Claim("Premise.")
    bg = Setting("Lab conditions.")
    c = derive("Conclusion.", given=a, background=[bg], rationale="Test.")
    assert c.supports[0].background == [bg]


def test_derive_registers_action_with_package():
    with CollectedPackage("v6_test") as pkg:
        a = Claim("Premise.")
        c = derive("Conclusion.", given=a, rationale="Test.")
    assert pkg.actions == [c.supports[0]]
