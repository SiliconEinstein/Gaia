import pytest

from gaia.lang import (
    Step,
    abduction,
    analogy,
    case_analysis,
    claim,
    composite,
    deduction,
    elimination,
    extrapolation,
    fills,
    induction,
    mathematical_induction,
    noisy_and,
    setting,
)
from gaia.lang.runtime.package import CollectedPackage


def test_noisy_and_explicit():
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    s = noisy_and(premises=[a, b], conclusion=c, reason=["Step 1", "Step 2"])
    assert s.type == "noisy_and"
    assert s.conclusion is c
    assert len(s.premises) == 2
    assert isinstance(s.reason, list)
    assert len(s.reason) == 2


def test_noisy_and_structured_steps():
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    s = noisy_and(
        premises=[a, b],
        conclusion=c,
        reason=[
            Step(reason="A and B jointly support C.", premises=[a, b]),
        ],
    )
    assert isinstance(s.reason[0], Step)
    assert s.reason[0].reason == "A and B jointly support C."
    assert s.reason[0].premises == [a, b]


def test_noisy_and_simple_reason():
    a = claim("A.")
    c = claim("C.")
    s = noisy_and(premises=[a], conclusion=c, reason="Because A implies C.")
    assert s.reason == "Because A implies C."


def test_step_premise_validation():
    a = claim("A.")
    b = claim("B.")
    c = claim("C.")
    outside = claim("Not a premise.")
    with pytest.raises(ValueError, match="not in the strategy's premise list"):
        noisy_and(
            premises=[a, b],
            conclusion=c,
            reason=[Step(reason="Bad step", premises=[outside])],
        )


def test_deduction():
    law = claim("forall x. P(x)", parameters=[{"name": "x", "type": "material"}])
    premise = claim("YBCO is in scope.")
    binding = setting("x = YBCO")
    instance = claim("P(YBCO)")
    s = deduction(
        premises=[law, premise],
        conclusion=instance,
        background=[binding],
        reason=[Step(reason="Instantiate the universal law.", premises=[law, premise])],
    )
    assert s.type == "deduction"
    assert s.formal_expr is None
    assert s.background == [binding]
    assert s.reason[0].reason == "Instantiate the universal law."


def test_deduction_single_premise():
    law = claim("forall x. P(x)")
    instance = claim("P(a)")
    s = deduction(premises=[law], conclusion=instance)
    assert s.type == "deduction"
    assert len(s.premises) == 1


def test_abduction():
    obs = claim("Observation.")
    hyp = claim("Hypothesis.")
    alt = claim("Alternative.")
    s = abduction(observation=obs, hypothesis=hyp, alternative=alt)
    assert s.type == "abduction"
    assert s.conclusion is hyp
    assert obs in s.premises
    assert alt in s.premises
    assert s.formal_expr is None


def test_abduction_auto_creates_alternative():
    obs = claim("Observation.")
    hyp = claim("Hypothesis.")
    s = abduction(observation=obs, hypothesis=hyp)
    assert s.type == "abduction"
    assert s.premises == [obs]


def test_analogy():
    source = claim("Source law.")
    target = claim("Target prediction.")
    bridge = claim("Bridge claim.")
    s = analogy(source=source, target=target, bridge=bridge)
    assert s.type == "analogy"
    assert s.formal_expr is None
    assert bridge in s.premises


def test_extrapolation():
    source = claim("Known behavior.")
    target = claim("Predicted behavior.")
    cont = claim("Continuity assumption.")
    s = extrapolation(source=source, target=target, continuity=cont)
    assert s.type == "extrapolation"
    assert s.formal_expr is None


def test_fills_exact_defaults_to_deduction():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    s = fills(source=source, target=target, reason="Source proves target.")
    assert s.type == "deduction"
    assert s.premises == [source]
    assert s.conclusion is target
    assert s.metadata["gaia"]["relation"] == {
        "type": "fills",
        "strength": "exact",
        "mode": "deduction",
    }


def test_fills_partial_defaults_to_infer():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    s = fills(source=source, target=target, strength="partial")
    assert s.type == "infer"
    assert s.metadata["gaia"]["relation"]["strength"] == "partial"
    assert s.metadata["gaia"]["relation"]["mode"] == "infer"


def test_fills_conditional_defaults_to_infer():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    s = fills(source=source, target=target, strength="conditional")
    assert s.type == "infer"
    assert s.metadata["gaia"]["relation"]["strength"] == "conditional"
    assert s.metadata["gaia"]["relation"]["mode"] == "infer"


def test_fills_explicit_mode_overrides_strength_default():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    s = fills(source=source, target=target, strength="partial", mode="deduction")
    assert s.type == "deduction"
    assert s.metadata["gaia"]["relation"] == {
        "type": "fills",
        "strength": "partial",
        "mode": "deduction",
    }


def test_fills_rejects_non_claim_source():
    source = setting("Background.")
    target = claim("Target premise.")
    with pytest.raises(ValueError, match="source.type == 'claim'"):
        fills(source=source, target=target)


def test_fills_rejects_non_claim_target():
    source = claim("Source theorem.")
    target = setting("Background.")
    with pytest.raises(ValueError, match="target.type == 'claim'"):
        fills(source=source, target=target)


def test_fills_rejects_invalid_mode():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    with pytest.raises(ValueError, match="mode must be one of"):
        fills(source=source, target=target, mode="maybe")  # type: ignore[arg-type]


def test_fills_rejects_invalid_strength():
    source = claim("Source theorem.")
    target = claim("Target premise.")
    with pytest.raises(ValueError, match="strength must be one of"):
        fills(source=source, target=target, strength="weak")  # type: ignore[arg-type]


def test_fills_does_not_mutate_foreign_target_strategy():
    foreign_pkg = CollectedPackage("foreign_pkg", namespace="github", version="1.0.0")
    with foreign_pkg:
        foreign_target = claim("Foreign target.")
        foreign_target.label = "foreign_target"

    local_pkg = CollectedPackage("local_pkg", namespace="github", version="1.0.0")
    with local_pkg:
        local_source = claim("Local theorem.")
        local_source.label = "local_source"
        bridge = fills(source=local_source, target=foreign_target)

    assert bridge.conclusion is foreign_target
    assert foreign_target.strategy is None


def test_elimination():
    exhaustive = claim("The listed candidates are exhaustive.")
    h1 = claim("Candidate 1.")
    e1 = claim("Evidence against candidate 1.")
    h2 = claim("Candidate 2.")
    e2 = claim("Evidence against candidate 2.")
    survivor = claim("Surviving candidate.")
    s = elimination(
        exhaustiveness=exhaustive,
        excluded=[(h1, e1), (h2, e2)],
        survivor=survivor,
    )
    assert s.type == "elimination"
    assert s.premises == [exhaustive, h1, e1, h2, e2]
    assert s.conclusion is survivor
    assert s.formal_expr is None


def test_case_analysis():
    exhaustive = claim("The listed cases are exhaustive.")
    c1 = claim("Case 1 holds.")
    p1 = claim("Case 1 implies the result.")
    c2 = claim("Case 2 holds.")
    p2 = claim("Case 2 implies the result.")
    conclusion = claim("The result holds.")
    s = case_analysis(
        exhaustiveness=exhaustive,
        cases=[(c1, p1), (c2, p2)],
        conclusion=conclusion,
    )
    assert s.type == "case_analysis"
    assert s.premises == [exhaustive, c1, p1, c2, p2]
    assert s.conclusion is conclusion
    assert s.formal_expr is None


def test_mathematical_induction():
    base = claim("P(0) holds.")
    step = claim("P(n) implies P(n+1).")
    conclusion = claim("P(n) holds for all n.")
    s = mathematical_induction(base=base, step=step, conclusion=conclusion)
    assert s.type == "mathematical_induction"
    assert s.premises == [base, step]
    assert s.conclusion is conclusion
    assert s.formal_expr is None


def test_composite():
    evidence = claim("Evidence.")
    intermediate = claim("Intermediate.")
    conclusion = claim("Conclusion.")
    s1 = noisy_and(premises=[evidence], conclusion=intermediate)
    s2 = noisy_and(premises=[intermediate], conclusion=conclusion)
    composite_strategy = composite(
        premises=[evidence],
        conclusion=conclusion,
        sub_strategies=[s1, s2],
        reason="Two-step argument.",
    )
    assert composite_strategy.type == "infer"
    assert composite_strategy.premises == [evidence]
    assert composite_strategy.conclusion is conclusion
    assert composite_strategy.sub_strategies == [s1, s2]


def test_composite_requires_sub_strategies():
    evidence = claim("Evidence.")
    conclusion = claim("Conclusion.")
    with pytest.raises(ValueError, match="at least one sub-strategy"):
        composite(premises=[evidence], conclusion=conclusion, sub_strategies=[])


def test_induction_top_down_basic():
    """Top-down: pass Knowledge list, auto-generate AltExps."""
    law = claim("All metals expand when heated.")
    obs1 = claim("Iron expands when heated.")
    obs2 = claim("Copper expands when heated.")
    obs3 = claim("Silver expands when heated.")

    s = induction([obs1, obs2, obs3], law)
    assert s.type == "induction"
    assert s.conclusion is law
    assert len(s.sub_strategies) == 3
    for sub in s.sub_strategies:
        assert sub.type == "abduction"
        assert sub.conclusion is law
    assert law.strategy is s


def test_induction_top_down_with_alt_exps():
    """Top-down: explicit AltExps provided."""
    law = claim("Drug X cures disease Y.")
    obs1 = claim("Patient 1 recovered.")
    obs2 = claim("Patient 2 recovered.")
    alt1 = claim("Patient 1 recovered spontaneously.")
    alt2 = claim("Patient 2 recovered spontaneously.")

    s = induction([obs1, obs2], law, alt_exps=[alt1, alt2])
    assert s.type == "induction"
    assert len(s.sub_strategies) == 2
    assert alt1 in s.sub_strategies[0].premises
    assert alt2 in s.sub_strategies[1].premises


def test_induction_top_down_mixed_alt_exps():
    """Top-down: some AltExps explicit, some None (auto-generated)."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")

    s = induction([obs1, obs2], law, alt_exps=[alt1, None])
    assert alt1 in s.sub_strategies[0].premises
    assert len(s.sub_strategies[1].premises) == 1


def test_induction_top_down_reason_stays_on_composite():
    """Induction-level reason text should not be copied to each sub-abduction."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    reason = [Step(reason="Combine both observations.", premises=[obs1, obs2])]

    s = induction([obs1, obs2], law, reason=reason)

    assert s.reason == reason
    assert all(sub.reason == "" for sub in s.sub_strategies)


def test_induction_bottom_up():
    """Bottom-up: bundle existing abductions."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")
    alt2 = claim("Alt 2.")

    abd1 = abduction(obs1, law, alt1)
    abd2 = abduction(obs2, law, alt2)
    assert law.strategy is abd2

    s = induction([abd1, abd2])
    assert s.type == "induction"
    assert s.conclusion is law
    assert len(s.sub_strategies) == 2
    assert s.sub_strategies[0] is abd1
    assert s.sub_strategies[1] is abd2
    assert law.strategy is s


def test_induction_bottom_up_with_law():
    """Bottom-up: law explicitly provided, validated for consistency."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")

    abd1 = abduction(obs1, law)
    abd2 = abduction(obs2, law)

    s = induction([abd1, abd2], law)
    assert s.conclusion is law


def test_induction_too_few_observations():
    """Top-down with fewer than 2 observations."""
    law = claim("Law.")
    obs = claim("Single obs.")
    with pytest.raises(ValueError, match="at least 2"):
        induction([obs], law)


def test_induction_alt_exps_length_mismatch():
    """alt_exps length doesn't match observations."""
    law = claim("Law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    alt1 = claim("Alt 1.")
    with pytest.raises(ValueError, match="alt_exps length"):
        induction([obs1, obs2], law, alt_exps=[alt1])


def test_induction_bottom_up_different_conclusions():
    """Bottom-up: sub-strategies with different conclusions."""
    law1 = claim("Law 1.")
    law2 = claim("Law 2.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    abd1 = abduction(obs1, law1)
    abd2 = abduction(obs2, law2)
    with pytest.raises(ValueError, match="same conclusion"):
        induction([abd1, abd2])


def test_induction_bottom_up_non_abduction():
    """Bottom-up: sub-strategy is not abduction."""
    law = claim("Law.")
    a = claim("A.")
    b = claim("B.")
    s1 = noisy_and(premises=[a], conclusion=law)
    s2 = noisy_and(premises=[b], conclusion=law)
    with pytest.raises(ValueError, match="must be abduction"):
        induction([s1, s2])


def test_induction_rejects_mixed_item_types():
    """Mixed Knowledge/Strategy input should fail at the DSL boundary."""
    law = claim("Law.")
    obs = claim("Obs.")
    abd = abduction(claim("Other obs."), law)
    with pytest.raises(TypeError, match="must all be Knowledge"):
        induction([obs, abd], law)


def test_induction_bottom_up_law_mismatch():
    """Bottom-up: explicit law doesn't match sub-strategies."""
    law = claim("Law.")
    other_law = claim("Other law.")
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    abd1 = abduction(obs1, law)
    abd2 = abduction(obs2, law)
    with pytest.raises(ValueError, match="does not match"):
        induction([abd1, abd2], other_law)


def test_induction_empty_list():
    """Empty items list."""
    with pytest.raises(ValueError, match="non-empty"):
        induction([])


def test_induction_top_down_no_law():
    """Top-down mode without law raises ValueError."""
    obs1 = claim("Obs 1.")
    obs2 = claim("Obs 2.")
    with pytest.raises(ValueError, match="requires law"):
        induction([obs1, obs2])


def test_induction_bottom_up_single():
    """Bottom-up with fewer than 2 strategies."""
    law = claim("Law.")
    obs = claim("Obs.")
    abd = abduction(obs, law)
    with pytest.raises(ValueError, match="at least 2"):
        induction([abd])
