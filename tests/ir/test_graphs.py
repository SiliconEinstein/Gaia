"""Tests for LocalCanonicalGraph."""

from gaia.ir import (
    Knowledge,
    Operator,
    Strategy,
    LocalCanonicalGraph,
)

NS = "reg"
PKG = "test"


def _local_graph(**kwargs):
    """Helper to create a LocalCanonicalGraph with default namespace/package_name."""
    kwargs.setdefault("namespace", NS)
    kwargs.setdefault("package_name", PKG)
    return LocalCanonicalGraph(**kwargs)


class TestLocalCanonicalGraph:
    def test_auto_hash(self):
        g = _local_graph(
            knowledges=[Knowledge(id="reg:test::k1", type="claim", content="A")],
            strategies=[
                Strategy(
                    scope="local",
                    type="infer",
                    premises=["reg:test::k1"],
                    conclusion="reg:test::k1",
                )
            ],
        )
        assert g.ir_hash.startswith("sha256:")

    def test_deterministic_hash(self):
        def make():
            return _local_graph(
                knowledges=[Knowledge(id="reg:test::k1", type="claim", content="A")],
            )

        assert make().ir_hash == make().ir_hash

    def test_different_content_different_hash(self):
        g1 = _local_graph(knowledges=[Knowledge(id="reg:test::k1", type="claim", content="A")])
        g2 = _local_graph(knowledges=[Knowledge(id="reg:test::k1", type="claim", content="B")])
        assert g1.ir_hash != g2.ir_hash

    def test_with_operators(self):
        g = _local_graph(
            knowledges=[
                Knowledge(id="reg:test::a", type="claim"),
                Knowledge(id="reg:test::b", type="claim"),
                Knowledge(id="reg:test::eq", type="claim"),
            ],
            operators=[
                Operator(
                    operator="equivalence",
                    variables=["reg:test::a", "reg:test::b"],
                    conclusion="reg:test::eq",
                ),
            ],
        )
        assert len(g.operators) == 1

    def test_scope_default(self):
        g = _local_graph(knowledges=[])
        assert g.scope == "local"

    def test_hash_independent_of_entity_order(self):
        k1 = Knowledge(id="reg:test::k1", type="claim", content="A")
        k2 = Knowledge(id="reg:test::k2", type="claim", content="B")
        s = Strategy(
            scope="local",
            type="infer",
            premises=["reg:test::k1"],
            conclusion="reg:test::k2",
        )

        g1 = _local_graph(knowledges=[k1, k2], strategies=[s])
        g2 = _local_graph(knowledges=[k2, k1], strategies=[s])

        assert g1.ir_hash == g2.ir_hash

    def test_local_graph_auto_assigns_qid(self):
        """Knowledge with label but no id gets QID from graph."""
        g = _local_graph(
            knowledges=[
                Knowledge(label="alpha", type="claim", content="Alpha claim"),
                Knowledge(label="beta", type="setting", content="Beta setting"),
            ],
        )
        assert g.knowledges[0].id == "reg:test::alpha"
        assert g.knowledges[1].id == "reg:test::beta"

    def test_local_graph_preserves_explicit_id(self):
        """Knowledge with explicit id is not overwritten by auto-assign."""
        g = _local_graph(
            knowledges=[
                Knowledge(
                    id="custom:pkg::explicit",
                    label="explicit",
                    type="claim",
                    content="Explicit ID",
                ),
            ],
        )
        assert g.knowledges[0].id == "custom:pkg::explicit"

    def test_namespace_and_package_name_required(self):
        """LocalCanonicalGraph requires namespace and package_name."""
        g = _local_graph(knowledges=[])
        assert g.namespace == NS
        assert g.package_name == PKG
