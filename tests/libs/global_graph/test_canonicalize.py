"""Tests for global canonicalization logic."""

from libs.global_graph.canonicalize import canonicalize_package
from libs.global_graph.models import (
    GlobalCanonicalNode,
    GlobalGraph,
    LocalCanonicalRef,
)
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
        if f.type == "reasoning":
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
    async def test_factors_get_bindings(self):
        nodes = [
            _lcn("lcn_p", "Premise P"),
            _lcn("lcn_c", "Conclusion C"),
        ]
        factor = FactorNode(
            factor_id="f_test",
            type="reasoning",
            premises=["lcn_p"],
            conclusion="lcn_c",
            metadata={"edge_type": "deduction"},
        )
        local = _local_graph(nodes, [factor])
        params = _local_params(nodes, [factor])

        result = await canonicalize_package(local, params, GlobalGraph())

        lcn_to_gcn = {b.local_canonical_id: b.global_canonical_id for b in result.bindings}
        assert "lcn_p" in lcn_to_gcn
        assert "lcn_c" in lcn_to_gcn
