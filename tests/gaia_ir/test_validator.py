"""Tests for Gaia IR validator."""

from gaia.gaia_ir import (
    Knowledge,
    KnowledgeType,
    Operator,
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
)
from gaia.gaia_ir.validator import (
    validate_local_graph,
    validate_global_graph,
    validate_parameterization,
    validate_bindings,
)


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

    def test_local_knowledge_must_have_content(self):
        k = Knowledge(id="lcn_a", type=KnowledgeType.CLAIM)
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("content" in e for e in r.errors)

    def test_local_knowledge_must_not_have_representative_lcn(self):
        from gaia.gaia_ir import LocalCanonicalRef

        k = Knowledge(
            id="lcn_a",
            type=KnowledgeType.CLAIM,
            content="test",
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_x", package_id="pkg", version="1"
            ),
        )
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("representative_lcn" in e for e in r.errors)

    def test_local_knowledge_must_not_have_local_members(self):
        from gaia.gaia_ir import LocalCanonicalRef

        k = Knowledge(
            id="lcn_a",
            type=KnowledgeType.CLAIM,
            content="test",
            local_members=[
                LocalCanonicalRef(local_canonical_id="lcn_x", package_id="pkg", version="1")
            ],
        )
        g = _local_graph(knowledges=[k])
        r = validate_local_graph(g)
        assert not r.valid
        assert any("local_members" in e for e in r.errors)


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

    def test_local_graph_rejects_global_scoped_operator(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            operators=[
                Operator(scope="global", operator="equivalence", variables=["lcn_a", "lcn_b"])
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)

    def test_global_graph_rejects_local_scoped_operator(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            operators=[
                Operator(scope="local", operator="equivalence", variables=["gcn_a", "gcn_b"])
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)


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
                    scope="local",
                    type="noisy_and",
                    premises=["lcn_a"],
                    conclusion="lcn_b",
                    background=["lcn_nonexistent"],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid  # warning, not error
        assert any("background" in w for w in r.warnings)

    def test_global_strategy_rejects_steps(self):
        """Pydantic model validation rejects steps on global Strategy at construction time."""
        import pytest
        from gaia.gaia_ir import Step

        with pytest.raises(Exception, match="global Strategy must not carry steps"):
            Strategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
                steps=[Step(reasoning="should not be here")],
            )

    def test_strategy_prefix_check(self):
        """Pydantic model validation rejects wrong ID prefix at construction time."""
        import pytest

        with pytest.raises(Exception, match="lcs_ prefix"):
            Strategy(
                strategy_id="gcs_wrong",
                scope="local",
                type="infer",
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_local_graph_rejects_global_scoped_strategy(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b")],
            strategies=[
                Strategy(scope="global", type="infer", premises=["lcn_a"], conclusion="lcn_b")
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)

    def test_global_graph_rejects_local_scoped_strategy(self):
        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b")],
            strategies=[
                Strategy(scope="local", type="infer", premises=["gcn_a"], conclusion="gcn_b")
            ],
        )
        r = validate_global_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() for e in r.errors)


class TestCompositeStrategyValidation:
    def test_valid_composite(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    sub_strategies=[
                        Strategy(
                            scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b"
                        ),
                    ],
                )
            ],
        )
        r = validate_local_graph(g)
        assert r.valid

    def test_nested_scope_mismatch_rejected(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_b"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local",
                    type="abduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    sub_strategies=[
                        Strategy(
                            scope="global",
                            type="noisy_and",
                            premises=["lcn_a"],
                            conclusion="lcn_b",
                        ),
                    ],
                )
            ],
        )
        r = validate_local_graph(g)
        assert not r.valid
        assert any("scope" in e.lower() and "incompatible" in e.lower() for e in r.errors)

    def test_sub_strategy_dangling_ref(self):
        g = _local_graph(
            knowledges=[_claim("lcn_a"), _claim("lcn_c")],
            strategies=[
                CompositeStrategy(
                    scope="local",
                    type="induction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    sub_strategies=[
                        Strategy(
                            scope="local",
                            type="noisy_and",
                            premises=["lcn_missing"],
                            conclusion="lcn_c",
                        ),
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
                    scope="local",
                    type="deduction",
                    premises=["lcn_a", "lcn_b"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="conjunction",
                                variables=["lcn_a", "lcn_b", "lcn_m"],
                                conclusion="lcn_m",
                            ),
                            Operator(
                                operator="implication",
                                variables=["lcn_m", "lcn_c"],
                                conclusion="lcn_c",
                            ),
                        ]
                    ),
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
                    scope="local",
                    type="deduction",
                    premises=["lcn_a"],
                    conclusion="lcn_c",
                    formal_expr=FormalExpr(
                        operators=[
                            Operator(
                                operator="implication",
                                variables=["lcn_missing", "lcn_c"],
                                conclusion="lcn_c",
                            ),
                        ]
                    ),
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


# ---------------------------------------------------------------------------
# 5. Parameterization completeness
# ---------------------------------------------------------------------------


class TestParameterizationValidation:
    def _graph(self):
        return _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _setting("gcn_s")],
            strategies=[
                Strategy(scope="global", type="noisy_and", premises=["gcn_a"], conclusion="gcn_b"),
            ],
        )

    def test_complete_parameterization(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid

    def test_missing_prior(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert not r.valid
        assert any("gcn_b" in e and "missing PriorRecord" in e for e in r.errors)

    def test_missing_strategy_param(self):
        from gaia.gaia_ir import PriorRecord

        g = self._graph()
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[],
        )
        assert not r.valid
        assert any("missing StrategyParamRecord" in e for e in r.errors)

    def test_setting_does_not_need_prior(self):
        """Settings don't carry probability — no PriorRecord needed."""
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid, conditional_probabilities=[0.85], source_id="s"
                ),
            ],
        )
        assert r.valid  # gcn_s (setting) doesn't need a prior

    def test_cromwell_bounds_on_priors(self):
        """PriorRecord auto-clamps, so raw values within bounds should pass."""
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a")],
            strategies=[],
        )
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[],
        )
        assert r.valid

    def test_dangling_prior_warning(self):
        from gaia.gaia_ir import PriorRecord

        g = _global_graph(knowledges=[_claim("gcn_a")])
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_nonexistent", value=0.5, source_id="s"),
            ],
            strategy_params=[],
        )
        assert r.valid  # warning, not error
        assert any("non-existent" in w for w in r.warnings)

    def test_dangling_strategy_param_warning(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(knowledges=[_claim("gcn_a")])
        r = validate_parameterization(
            g,
            priors=[PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s")],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id="gcs_ghost", conditional_probabilities=[0.5], source_id="s"
                ),
            ],
        )
        assert r.valid
        assert any("non-existent" in w for w in r.warnings)

    def test_empty_graph_no_requirements(self):
        r = validate_parameterization(_global_graph(), [], [])
        assert r.valid

    def test_noisy_and_wrong_arity_rejected(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = self._graph()
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.7, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.2, 0.3, 0.4, 0.5],
                    source_id="s",
                ),
            ],
        )
        assert not r.valid
        assert any("noisy_and" in e and "requires 1" in e for e in r.errors)

    def test_infer_wrong_arity_rejected(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_c")],
            strategies=[
                Strategy(
                    scope="global",
                    type="infer",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.8, 0.9],  # needs 2^2=4
                    source_id="s",
                ),
            ],
        )
        assert not r.valid
        assert any("2^2=4" in e for e in r.errors)

    def test_infer_correct_arity_passes(self):
        from gaia.gaia_ir import PriorRecord, StrategyParamRecord

        g = _global_graph(
            knowledges=[_claim("gcn_a"), _claim("gcn_b"), _claim("gcn_c")],
            strategies=[
                Strategy(
                    scope="global",
                    type="infer",
                    premises=["gcn_a", "gcn_b"],
                    conclusion="gcn_c",
                ),
            ],
        )
        sid = g.strategies[0].strategy_id
        r = validate_parameterization(
            g,
            priors=[
                PriorRecord(gcn_id="gcn_a", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_b", value=0.5, source_id="s"),
                PriorRecord(gcn_id="gcn_c", value=0.5, source_id="s"),
            ],
            strategy_params=[
                StrategyParamRecord(
                    strategy_id=sid,
                    conditional_probabilities=[0.8, 0.7, 0.6, 0.9],
                    source_id="s",
                ),
            ],
        )
        assert r.valid


# ---------------------------------------------------------------------------
# 6. CanonicalBinding validation
# ---------------------------------------------------------------------------


class TestBindingValidation:
    def test_valid_bindings(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_b")])
        global_ = _global_graph(knowledges=[_claim("gcn_x"), _claim("gcn_y")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="similarity 0.95",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_b",
                global_canonical_id="gcn_y",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="no match",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert r.valid

    def test_missing_binding(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a"), _claim("lcn_b")])
        global_ = _global_graph(knowledges=[_claim("gcn_x")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="match",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("lcn_b" in e and "no CanonicalBinding" in e for e in r.errors)

    def test_duplicate_binding(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[_claim("gcn_x"), _claim("gcn_y")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="first",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_y",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="second",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("2 bindings" in e for e in r.errors)

    def test_binding_dangling_local(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[_claim("gcn_x")])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="ok",
            ),
            CanonicalBinding(
                local_canonical_id="lcn_ghost",
                global_canonical_id="gcn_x",
                package_id="pkg",
                version="1",
                decision=BindingDecision.MATCH_EXISTING,
                reason="dangling",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("not found in local" in e for e in r.errors)

    def test_binding_dangling_global(self):
        from gaia.gaia_ir import CanonicalBinding, BindingDecision

        local = _local_graph(knowledges=[_claim("lcn_a")])
        global_ = _global_graph(knowledges=[])
        bindings = [
            CanonicalBinding(
                local_canonical_id="lcn_a",
                global_canonical_id="gcn_ghost",
                package_id="pkg",
                version="1",
                decision=BindingDecision.CREATE_NEW,
                reason="dangling global",
            ),
        ]
        r = validate_bindings(bindings, local, global_)
        assert not r.valid
        assert any("not found in global" in e for e in r.errors)

    def test_empty_bindings_for_empty_graph(self):
        r = validate_bindings([], _local_graph(), _global_graph())
        assert r.valid
