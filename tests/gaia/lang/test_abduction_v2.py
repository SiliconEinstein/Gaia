"""Tests for abduction() as a binary CompositeStrategy (IBE)."""

import pytest

from gaia.lang import Knowledge, Strategy, claim, support
from gaia.lang.dsl.strategies import abduction


def _make_support_pair():
    """Helper: create two support strategies sharing an observation."""
    theory_h = claim("Theory H explains the observation.")
    pred_h = claim("Prediction from H.")
    theory_alt = claim("Alternative theory.")
    pred_alt = claim("Prediction from Alt.")
    obs = claim("Observation.")

    sup_h = support(premises=[theory_h], conclusion=pred_h, reason="H predicts this.")
    sup_alt = support(premises=[theory_alt], conclusion=pred_alt, reason="Alt predicts this.")
    return sup_h, sup_alt, obs


def test_abduction_binary_composite():
    """abduction takes 2 supports + observation, returns CompositeStrategy."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs)

    assert isinstance(s, Strategy)
    assert s.type == "abduction"
    assert len(s.sub_strategies) == 3  # support_h, support_alt, compare
    assert s.sub_strategies[0] is sup_h
    assert s.sub_strategies[1] is sup_alt
    assert s.sub_strategies[2].type == "compare"


def test_abduction_conclusion_is_comparison_claim():
    """conclusion has helper_kind='comparison_result'."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs)

    assert s.conclusion is not None
    assert s.conclusion.type == "claim"
    assert s.conclusion.metadata.get("helper_kind") == "comparison_result"
    assert s.conclusion.metadata.get("generated") is True


def test_abduction_composition_warrant():
    """composition_warrant exists and has correct metadata."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs, reason="Both predict same obs.")

    assert s.composition_warrant is not None
    assert isinstance(s.composition_warrant, Knowledge)
    assert s.composition_warrant.type == "claim"
    assert s.composition_warrant.metadata["helper_kind"] == "composition_validity"
    assert s.composition_warrant.metadata["warrant"] == "Both predict same obs."


def test_abduction_composition_warrant_no_reason():
    """composition_warrant without reason has no 'warrant' key."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs)

    assert s.composition_warrant is not None
    assert "warrant" not in s.composition_warrant.metadata


def test_abduction_first_arg_is_claimed_better():
    """First support argument's prediction is first in comparison content."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs)

    # The compare sub-strategy's first premise should be sup_h.conclusion
    compare_sub = s.sub_strategies[2]
    assert compare_sub.premises[0] is sup_h.conclusion
    assert compare_sub.premises[1] is sup_alt.conclusion


def test_abduction_requires_strategy_inputs():
    """Raises TypeError for non-Strategy inputs."""
    obs = claim("Observation.")
    k = claim("Not a strategy.")

    sup = support(premises=[claim("Theory.")], conclusion=claim("Pred."))

    with pytest.raises(TypeError, match="support_h must be a Strategy"):
        abduction(k, sup, obs)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="support_alt must be a Strategy"):
        abduction(sup, k, obs)  # type: ignore[arg-type]


def test_abduction_premises_are_deduplicated():
    """Premises from all sub-strategies are merged without duplicates."""
    theory = claim("Theory.")
    pred_h = claim("Prediction H.")
    pred_alt = claim("Prediction Alt.")
    obs = claim("Observation.")

    sup_h = support(premises=[theory], conclusion=pred_h)
    # Use the same theory as premise for alt (shared premise)
    sup_alt = support(premises=[theory], conclusion=pred_alt)

    s = abduction(sup_h, sup_alt, obs)

    # theory should appear only once in premises
    theory_count = sum(1 for p in s.premises if p is theory)
    assert theory_count == 1


def test_abduction_strategy_attached_to_conclusion():
    """The abduction strategy is attached to the comparison claim's .strategy."""
    sup_h, sup_alt, obs = _make_support_pair()
    s = abduction(sup_h, sup_alt, obs)

    assert s.conclusion.strategy is s


def test_abduction_with_background():
    """Background is passed through."""
    sup_h, sup_alt, obs = _make_support_pair()
    bg = claim("Background context.")
    s = abduction(sup_h, sup_alt, obs, background=[bg])

    assert s.background == [bg]
