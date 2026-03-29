"""Tests for Gaia IR validator."""

import pytest
from gaia.gaia_ir import (
    Knowledge,
    KnowledgeType,
    Operator,
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    StrategyType,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
)
from gaia.gaia_ir.validator import validate_local_graph, validate_global_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _claim(id: str, content: str = "test") -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.CLAIM, content=content)


def _setting(id: str) -> Knowledge:
    return Knowledge(id=id, type=KnowledgeType.SETTING)


def _local_graph(**kwargs) -> LocalCanonicalGraph:
    defaults = {"knowledges": [], "operators": [], "strategies": []}
    defaults.update(kwargs)
    return LocalCanonicalGraph(**defaults)


def _global_graph(**kwargs) -> GlobalCanonicalGraph:
    defaults = {"knowledges": [], "operators": [], "strategies": []}
    defaults.update(kwargs)
    return GlobalCanonicalGraph(**defaults)


# ---------------------------------------------------------------------------
# 1. Knowledge validation
# ---------------------------------------------------------------------------


class TestKnowledgeValidation:
    def test_valid_local(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        r = validate_local_graph(g)
        assert r.valid

    def test_wrong_prefix_local(self):
        g = _local_graph(knowledges=[_claim("gcn_wrong")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("prefix" in e for e in r.errors)

    def test_wrong_prefix_global(self):
        g = _global_graph(knowledges=[_claim("lcn_wrong")])
        r = validate_global_graph(g)
        assert not r.valid

    def test_duplicate_id(self):
        g = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_a", "other")])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("duplicate" in e for e in r.errors)

    def test_claim_without_content_or_repr(self):
        k = Knowledge(id="gcn_bad", type=KnowledgeType.CLAIM)
        g = _global_graph(knowledges=[k])
        r = validate_global_graph(g)
        assert not r.valid
        assert any("content or representative_lcn" in e for e in r.errors)

    def test_claim_with_representative_lcn_ok(self):
        from gaia.gaia_ir import LocalCanonicalRef
        k = Knowledge(
            id="gcn_ok",
            type=KnowledgeType.CLAIM,
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_x", package_id="pkg", version="1"
            ),
        )
        g = _global_graph(knowledges=[k])
        r = validate_global_graph(g)
        assert r.valid


# ---------------------------------------------------------------------------
# 2. Operator validation
# ---------------------------------------------------------------------------


class TestOperatorValidation:
    def test_valid_operator(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[Operator(operator="equivalence", variables=["lcn_a", "lcn_b"])],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_reference(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            operators=[Operator(operator="equivalence", variables=["lcn_a", "lcn_missing"])],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("not found" in e for e in r.errors)

    def test_operator_on_non_claim(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _setting("lcn_s")],
            operators=[Operator(operator="equivalence", variables=["lcn_a", "lcn_s"])],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("must be claim" in e for e in r.errors)


# ---------------------------------------------------------------------------
# 3. Strategy validation
# ---------------------------------------------------------------------------


class TestStrategyValidation:
    def test_valid_strategy(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_dangling_premise(self):
        g = _local_graph(
            knowledges=[_claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_missing"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "not found" in e for e in r.errors)

    def test_dangling_conclusion(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_missing")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "not found" in e for e in r.errors)

    def test_premise_must_be_claim(self):
        g = _local_graph(
            knowledges=[_setting("lcn_s"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_s"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("premise" in e and "must be claim" in e for e in r.errors)

    def test_conclusion_must_be_claim(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _setting("lcn_s")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_s")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("conclusion" in e and "must be claim" in e for e in r.errors)

    def test_self_loop_rejected(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["lcn_a"], conclusion="lcn_a")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("self-loop" in e for e in r.errors)

    def test_background_warning_if_missing(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(
                    scope="local", type="noisy_and",
                    premises=["lcn_a"], conclusion="lcn_b",
                    background=["lcn_nonexistent"],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid  # warning, not error
        assert any("background" in w for w in r.warnings)

    def test_global_strategy_rejects_steps(self):
        from gaia.gaia_ir import Step
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                Strategy(
                    scope="global", type="infer",
                    premises=["gcn_a"], conclusion="gcn_b",
                    steps=[Step(reasoning="should not be here")],
                )
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid
        assert any("steps" in e for e in r.errors)

    def test_strategy_prefix_check(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(
                    strategy_id="gcs_wrong",
                    scope="local", type="infer",
                    premises=["lcn_a"], conclusion="lcn_b",
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("prefix" in e for e in r.errors)


class TestCompositeStrategyValidation:
    def test_valid_composite(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local", type="abduction",
                    premises=["lcn_a"], conclusion="lcn_c",
                    sub_strategies=[
                        Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b"),
                    ],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_sub_strategy_dangling_ref(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local", type="induction",
                    premises=["lcn_a"], conclusion="lcn_c",
                    sub_strategies=[
                        Strategy(scope="local", type="noisy_and", premises=["lcn_missing"], conclusion="lcn_c"),
                    ],
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid


class TestFormalStrategyValidation:
    def test_valid_formal(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_m"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local", type="deduction",
                    premises=["lcn_a", "lcn_b"], conclusion="lcn_c",
                    formal_expr=FormalExpr(operators=[
                        Operator(operator="conjunction", variables=["lcn_a", "lcn_b", "lcn_m"], conclusion="lcn_m"),
                        Operator(operator="implication", variables=["lcn_m", "lcn_c"], conclusion="lcn_c"),
                    ]),
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_formal_expr_dangling_ref(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c")],
            strategies=[
                FormalStrategy(
                    scope="local", type="deduction",
                    premises=["lcn_a"], conclusion="lcn_c",
                    formal_expr=FormalExpr(operators=[
                        Operator(operator="implication", variables=["lcn_missing", "lcn_c"], conclusion="lcn_c"),
                    ]),
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid


# ---------------------------------------------------------------------------
# 4. Graph-level validation
# ---------------------------------------------------------------------------


class TestGraphLevelValidation:
    def test_scope_consistency_local(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["gcn_wrong"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("wrong prefix" in e for e in r.errors)

    def test_scope_consistency_global(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                Strategy(scope="global", type="infer", premises=["lcn_wrong"], conclusion="gcn_b")
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid

    def test_hash_consistency(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        r = validate_local_graph(g)
        assert r.valid  # auto-computed hash should match

    def test_hash_mismatch(self):
        g = _local_graph(knowledges=[_claim("lcn_a")])
        g.ir_hash = "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        r = validate_local_graph(g)
        assert not r.valid
        assert any("ir_hash mismatch" in e for e in r.errors)

    def test_empty_graph_valid(self):
        r = validate_local_graph(_local_graph())
        assert r.valid

    def test_empty_global_valid(self):
        r = validate_global_graph(_global_graph())
        assert r.valid
