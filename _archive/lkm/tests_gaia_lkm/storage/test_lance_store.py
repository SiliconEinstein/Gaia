"""Integration tests for LanceContentStore — real LanceDB, tmp_path."""

import pytest

from gaia.lkm.models import (
    CanonicalBinding,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    Step,
    compute_content_hash,
    new_gcn_id,
)
from gaia.lkm.storage import StorageConfig, StorageManager


@pytest.fixture
async def storage(tmp_path):
    """Create a StorageManager with a fresh LanceDB in tmp_path."""
    config = StorageConfig(lancedb_path=str(tmp_path / "test_lkm.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


def _make_local_var(
    label: str,
    content: str,
    package: str,
    type_: str = "claim",
    visibility: str = "public",
    version: str = "1.0.0",
) -> LocalVariableNode:
    """Helper to construct a LocalVariableNode with computed content_hash."""
    qid = f"github:{package}::{label}"
    ch = compute_content_hash(type_, content, [])
    return LocalVariableNode(
        id=qid,
        type=type_,
        visibility=visibility,
        content=content,
        content_hash=ch,
        parameters=[],
        source_package=package,
        version=version,
    )


class TestTableCreation:
    async def test_all_8_tables_created(self, storage):
        tables = set(storage.content._db.list_tables().tables)
        expected = {
            "local_variable_nodes",
            "local_factor_nodes",
            "global_variable_nodes",
            "global_factor_nodes",
            "canonical_bindings",
            "prior_records",
            "factor_param_records",
            "param_sources",
        }
        assert expected.issubset(tables)


class TestIngestVisibility:
    async def test_preparing_nodes_invisible(self, storage):
        """Nodes with ingest_status='preparing' should not be returned by reads."""
        node = _make_local_var("claim1", "test content", "pkg_a")
        await storage.ingest_local_graph("pkg_a", "1.0.0", [node], [])

        result = await storage.get_local_variable("github:pkg_a::claim1")
        assert result is None

    async def test_merged_nodes_visible(self, storage):
        """After commit, nodes should be visible."""
        node = _make_local_var("claim1", "test content", "pkg_a")
        await storage.ingest_local_graph("pkg_a", "1.0.0", [node], [])
        await storage.commit_package("pkg_a", "1.0.0")

        result = await storage.get_local_variable("github:pkg_a::claim1")
        assert result is not None
        assert result.content == "test content"
        assert result.id == "github:pkg_a::claim1"


class TestContentHashDedup:
    async def test_find_global_by_content_hash(self, storage):
        """content_hash lookup must work for dedup."""
        content = "Objects fall at equal rates in vacuum"
        ch = compute_content_hash("claim", content, [])
        gcn_id = new_gcn_id()
        ref = LocalCanonicalRef(
            local_id="github:galileo::vac", package_id="galileo", version="1.0.0"
        )

        global_var = GlobalVariableNode(
            id=gcn_id,
            type="claim",
            visibility="public",
            content_hash=ch,
            parameters=[],
            representative_lcn=ref,
            local_members=[ref],
        )
        await storage.integrate_global_graph([global_var], [], [])

        found = await storage.find_global_by_content_hash(ch)
        assert found is not None
        assert found.id == gcn_id

    async def test_content_hash_miss(self, storage):
        """Non-existent content_hash returns None."""
        found = await storage.find_global_by_content_hash("nonexistent_hash")
        assert found is None


class TestBindings:
    async def test_bidirectional_binding_lookup(self, storage):
        """Bindings should be queryable by both local_id and global_id."""
        binding = CanonicalBinding(
            local_id="github:galileo::claim1",
            global_id="gcn_abc123",
            binding_type="variable",
            package_id="galileo",
            version="1.0.0",
            decision="create_new",
            reason="no matching global node",
        )
        await storage.content.write_bindings([binding])

        found = await storage.find_canonical_binding("github:galileo::claim1")
        assert found is not None
        assert found.global_id == "gcn_abc123"

        found_list = await storage.find_bindings_by_global_id("gcn_abc123")
        assert len(found_list) == 1
        assert found_list[0].local_id == "github:galileo::claim1"


class TestImportStatus:
    async def test_write_and_read_import_status(self, storage: StorageManager):
        """Batch write import_status records and read them back."""
        from gaia.lkm.models import ImportStatusRecord

        records = [
            ImportStatusRecord(
                package_id="paper:aaa",
                status="ingested",
                variable_count=10,
                factor_count=3,
                prior_count=8,
                factor_param_count=2,
            ),
            ImportStatusRecord(
                package_id="paper:bbb",
                status="failed:download",
                variable_count=0,
                factor_count=0,
                prior_count=0,
                factor_param_count=0,
                error="TOS timeout",
            ),
        ]
        await storage.write_import_status_batch(records)

        result = await storage.get_import_status("paper:aaa")
        assert result is not None
        assert result.status == "ingested"
        assert result.variable_count == 10

        result2 = await storage.get_import_status("paper:bbb")
        assert result2 is not None
        assert result2.status == "failed:download"

        missing = await storage.get_import_status("paper:zzz")
        assert missing is None

    async def test_import_status_is_append_only_attempt_log(self, storage: StorageManager):
        """Multiple attempts for the same package_id must all be preserved.

        Earlier the lance store used merge_key='package_id' which silently
        overwrote previous attempts. The table is semantically an attempt
        log keyed on (package_id, started_at) — this test pins the
        append-only contract.
        """
        from datetime import datetime, timedelta, timezone

        from gaia.lkm.models import ImportStatusRecord

        t0 = datetime(2026, 4, 8, 6, 0, 0, tzinfo=timezone.utc)
        attempts = [
            ImportStatusRecord(
                package_id="paper:retry",
                status="failed:ValueError",
                started_at=t0 + timedelta(minutes=15 * i),
                completed_at=t0 + timedelta(minutes=15 * i, seconds=30),
                error=f"attempt {i}",
            )
            for i in range(3)
        ]
        # Final attempt succeeds
        attempts.append(
            ImportStatusRecord(
                package_id="paper:retry",
                status="ingested",
                variable_count=5,
                started_at=t0 + timedelta(minutes=60),
                completed_at=t0 + timedelta(minutes=60, seconds=10),
            )
        )

        # Write in two batches to exercise cross-call append-only behavior
        await storage.write_import_status_batch(attempts[:2])
        await storage.write_import_status_batch(attempts[2:])

        # All 4 rows must be present
        total = await storage.content.count("import_status")
        assert total == 4

        # get_import_status returns the latest attempt (the successful one)
        latest = await storage.get_import_status("paper:retry")
        assert latest is not None
        assert latest.status == "ingested"
        assert latest.variable_count == 5

        # list_ingested_package_ids dedupes
        ingested = await storage.list_ingested_package_ids()
        assert ingested.count("paper:retry") == 1


class TestBatchUpsertLocalNodes:
    async def test_batch_upsert_writes_as_merged(self, storage):
        """batch_upsert_local_nodes writes directly as 'merged'."""
        v1 = _make_local_var("c1", "content one", "pkg_a")
        v2 = _make_local_var("c2", "content two", "pkg_a")
        await storage.content.batch_upsert_local_nodes([v1, v2], [])

        count = await storage.content.count("local_variable_nodes")
        assert count == 2

        # Verify data via package query (doesn't depend on id index)
        results = await storage.content.get_local_variables_by_package("pkg_a")
        assert len(results) == 2
        contents = {r.content for r in results}
        assert "content one" in contents

    async def test_batch_upsert_idempotent(self, storage):
        """Running batch_upsert twice does not duplicate rows."""
        v1 = _make_local_var("c1", "content", "pkg_a")
        await storage.content.batch_upsert_local_nodes([v1], [])
        count1 = await storage.content.count("local_variable_nodes")

        await storage.content.batch_upsert_local_nodes([v1], [])
        count2 = await storage.content.count("local_variable_nodes")
        assert count1 == count2


class TestBatchReads:
    async def test_find_globals_by_content_hashes(self, storage):
        """Batch content_hash lookup returns matching globals."""
        ch1 = compute_content_hash("claim", "fact one", [])
        ch2 = compute_content_hash("claim", "fact two", [])
        ref = LocalCanonicalRef(local_id="x", package_id="p", version="1")
        g1 = GlobalVariableNode(
            id=new_gcn_id(),
            type="claim",
            visibility="public",
            content_hash=ch1,
            parameters=[],
            representative_lcn=ref,
            local_members=[ref],
        )
        g2 = GlobalVariableNode(
            id=new_gcn_id(),
            type="claim",
            visibility="public",
            content_hash=ch2,
            parameters=[],
            representative_lcn=ref,
            local_members=[ref],
        )
        await storage.integrate_global_graph([g1, g2], [], [])

        result = await storage.find_globals_by_content_hashes({ch1, ch2, "nonexistent"})
        assert ch1 in result
        assert ch2 in result
        assert "nonexistent" not in result

    async def test_find_globals_empty_set(self, storage):
        result = await storage.find_globals_by_content_hashes(set())
        assert result == {}

    async def test_find_bindings_by_local_ids(self, storage):
        """Batch binding lookup by local_id."""
        b1 = CanonicalBinding(
            local_id="l1",
            global_id="g1",
            binding_type="variable",
            package_id="p",
            version="1",
            decision="create_new",
            reason="test",
        )
        b2 = CanonicalBinding(
            local_id="l2",
            global_id="g2",
            binding_type="variable",
            package_id="p",
            version="1",
            decision="create_new",
            reason="test",
        )
        await storage.content.write_bindings([b1, b2])

        result = await storage.find_bindings_by_local_ids({"l1", "l2", "missing"})
        assert "l1" in result
        assert "l2" in result
        assert "missing" not in result


class TestWriteReadRoundtrip:
    async def test_local_variable_roundtrip(self, storage):
        """Write + commit + read should preserve all fields."""
        params = [Parameter(name="x", type="int")]
        ch = compute_content_hash("claim", "test", [("x", "int")])
        node = LocalVariableNode(
            id="github:pkg::c1",
            type="claim",
            visibility="public",
            content="test",
            content_hash=ch,
            parameters=params,
            source_package="pkg",
            version="1.0.0",
            metadata={"key": "value"},
        )
        await storage.ingest_local_graph("pkg", "1.0.0", [node], [])
        await storage.commit_package("pkg", "1.0.0")

        result = await storage.get_local_variable("github:pkg::c1")
        assert result is not None
        assert result.parameters[0].name == "x"
        assert result.metadata == {"key": "value"}
        assert result.content_hash == ch

    async def test_local_factor_roundtrip(self, storage):
        """Factor write + commit + read preserves steps and background."""
        factor = LocalFactorNode(
            id="lfac_test123",
            factor_type="strategy",
            subtype="infer",
            premises=["github:pkg::p1", "github:pkg::p2"],
            conclusion="github:pkg::c1",
            background=["github:pkg::setting1"],
            steps=[Step(reasoning="Because reasons", premises=["github:pkg::p1"])],
            source_package="pkg",
            version="1.0.0",
        )
        await storage.ingest_local_graph("pkg", "1.0.0", [], [factor])
        await storage.commit_package("pkg", "1.0.0")

        result = await storage.content.get_local_factor("lfac_test123")
        assert result is not None
        assert result.premises == ["github:pkg::p1", "github:pkg::p2"]
        assert result.steps[0].reasoning == "Because reasons"
        assert result.background == ["github:pkg::setting1"]
