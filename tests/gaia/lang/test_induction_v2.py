"""Tests for induction() as a binary CompositeStrategy."""

import pytest

from gaia.lang import Knowledge, Strategy, claim, support
from gaia.lang.dsl.strategies import induction


def test_induction_binary_composite():
    """induction takes 2 supports + law."""
    obs1 = claim("Iron expands when heated.")
    obs2 = claim("Copper expands when heated.")
    law = claim("All metals expand when heated.")

    sup1 = support(premises=[law], conclusion=obs1, reason="Law predicts iron.", prior=0.9)
    sup2 = support(premises=[law], conclusion=obs2, reason="Law predicts copper.", prior=0.9)

    s = induction(sup1, sup2, law)

    assert isinstance(s, Strategy)
    assert s.type == "induction"
    assert len(s.sub_strategies) == 2
    assert s.sub_strategies[0] is sup1
    assert s.sub_strategies[1] is sup2


def test_induction_conclusion_is_law():
    """conclusion is the law Knowledge."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)

    s = induction(sup1, sup2, law)

    assert s.conclusion is law


def test_induction_chaining():
    """induction(prev_induction, new_support, law) works."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    obs3 = claim("Obs 3.")
    law = claim("Law.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)
    sup3 = support(premises=[law], conclusion=obs3)

    # First induction
    ind1 = induction(sup1, sup2, law)
    assert ind1.type == "induction"

    # Chain: previous induction + new support
    ind2 = induction(ind1, sup3, law)
    assert ind2.type == "induction"
    assert ind2.conclusion is law
    assert ind2.sub_strategies[0] is ind1
    assert ind2.sub_strategies[1] is sup3


def test_induction_composition_warrant():
    """composition_warrant exists."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)

    s = induction(sup1, sup2, law, reason="Independent observations.")

    assert s.composition_warrant is not None
    assert isinstance(s.composition_warrant, Knowledge)
    assert s.composition_warrant.type == "claim"
    assert s.composition_warrant.metadata["helper_kind"] == "composition_validity"
    assert s.composition_warrant.metadata["warrant"] == "Independent observations."


def test_induction_composition_warrant_no_reason():
    """composition_warrant without reason has no 'warrant' key."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)

    s = induction(sup1, sup2, law)

    assert s.composition_warrant is not None
    assert "warrant" not in s.composition_warrant.metadata


def test_induction_requires_strategy_inputs():
    """Raises TypeError for non-Strategy inputs."""
    law = claim("Law.")
    k = claim("Not a strategy.")
    sup = support(premises=[law], conclusion=claim("Obs."))

    with pytest.raises(TypeError, match="support_1 must be a Strategy"):
        induction(k, sup, law)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="support_2 must be a Strategy"):
        induction(sup, k, law)  # type: ignore[arg-type]


def test_induction_requires_support_or_previous_induction_for_first_input():
    """The first input cannot be an unrelated strategy type."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")
    unrelated = Strategy(type="compare", premises=[obs1], conclusion=law)
    sup = support(premises=[law], conclusion=obs2)

    with pytest.raises(TypeError, match="support_1 must be a support strategy"):
        induction(unrelated, sup, law)


def test_induction_requires_support_for_second_input():
    """Chained induction only accepts a new support as the second input."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    obs3 = claim("Obs 3.")
    law = claim("Law.")
    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)
    previous = induction(sup1, sup2, law)
    not_support = Strategy(type="compare", premises=[law], conclusion=obs3)

    with pytest.raises(TypeError, match="support_2 must be a support strategy"):
        induction(previous, not_support, law)


def test_induction_requires_sub_strategies_to_include_law():
    """Reject supports that don't reference the law as premise or conclusion."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")
    missing_law = support(premises=[obs1], conclusion=obs2)
    valid_support = support(premises=[law], conclusion=obs2)

    with pytest.raises(ValueError, match="support_1 must reference the law"):
        induction(missing_law, valid_support, law)

    with pytest.raises(ValueError, match="support_2 must reference the law"):
        induction(valid_support, missing_law, law)


def test_induction_premises_are_deduplicated():
    """Premises from both sub-strategies are merged without duplicates."""
    shared_obs = claim("Shared observation.")
    law = claim("Law.")

    sup1 = support(premises=[law, shared_obs], conclusion=claim("Obs 1."))
    sup2 = support(premises=[law, shared_obs], conclusion=claim("Obs 2."))

    s = induction(sup1, sup2, law)

    # shared_obs should appear only once
    obs_count = sum(1 for p in s.premises if p is shared_obs)
    assert obs_count == 1


def test_induction_strategy_attached_to_law():
    """The induction strategy is attached to law.strategy."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)

    s = induction(sup1, sup2, law)

    assert law.strategy is s


def test_induction_with_background():
    """Background is passed through."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    law = claim("Law.")
    bg = claim("Background context.")

    sup1 = support(premises=[law], conclusion=obs1)
    sup2 = support(premises=[law], conclusion=obs2)

    s = induction(sup1, sup2, law, background=[bg])

    assert s.background == [bg]
