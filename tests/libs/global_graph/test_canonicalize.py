"""Tests for global canonicalization logic."""

from pathlib import Path

from libs.global_graph.canonicalize import canonicalize_package
from libs.global_graph.models import (
    GlobalCanonicalNode,
    GlobalGraph,
    LocalCanonicalRef,
    PackageRef,
)
from libs.global_graph.serialize import load_global_graph, save_global_graph
from libs.graph_ir.models import (
    FactorNode,
    FactorParams,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    LocalParameterization,
    SourceRef,
)


def _lcn(lcn_id: str, content: str, ktype: str = "claim", pkg: str = "test_pkg"):
    return LocalCanonicalNode(
        local_canonical_id=lcn_id,
        package=pkg,
        knowledge_type=ktype,
        representative_content=content,
        member_raw_node_ids=[f"raw_{lcn_id[4:]}"],
        source_refs=[SourceRef(package=pkg, version="1.0.0", module="core", knowledge_name=lcn_id)],
    )


def _local_graph(nodes, factors=None, pkg="test_pkg"):
    return LocalCanonicalGraph(
        package=pkg,
        version="1.0.0",
        knowledge_nodes=nodes,
        factor_nodes=factors or [],
    )


def _local_params(nodes, factors=None):
    priors = {n.local_canonical_id: 0.5 for n in nodes}
    fparams = {}
    for f in factors or []:
        if f.type == "infer":
            fparams[f.factor_id] = FactorParams(conditional_probability=0.9)
    return LocalParameterization(
        graph_hash="sha256:test", node_priors=priors, factor_parameters=fparams
    )


class TestCanonicalizeFirstPackage:
    async def test_all_create_new_on_empty_global(self):
        nodes = [
            _lcn("lcn_a", "Free fall acceleration is independent of mass"),
            _lcn("lcn_b", "Superconductivity occurs below critical temperature"),
        ]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, GlobalGraph())

        assert len(result.bindings) == 2
        assert all(b.decision == "create_new" for b in result.bindings)
        assert len(result.new_global_nodes) == 2
        assert len(result.matched_global_nodes) == 0

    async def test_global_ids_are_assigned(self):
        nodes = [_lcn("lcn_a", "Claim A")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, GlobalGraph())

        gcn = result.new_global_nodes[0]
        assert gcn.global_canonical_id.startswith("gcn_")
        assert gcn.knowledge_type == "claim"
        assert gcn.representative_content == "Claim A"
        assert len(gcn.member_local_nodes) == 1
        assert gcn.member_local_nodes[0].local_canonical_id == "lcn_a"

    async def test_source_knowledge_names_stored(self):
        nodes = [_lcn("lcn_a", "Claim A")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, GlobalGraph())

        gcn = result.new_global_nodes[0]
        names = gcn.metadata.get("source_knowledge_names", [])
        assert "test_pkg.lcn_a" in names


class TestCanonicalizeWithExistingGlobal:
    async def test_match_existing_high_similarity(self):
        existing = GlobalCanonicalNode(
            global_canonical_id="gcn_existing",
            knowledge_type="claim",
            representative_content="Free fall acceleration is independent of mass",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_old", version="1.0.0", local_canonical_id="lcn_old"),
            ],
        )
        global_graph = GlobalGraph(knowledge_nodes=[existing])

        nodes = [_lcn("lcn_new", "Free fall acceleration is independent of mass")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, global_graph)

        matched = [b for b in result.bindings if b.decision == "match_existing"]
        assert len(matched) == 1
        assert matched[0].global_canonical_id == "gcn_existing"

    async def test_create_new_low_similarity(self):
        existing = GlobalCanonicalNode(
            global_canonical_id="gcn_existing",
            knowledge_type="claim",
            representative_content="Superconductivity requires low temperature",
        )
        global_graph = GlobalGraph(knowledge_nodes=[existing])

        nodes = [_lcn("lcn_new", "Photosynthesis produces oxygen")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, global_graph)

        assert all(b.decision == "create_new" for b in result.bindings)

    async def test_matched_node_gets_new_member(self):
        existing = GlobalCanonicalNode(
            global_canonical_id="gcn_existing",
            knowledge_type="claim",
            representative_content="Free fall acceleration is independent of mass",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_old", version="1.0.0", local_canonical_id="lcn_old"),
            ],
            provenance=[],
        )
        global_graph = GlobalGraph(knowledge_nodes=[existing])

        nodes = [_lcn("lcn_new", "Free fall acceleration is independent of mass")]
        local = _local_graph(nodes)
        params = _local_params(nodes)

        await canonicalize_package(local, params, global_graph)

        assert len(existing.member_local_nodes) == 2
        assert existing.member_local_nodes[1].local_canonical_id == "lcn_new"


class TestFactorIntegration:
    async def test_local_factors_lifted_to_global(self):
        nodes = [
            _lcn("lcn_p", "Premise P"),
            _lcn("lcn_c", "Conclusion C"),
        ]
        factor = FactorNode(
            factor_id="f_test",
            type="infer",
            premises=["lcn_p"],
            conclusion="lcn_c",
            metadata={"edge_type": "deduction"},
        )
        local = _local_graph(nodes, [factor])
        params = _local_params(nodes, [factor])

        result = await canonicalize_package(local, params, GlobalGraph())

        assert len(result.global_factors) == 1
        gf = result.global_factors[0]
        assert gf.factor_id == "f_test"
        assert all(p.startswith("gcn_") for p in gf.premises)
        assert gf.conclusion.startswith("gcn_")

    async def test_ext_refs_resolved_against_global(self):
        # Simulate: pkg_a already canonicalized, pkg_b references pkg_a
        gcn_target = GlobalCanonicalNode(
            global_canonical_id="gcn_target",
            knowledge_type="claim",
            representative_content="Target claim from package A",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg_a", version="1.0.0", local_canonical_id="lcn_t"),
            ],
            provenance=[PackageRef(package="pkg_a", version="1.0.0")],
            metadata={"source_knowledge_names": ["pkg_a.target_claim"]},
        )
        global_graph = GlobalGraph(knowledge_nodes=[gcn_target])

        # pkg_b has a local node + a factor referencing ext:pkg_a.target_claim
        nodes = [_lcn("lcn_local", "Local claim from B", pkg="pkg_b")]
        factor = FactorNode(
            factor_id="f_cross",
            type="equivalence",
            premises=["lcn_local", "ext:pkg_a.target_claim"],
            conclusion="lcn_local",  # simplified
            metadata={"edge_type": "relation_equivalence"},
        )
        local = _local_graph(nodes, [factor], pkg="pkg_b")
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, global_graph)

        # The factor should be resolved — ext: replaced with gcn_target
        assert len(result.global_factors) == 1
        gf = result.global_factors[0]
        assert "gcn_target" in gf.premises
        assert len(result.unresolved_cross_refs) == 0

    async def test_unresolved_ext_ref_tracked(self):
        # No matching global node for the ext: ref
        nodes = [_lcn("lcn_local", "Local claim")]
        factor = FactorNode(
            factor_id="f_broken",
            type="infer",
            premises=["lcn_local", "ext:unknown_pkg.missing_node"],
            conclusion="lcn_local",
            metadata={"edge_type": "deduction"},
        )
        local = _local_graph(nodes, [factor])
        params = _local_params(nodes)

        result = await canonicalize_package(local, params, GlobalGraph())

        # Factor not generated (unresolved premise)
        assert len(result.global_factors) == 0
        assert "ext:unknown_pkg.missing_node" in result.unresolved_cross_refs

    async def test_contexts_optional_not_blocking(self):
        nodes = [
            _lcn("lcn_p", "Premise"),
            _lcn("lcn_c", "Conclusion"),
        ]
        # Factor with an ext: context — should still generate even if context unresolved
        factor = FactorNode(
            factor_id="f_ctx",
            type="infer",
            premises=["lcn_p"],
            contexts=["ext:other_pkg.optional_context"],
            conclusion="lcn_c",
            metadata={"edge_type": "deduction"},
        )
        local = _local_graph(nodes, [factor])
        params = _local_params(nodes, [factor])

        result = await canonicalize_package(local, params, GlobalGraph())

        # Factor generated — unresolved context is dropped, not blocking
        assert len(result.global_factors) == 1
        assert result.global_factors[0].contexts == []

    async def test_multiple_factors_mixed_resolution(self):
        gcn_ext = GlobalCanonicalNode(
            global_canonical_id="gcn_ext",
            knowledge_type="claim",
            representative_content="External claim",
            metadata={"source_knowledge_names": ["ext_pkg.ext_claim"]},
        )
        global_graph = GlobalGraph(knowledge_nodes=[gcn_ext])

        nodes = [
            _lcn("lcn_a", "Claim A"),
            _lcn("lcn_b", "Claim B"),
        ]
        factors = [
            # Fully local — should resolve
            FactorNode(
                factor_id="f_local",
                type="infer",
                premises=["lcn_a"],
                conclusion="lcn_b",
                metadata={"edge_type": "deduction"},
            ),
            # Cross-package resolvable — should resolve
            FactorNode(
                factor_id="f_cross_ok",
                type="infer",
                premises=["lcn_a", "ext:ext_pkg.ext_claim"],
                conclusion="lcn_b",
                metadata={"edge_type": "deduction"},
            ),
            # Cross-package unresolvable — should fail
            FactorNode(
                factor_id="f_cross_fail",
                type="infer",
                premises=["lcn_a", "ext:missing.node"],
                conclusion="lcn_b",
                metadata={"edge_type": "deduction"},
            ),
        ]
        local = _local_graph(nodes, factors)
        params = _local_params(nodes, factors)

        result = await canonicalize_package(local, params, global_graph)

        assert len(result.global_factors) == 2  # f_local + f_cross_ok
        factor_ids = {f.factor_id for f in result.global_factors}
        assert "f_local" in factor_ids
        assert "f_cross_ok" in factor_ids
        assert "f_cross_fail" not in factor_ids
        assert "ext:missing.node" in result.unresolved_cross_refs


class TestSerialization:
    def test_round_trip(self, tmp_path: Path):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_001",
            knowledge_type="claim",
            representative_content="Test",
            metadata={"source_knowledge_names": ["pkg.test"]},
        )
        graph = GlobalGraph(knowledge_nodes=[node])

        save_global_graph(graph, tmp_path)
        loaded = load_global_graph(tmp_path / "global_graph.json")

        assert len(loaded.knowledge_nodes) == 1
        assert loaded.knowledge_nodes[0].global_canonical_id == "gcn_001"
        assert loaded.knowledge_nodes[0].metadata["source_knowledge_names"] == ["pkg.test"]

    def test_load_nonexistent_returns_empty(self, tmp_path: Path):
        loaded = load_global_graph(tmp_path / "nonexistent.json")
        assert len(loaded.knowledge_nodes) == 0
        assert len(loaded.factor_nodes) == 0
