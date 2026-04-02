"""Tests for gaia.bp.lowering."""

from __future__ import annotations

import pytest

from gaia.bp import FactorType, lower_local_graph, lower_operator
from gaia.bp.factor_graph import FactorGraph
from gaia.bp.exact import exact_inference
from gaia.ir import Knowledge, Operator, Strategy, LocalCanonicalGraph

NS, PKG = "reg", "lowertest"


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
            Knowledge(id="reg:lowertest::a", type="claim", content="A"),
            Knowledge(id="reg:lowertest::b", type="claim", content="B"),
            Knowledge(id="reg:lowertest::h", type="claim", content="H"),
        ],
        operators=[
            Operator(
                operator="equivalence",
                variables=["reg:lowertest::a", "reg:lowertest::b"],
                conclusion="reg:lowertest::h",
            ),
        ],
    )
    fg = lower_local_graph(
        g,
        node_priors={
            "reg:lowertest::a": 0.7,
            "reg:lowertest::b": 0.4,
            "reg:lowertest::h": 0.95,
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
            Knowledge(id="reg:lowertest::x", type="claim", content="X"),
            Knowledge(id="reg:lowertest::y", type="claim", content="Y"),
            Knowledge(id="reg:lowertest::r", type="claim", content="R"),
        ],
        operators=[
            Operator(
                operator="contradiction",
                variables=["reg:lowertest::x", "reg:lowertest::y"],
                conclusion="reg:lowertest::r",
            ),
        ],
    )
    fg = lower_local_graph(g)
    assert fg.variables["reg:lowertest::r"] == pytest.approx(1.0 - CROMWELL_EPS)


def test_contradiction_actually_constrains():
    """With prior ~1.0 on helper, CONTRADICTION suppresses joint X=Y=1."""
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::x", type="claim", content="X"),
            Knowledge(id="reg:lowertest::y", type="claim", content="Y"),
            Knowledge(id="reg:lowertest::r", type="claim", content="R"),
        ],
        operators=[
            Operator(
                operator="contradiction",
                variables=["reg:lowertest::x", "reg:lowertest::y"],
                conclusion="reg:lowertest::r",
            ),
        ],
    )
    fg = lower_local_graph(
        g,
        node_priors={"reg:lowertest::x": 0.8, "reg:lowertest::y": 0.8},
    )
    beliefs, _ = exact_inference(fg)
    assert beliefs["reg:lowertest::x"] < 0.8 or beliefs["reg:lowertest::y"] < 0.8


def test_noisy_and_strategy_lowering():
    s = Strategy(
        scope="local",
        type="noisy_and",
        premises=["reg:lowertest::p1", "reg:lowertest::p2"],
        conclusion="reg:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::p1", type="claim", content="P1"),
            Knowledge(id="reg:lowertest::p2", type="claim", content="P2"),
            Knowledge(id="reg:lowertest::c", type="claim", content="C"),
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
        premises=["reg:lowertest::x"],
        conclusion="reg:lowertest::y",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::x", type="claim", content="X"),
            Knowledge(id="reg:lowertest::y", type="claim", content="Y"),
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
        premises=["reg:lowertest::p"],
        conclusion="reg:lowertest::c",
        formal_expr=FormalExpr(
            operators=[
                Operator(
                    operator="implication",
                    variables=["reg:lowertest::p"],
                    conclusion="reg:lowertest::c",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::p", type="claim", content="P"),
            Knowledge(id="reg:lowertest::c", type="claim", content="C"),
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
        premises=["reg:lowertest::p"],
        conclusion="reg:lowertest::c",
        formal_expr=FormalExpr(
            operators=[
                Operator(
                    operator="implication",
                    variables=["reg:lowertest::p"],
                    conclusion="reg:lowertest::c",
                ),
            ],
        ),
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::p", type="claim", content="P"),
            Knowledge(id="reg:lowertest::c", type="claim", content="C"),
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
        premises=["reg:lowertest::a", "reg:lowertest::b"],
        conclusion="reg:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::a", type="claim", content="A"),
            Knowledge(id="reg:lowertest::b", type="claim", content="B"),
            Knowledge(id="reg:lowertest::c", type="claim", content="C"),
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
        premises=["reg:lowertest::src", "reg:lowertest::bridge"],
        conclusion="reg:lowertest::tgt",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::src", type="claim", content="SourceLaw"),
            Knowledge(id="reg:lowertest::bridge", type="claim", content="BridgeClaim"),
            Knowledge(id="reg:lowertest::tgt", type="claim", content="Target"),
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
        premises=["reg:lowertest::law", "reg:lowertest::cont"],
        conclusion="reg:lowertest::ext",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::law", type="claim", content="KnownLaw"),
            Knowledge(id="reg:lowertest::cont", type="claim", content="ContinuityClaim"),
            Knowledge(id="reg:lowertest::ext", type="claim", content="Extended"),
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
        premises=["reg:lowertest::obs"],
        conclusion="reg:lowertest::hyp",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::obs", type="claim", content="Obs"),
            Knowledge(id="reg:lowertest::hyp", type="claim", content="Hypothesis"),
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
        premises=["reg:lowertest::base", "reg:lowertest::step"],
        conclusion="reg:lowertest::law",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::base", type="claim", content="Base"),
            Knowledge(id="reg:lowertest::step", type="claim", content="Step"),
            Knowledge(id="reg:lowertest::law", type="claim", content="Law"),
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
        premises=["reg:lowertest::p"],
        conclusion="reg:lowertest::c",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::p", type="claim", content="P"),
            Knowledge(id="reg:lowertest::c", type="claim", content="C"),
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
        premises=["reg:lowertest::obs2"],
        conclusion="reg:lowertest::hyp2",
    )
    g = _lg(
        knowledges=[
            Knowledge(id="reg:lowertest::obs2", type="claim", content="Obs2"),
            Knowledge(id="reg:lowertest::hyp2", type="claim", content="Hyp2"),
        ],
        strategies=[s],
    )
    # First pass: discover the auto-generated alt-explanation variable ID
    fg0 = lower_local_graph(g)
    alt_id = [v for v in fg0.variables if "alternative_explanation" in v][0]

    # Second pass: supply a custom prior for the auto-generated claim
    fg1 = lower_local_graph(g, node_priors={alt_id: 0.1})
    assert fg1.variables[alt_id] == pytest.approx(0.1)
