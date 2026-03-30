"""Tests for LocalCanonicalGraph and GlobalCanonicalGraph."""

import pytest

from gaia.gaia_ir import (
    Knowledge,
    LocalCanonicalRef,
    Operator,
    Strategy,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
)


def make_local_claim(knowledge_id: str, content: str) -> Knowledge:
    return Knowledge(id=knowledge_id, type="claim", content=content)


def make_global_claim(knowledge_id: str, representative_suffix: str) -> Knowledge:
    representative = LocalCanonicalRef(
        local_canonical_id=f"lcn_{representative_suffix}",
        package_id="pkg.demo",
        version="1.0.0",
    )
    return Knowledge(
        id=knowledge_id,
        type="claim",
        representative_lcn=representative,
        local_members=[representative],
    )


class TestLocalCanonicalGraph:
    def test_auto_hash(self):
        g = LocalCanonicalGraph(
            knowledges=[make_local_claim("lcn_1", "A")],
            strategies=[Strategy(scope="local", type="infer", premises=["lcn_1"], conclusion="lcn_1")],
        )
        assert g.ir_hash.startswith("sha256:")

    def test_deterministic_hash(self):
        def make():
            return LocalCanonicalGraph(
                knowledges=[make_local_claim("lcn_1", "A")],
            )
        assert make().ir_hash == make().ir_hash

    def test_hash_independent_of_entity_order(self):
        k1 = make_local_claim("lcn_1", "A")
        k2 = make_local_claim("lcn_2", "B")
        s = Strategy(scope="local", type="infer", premises=["lcn_1"], conclusion="lcn_2")

        g1 = LocalCanonicalGraph(knowledges=[k1, k2], strategies=[s])
        g2 = LocalCanonicalGraph(knowledges=[k2, k1], strategies=[s])

        assert g1.ir_hash == g2.ir_hash

    def test_different_content_different_hash(self):
        g1 = LocalCanonicalGraph(knowledges=[make_local_claim("lcn_1", "A")])
        g2 = LocalCanonicalGraph(knowledges=[make_local_claim("lcn_1", "B")])
        assert g1.ir_hash != g2.ir_hash

    def test_with_operators(self):
        g = LocalCanonicalGraph(
            knowledges=[
                make_local_claim("lcn_a", "A"),
                make_local_claim("lcn_b", "B"),
            ],
            operators=[
                Operator(operator="equivalence", variables=["lcn_a", "lcn_b"]),
            ],
        )
        assert len(g.operators) == 1

    def test_rejects_local_knowledge_without_content(self):
        with pytest.raises(ValueError, match="carry content"):
            LocalCanonicalGraph(
                knowledges=[Knowledge(id="lcn_a", type="claim")],
            )

    def test_scope_default(self):
        g = LocalCanonicalGraph(knowledges=[])
        assert g.scope == "local"


class TestGlobalCanonicalGraph:
    def test_no_hash(self):
        """Global graph is incremental — no overall hash."""
        g = GlobalCanonicalGraph(
            knowledges=[make_global_claim("gcn_1", "1")],
        )
        assert not hasattr(g, "ir_hash") or getattr(g, "ir_hash", None) is None

    def test_scope_default(self):
        g = GlobalCanonicalGraph()
        assert g.scope == "global"

    def test_empty_defaults(self):
        g = GlobalCanonicalGraph()
        assert g.knowledges == []
        assert g.operators == []
        assert g.strategies == []

    def test_three_entity_types(self):
        g = GlobalCanonicalGraph(
            knowledges=[make_global_claim("gcn_a", "a"), make_global_claim("gcn_b", "b")],
            operators=[Operator(operator="equivalence", variables=["gcn_a", "gcn_b"])],
            strategies=[Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")],
        )
        assert len(g.knowledges) == 2
        assert len(g.operators) == 1
        assert len(g.strategies) == 1

    def test_rejects_global_knowledge_without_content_source(self):
        with pytest.raises(ValueError, match="carry content or representative_lcn"):
            GlobalCanonicalGraph(
                knowledges=[Knowledge(id="gcn_a", type="claim")],
            )
