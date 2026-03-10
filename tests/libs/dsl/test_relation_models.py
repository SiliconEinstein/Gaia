from libs.dsl.models import RetractAction


def test_retract_action_model():
    r = RetractAction(
        name="retract_aristotle",
        target="heavier_falls_faster",
        reason="tied_balls_contradiction",
        prior=0.96,
    )
    assert r.type == "retract_action"
    assert r.target == "heavier_falls_faster"
    assert r.reason == "tied_balls_contradiction"
    assert r.prior == 0.96


def test_retract_action_in_declaration_map():
    from libs.dsl.models import DECLARATION_TYPE_MAP
    assert "retract_action" in DECLARATION_TYPE_MAP
    assert DECLARATION_TYPE_MAP["retract_action"] is RetractAction


from libs.dsl.loader import _parse_declaration
from libs.dsl.models import Contradiction, Equivalence


def test_parse_contradiction_from_yaml_dict():
    data = {
        "type": "contradiction",
        "name": "test_contra",
        "between": ["claim_a", "claim_b"],
        "prior": 0.95,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, Contradiction)
    assert decl.between == ["claim_a", "claim_b"]
    assert decl.prior == 0.95


def test_parse_equivalence_from_yaml_dict():
    data = {
        "type": "equivalence",
        "name": "test_equiv",
        "between": ["claim_x", "claim_y"],
        "prior": 0.90,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, Equivalence)
    assert decl.between == ["claim_x", "claim_y"]


def test_parse_retract_action_from_yaml_dict():
    data = {
        "type": "retract_action",
        "name": "retract_test",
        "target": "some_claim",
        "reason": "some_contradiction",
        "prior": 0.96,
    }
    decl = _parse_declaration(data)
    assert isinstance(decl, RetractAction)
    assert decl.target == "some_claim"
    assert decl.reason == "some_contradiction"
