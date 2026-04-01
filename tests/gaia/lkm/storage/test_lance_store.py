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
    qid = f"reg:{package}::{label}"
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

        result = await storage.get_local_variable("reg:pkg_a::claim1")
        assert result is None

    async def test_merged_nodes_visible(self, storage):
        """After commit, nodes should be visible."""
        node = _make_local_var("claim1", "test content", "pkg_a")
        await storage.ingest_local_graph("pkg_a", "1.0.0", [node], [])
        await storage.commit_package("pkg_a", "1.0.0")

        result = await storage.get_local_variable("reg:pkg_a::claim1")
        assert result is not None
        assert result.content == "test content"
        assert result.id == "reg:pkg_a::claim1"


class TestContentHashDedup:
    async def test_find_global_by_content_hash(self, storage):
        """content_hash lookup must work for dedup."""
        content = "Objects fall at equal rates in vacuum"
        ch = compute_content_hash("claim", content, [])
        gcn_id = new_gcn_id()
        ref = LocalCanonicalRef(local_id="reg:galileo::vac", package_id="galileo", version="1.0.0")

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
            local_id="reg:galileo::claim1",
            global_id="gcn_abc123",
            binding_type="variable",
            package_id="galileo",
            version="1.0.0",
            decision="create_new",
            reason="no matching global node",
        )
        await storage.content.write_bindings([binding])

        found = await storage.find_canonical_binding("reg:galileo::claim1")
        assert found is not None
        assert found.global_id == "gcn_abc123"

        found_list = await storage.find_bindings_by_global_id("gcn_abc123")
        assert len(found_list) == 1
        assert found_list[0].local_id == "reg:galileo::claim1"


class TestWriteReadRoundtrip:
    async def test_local_variable_roundtrip(self, storage):
        """Write + commit + read should preserve all fields."""
        params = [Parameter(name="x", type="int")]
        ch = compute_content_hash("claim", "test", [("x", "int")])
        node = LocalVariableNode(
            id="reg:pkg::c1",
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

        result = await storage.get_local_variable("reg:pkg::c1")
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
            premises=["reg:pkg::p1", "reg:pkg::p2"],
            conclusion="reg:pkg::c1",
            background=["reg:pkg::setting1"],
            steps=[Step(reasoning="Because reasons", premises=["reg:pkg::p1"])],
            source_package="pkg",
            version="1.0.0",
        )
        await storage.ingest_local_graph("pkg", "1.0.0", [], [factor])
        await storage.commit_package("pkg", "1.0.0")

        result = await storage.content.get_local_factor("lfac_test123")
        assert result is not None
        assert result.premises == ["reg:pkg::p1", "reg:pkg::p2"]
        assert result.steps[0].reasoning == "Because reasons"
        assert result.background == ["reg:pkg::setting1"]
