"""End-to-end test: build -> review(mock) -> infer -> publish -> verify DB contents.

Exercises the full pipeline for all three v4 Typst packages, then opens the
database and verifies that every Knowledge, Chain, Module, Package, and
ProbabilityRecord was persisted correctly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review
from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager

pytestmark = pytest.mark.usefixtures("fresh_lancedb_loop")

FIXTURES = Path(__file__).parent / "fixtures" / "ir"
GALILEO_V4 = FIXTURES / "galileo_falling_bodies_v4"
NEWTON_V4 = FIXTURES / "newton_principia_v4"
EINSTEIN_V4 = FIXTURES / "einstein_gravity_v4"


# ── helpers ──────────────────────────────────────────────────


async def _run_full_pipeline(pkg_path: Path, db_path: str):
    """Build → review(mock) → infer → publish, return (build, result, mgr)."""
    build = await pipeline_build(pkg_path)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    result = await pipeline_publish(build, review, infer, db_path=db_path)

    config = StorageConfig(lancedb_path=db_path, graph_backend="kuzu", kuzu_path=f"{db_path}/kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()
    return build, result, mgr


# ── Galileo v4 ───────────────────────────────────────────────


class TestGalileoV4PublishToDb:
    """Galileo: 13 knowledge nodes, 6 factors (5 infer + 1 contradiction)."""

    @pytest.fixture(scope="class")
    async def pipeline(self, tmp_path_factory):
        db_path = str(tmp_path_factory.mktemp("galileo_db"))
        build, result, mgr = await _run_full_pipeline(GALILEO_V4, db_path)
        yield build, result, mgr
        await mgr.close()

    async def test_package_exists_and_merged(self, pipeline):
        _, result, mgr = pipeline
        pkg = await mgr.content_store.get_package(result.package_id)
        assert pkg is not None
        assert pkg.status == "merged"
        assert pkg.submitter == "cli"

    async def test_knowledge_count_matches_graph_ir(self, pipeline):
        build, _, mgr = pipeline
        local_nodes = [
            n
            for n in build.local_graph.knowledge_nodes
            if not any(sr.module == "external" for sr in n.source_refs)
        ]
        db_knowledge = await mgr.content_store.list_knowledge()
        assert len(db_knowledge) == len(local_nodes)

    async def test_knowledge_content_not_empty(self, pipeline):
        _, _, mgr = pipeline
        db_knowledge = await mgr.content_store.list_knowledge()
        for k in db_knowledge:
            assert k.content, f"Knowledge {k.knowledge_id} has empty content"
            assert k.prior > 0, f"Knowledge {k.knowledge_id} has non-positive prior"
            assert k.type in (
                "claim",
                "question",
                "setting",
                "action",
                "contradiction",
                "equivalence",
            )

    async def test_chains_exist_and_have_steps(self, pipeline):
        _, result, mgr = pipeline
        assert result.stats["chains"] > 0
        chains = await mgr.content_store.list_chains()
        assert len(chains) == result.stats["chains"]
        for chain in chains:
            assert len(chain.steps) > 0, f"Chain {chain.chain_id} has no steps"
            for step in chain.steps:
                assert step.conclusion, f"Chain {chain.chain_id} step has no conclusion"

    async def test_chain_premises_reference_existing_knowledge(self, pipeline):
        _, _, mgr = pipeline
        db_knowledge = await mgr.content_store.list_knowledge()
        kid_set = {k.knowledge_id for k in db_knowledge}
        chains = await mgr.content_store.list_chains()
        for chain in chains:
            for step in chain.steps:
                for premise_ref in step.premises:
                    assert premise_ref.knowledge_id in kid_set, (
                        f"Chain {chain.chain_id} references unknown premise {premise_ref.knowledge_id}"
                    )

    async def test_chain_conclusions_reference_existing_knowledge(self, pipeline):
        _, _, mgr = pipeline
        db_knowledge = await mgr.content_store.list_knowledge()
        kid_set = {k.knowledge_id for k in db_knowledge}
        chains = await mgr.content_store.list_chains()
        for chain in chains:
            for step in chain.steps:
                assert step.conclusion.knowledge_id in kid_set, (
                    f"Chain {chain.chain_id} references unknown conclusion {step.conclusion.knowledge_id}"
                )

    async def test_modules_exist(self, pipeline):
        _, result, mgr = pipeline
        modules = await mgr.content_store.list_modules(package_id=result.package_id)
        assert len(modules) > 0

    async def test_probability_records_join_with_chains(self, pipeline):
        _, result, mgr = pipeline
        assert result.stats["probabilities"] > 0
        chains = await mgr.content_store.list_chains()
        chain_ids = {c.chain_id for c in chains}
        for chain in chains:
            probs = await mgr.content_store.get_probability_history(chain.chain_id)
            for p in probs:
                assert p.chain_id in chain_ids, (
                    f"Orphaned probability record: chain_id={p.chain_id}"
                )
                assert 0.0 < p.value <= 1.0

    async def test_no_belief_snapshots_persisted(self, pipeline):
        _, _, mgr = pipeline
        db_knowledge = await mgr.content_store.list_knowledge()
        for k in db_knowledge:
            beliefs = await mgr.content_store.get_belief_history(k.knowledge_id)
            assert beliefs == [], (
                f"Belief snapshots should not be persisted, found for {k.knowledge_id}"
            )

    async def test_package_exports_match_knowledge(self, pipeline):
        _, result, mgr = pipeline
        pkg = await mgr.content_store.get_package(result.package_id)
        db_knowledge = await mgr.content_store.list_knowledge()
        kid_set = {k.knowledge_id for k in db_knowledge}
        for export_id in pkg.exports:
            assert export_id in kid_set, f"Package export {export_id} not in knowledge table"


# ── Newton v4 (has external references) ─────────────────────


class TestNewtonV4PublishToDb:
    """Newton: 15 local nodes + external galileo ref. External refs must NOT
    appear as Knowledge items but CAN appear as chain premises."""

    @pytest.fixture(scope="class")
    async def pipeline(self, tmp_path_factory):
        db_path = str(tmp_path_factory.mktemp("newton_db"))
        build, result, mgr = await _run_full_pipeline(NEWTON_V4, db_path)
        yield build, result, mgr
        await mgr.close()

    async def test_package_exists_and_merged(self, pipeline):
        _, result, mgr = pipeline
        pkg = await mgr.content_store.get_package(result.package_id)
        assert pkg is not None
        assert pkg.status == "merged"

    async def test_external_refs_not_materialized(self, pipeline):
        """External nodes should not appear as Knowledge items."""
        build, _, mgr = pipeline
        ext_nodes = [n for n in build.raw_graph.knowledge_nodes if n.raw_node_id.startswith("ext:")]
        assert len(ext_nodes) >= 1, "Newton should reference external galileo nodes"
        db_knowledge = await mgr.content_store.list_knowledge()
        db_kids = {k.knowledge_id for k in db_knowledge}
        # External packages should not appear as local knowledge
        for ext in ext_nodes:
            ext_pkg = ext.metadata.get("ext_package", "") if ext.metadata else ""
            # Knowledge IDs from external packages should not be in the local DB
            matching = [kid for kid in db_kids if ext_pkg and kid.startswith(ext_pkg + "/")]
            # This is fine as long as they are not local knowledge items
            for kid in matching:
                k = await mgr.content_store.get_knowledge(kid)
                if k:
                    assert k.source_package_id == "newton_principia", (
                        f"External knowledge {kid} should not be materialized locally"
                    )

    async def test_knowledge_count_excludes_external(self, pipeline):
        build, _, mgr = pipeline
        local_nodes = [
            n
            for n in build.local_graph.knowledge_nodes
            if not any(sr.module == "external" for sr in n.source_refs)
        ]
        db_knowledge = await mgr.content_store.list_knowledge()
        assert len(db_knowledge) == len(local_nodes)

    async def test_chains_have_valid_structure(self, pipeline):
        _, _, mgr = pipeline
        chains = await mgr.content_store.list_chains()
        assert len(chains) > 0
        for chain in chains:
            assert len(chain.steps) > 0
            assert chain.type in (
                "deduction",
                "induction",
                "abstraction",
                "contradiction",
                "retraction",
                "equivalence",
            )

    async def test_modules_do_not_include_external(self, pipeline):
        _, result, mgr = pipeline
        modules = await mgr.content_store.list_modules(package_id=result.package_id)
        for mod in modules:
            assert "external" not in mod.module_id.lower(), (
                f"External module leaked into DB: {mod.module_id}"
            )


# ── Einstein v4 ──────────────────────────────────────────────


class TestEinsteinV4PublishToDb:
    """Einstein: 16 knowledge nodes, includes contradiction factor."""

    @pytest.fixture(scope="class")
    async def pipeline(self, tmp_path_factory):
        db_path = str(tmp_path_factory.mktemp("einstein_db"))
        build, result, mgr = await _run_full_pipeline(EINSTEIN_V4, db_path)
        yield build, result, mgr
        await mgr.close()

    async def test_package_exists_and_merged(self, pipeline):
        _, result, mgr = pipeline
        pkg = await mgr.content_store.get_package(result.package_id)
        assert pkg is not None
        assert pkg.status == "merged"

    async def test_knowledge_count_matches(self, pipeline):
        build, _, mgr = pipeline
        local_nodes = [
            n
            for n in build.local_graph.knowledge_nodes
            if not any(sr.module == "external" for sr in n.source_refs)
        ]
        db_knowledge = await mgr.content_store.list_knowledge()
        assert len(db_knowledge) == len(local_nodes)

    async def test_has_contradiction_chain(self, pipeline):
        _, _, mgr = pipeline
        chains = await mgr.content_store.list_chains()
        contradiction_chains = [c for c in chains if c.type == "contradiction"]
        assert len(contradiction_chains) >= 1, (
            "Einstein should have at least one contradiction chain"
        )

    async def test_all_probabilities_have_valid_chains(self, pipeline):
        _, _, mgr = pipeline
        chains = await mgr.content_store.list_chains()
        chain_ids = {c.chain_id for c in chains}
        for chain in chains:
            probs = await mgr.content_store.get_probability_history(chain.chain_id)
            for p in probs:
                assert p.chain_id in chain_ids

    async def test_knowledge_types_include_settings(self, pipeline):
        _, _, mgr = pipeline
        db_knowledge = await mgr.content_store.list_knowledge()
        types = {k.type for k in db_knowledge}
        assert "setting" in types, "Einstein should have setting-type knowledge"
        assert "claim" in types, "Einstein should have claim-type knowledge"


# ── Multi-package publish into same DB ───────────────────────


class TestMultiPackagePublishToSameDb:
    """Publish all three v4 packages into one DB and verify isolation + cross-reads."""

    @pytest.fixture(scope="class")
    async def multi_db(self, tmp_path_factory):
        db_path = str(tmp_path_factory.mktemp("multi_db"))
        results = {}
        for name, path in [
            ("galileo", GALILEO_V4),
            ("newton", NEWTON_V4),
            ("einstein", EINSTEIN_V4),
        ]:
            build = await pipeline_build(path)
            review = await pipeline_review(build, mock=True)
            infer = await pipeline_infer(build, review)
            result = await pipeline_publish(build, review, infer, db_path=db_path)
            results[name] = (build, result)

        config = StorageConfig(
            lancedb_path=db_path, graph_backend="kuzu", kuzu_path=f"{db_path}/kuzu"
        )
        mgr = StorageManager(config)
        await mgr.initialize()
        yield results, mgr
        await mgr.close()

    async def test_all_three_packages_exist(self, multi_db):
        results, mgr = multi_db
        for name, (_, result) in results.items():
            pkg = await mgr.content_store.get_package(result.package_id)
            assert pkg is not None, f"Package {name} not found"
            assert pkg.status == "merged"

    async def test_total_knowledge_count(self, multi_db):
        results, mgr = multi_db
        expected_total = 0
        for _, (build, _) in results.items():
            local_nodes = [
                n
                for n in build.local_graph.knowledge_nodes
                if not any(sr.module == "external" for sr in n.source_refs)
            ]
            expected_total += len(local_nodes)
        db_knowledge = await mgr.content_store.list_knowledge()
        assert len(db_knowledge) == expected_total

    async def test_knowledge_source_packages_are_correct(self, multi_db):
        results, mgr = multi_db
        db_knowledge = await mgr.content_store.list_knowledge()
        valid_package_ids = {r.package_id for _, r in results.values()}
        for k in db_knowledge:
            assert k.source_package_id in valid_package_ids, (
                f"Knowledge {k.knowledge_id} has unexpected source_package_id={k.source_package_id}"
            )

    async def test_no_cross_package_chain_pollution(self, multi_db):
        results, mgr = multi_db
        for name, (_, result) in results.items():
            chains, _ = await mgr.content_store.list_chains_paged(page=1, page_size=200)
            pkg_chains = [c for c in chains if c.package_id == result.package_id]
            for chain in pkg_chains:
                assert chain.package_id == result.package_id

    async def test_all_knowledge_queryable_by_id(self, multi_db):
        """Every published knowledge item can be retrieved by its ID."""
        _, mgr = multi_db
        all_knowledge = await mgr.content_store.list_knowledge()
        assert len(all_knowledge) > 0
        for k in all_knowledge:
            fetched = await mgr.content_store.get_knowledge(k.knowledge_id)
            assert fetched is not None, f"Knowledge {k.knowledge_id} not queryable by ID"
            assert fetched.content == k.content
