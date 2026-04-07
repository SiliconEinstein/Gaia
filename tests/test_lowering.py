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
    op = Operator(operator="implication", variables=["a"], conclusion="b")
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
                    variables=["github:lowertest::p"],
                    conclusion="github:lowertest::c",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="P"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
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
                    variables=["github:lowertest::p"],
                    conclusion="github:lowertest::c",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="github:lowertest::p", type="claim", content="P"),
            Knowledge(id="github:lowertest::c", type="claim", content="C"),
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
                    variables=["github:lowertest::_g"],
                    conclusion="github:lowertest::s",
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

    # Relation operator conclusions (_eq, _contra) must have assertion prior 1-ε
    assert fg.variables["github:lowertest::_eq"] == pytest.approx(1.0 - CROMWELL_EPS)
    assert fg.variables["github:lowertest::_contra"] == pytest.approx(1.0 - CROMWELL_EPS)

    # Disjunction is in _RELATION_OPS (IR §2.4 classification) → assertion prior
    assert fg.variables["github:lowertest::_d"] == pytest.approx(1.0 - CROMWELL_EPS)
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
