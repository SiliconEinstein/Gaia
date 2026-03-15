"""Tests for LanceContentStore."""

from datetime import datetime

import pytest

from libs.storage.models import (
    BeliefSnapshot,
    CanonicalBinding,
    FactorNode,
    FactorParams,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    LocalCanonicalRef,
    PackageRef,
    PackageSubmissionArtifact,
    Parameter,
    SourceRef,
)


class TestInitialize:
    async def test_initialize_creates_tables(self, content_store):
        db = content_store._db
        tables = db.list_tables().tables
        expected = {
            "packages",
            "modules",
            "knowledge",
            "chains",
            "probabilities",
            "belief_history",
            "resources",
            "resource_attachments",
            "factors",
            "canonical_bindings",
            "global_canonical_nodes",
            "global_inference_state",
            "submission_artifacts",
        }
        assert expected.issubset(set(tables))


class TestWritePackage:
    async def test_write_and_get_package(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        pkg = await content_store.get_package("galileo_falling_bodies")
        assert pkg is not None
        assert pkg.package_id == "galileo_falling_bodies"
        assert pkg.status == "merged"
        assert "galileo_falling_bodies.setting" in pkg.modules

    async def test_get_nonexistent_package(self, content_store):
        pkg = await content_store.get_package("nonexistent")
        assert pkg is None

    async def test_write_and_get_module(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        mod = await content_store.get_module("galileo_falling_bodies.setting")
        assert mod is not None
        assert mod.name == "setting"
        assert mod.role == "setting"

    async def test_get_nonexistent_module(self, content_store):
        mod = await content_store.get_module("nonexistent")
        assert mod is None

    async def test_write_package_idempotent(self, content_store, packages, modules):
        """Writing the same package twice should not create duplicates."""
        await content_store.write_package(packages[0], modules)
        await content_store.write_package(packages[0], modules)
        # Should still return single package, not error or duplicate
        pkg = await content_store.get_package("galileo_falling_bodies")
        assert pkg is not None
        all_packages_table = content_store._db.open_table("packages")
        assert all_packages_table.count_rows() == 1
        all_modules_table = content_store._db.open_table("modules")
        assert all_modules_table.count_rows() == 2  # 2 unique modules, not 4


class TestWriteEmptyInputs:
    async def test_write_knowledge_empty(self, content_store):
        await content_store.write_knowledge([])  # should not raise

    async def test_write_chains_empty(self, content_store):
        await content_store.write_chains([])  # should not raise

    async def test_write_probabilities_empty(self, content_store):
        await content_store.write_probabilities([])  # should not raise

    async def test_write_belief_snapshots_empty(self, content_store):
        await content_store.write_belief_snapshots([])  # should not raise


class TestWriteKnowledge:
    async def test_write_and_get_knowledge(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        c = await content_store.get_knowledge(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert c is not None
        assert c.prior == pytest.approx(0.3)

    async def test_get_latest_version(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        v2 = knowledge_items[0].model_copy(update={"version": 2, "content": "updated content"})
        await content_store.write_knowledge([v2])
        latest = await content_store.get_knowledge(knowledge_items[0].knowledge_id)
        assert latest is not None
        assert latest.version == 2
        assert latest.content == "updated content"

    async def test_get_specific_version(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        c = await content_store.get_knowledge(knowledge_items[0].knowledge_id, version=1)
        assert c is not None
        assert c.version == 1

    async def test_get_nonexistent_knowledge(self, content_store):
        c = await content_store.get_knowledge("nonexistent")
        assert c is None

    async def test_get_nonexistent_specific_version(
        self, content_store, packages, modules, knowledge_items
    ):
        """get_knowledge with a specific version that doesn't exist should return None."""
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        c = await content_store.get_knowledge(knowledge_items[0].knowledge_id, version=999)
        assert c is None

    async def test_get_knowledge_versions(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        v2 = knowledge_items[0].model_copy(update={"version": 2})
        await content_store.write_knowledge([v2])
        versions = await content_store.get_knowledge_versions(knowledge_items[0].knowledge_id)
        assert len(versions) == 2
        assert versions[0].version == 1
        assert versions[1].version == 2

    async def test_skip_duplicate_knowledge(
        self, content_store, packages, modules, knowledge_items
    ):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_knowledge(knowledge_items)
        versions = await content_store.get_knowledge_versions(knowledge_items[0].knowledge_id)
        assert len(versions) == 1

    async def test_write_knowledge_upsert_updates_content(
        self, content_store, packages, modules, knowledge_items
    ):
        """Writing the same (knowledge_id, version) twice should update, not duplicate."""
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        updated = knowledge_items[0].model_copy(update={"content": "updated via upsert"})
        await content_store.write_knowledge([updated])
        k = await content_store.get_knowledge(knowledge_items[0].knowledge_id, version=1)
        assert k is not None
        assert k.content == "updated via upsert"
        # No duplicates
        versions = await content_store.get_knowledge_versions(knowledge_items[0].knowledge_id)
        assert len(versions) == 1


class TestWriteChains:
    async def test_write_and_get_chains_by_module(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        result = await content_store.get_chains_by_module("galileo_falling_bodies.reasoning")
        assert len(result) == 2
        chain_ids = {c.chain_id for c in result}
        assert "galileo_falling_bodies.reasoning.contradiction_chain" in chain_ids
        assert "galileo_falling_bodies.reasoning.verdict_chain" in chain_ids

    async def test_chain_steps_roundtrip(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        result = await content_store.get_chains_by_module("galileo_falling_bodies.reasoning")
        verdict = next(c for c in result if "verdict" in c.chain_id)
        assert len(verdict.steps) == 2
        assert verdict.steps[0].step_index == 0
        assert len(verdict.steps[0].premises) > 0
        assert verdict.steps[0].conclusion.knowledge_id != ""

    async def test_get_chains_empty_module(self, content_store):
        result = await content_store.get_chains_by_module("nonexistent")
        assert result == []


class TestProbabilities:
    async def test_write_and_get_history(self, content_store, probabilities):
        await content_store.write_probabilities(probabilities)
        history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain"
        )
        assert len(history) == 3

    async def test_filter_by_step_index(self, content_store, probabilities):
        await content_store.write_probabilities(probabilities)
        history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain", step_index=0
        )
        assert len(history) == 2
        assert all(r.step_index == 0 for r in history)

    async def test_empty_history(self, content_store):
        history = await content_store.get_probability_history("nonexistent")
        assert history == []


class TestBeliefs:
    async def test_write_and_get_history(self, content_store, beliefs):
        await content_store.write_belief_snapshots(beliefs)
        history = await content_store.get_belief_history(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert len(history) >= 1
        if len(history) > 1:
            assert history[0].computed_at <= history[1].computed_at

    async def test_empty_history(self, content_store):
        history = await content_store.get_belief_history("nonexistent")
        assert history == []


class TestResources:
    async def test_write_and_get_resources(self, content_store, resources, attachments):
        await content_store.write_resources(resources, attachments)
        result = await content_store.get_resources_for(
            "knowledge", "galileo_falling_bodies.reasoning.contradiction_result"
        )
        assert len(result) == 1
        assert result[0].type == "image"

    async def test_get_resources_for_chain_step(self, content_store, resources, attachments):
        await content_store.write_resources(resources, attachments)
        result = await content_store.get_resources_for(
            "chain_step", "galileo_falling_bodies.reasoning.contradiction_chain:0"
        )
        assert len(result) == 1

    async def test_get_resources_empty(self, content_store):
        result = await content_store.get_resources_for("knowledge", "nonexistent")
        assert result == []

    async def test_size_bytes_zero_roundtrip(self, content_store, attachments):
        """size_bytes=0 should survive roundtrip, not become None."""
        from libs.storage.models import Resource, ResourceAttachment

        res = Resource(
            resource_id="empty_file",
            type="other",
            format="bin",
            storage_backend="local",
            storage_path="/dev/null",
            size_bytes=0,
            metadata={},
            created_at="2026-01-01T00:00:00Z",
            source_package_id="test",
        )
        att = ResourceAttachment(
            resource_id="empty_file",
            target_type="knowledge",
            target_id="test_target",
            role="supplement",
        )
        await content_store.write_resources([res], [att])
        result = await content_store.get_resources_for("knowledge", "test_target")
        assert len(result) == 1
        assert result[0].size_bytes == 0


class TestDeletePackage:
    async def test_delete_package_removes_all_data(
        self, content_store, packages, modules, knowledge_items, chains
    ):
        """delete_package should remove knowledge, chains, and related records."""
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_chains(chains)

        pkg_id = knowledge_items[0].source_package_id
        await content_store.delete_package(pkg_id)

        # All knowledge gone
        for c in knowledge_items:
            assert await content_store.get_knowledge(c.knowledge_id) is None

        # All chains gone
        result = await content_store.get_chains_by_module(chains[0].module_id)
        assert len(result) == 0

    async def test_delete_package_removes_packages_and_modules(
        self, content_store, packages, modules, knowledge_items, chains
    ):
        """delete_package should also remove the package and module records."""
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_chains(chains)

        pkg_id = packages[0].package_id
        await content_store.delete_package(pkg_id)

        assert await content_store.get_package(pkg_id) is None
        for m in modules:
            assert await content_store.get_module(m.module_id) is None

    async def test_delete_package_is_idempotent(self, content_store):
        """Deleting a non-existent package should not raise."""
        await content_store.delete_package("nonexistent_pkg")  # should not raise

    async def test_delete_package_removes_slash_qualified_belief_history(self, content_store):
        """Current CLI knowledge IDs use `package/decl`, which must be deleted too."""
        knowledge = Knowledge(
            knowledge_id="galileo_falling_bodies/vacuum_prediction",
            version=1,
            type="claim",
            content="In a vacuum, fall rates are equal.",
            prior=0.7,
            source_package_id="galileo_falling_bodies",
            source_module_id="galileo_falling_bodies.reasoning",
            created_at=datetime(2026, 1, 1),
        )
        belief = BeliefSnapshot(
            knowledge_id=knowledge.knowledge_id,
            version=1,
            belief=0.9,
            bp_run_id="bp-run",
            computed_at=datetime(2026, 1, 2),
        )

        await content_store.write_knowledge([knowledge])
        await content_store.write_belief_snapshots([belief])
        await content_store.delete_package("galileo_falling_bodies")

        assert await content_store.get_knowledge(knowledge.knowledge_id) is None
        assert await content_store.get_belief_history(knowledge.knowledge_id) == []


class TestBM25Search:
    async def test_search_finds_relevant_knowledge(
        self, content_store, packages, modules, knowledge_items
    ):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        results = await content_store.search_bm25("heavier objects fall faster", top_k=5)
        assert len(results) >= 1
        ids = [r.knowledge.knowledge_id for r in results]
        assert any("heavier" in kid for kid in ids)

    async def test_search_respects_top_k(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        results = await content_store.search_bm25("falls", top_k=2)
        assert len(results) <= 2

    async def test_search_returns_scores(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        results = await content_store.search_bm25("experiment", top_k=5)
        if results:
            assert all(r.score > 0 for r in results)

    async def test_search_empty_table(self, content_store):
        results = await content_store.search_bm25("anything", top_k=5)
        assert results == []


class TestBPBulkLoad:
    async def test_list_knowledge(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        result = await content_store.list_knowledge()
        assert len(result) == 6

    async def test_list_chains(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        result = await content_store.list_chains()
        assert len(result) == 2

    async def test_list_knowledge_empty(self, content_store):
        result = await content_store.list_knowledge()
        assert result == []

    async def test_list_chains_empty(self, content_store):
        result = await content_store.list_chains()
        assert result == []


class TestFullFixtureRoundtrip:
    async def test_full_roundtrip(
        self,
        content_store,
        packages,
        modules,
        knowledge_items,
        chains,
        probabilities,
        beliefs,
        resources,
        attachments,
    ):
        # Write all fixture data
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_chains(chains)
        await content_store.write_probabilities(probabilities)
        await content_store.write_belief_snapshots(beliefs)
        await content_store.write_resources(resources, attachments)

        # Verify counts
        all_knowledge = await content_store.list_knowledge()
        assert len(all_knowledge) == 6
        all_chains = await content_store.list_chains()
        assert len(all_chains) == 2

        # Verify cross-references
        pkg = await content_store.get_package("galileo_falling_bodies")
        assert pkg is not None
        mod = await content_store.get_module("galileo_falling_bodies.reasoning")
        assert mod is not None
        chains_for_mod = await content_store.get_chains_by_module(mod.module_id)
        assert len(chains_for_mod) == 2

        # Verify probability history
        prob_history = await content_store.get_probability_history(
            "galileo_falling_bodies.reasoning.verdict_chain"
        )
        assert len(prob_history) == 3

        # Verify belief history
        belief_history = await content_store.get_belief_history(
            "galileo_falling_bodies.reasoning.heavier_falls_faster"
        )
        assert len(belief_history) >= 1

        # Verify BM25 search
        search_results = await content_store.search_bm25("heavier objects fall faster", top_k=10)
        assert len(search_results) >= 1

        # Verify resources
        res = await content_store.get_resources_for(
            "knowledge", "galileo_falling_bodies.reasoning.contradiction_result"
        )
        assert len(res) == 1


class TestCommitPackage:
    async def test_commit_flips_status(self, content_store, packages, modules):
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, modules)
        # Preparing package is invisible to get_package
        p = await content_store.get_package(pkg.package_id)
        assert p is None

        await content_store.commit_package(pkg.package_id, pkg.version)
        p = await content_store.get_package(pkg.package_id)
        assert p is not None
        assert p.status == "merged"

    async def test_get_committed_packages(self, content_store, packages, modules):
        # Write one committed, one preparing
        pkg1 = packages[0]  # status="merged"
        await content_store.write_package(pkg1, modules)

        pkg2 = packages[0].model_copy(update={"package_id": "preparing_pkg", "status": "preparing"})
        await content_store.write_package(pkg2, [])

        committed = await content_store.get_committed_packages()
        assert (pkg1.package_id, pkg1.version) in committed
        assert ("preparing_pkg", pkg2.version) not in committed


class TestVisibilityGate:
    async def test_preparing_package_invisible_to_get_package(
        self, content_store, packages, modules
    ):
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, [])
        assert await content_store.get_package(pkg.package_id) is None

    async def test_preparing_knowledge_invisible_to_get(
        self, content_store, packages, knowledge_items
    ):
        # Write a preparing package
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, [])
        # Write knowledge belonging to that preparing package
        await content_store.write_knowledge(knowledge_items)
        # Knowledge should be invisible
        assert await content_store.get_knowledge(knowledge_items[0].knowledge_id) is None

    async def test_preparing_knowledge_invisible_to_search(
        self, content_store, packages, knowledge_items
    ):
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, [])
        k = knowledge_items[0].model_copy(update={"content": "unique_invisible_content_xyz"})
        await content_store.write_knowledge([k])
        results = await content_store.search_bm25("unique_invisible_content_xyz", top_k=5)
        assert all(r.knowledge.knowledge_id != k.knowledge_id for r in results)

    async def test_committed_knowledge_visible(
        self, content_store, packages, modules, knowledge_items
    ):
        await content_store.write_package(packages[0], modules)  # status="merged"
        await content_store.write_knowledge(knowledge_items)
        k = await content_store.get_knowledge(knowledge_items[0].knowledge_id)
        assert k is not None

    async def test_list_knowledge_excludes_preparing(
        self, content_store, packages, modules, knowledge_items
    ):
        # Write committed package data
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        # Write knowledge for invisible package
        invisible_k = knowledge_items[0].model_copy(
            update={"source_package_id": "invisible_pkg", "knowledge_id": "invisible.k"}
        )
        await content_store.write_knowledge([invisible_k])
        all_k = await content_store.list_knowledge()
        assert all(ki.knowledge_id != "invisible.k" for ki in all_k)

    async def test_list_chains_excludes_preparing(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        # Add a chain for invisible package
        invisible_chain = chains[0].model_copy(
            update={"package_id": "invisible_pkg", "chain_id": "invisible.chain"}
        )
        await content_store.write_chains([invisible_chain])
        all_c = await content_store.list_chains()
        assert all(c.chain_id != "invisible.chain" for c in all_c)

    async def test_get_module_excludes_preparing(self, content_store, packages, modules):
        # Write preparing package with modules
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, modules)
        mod = await content_store.get_module(modules[0].module_id)
        assert mod is None

    async def test_get_chains_by_module_excludes_preparing(
        self, content_store, packages, modules, chains
    ):
        pkg = packages[0].model_copy(update={"status": "preparing"})
        await content_store.write_package(pkg, modules)
        await content_store.write_chains(chains)
        result = await content_store.get_chains_by_module(chains[0].module_id)
        assert len(result) == 0


# ── Task 4: Knowledge kind/parameters roundtrip ──


async def test_knowledge_kind_parameters_roundtrip(content_store, packages, modules):
    """Knowledge with kind and parameters survives write->read."""
    await content_store.write_package(packages[0], modules)
    k = Knowledge(
        knowledge_id="test/schema1",
        version=1,
        type="claim",
        kind="universal_law",
        content="For all A satisfying C: P(A)",
        parameters=[Parameter(name="A", constraint="any substance")],
        prior=0.5,
        source_package_id="galileo_falling_bodies",
        source_package_version="1.0.0",
        source_module_id="galileo_falling_bodies.setting",
        created_at=datetime.now(),
    )
    await content_store.write_knowledge([k])
    result = await content_store.get_knowledge("test/schema1", version=1)
    assert result is not None
    assert result.kind == "universal_law"
    assert len(result.parameters) == 1
    assert result.parameters[0].name == "A"
    assert result.is_schema is True


async def test_knowledge_kind_none_roundtrip(content_store, packages, modules):
    """Knowledge without kind/parameters defaults correctly."""
    await content_store.write_package(packages[0], modules)
    k = Knowledge(
        knowledge_id="test/ground1",
        version=1,
        type="claim",
        content="X is true",
        prior=0.7,
        source_package_id="galileo_falling_bodies",
        source_package_version="1.0.0",
        source_module_id="galileo_falling_bodies.setting",
        created_at=datetime.now(),
    )
    await content_store.write_knowledge([k])
    result = await content_store.get_knowledge("test/ground1", version=1)
    assert result is not None
    assert result.kind is None
    assert result.parameters == []
    assert result.is_schema is False


# ── Task 5: Factors table ──


async def test_write_and_list_factors(content_store):
    factors = [
        FactorNode(
            factor_id="pkg.mod.chain1",
            type="reasoning",
            premises=["pkg/k1", "pkg/k2"],
            contexts=["pkg/k3"],
            conclusion="pkg/k4",
            package_id="pkg",
            source_ref=SourceRef(
                package="pkg", version="1.0.0", module="pkg.mod", knowledge_name="k4"
            ),
        ),
        FactorNode(
            factor_id="pkg.mutex.1",
            type="mutex_constraint",
            premises=["pkg/k1", "pkg/k2"],
            conclusion="pkg/contra1",
            package_id="pkg",
        ),
    ]
    await content_store.write_factors(factors)
    result = await content_store.list_factors()
    assert len(result) == 2
    ids = {f.factor_id for f in result}
    assert ids == {"pkg.mod.chain1", "pkg.mutex.1"}


async def test_get_factors_by_package(content_store):
    factors = [
        FactorNode(
            factor_id="a.mod.chain1",
            type="reasoning",
            premises=["a/k1"],
            conclusion="a/k2",
            package_id="a",
        ),
        FactorNode(
            factor_id="b.mod.chain1",
            type="reasoning",
            premises=["b/k1"],
            conclusion="b/k2",
            package_id="b",
        ),
    ]
    await content_store.write_factors(factors)
    result = await content_store.get_factors_by_package("a")
    assert len(result) == 1
    assert result[0].factor_id == "a.mod.chain1"


async def test_factors_upsert_idempotent(content_store):
    f = FactorNode(
        factor_id="pkg.f1",
        type="instantiation",
        premises=["pkg/s1"],
        conclusion="pkg/g1",
        package_id="pkg",
    )
    await content_store.write_factors([f])
    await content_store.write_factors([f])
    result = await content_store.list_factors()
    assert len(result) == 1


# ── Task 6: Canonical bindings and global canonical nodes ──


async def test_write_and_get_canonical_bindings(content_store):
    bindings = [
        CanonicalBinding(
            package="pkg",
            version="1.0.0",
            local_graph_hash="sha256:abc",
            local_canonical_id="pkg/lc_k1",
            decision="create_new",
            global_canonical_id="gcn_01",
            decided_at=datetime.now(),
            decided_by="auto",
        ),
        CanonicalBinding(
            package="pkg",
            version="1.0.0",
            local_graph_hash="sha256:abc",
            local_canonical_id="pkg/lc_k2",
            decision="match_existing",
            global_canonical_id="gcn_02",
            decided_at=datetime.now(),
            decided_by="auto",
        ),
    ]
    await content_store.write_canonical_bindings(bindings)
    result = await content_store.get_canonical_bindings("pkg", "1.0.0")
    assert len(result) == 2
    ids = {b.local_canonical_id for b in result}
    assert ids == {"pkg/lc_k1", "pkg/lc_k2"}


async def test_canonical_bindings_upsert(content_store):
    b = CanonicalBinding(
        package="pkg",
        version="1.0.0",
        local_graph_hash="sha256:abc",
        local_canonical_id="pkg/lc_k1",
        decision="create_new",
        global_canonical_id="gcn_01",
        decided_at=datetime.now(),
        decided_by="auto",
    )
    await content_store.write_canonical_bindings([b])
    await content_store.write_canonical_bindings([b])
    result = await content_store.get_canonical_bindings("pkg", "1.0.0")
    assert len(result) == 1


async def test_write_and_get_global_canonical_node(content_store):
    node = GlobalCanonicalNode(
        global_canonical_id="gcn_01",
        knowledge_type="claim",
        representative_content="X is true",
        member_local_nodes=[
            LocalCanonicalRef(package="pkg", version="1.0.0", local_canonical_id="pkg/lc_k1")
        ],
        provenance=[PackageRef(package="pkg", version="1.0.0")],
    )
    await content_store.upsert_global_nodes([node])
    result = await content_store.get_global_node("gcn_01")
    assert result is not None
    assert result.knowledge_type == "claim"
    assert len(result.member_local_nodes) == 1


async def test_global_node_upsert_updates_existing(content_store):
    node1 = GlobalCanonicalNode(
        global_canonical_id="gcn_01",
        knowledge_type="claim",
        representative_content="X is true",
        member_local_nodes=[
            LocalCanonicalRef(package="p1", version="1.0.0", local_canonical_id="p1/lc1")
        ],
        provenance=[PackageRef(package="p1", version="1.0.0")],
    )
    await content_store.upsert_global_nodes([node1])
    node2 = node1.model_copy(
        update={
            "member_local_nodes": [
                LocalCanonicalRef(package="p1", version="1.0.0", local_canonical_id="p1/lc1"),
                LocalCanonicalRef(package="p2", version="1.0.0", local_canonical_id="p2/lc2"),
            ],
            "provenance": [
                PackageRef(package="p1", version="1.0.0"),
                PackageRef(package="p2", version="1.0.0"),
            ],
        }
    )
    await content_store.upsert_global_nodes([node2])
    result = await content_store.get_global_node("gcn_01")
    assert len(result.member_local_nodes) == 2


# ── Task 7: Global inference state and submission artifacts ──


async def test_write_and_get_inference_state(content_store):
    state = GlobalInferenceState(
        graph_hash="sha256:xyz",
        node_priors={"gcn_01": 0.7},
        factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
        node_beliefs={"gcn_01": 0.8},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state)
    result = await content_store.get_inference_state()
    assert result is not None
    assert result.graph_hash == "sha256:xyz"
    assert result.node_priors["gcn_01"] == 0.7
    assert result.factor_parameters["f1"].conditional_probability == 0.9
    assert result.node_beliefs["gcn_01"] == 0.8


async def test_inference_state_update_replaces(content_store):
    state1 = GlobalInferenceState(
        graph_hash="sha256:v1",
        node_priors={"gcn_01": 0.7},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state1)
    state2 = GlobalInferenceState(
        graph_hash="sha256:v2",
        node_priors={"gcn_01": 0.8, "gcn_02": 0.6},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state2)
    result = await content_store.get_inference_state()
    assert result.graph_hash == "sha256:v2"
    assert len(result.node_priors) == 2


async def test_inference_state_none_when_empty(content_store):
    result = await content_store.get_inference_state()
    assert result is None


async def test_write_and_get_submission_artifact(content_store):
    art = PackageSubmissionArtifact(
        package_name="pkg",
        commit_hash="abc123",
        source_files={"main.gaia": "knowledge { content: 'X' }"},
        raw_graph={"schema_version": "1.0", "knowledge_nodes": []},
        local_canonical_graph={"schema_version": "1.0", "knowledge_nodes": []},
        canonicalization_log=[{"local_canonical_id": "lc1", "members": ["r1"], "reason": "unique"}],
        submitted_at=datetime.now(),
    )
    await content_store.write_submission_artifact(art)
    result = await content_store.get_submission_artifact("pkg", "abc123")
    assert result is not None
    assert result.package_name == "pkg"
    assert result.source_files["main.gaia"] == "knowledge { content: 'X' }"


async def test_submission_artifact_not_found(content_store):
    result = await content_store.get_submission_artifact("nonexistent", "xxx")
    assert result is None


# ── List/Graph endpoints ──


class TestListEndpoints:
    async def test_list_packages_returns_merged(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        items, total = await content_store.list_packages()
        assert total >= 1
        ids = [p.package_id for p in items]
        assert packages[0].package_id in ids

    async def test_list_packages_excludes_preparing(self, content_store, packages):
        pkg = packages[0].model_copy(update={"status": "preparing", "package_id": "invisible_pkg"})
        await content_store.write_package(pkg, [])
        items, total = await content_store.list_packages()
        assert all(p.package_id != "invisible_pkg" for p in items)
        assert total == 0

    async def test_list_packages_pagination(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        items, total = await content_store.list_packages(page=1, page_size=1)
        assert total == 1
        assert len(items) == 1
        assert items[0].package_id == packages[0].package_id

    async def test_list_knowledge_paged(self, content_store, packages, modules, knowledge_items):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        items, total = await content_store.list_knowledge_paged(page=1, page_size=100)
        assert total == len(knowledge_items)
        assert len(items) == len(knowledge_items)

    async def test_list_knowledge_paged_type_filter(
        self, content_store, packages, modules, knowledge_items
    ):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        items, total = await content_store.list_knowledge_paged(
            page=1, page_size=100, type_filter="setting"
        )
        assert all(k.type == "setting" for k in items)
        assert total == sum(1 for k in knowledge_items if k.type == "setting")

    async def test_list_modules(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        result = await content_store.list_modules()
        assert len(result) == len(modules)
        module_ids = {m.module_id for m in result}
        for m in modules:
            assert m.module_id in module_ids

    async def test_list_modules_filtered_by_package(self, content_store, packages, modules):
        await content_store.write_package(packages[0], modules)
        result = await content_store.list_modules(package_id=packages[0].package_id)
        assert len(result) == len(modules)
        assert all(m.package_id == packages[0].package_id for m in result)

        result_missing = await content_store.list_modules(package_id="nonexistent_pkg")
        assert result_missing == []

    async def test_list_chains_paged(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        items, total = await content_store.list_chains_paged(page=1, page_size=100)
        assert total == len(chains)
        assert len(items) == len(chains)

    async def test_list_chains_paged_filtered_by_module(
        self, content_store, packages, modules, chains
    ):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        # All fixture chains belong to galileo_falling_bodies.reasoning
        items, total = await content_store.list_chains_paged(
            page=1, page_size=100, module_id="galileo_falling_bodies.reasoning"
        )
        assert total == len(chains)
        assert all(c.module_id == "galileo_falling_bodies.reasoning" for c in items)

        items_none, total_none = await content_store.list_chains_paged(
            page=1, page_size=100, module_id="nonexistent_module"
        )
        assert total_none == 0
        assert items_none == []

    async def test_get_chain(self, content_store, packages, modules, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_chains(chains)
        chain = await content_store.get_chain(chains[0].chain_id)
        assert chain is not None
        assert chain.chain_id == chains[0].chain_id

    async def test_get_chain_not_found(self, content_store):
        result = await content_store.get_chain("nonexistent_chain_id")
        assert result is None

    async def test_get_graph_data(self, content_store, packages, modules, knowledge_items, chains):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_chains(chains)
        data = await content_store.get_graph_data()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) == len(knowledge_items)
        # Edges should be produced for chain steps with valid premise→conclusion node pairs
        assert len(data["edges"]) > 0
        # Each node should have the required fields
        node = data["nodes"][0]
        assert "id" in node
        assert "knowledge_id" in node
        assert "version" in node
        assert "type" in node
        assert "content" in node
        assert "prior" in node
        # Each edge should have the required fields
        edge = data["edges"][0]
        assert "chain_id" in edge
        assert "from" in edge
        assert "to" in edge
        assert "chain_type" in edge
        assert "step_index" in edge

    async def test_get_graph_data_filtered_by_package(
        self, content_store, packages, modules, knowledge_items, chains
    ):
        await content_store.write_package(packages[0], modules)
        await content_store.write_knowledge(knowledge_items)
        await content_store.write_chains(chains)

        pkg_id = packages[0].package_id
        data = await content_store.get_graph_data(package_id=pkg_id)
        assert len(data["nodes"]) == len(knowledge_items)
        assert len(data["edges"]) > 0

        # Filter for a non-existent package should yield empty graph
        data_empty = await content_store.get_graph_data(package_id="nonexistent_pkg")
        assert data_empty["nodes"] == []
        assert data_empty["edges"] == []
