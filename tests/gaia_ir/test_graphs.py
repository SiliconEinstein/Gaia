"""Tests for LocalCanonicalGraph and GlobalCanonicalGraph."""

from gaia.gaia_ir import (
    Knowledge,
    Operator,
    Strategy,
    LocalCanonicalGraph,
    GlobalCanonicalGraph,
)


class TestLocalCanonicalGraph:
    def test_auto_hash(self):
        g = LocalCanonicalGraph(
            knowledges=[Knowledge(id="lcn_1", type="claim", content="A")],
            strategies=[Strategy(scope="local", type="infer", premises=["lcn_1"], conclusion="lcn_1")],
        )
        assert g.ir_hash.startswith("sha256:")

    def test_deterministic_hash(self):
        def make():
            return LocalCanonicalGraph(
                knowledges=[Knowledge(id="lcn_1", type="claim", content="A")],
            )
        assert make().ir_hash == make().ir_hash

    def test_different_content_different_hash(self):
        g1 = LocalCanonicalGraph(knowledges=[Knowledge(id="lcn_1", type="claim", content="A")])
        g2 = LocalCanonicalGraph(knowledges=[Knowledge(id="lcn_1", type="claim", content="B")])
        assert g1.ir_hash != g2.ir_hash

    def test_with_operators(self):
        g = LocalCanonicalGraph(
            knowledges=[
                Knowledge(id="lcn_a", type="claim"),
                Knowledge(id="lcn_b", type="claim"),
            ],
            operators=[
                Operator(operator="equivalence", variables=["lcn_a", "lcn_b"]),
            ],
        )
        assert len(g.operators) == 1

    def test_scope_default(self):
        g = LocalCanonicalGraph(knowledges=[])
        assert g.scope == "local"


class TestGlobalCanonicalGraph:
    def test_no_hash(self):
        """Global graph is incremental — no overall hash."""
        g = GlobalCanonicalGraph(
            knowledges=[Knowledge(id="gcn_1", type="claim")],
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
            knowledges=[Knowledge(id="gcn_a", type="claim"), Knowledge(id="gcn_b", type="claim")],
            operators=[Operator(operator="equivalence", variables=["gcn_a", "gcn_b"])],
            strategies=[Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")],
        )
        assert len(g.knowledges) == 2
        assert len(g.operators) == 1
        assert len(g.strategies) == 1
