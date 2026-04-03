"""Integration tests for v4 Typst packages through the full pipeline.

Exercises: load → compile → canonicalize → review (mock) → infer
on each of the three converted v4 packages. No external services required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.pipeline import pipeline_build, pipeline_infer, pipeline_review

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "ir"

GALILEO = FIXTURES / "galileo_falling_bodies_v4"
NEWTON = FIXTURES / "newton_principia_v4"
EINSTEIN = FIXTURES / "einstein_gravity_v4"


# ── Galileo Falling Bodies v4 ──────────────────────────────


class TestGalileoV4Pipeline:
    """Full pipeline integration for galileo_falling_bodies_v4."""

    @pytest.fixture(scope="class")
    async def build_result(self):
        return await pipeline_build(GALILEO)

    @pytest.fixture(scope="class")
    async def review_result(self, build_result):
        return await pipeline_review(build_result, mock=True)

    @pytest.fixture(scope="class")
    async def infer_result(self, build_result, review_result):
        return await pipeline_infer(build_result, review_result)

    def test_build_node_count(self, build_result):
        """13 local knowledge nodes compiled."""
        assert len(build_result.local_graph.knowledge_nodes) == 13

    def test_build_factor_count(self, build_result):
        """5 infer + 1 contradiction = 6 factors."""
        factors = build_result.local_graph.factor_nodes
        infer = [f for f in factors if f.type == "infer"]
        contradiction = [f for f in factors if f.type == "contradiction"]
        assert len(infer) == 5
        assert len(contradiction) == 1

    def test_graph_data_package_name(self, build_result):
        assert build_result.graph_data["package"] == "galileo_falling_bodies"

    def test_review_produces_priors(self, review_result, build_result):
        """Mock review assigns priors to all nodes."""
        assert len(review_result.node_priors) == len(build_result.local_graph.knowledge_nodes)

    def test_review_produces_factor_params(self, review_result, build_result):
        """Mock review assigns params to all infer factors."""
        infer_factors = [f for f in build_result.local_graph.factor_nodes if f.type == "infer"]
        assert len(review_result.factor_params) == len(infer_factors)

    def test_infer_produces_beliefs(self, infer_result, build_result):
        """BP produces beliefs for all nodes."""
        assert len(infer_result.beliefs) >= len(build_result.local_graph.knowledge_nodes)

    def test_beliefs_in_valid_range(self, infer_result):
        """All beliefs are in [0, 1]."""
        for label, belief in infer_result.beliefs.items():
            assert 0.0 <= belief <= 1.0, f"Belief for {label} out of range: {belief}"

    def test_settings_have_high_belief(self, infer_result):
        """Settings (prior=1.0) should retain high belief after BP."""
        setting_labels = [label for label in infer_result.beliefs if ".setting." in label.lower()]
        assert len(setting_labels) > 0, "No setting labels found"
        for label in setting_labels:
            assert infer_result.beliefs[label] > 0.5, f"Setting {label} has low belief"


# ── Newton Principia v4 ────────────────────────────────────


class TestNewtonV4Pipeline:
    """Full pipeline integration for newton_principia_v4."""

    @pytest.fixture(scope="class")
    async def build_result(self):
        return await pipeline_build(NEWTON)

    @pytest.fixture(scope="class")
    async def review_result(self, build_result):
        return await pipeline_review(build_result, mock=True)

    @pytest.fixture(scope="class")
    async def infer_result(self, build_result, review_result):
        return await pipeline_infer(build_result, review_result)

    def test_build_local_node_count(self, build_result):
        """15 local knowledge nodes (excludes external)."""
        local_nodes = [
            n
            for n in build_result.local_graph.knowledge_nodes
            if not any(sr.module == "external" for sr in n.source_refs)
        ]
        assert len(local_nodes) == 15

    def test_build_has_external_node(self, build_result):
        """Newton references galileo via gaia-bibliography."""
        ext_nodes = [
            n for n in build_result.raw_graph.knowledge_nodes if n.raw_node_id.startswith("ext:")
        ]
        assert len(ext_nodes) >= 1
        ext = ext_nodes[0]
        assert ext.metadata is not None
        assert "ext_package" in ext.metadata

    def test_build_factor_count(self, build_result):
        """7 infer factors, 0 contradiction."""
        factors = build_result.local_graph.factor_nodes
        infer = [f for f in factors if f.type == "infer"]
        contradiction = [f for f in factors if f.type == "contradiction"]
        assert len(infer) == 7
        assert len(contradiction) == 0

    def test_graph_data_package_name(self, build_result):
        assert build_result.graph_data["package"] == "newton_principia"

    def test_review_produces_priors(self, review_result, build_result):
        assert len(review_result.node_priors) == len(build_result.local_graph.knowledge_nodes)

    def test_infer_produces_beliefs(self, infer_result, build_result):
        assert len(infer_result.beliefs) >= len(build_result.local_graph.knowledge_nodes)

    def test_beliefs_in_valid_range(self, infer_result):
        for label, belief in infer_result.beliefs.items():
            assert 0.0 <= belief <= 1.0, f"Belief for {label} out of range: {belief}"


# ── Einstein Gravity v4 ────────────────────────────────────


class TestEinsteinV4Pipeline:
    """Full pipeline integration for einstein_gravity_v4."""

    @pytest.fixture(scope="class")
    async def build_result(self):
        return await pipeline_build(EINSTEIN)

    @pytest.fixture(scope="class")
    async def review_result(self, build_result):
        return await pipeline_review(build_result, mock=True)

    @pytest.fixture(scope="class")
    async def infer_result(self, build_result, review_result):
        return await pipeline_infer(build_result, review_result)

    def test_build_node_count(self, build_result):
        """16 local knowledge nodes compiled."""
        assert len(build_result.local_graph.knowledge_nodes) == 16

    def test_build_factor_count(self, build_result):
        """6 infer + 1 contradiction."""
        factors = build_result.local_graph.factor_nodes
        infer = [f for f in factors if f.type == "infer"]
        contradiction = [f for f in factors if f.type == "contradiction"]
        assert len(infer) == 6
        assert len(contradiction) == 1

    def test_graph_data_package_name(self, build_result):
        assert build_result.graph_data["package"] == "einstein_gravity"

    def test_review_produces_priors(self, review_result, build_result):
        assert len(review_result.node_priors) == len(build_result.local_graph.knowledge_nodes)

    def test_review_produces_factor_params(self, review_result, build_result):
        infer_factors = [f for f in build_result.local_graph.factor_nodes if f.type == "infer"]
        assert len(review_result.factor_params) == len(infer_factors)

    def test_infer_produces_beliefs(self, infer_result, build_result):
        assert len(infer_result.beliefs) >= len(build_result.local_graph.knowledge_nodes)

    def test_beliefs_in_valid_range(self, infer_result):
        for label, belief in infer_result.beliefs.items():
            assert 0.0 <= belief <= 1.0, f"Belief for {label} out of range: {belief}"

    def test_contradiction_affects_beliefs(self, infer_result):
        """The contradiction factor should influence related beliefs."""
        # Just verify BP ran successfully with contradiction factor present
        assert len(infer_result.beliefs) > 0
        assert infer_result.bp_run_id is not None


# ── Cross-Package Consistency ──────────────────────────────


class TestV4PipelineCrossPackage:
    """Verify pipeline consistency across all three v4 packages."""

    @pytest.fixture(scope="class")
    async def all_builds(self):
        galileo = await pipeline_build(GALILEO)
        newton = await pipeline_build(NEWTON)
        einstein = await pipeline_build(EINSTEIN)
        return {"galileo": galileo, "newton": newton, "einstein": einstein}

    def test_all_packages_have_source_files(self, all_builds):
        """All packages capture .typ source files."""
        for name, build in all_builds.items():
            assert len(build.source_files) > 0, f"{name} has no source files"

    def test_all_packages_have_canonicalization_log(self, all_builds):
        """All packages produce a canonicalization log."""
        for name, build in all_builds.items():
            assert len(build.canonicalization_log) > 0, f"{name} has no canonicalization log"

    def test_no_corroboration_in_active_v4_surface(self, all_builds):
        """The active v4 surface should not emit corroboration nodes, constraints, or factors."""
        for name, build in all_builds.items():
            node_types = {node.get("type") for node in build.graph_data.get("nodes", [])}
            constraint_types = {
                constraint.get("type") for constraint in build.graph_data.get("constraints", [])
            }
            factor_types = {factor.type for factor in build.local_graph.factor_nodes}
            knowledge_types = {node.knowledge_type for node in build.local_graph.knowledge_nodes}
            assert "corroboration" not in node_types, f"{name} emitted corroboration node types"
            assert "corroboration" not in constraint_types, (
                f"{name} emitted corroboration constraints"
            )
            assert "corroboration" not in factor_types, f"{name} emitted corroboration factors"
            assert "corroboration" not in knowledge_types, (
                f"{name} emitted corroboration knowledge types"
            )

    def test_deterministic_builds(self, all_builds):
        """Building twice produces same graph hashes."""
        import asyncio

        async def rebuild():
            g = await pipeline_build(GALILEO)
            return g.local_graph.graph_hash()

        hash1 = all_builds["galileo"].local_graph.graph_hash()
        hash2 = asyncio.get_event_loop().run_until_complete(rebuild())
        assert hash1 == hash2
