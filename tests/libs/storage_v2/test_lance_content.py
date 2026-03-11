"""Tests for LanceContentStore."""

import pytest


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
        from libs.storage_v2.models import Resource, ResourceAttachment

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

        await content_store.commit_package(pkg.package_id)
        p = await content_store.get_package(pkg.package_id)
        assert p is not None
        assert p.status == "merged"

    async def test_get_committed_package_ids(self, content_store, packages, modules):
        # Write one committed, one preparing
        pkg1 = packages[0]  # status="merged"
        await content_store.write_package(pkg1, modules)

        pkg2 = packages[0].model_copy(update={"package_id": "preparing_pkg", "status": "preparing"})
        await content_store.write_package(pkg2, [])

        committed = await content_store.get_committed_package_ids()
        assert pkg1.package_id in committed
        assert "preparing_pkg" not in committed


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
