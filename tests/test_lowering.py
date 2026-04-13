"""Tests for gaia.bp.lowering."""

from __future__ import annotations

import pytest

from gaia.bp import FactorType, lower_local_graph, lower_operator
from gaia.bp.factor_graph import FactorGraph
from gaia.bp.exact import exact_inference
from gaia.bp.lowering import fold_composite_to_cpt
from gaia.ir import Knowledge, Operator, Strategy, CompositeStrategy, LocalCanonicalGraph

NS, PKG = "github", "lowertest"


def _lg(**kwargs) -> LocalCanonicalGraph:
    kwargs.setdefault("namespace", NS)
    kwargs.setdefault("package_name", PKG)
    return LocalCanonicalGraph(**kwargs)


def test_lower_operator_helper():
    fg = FactorGraph()
    fg.add_variable("a", 0.5)
    fg.add_variable("b", 0.5)
    fg.add_variable("h", 0.5)
    op = Operator(operator="implication", variables=["a", "b"], conclusion="h")
    lower_operator(fg, op, "f1")
    assert len(fg.factors) == 1
    assert fg.factors[0].factor_type == FactorType.IMPLICATION


def test_equivalence_operator_round_trip():
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
            Knowledge(id="github:lowertest::h", type="claim", content="H"),
        ],
        operators=[
            Operator(
                operator="equivalence",
                variables=["github:lowertest::a", "github:lowertest::b"],
                conclusion="github:lowertest::h",
            ),
        ],
    )
    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::a": 0.7,
            "github:lowertest::b": 0.4,
            "github:lowertest::h": 0.95,
        },
    )
    assert not fg.validate()
    beliefs, _ = exact_inference(fg)
    assert all(0 < beliefs[v] < 1 for v in beliefs)


def test_contradiction_default_prior_near_one():
    """Relation-type operator conclusion defaults to ~1.0 (constraint active)."""
    from gaia.bp.factor_graph import CROMWELL_EPS

    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::x", type="claim", content="X"),
            Knowledge(id="github:lowertest::y", type="claim", content="Y"),
            Knowledge(id="github:lowertest::r", type="claim", content="R"),
        ],
        operators=[
            Operator(
                operator="contradiction",
                variables=["github:lowertest::x", "github:lowertest::y"],
                conclusion="github:lowertest::r",
            ),
        ],
    )
    fg = lower_local_graph(g)
    assert fg.variables["github:lowertest::r"] == pytest.approx(1.0 - CROMWELL_EPS)


def test_contradiction_actually_constrains():
    """With prior ~1.0 on helper, CONTRADICTION suppresses joint X=Y=1."""
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::x", type="claim", content="X"),
            Knowledge(id="github:lowertest::y", type="claim", content="Y"),
            Knowledge(id="github:lowertest::r", type="claim", content="R"),
        ],
        operators=[
            Operator(
                operator="contradiction",
                variables=["github:lowertest::x", "github:lowertest::y"],
                conclusion="github:lowertest::r",
            ),
        ],
    )
    fg = lower_local_graph(
        g,
        node_priors={"github:lowertest::x": 0.8, "github:lowertest::y": 0.8},
    )
    beliefs, _ = exact_inference(fg)
    assert beliefs["github:lowertest::x"] < 0.8 or beliefs["github:lowertest::y"] < 0.8


def test_noisy_and_strategy_lowering():
    s = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::p1", "github:lowertest::p2"],
        conclusion="github:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p1", type="claim", content="P1"),
            Knowledge(id="github:lowertest::p2", type="claim", content="P2"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(
        g,
        strategy_conditional_params={s.strategy_id: [0.85]},
    )
    fts = [f.factor_type for f in fg.factors]
    assert FactorType.CONJUNCTION in fts
    assert FactorType.SOFT_ENTAILMENT in fts


def test_infer_conditional_lowering():
    s = Strategy(
        scope="local",
        type="infer",
        premises=["github:lowertest::x"],
        conclusion="github:lowertest::y",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::x", type="claim", content="X"),
            Knowledge(id="github:lowertest::y", type="claim", content="Y"),
        ],
        strategies=[s],
    )
    cpt = [0.3, 0.9]
    fg = lower_local_graph(g, strategy_conditional_params={s.strategy_id: cpt})
    cond = [f for f in fg.factors if f.factor_type == FactorType.CONDITIONAL]
    assert len(cond) == 1
    assert cond[0].cpt == tuple(cpt)


def test_formal_strategy_expand_implication():
    from gaia.ir.strategy import FormalExpr, FormalStrategy

    fs = FormalStrategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::p"],
        conclusion="github:lowertest::c",
        formal_expr=FormalExpr(
            operators=[
                Operator(
                    operator="implication",
                    variables=["github:lowertest::p", "github:lowertest::c"],
                    conclusion="github:lowertest::h",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="P"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
            Knowledge(id="github:lowertest::h", type="claim", content="H"),
        ],
        strategies=[fs],
    )
    fg = lower_local_graph(g, expand_formal=True)
    assert any(f.factor_type == FactorType.IMPLICATION for f in fg.factors)


def test_formal_fold_not_implemented():
    from gaia.ir.strategy import FormalExpr, FormalStrategy

    fs = FormalStrategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::p"],
        conclusion="github:lowertest::c",
        formal_expr=FormalExpr(
            operators=[
                Operator(
                    operator="implication",
                    variables=["github:lowertest::p", "github:lowertest::c"],
                    conclusion="github:lowertest::h",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="P"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
            Knowledge(id="github:lowertest::h", type="claim", content="H"),
        ],
        strategies=[fs],
    )
    with pytest.raises(NotImplementedError):
        lower_local_graph(g, expand_formal=False)


# ---------------------------------------------------------------------------
# Named leaf strategy auto-formalization (07-lowering.md §4.1 / §4.3)
# ---------------------------------------------------------------------------


def test_deduction_leaf_strategy_auto_formalizes():
    """Plain Strategy(type=deduction) is auto-formalized to CONJUNCTION + IMPLICATION."""
    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::a", "github:lowertest::b"],
        conclusion="github:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    assert not fg.validate()
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.CONJUNCTION in ftypes
    assert FactorType.IMPLICATION in ftypes


def test_analogy_leaf_strategy_auto_formalizes():
    """Plain Strategy(type=analogy) produces CONJUNCTION + IMPLICATION factors."""
    s = Strategy(
        scope="local",
        type="analogy",
        premises=["github:lowertest::src", "github:lowertest::bridge"],
        conclusion="github:lowertest::tgt",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::src", type="claim", content="SourceLaw"),
            Knowledge(id="github:lowertest::bridge", type="claim", content="BridgeClaim"),
            Knowledge(id="github:lowertest::tgt", type="claim", content="Target"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    assert not fg.validate()
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.CONJUNCTION in ftypes
    assert FactorType.IMPLICATION in ftypes


def test_extrapolation_leaf_strategy_auto_formalizes():
    """Plain Strategy(type=extrapolation) produces CONJUNCTION + IMPLICATION factors."""
    s = Strategy(
        scope="local",
        type="extrapolation",
        premises=["github:lowertest::law", "github:lowertest::cont"],
        conclusion="github:lowertest::ext",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::law", type="claim", content="KnownLaw"),
            Knowledge(id="github:lowertest::cont", type="claim", content="ContinuityClaim"),
            Knowledge(id="github:lowertest::ext", type="claim", content="Extended"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    assert not fg.validate()
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.CONJUNCTION in ftypes
    assert FactorType.IMPLICATION in ftypes


def test_abduction_leaf_strategy_generates_interface_claim():
    """Plain Strategy(type=abduction) generates AlternativeExplanationForObs interface claim."""
    s = Strategy(
        scope="local",
        type="abduction",
        premises=["github:lowertest::obs"],
        conclusion="github:lowertest::hyp",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::obs", type="claim", content="Obs"),
            Knowledge(id="github:lowertest::hyp", type="claim", content="Hypothesis"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    assert not fg.validate()
    ftypes = {f.factor_type for f in fg.factors}
    # abduction skeleton: disjunction(H, Alt -> ExplainUnion) + equivalence(ExplainUnion, Obs -> EqH)
    assert FactorType.DISJUNCTION in ftypes
    assert FactorType.EQUIVALENCE in ftypes
    # The auto-generated AlternativeExplanationForObs must appear as a variable
    alt_vars = [v for v in fg.variables if "alternative_explanation" in v]
    assert len(alt_vars) == 1


def test_mathematical_induction_leaf_strategy_auto_formalizes():
    """Plain Strategy(type=mathematical_induction) produces CONJUNCTION + IMPLICATION."""
    s = Strategy(
        scope="local",
        type="mathematical_induction",
        premises=["github:lowertest::base", "github:lowertest::step"],
        conclusion="github:lowertest::law",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::base", type="claim", content="Base"),
            Knowledge(id="github:lowertest::step", type="claim", content="Step"),
            Knowledge(id="github:lowertest::law", type="claim", content="Law"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    assert not fg.validate()
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.CONJUNCTION in ftypes
    assert FactorType.IMPLICATION in ftypes


def test_deferred_leaf_strategy_raises():
    """Deferred leaf strategy types (reductio) raise NotImplementedError."""
    s = Strategy(
        scope="local",
        type="reductio",
        premises=["github:lowertest::p"],
        conclusion="github:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="P"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
        ],
        strategies=[s],
    )
    with pytest.raises(NotImplementedError, match="deferred"):
        lower_local_graph(g)


def test_named_leaf_node_priors_respected():
    """User-supplied node_priors for auto-generated claims are applied via _ensure_claim_var."""
    s = Strategy(
        scope="local",
        type="abduction",
        premises=["github:lowertest::obs2"],
        conclusion="github:lowertest::hyp2",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::obs2", type="claim", content="Obs2"),
            Knowledge(id="github:lowertest::hyp2", type="claim", content="Hyp2"),
        ],
        strategies=[s],
    )
    # First pass: discover the auto-generated alt-explanation variable ID
    fg0 = lower_local_graph(g)
    alt_id = [v for v in fg0.variables if "alternative_explanation" in v][0]

    # Second pass: supply a custom prior for the auto-generated claim
    fg1 = lower_local_graph(g, node_priors={alt_id: 0.1})
    assert fg1.variables[alt_id] == pytest.approx(0.1)


def test_composite_strategy_expands_sub_strategies():
    """CompositeStrategy default lowering recursively expands sub-strategies."""
    sub1 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::m",
    )
    sub2 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::m"],
        conclusion="github:lowertest::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::c",
        sub_strategies=[sub1.strategy_id, sub2.strategy_id],
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::m", type="claim", content="M"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
        ],
        strategies=[sub1, sub2, comp],
    )
    fg = lower_local_graph(
        g,
        strategy_conditional_params={
            sub1.strategy_id: [0.9],
            sub2.strategy_id: [0.8],
        },
    )
    # Default: sub-strategies are expanded (sub1/sub2 lowered as top-level AND
    # again via the composite), producing SOFT_ENTAILMENT factors.
    se_factors = [f for f in fg.factors if f.factor_type == FactorType.SOFT_ENTAILMENT]
    assert len(se_factors) >= 2
    # Intermediate variable M is visible in the factor graph
    assert "github:lowertest::m" in fg.variables
    # No CONDITIONAL factor — composite does not fold by default
    cond_factors = [f for f in fg.factors if f.factor_type == FactorType.CONDITIONAL]
    assert len(cond_factors) == 0


def test_formal_expr_relation_conclusion_gets_assertion_prior():
    """FormalExpr internal relation operator conclusions must get π=1-ε (assertion),
    not the default 0.5.  Bug: lowering.py FormalExpr expand path uses
    _ensure_claim_var for all conclusions, which defaults to 0.5."""
    from gaia.bp.factor_graph import CROMWELL_EPS
    from gaia.ir.strategy import FormalExpr, FormalStrategy

    # Build a FormalStrategy that contains an equivalence operator internally
    # (mimics elimination's equivalence([D, Exh]) → Eq)
    fs = FormalStrategy(
        scope="local",
        type="elimination",
        premises=[
            "github:lowertest::exh",
            "github:lowertest::c1",
            "github:lowertest::e1",
        ],
        conclusion="github:lowertest::s",
        formal_expr=FormalExpr(
            operators=[
                Operator(
                    operator="disjunction",
                    variables=[
                        "github:lowertest::c1",
                        "github:lowertest::s",
                    ],
                    conclusion="github:lowertest::_d",
                ),
                Operator(
                    operator="equivalence",
                    variables=[
                        "github:lowertest::_d",
                        "github:lowertest::exh",
                    ],
                    conclusion="github:lowertest::_eq",
                ),
                Operator(
                    operator="contradiction",
                    variables=[
                        "github:lowertest::c1",
                        "github:lowertest::e1",
                    ],
                    conclusion="github:lowertest::_contra",
                ),
                Operator(
                    operator="conjunction",
                    variables=[
                        "github:lowertest::exh",
                        "github:lowertest::e1",
                    ],
                    conclusion="github:lowertest::_g",
                ),
                Operator(
                    operator="implication",
                    variables=["github:lowertest::_g", "github:lowertest::s"],
                    conclusion="github:lowertest::_impl",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::exh", type="claim", content="Exh"),
            Knowledge(id="github:lowertest::c1", type="claim", content="C1"),
            Knowledge(id="github:lowertest::e1", type="claim", content="E1"),
            Knowledge(id="github:lowertest::s", type="claim", content="S"),
        ],
        strategies=[fs],
    )
    fg = lower_local_graph(g, expand_formal=True)

    # Relation operator conclusions (_eq, _contra, _impl) must have assertion prior 1-ε
    assert fg.variables["github:lowertest::_eq"] == pytest.approx(1.0 - CROMWELL_EPS)
    assert fg.variables["github:lowertest::_contra"] == pytest.approx(1.0 - CROMWELL_EPS)
    assert fg.variables["github:lowertest::_impl"] == pytest.approx(1.0 - CROMWELL_EPS)

    # Disjunction is COMPOSITIONAL (h = a OR b is a derived value), not a relation
    # assertion.  Its helper stays at neutral 0.5; the factor potential drives the
    # marginal.  DISJUNCTION was incorrectly in _RELATION_OPS before Fix 1.
    assert fg.variables["github:lowertest::_d"] == pytest.approx(0.5)
    # Directed operator conclusions (_g) must have computation prior 0.5
    assert fg.variables["github:lowertest::_g"] == pytest.approx(0.5)


def test_auto_formalized_abduction_relation_conclusions_get_assertion_prior():
    """Named strategy auto-formalization path: formalize_named_strategy generates
    helper claims that are registered via _ensure_claim_var (π=0.5) BEFORE the
    FormalStrategy expand path runs.  Relation conclusions must still get π=1-ε."""
    from gaia.bp.factor_graph import CROMWELL_EPS

    s = Strategy(
        scope="local",
        type="abduction",
        premises=["github:lowertest::obs3"],
        conclusion="github:lowertest::hyp3",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::obs3", type="claim", content="Obs3"),
            Knowledge(id="github:lowertest::hyp3", type="claim", content="Hyp3"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g, expand_formal=True)

    # Find the equivalence conclusions (auto-generated helper claims)
    eq_vars = [v for v in fg.variables if "equivalence_result" in v]

    # Equivalence conclusion is a relation operator → must have assertion prior 1-ε
    for v in eq_vars:
        assert fg.variables[v] == pytest.approx(1.0 - CROMWELL_EPS), (
            f"Relation conclusion {v} should have prior 1-ε, got {fg.variables[v]}"
        )


def test_fold_composite_to_cpt_directly():
    """fold_composite_to_cpt returns a CPT derived from sub-strategies."""
    sub = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::a", "github:lowertest::b"],
        conclusion="github:lowertest::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:lowertest::a", "github:lowertest::b"],
        conclusion="github:lowertest::c",
        sub_strategies=[sub.strategy_id],
    )
    strat_by_id = {sub.strategy_id: sub, comp.strategy_id: comp}
    cpt = fold_composite_to_cpt(
        comp,
        strat_by_id,
        {sub.strategy_id: [0.85]},
    )
    assert len(cpt) == 4  # 2^2 entries
    # (A=0, B=0): both premises false → conclusion low
    assert cpt[0] < 0.1
    # (A=1, B=0) and (A=0, B=1): one premise false → conjunction fails → low
    assert cpt[1] < 0.1
    assert cpt[2] < 0.1
    # (A=1, B=1): both true → noisy_and fires with p=0.85 → high
    assert cpt[3] > 0.7


def test_fold_composite_to_cpt_chain():
    """fold_composite_to_cpt derives CPT for a two-step chain A → M → C."""
    sub1 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::m",
    )
    sub2 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:lowertest::m"],
        conclusion="github:lowertest::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::c",
        sub_strategies=[sub1.strategy_id, sub2.strategy_id],
    )
    strat_by_id = {
        sub1.strategy_id: sub1,
        sub2.strategy_id: sub2,
        comp.strategy_id: comp,
    }
    cpt = fold_composite_to_cpt(
        comp,
        strat_by_id,
        {sub1.strategy_id: [0.9], sub2.strategy_id: [0.8]},
    )
    assert len(cpt) == 2  # 2^1 = 2 entries (single premise A)
    assert cpt[0] < 0.1  # A=0 → M low → C low
    assert cpt[1] > 0.5  # A=1 → M≈0.9 → C≈0.72


# ---------------------------------------------------------------------------
# E2E: binary implication full pipeline
# ---------------------------------------------------------------------------


def test_e2e_deduction_binary_implication_full_pipeline():
    """E2E: deduction([A, B], C) → formalize → lower → BP runs without error.

    Verifies the full pipeline with the new binary implication operator:
    1. Strategy auto-formalization generates CONJUNCTION + IMPLICATION with helper
    2. Lowering produces a valid factor graph with helper claim at ~1-eps prior
    3. BP (exact inference) runs and produces meaningful beliefs
    """
    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::a", "github:lowertest::b"],
        conclusion="github:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="Premise A"),
            Knowledge(id="github:lowertest::b", type="claim", content="Premise B"),
            Knowledge(id="github:lowertest::c", type="claim", content="Conclusion C"),
        ],
        strategies=[s],
    )

    # Step 1: lower (auto-formalizes deduction → CONJUNCTION + IMPLICATION with helper)
    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::a": 0.8,
            "github:lowertest::b": 0.9,
            "github:lowertest::c": 0.5,
        },
    )
    assert not fg.validate()

    # The factor graph should contain both factor types
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.CONJUNCTION in ftypes
    assert FactorType.IMPLICATION in ftypes

    # IMPLICATION factor should have 2 variables (not 1)
    impl_factors = [f for f in fg.factors if f.factor_type == FactorType.IMPLICATION]
    assert len(impl_factors) == 1
    assert len(impl_factors[0].variables) == 2

    # Helper claim (implication conclusion) should be at assertion prior ~1-eps
    from gaia.bp.factor_graph import CROMWELL_EPS

    impl_concl = impl_factors[0].conclusion
    assert fg.variables[impl_concl] == pytest.approx(1.0 - CROMWELL_EPS)

    # Step 2: run exact inference — must not error
    beliefs, _ = exact_inference(fg)
    assert all(0 < beliefs[v] < 1 for v in beliefs)
    # With high-prior premises, conclusion should be lifted above 0.5
    assert beliefs["github:lowertest::c"] > 0.5


def test_e2e_single_premise_deduction_binary_implication():
    """E2E: single-premise deduction uses binary implication (no conjunction)."""
    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::p"],
        conclusion="github:lowertest::q",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="Premise P"),
            Knowledge(id="github:lowertest::q", type="claim", content="Conclusion Q"),
        ],
        strategies=[s],
    )

    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::p": 0.9,
            "github:lowertest::q": 0.5,
        },
    )
    assert not fg.validate()

    # Only IMPLICATION factor (no CONJUNCTION for single premise)
    ftypes = [f.factor_type for f in fg.factors]
    assert FactorType.IMPLICATION in ftypes
    assert FactorType.CONJUNCTION not in ftypes

    # IMPLICATION has 2 variables
    impl_f = [f for f in fg.factors if f.factor_type == FactorType.IMPLICATION][0]
    assert len(impl_f.variables) == 2

    # Run inference
    beliefs, _ = exact_inference(fg)
    assert all(0 < beliefs[v] < 1 for v in beliefs)
    assert beliefs["github:lowertest::q"] > 0.5


def test_relation_helper_defaults_to_assertion_prior():
    """Relation operator helper claims default to 1-ε when absent from node_priors.

    Callers that generate node_priors should set relation helpers to 1-ε
    (not 0.5). When the helper is absent from node_priors, lowering falls
    back to the structural default 1-ε.
    """
    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::b",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
        ],
        strategies=[s],
    )

    from gaia.bp.factor_graph import CROMWELL_EPS

    # Case 1: helper NOT in node_priors → lowering uses 1-ε default
    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::a": 0.8,
            "github:lowertest::b": 0.5,
        },
    )
    impl_f = [f for f in fg.factors if f.factor_type == FactorType.IMPLICATION][0]
    helper_id = impl_f.conclusion
    assert fg.variables[helper_id] == pytest.approx(1.0 - CROMWELL_EPS)

    # Case 2: helper in node_priors at 1-ε (correct generation) → lowering uses it
    fg2 = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::a": 0.8,
            "github:lowertest::b": 0.5,
            helper_id: 1.0 - CROMWELL_EPS,
        },
    )
    assert fg2.variables[helper_id] == pytest.approx(1.0 - CROMWELL_EPS)

    # Both cases: BP propagates correctly
    beliefs, _ = exact_inference(fg)
    assert beliefs["github:lowertest::b"] > 0.5


# ---------------------------------------------------------------------------
# E2E: support() full pipeline
# ---------------------------------------------------------------------------


def test_e2e_support_compiles_and_runs_bp():
    """E2E: support([A], B) -> formalize (2 IMPLIES) -> lower -> BP."""
    s = Strategy(
        scope="local",
        type="support",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::b",
        metadata={"reverse_reason": "B implies A"},
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
        ],
        strategies=[s],
    )

    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::a": 0.8,
            "github:lowertest::b": 0.5,
        },
    )
    assert not fg.validate()

    # Support produces 2 IMPLICATION factors (forward + reverse)
    impl_factors = [f for f in fg.factors if f.factor_type == FactorType.IMPLICATION]
    assert len(impl_factors) == 2

    # Run inference
    beliefs, _ = exact_inference(fg)
    assert all(0 < beliefs[v] < 1 for v in beliefs)
    # With high prior on A, B should be lifted above 0.5 via support
    assert beliefs["github:lowertest::b"] > 0.5


# ---------------------------------------------------------------------------
# Deprecation test: noisy_and
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# E2E: compare() full pipeline
# ---------------------------------------------------------------------------


def test_e2e_compare_compiles_and_runs_bp():
    """E2E: compare(pred_h, pred_alt, obs) -> formalize (2 EQUIV + 1 IMPL) -> lower -> BP."""
    s = Strategy(
        scope="local",
        type="compare",
        premises=[
            "github:lowertest::pred_h",
            "github:lowertest::pred_alt",
            "github:lowertest::obs",
        ],
        conclusion="github:lowertest::comparison",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::pred_h", type="claim", content="GR prediction"),
            Knowledge(id="github:lowertest::pred_alt", type="claim", content="Newton prediction"),
            Knowledge(id="github:lowertest::obs", type="claim", content="Observation"),
            Knowledge(id="github:lowertest::comparison", type="claim", content="Comparison result"),
        ],
        strategies=[s],
    )

    fg = lower_local_graph(
        g,
        node_priors={
            "github:lowertest::pred_h": 0.9,
            "github:lowertest::pred_alt": 0.4,
            "github:lowertest::obs": 0.95,
            "github:lowertest::comparison": 0.5,
        },
    )
    assert not fg.validate()

    # Compare produces 2 EQUIVALENCE + 1 IMPLICATION factors
    ftypes = {f.factor_type for f in fg.factors}
    assert FactorType.EQUIVALENCE in ftypes
    assert FactorType.IMPLICATION in ftypes

    eq_factors = [f for f in fg.factors if f.factor_type == FactorType.EQUIVALENCE]
    impl_factors = [f for f in fg.factors if f.factor_type == FactorType.IMPLICATION]
    assert len(eq_factors) == 2
    assert len(impl_factors) == 1

    # Run inference
    beliefs, _ = exact_inference(fg)
    assert all(0 < beliefs[v] < 1 for v in beliefs)


def test_noisy_and_deprecated():
    """noisy_and() emits DeprecationWarning and delegates to support()."""
    import warnings

    from gaia.lang import claim as dsl_claim
    from gaia.lang import noisy_and as dsl_noisy_and

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        a = dsl_claim("A")
        b = dsl_claim("B")
        s = dsl_noisy_and([a], b)
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "noisy_and" in str(w[0].message)
    # The returned strategy should be a support strategy
    assert s.type == "support"


# ---------------------------------------------------------------------------
# E2E: abduction full pipeline (DSL → structure verification)
# ---------------------------------------------------------------------------


def test_e2e_abduction_full_pipeline():
    """E2E: support + support + compare -> abduction -> CompositeStrategy (3 sub-strategies).

    Verifies the full DSL pipeline: abduction creates a well-formed
    CompositeStrategy with 2 supports + 1 compare, composition warrant,
    and comparison.conclusion as conclusion.
    """
    from gaia.lang import claim as dsl_claim
    from gaia.lang import compare as dsl_compare
    from gaia.lang import support as dsl_support
    from gaia.lang.dsl.strategies import abduction as dsl_abduction

    h = dsl_claim("Theory H")
    alt = dsl_claim("Theory Alt")
    obs = dsl_claim("Observed X")
    pred_h = dsl_claim("Pred from H")
    pred_alt = dsl_claim("Pred from Alt")

    s_h = dsl_support(
        [h],
        obs,
        reason="H explains obs",
        prior=0.9,
        reverse_reason="obs validates H",
        reverse_prior=0.8,
    )
    s_alt = dsl_support(
        [alt],
        obs,
        reason="Alt explains obs",
        prior=0.5,
        reverse_reason="obs validates Alt",
        reverse_prior=0.5,
    )
    comp = dsl_compare(pred_h, pred_alt, obs, reason="H matches obs better", prior=0.9)
    abd = dsl_abduction(s_h, s_alt, comp, reason="both explain same observation")

    # Structure checks
    assert abd.type == "abduction"
    assert len(abd.sub_strategies) == 3  # support_h, support_alt, compare
    assert abd.sub_strategies[0] is s_h
    assert abd.sub_strategies[1] is s_alt
    assert abd.sub_strategies[2] is comp

    # Composition warrant
    assert abd.composition_warrant is not None
    assert abd.composition_warrant.type == "claim"
    assert abd.composition_warrant.metadata.get("helper_kind") == "composition_validity"

    # Conclusion is the comparison_claim from compare
    assert abd.conclusion is not None
    assert abd.conclusion is comp.conclusion


def test_e2e_induction_chain():
    """E2E: support + support → induction chain → law accumulated."""
    from gaia.lang import claim as dsl_claim
    from gaia.lang import support as dsl_support
    from gaia.lang.dsl.strategies import induction as dsl_induction

    law = dsl_claim("Mendel's law")
    obs1 = dsl_claim("Seed shape 2.96:1")
    obs2 = dsl_claim("Seed color 3.01:1")
    obs3 = dsl_claim("Flower color 3.15:1")

    s1 = dsl_support(
        [law],
        obs1,
        reason="law predicts 3:1",
        prior=0.9,
        reverse_reason="2.96 matches",
        reverse_prior=0.9,
    )
    s2 = dsl_support(
        [law],
        obs2,
        reason="law predicts 3:1",
        prior=0.9,
        reverse_reason="3.01 matches",
        reverse_prior=0.9,
    )
    s3 = dsl_support(
        [law],
        obs3,
        reason="law predicts 3:1",
        prior=0.9,
        reverse_reason="3.15 matches",
        reverse_prior=0.9,
    )

    # Binary induction
    ind_12 = dsl_induction(s1, s2, law=law, reason="shape and color are independent traits")
    assert ind_12.type == "induction"
    assert ind_12.conclusion is law
    assert len(ind_12.sub_strategies) == 2
    assert ind_12.composition_warrant is not None
    assert ind_12.composition_warrant.metadata.get("helper_kind") == "composition_validity"

    # Chain: induction(prev_induction, new_support, law)
    ind_123 = dsl_induction(ind_12, s3, law=law, reason="flower color independent of seed traits")
    assert ind_123.type == "induction"
    assert ind_123.conclusion is law
    assert len(ind_123.sub_strategies) == 2  # prev_induction + s3
    assert ind_123.sub_strategies[0] is ind_12
    assert ind_123.sub_strategies[1] is s3


def test_e2e_mendel_peirce_cycle():
    """E2E: Full Peirce cycle -- deduction + support + compare + abduction + induction."""
    from gaia.lang import claim as dsl_claim
    from gaia.lang import compare as dsl_compare
    from gaia.lang import deduction as dsl_deduction
    from gaia.lang import support as dsl_support
    from gaia.lang.dsl.strategies import abduction as dsl_abduction
    from gaia.lang.dsl.strategies import induction as dsl_induction

    # Knowledge
    H = dsl_claim("Discrete heritable factors")
    alt = dsl_claim("Blending inheritance")
    obs = dsl_claim("F2 ratio 2.96:1")

    # 1. Deduction: H -> prediction (standalone reasoning step)
    pred_h = dsl_claim("H predicts 3:1")
    pred_alt = dsl_claim("Blending predicts continuous")
    dsl_deduction([H], pred_h, reason="Punnett square derivation", prior=0.99)

    # 2. Supports: theory -> observation directly
    s_h = dsl_support(
        [H],
        obs,
        reason="H explains 3:1 ratio",
        prior=0.9,
        reverse_reason="ratio validates H",
        reverse_prior=0.9,
    )
    s_alt = dsl_support(
        [alt],
        obs,
        reason="blending explains ratio",
        prior=0.5,
        reverse_reason="ratio indicates blending",
        reverse_prior=0.5,
    )

    # 3. Compare: H vs Alt predictions against observation
    comp = dsl_compare(pred_h, pred_alt, obs, reason="H matches 3:1 better", prior=0.9)

    # 4. Abduction: two supports + compare, conclusion is comparison_claim
    abd = dsl_abduction(s_h, s_alt, comp, reason="both explain F2 pattern")
    assert abd.conclusion is comp.conclusion
    assert len(abd.sub_strategies) == 3

    # 5. Induction: multiple traits
    obs2 = dsl_claim("Seed color 3.01:1")
    s_shape = dsl_support(
        [H], obs, reason="H predicts", prior=0.9, reverse_reason="matches", reverse_prior=0.9
    )
    s_color = dsl_support(
        [H], obs2, reason="H predicts", prior=0.9, reverse_reason="matches", reverse_prior=0.9
    )
    ind = dsl_induction(s_shape, s_color, law=H, reason="traits independent")
    assert ind.conclusion is H


# ---------------------------------------------------------------------------
# Part 3: lowering uses author-set prior from metadata
# ---------------------------------------------------------------------------


def test_lowering_uses_author_prior_for_relation_helper():
    """If helper claim has metadata['prior'], lowering uses it instead of 1-eps."""
    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::b",
        metadata={"prior": 0.85},
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    # Find the implication helper variable (auto-generated, label starts with __)
    helper_vars = [
        vid for vid in fg.variables if vid.startswith("github:lowertest::__implication_result")
    ]
    assert len(helper_vars) == 1
    assert fg.variables[helper_vars[0]] == pytest.approx(0.85)


def test_lowering_default_prior_for_relation_helper_without_author():
    """Without author prior, relation helper gets 1-eps as before."""
    from gaia.bp.factor_graph import CROMWELL_EPS

    s = Strategy(
        scope="local",
        type="deduction",
        premises=["github:lowertest::a"],
        conclusion="github:lowertest::b",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::a", type="claim", content="A"),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
        ],
        strategies=[s],
    )
    fg = lower_local_graph(g)
    helper_vars = [
        vid for vid in fg.variables if vid.startswith("github:lowertest::__implication_result")
    ]
    assert len(helper_vars) == 1
    assert fg.variables[helper_vars[0]] == pytest.approx(1.0 - CROMWELL_EPS)


def test_claim_metadata_prior_used_in_lowering():
    """Claims with metadata['prior'] use that value instead of default 0.5."""
    from gaia.ir import Knowledge

    g = _lg(
        knowledges=[
            Knowledge(
                id="github:lowertest::a",
                type="claim",
                content="A",
                metadata={"prior": 0.85},
            ),
            Knowledge(id="github:lowertest::b", type="claim", content="B"),
        ],
    )
    fg = lower_local_graph(g)
    assert fg.variables["github:lowertest::a"] == pytest.approx(0.85)
    assert fg.variables["github:lowertest::b"] == pytest.approx(0.5)  # default
