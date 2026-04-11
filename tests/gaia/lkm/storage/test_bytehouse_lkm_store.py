"""Unit tests for BytehouseLkmStore (mocked clickhouse client)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    ParameterizationSource,
    PriorRecord,
)
from gaia.lkm.models.import_status import ImportStatusRecord
from gaia.lkm.storage._bytehouse_schemas import COLUMN_ORDER, LKM_TABLES
from gaia.lkm.storage.bytehouse_lkm_store import LANCE_TO_BH_TABLE, BytehouseLkmStore
from gaia.lkm.storage.protocol import LkmContentStore


@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def store(mock_client: MagicMock) -> BytehouseLkmStore:
    with patch("clickhouse_connect.get_client", return_value=mock_client):
        s = BytehouseLkmStore(
            host="localhost",
            user="user",
            password="pw",
            database="paper_data",
            secure=True,
            replication_root="/clickhouse/test/root",
        )
    return s


def _query_result(rows: list[tuple], cols: list[str]) -> SimpleNamespace:
    return SimpleNamespace(result_rows=rows, column_names=cols)


# ── Sample model factories ──────────────────────────────────────────────────


def _local_var(idx: int = 1) -> LocalVariableNode:
    return LocalVariableNode(
        id=f"pkg::v{idx}",
        type="claim",
        visibility="public",
        content=f"content {idx}",
        content_hash=f"hash{idx}",
        parameters=[Parameter(name="x", type="int")],
        source_package="pkg",
        version="0.1.0",
        metadata={"k": "v"},
    )


def _local_factor(idx: int = 1) -> LocalFactorNode:
    return LocalFactorNode(
        id=f"lfac_{idx}",
        factor_type="strategy",
        subtype="infer",
        premises=[f"pkg::v{idx}", f"pkg::v{idx + 1}"],
        conclusion=f"pkg::v{idx + 2}",
        source_package="pkg",
        version="0.1.0",
    )


def _global_var(idx: int = 1) -> GlobalVariableNode:
    ref = LocalCanonicalRef(local_id=f"pkg::v{idx}", package_id="pkg", version="0.1.0")
    return GlobalVariableNode(
        id=f"gcn_{idx:016d}",
        type="claim",
        visibility="public",
        content_hash=f"hash{idx}",
        parameters=[],
        representative_lcn=ref,
        local_members=[ref],
    )


def _global_factor(idx: int = 1) -> GlobalFactorNode:
    return GlobalFactorNode(
        id=f"gfac_{idx:016d}",
        factor_type="strategy",
        subtype="infer",
        premises=[f"gcn_{idx:016d}", f"gcn_{idx + 1:016d}"],
        conclusion=f"gcn_{idx + 2:016d}",
        representative_lfn=f"lfac_{idx}",
        source_package="pkg",
    )


# ── Static structural tests ─────────────────────────────────────────────────


def test_protocol_satisfied(store: BytehouseLkmStore) -> None:
    assert isinstance(store, LkmContentStore)


def test_table_name_map_complete() -> None:
    """Every Lance-style table name maps to a known ByteHouse table in DDL."""
    assert set(LANCE_TO_BH_TABLE.values()) == set(LKM_TABLES.keys())
    assert set(LKM_TABLES.keys()) == set(COLUMN_ORDER.keys())


def test_constructor_passes_args() -> None:
    with patch("clickhouse_connect.get_client", return_value=MagicMock()) as get:
        BytehouseLkmStore(
            host="bh",
            user="u",
            password="p",
            database="d",
            secure=False,
            replication_root="/r",
        )
        get.assert_called_once_with(
            host="bh",
            user="u",
            password="p",
            database="d",
            secure=False,
            compress=False,
        )


# ── initialize() ────────────────────────────────────────────────────────────


async def test_initialize_creates_all_tables(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    await store.initialize()
    assert mock_client.command.call_count == len(LKM_TABLES)
    issued = [call.args[0] for call in mock_client.command.call_args_list]
    for name in LKM_TABLES:
        assert any(name in ddl for ddl in issued)
        assert any("HaUniqueMergeTree" in ddl for ddl in issued)


async def test_initialize_requires_replication_root(mock_client: MagicMock) -> None:
    with patch("clickhouse_connect.get_client", return_value=mock_client):
        s = BytehouseLkmStore(host="h", user="u", password="p", database="d", replication_root="")
    with pytest.raises(ValueError, match="replication_root"):
        await s.initialize()


# ── Writes ──────────────────────────────────────────────────────────────────


async def test_write_local_variables_uses_preparing(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    await store.write_local_variables([_local_var(1), _local_var(2)])
    mock_client.insert.assert_called_once()
    table, data = mock_client.insert.call_args.args[:2]
    assert table == "lkm_local_variables"
    cols = mock_client.insert.call_args.kwargs["column_names"]
    assert cols == COLUMN_ORDER["lkm_local_variables"]
    status_idx = cols.index("ingest_status")
    assert all(row[status_idx] == "preparing" for row in data)


async def test_write_local_factors_premises_array(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    await store.write_local_factors([_local_factor(1)])
    table, data = mock_client.insert.call_args.args[:2]
    assert table == "lkm_local_factors"
    cols = mock_client.insert.call_args.kwargs["column_names"]
    premises_idx = cols.index("premises")
    # Must be a Python list (Array(String)), not JSON string
    assert isinstance(data[0][premises_idx], list)
    assert data[0][premises_idx] == ["pkg::v1", "pkg::v2"]


async def test_batch_upsert_local_nodes_uses_merged(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    await store.batch_upsert_local_nodes(variables=[_local_var(1)], factors=[_local_factor(1)])
    assert mock_client.insert.call_count == 2
    for call in mock_client.insert.call_args_list:
        cols = call.kwargs["column_names"]
        data = call.args[1]
        assert data[0][cols.index("ingest_status")] == "merged"


async def test_write_global_factors_premises_array(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    await store.write_global_factors([_global_factor(1)])
    table, data = mock_client.insert.call_args.args[:2]
    assert table == "lkm_global_factors"
    cols = mock_client.insert.call_args.kwargs["column_names"]
    premises_idx = cols.index("premises")
    assert isinstance(data[0][premises_idx], list)


async def test_write_global_variables(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    await store.write_global_variables([_global_var(1)])
    assert mock_client.insert.call_args.args[0] == "lkm_global_variables"


async def test_write_bindings(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    binding = CanonicalBinding(
        local_id="pkg::v1",
        global_id="gcn_x",
        binding_type="variable",
        package_id="pkg",
        version="0.1.0",
        decision="create_new",
        reason="ok",
    )
    await store.write_bindings([binding])
    assert mock_client.insert.call_args.args[0] == "lkm_canonical_bindings"


async def test_write_prior_records(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    rec = PriorRecord(
        variable_id="gcn_x",
        value=0.5,
        source_id="src",
        created_at=datetime.now(timezone.utc),
    )
    await store.write_prior_records([rec])
    table, data = mock_client.insert.call_args.args[:2]
    assert table == "lkm_prior_records"
    cols = mock_client.insert.call_args.kwargs["column_names"]
    # Composite id: variable_id::source_id
    assert data[0][cols.index("id")] == "gcn_x::src"


async def test_write_factor_param_records(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    rec = FactorParamRecord(
        factor_id="gfac_x",
        conditional_probabilities=[0.1, 0.9],
        source_id="src",
        created_at=datetime.now(timezone.utc),
    )
    await store.write_factor_param_records([rec])
    assert mock_client.insert.call_args.args[0] == "lkm_factor_param_records"


async def test_write_param_source(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    src = ParameterizationSource(
        source_id="src",
        source_class="heuristic",
        model="m",
        policy="default",
        config={"k": 1},
        created_at=datetime.now(timezone.utc),
    )
    await store.write_param_source(src)
    assert mock_client.insert.call_args.args[0] == "lkm_param_sources"


async def test_write_import_status_batch(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    rec = ImportStatusRecord(
        package_id="pkg",
        status="ingested",
        variable_count=1,
        factor_count=1,
        prior_count=0,
        factor_param_count=0,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    await store.write_import_status_batch([rec])
    assert mock_client.insert.call_args.args[0] == "lkm_import_status"


async def test_empty_writes_are_noops(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    await store.write_local_variables([])
    await store.write_local_factors([])
    await store.write_global_variables([])
    await store.write_global_factors([])
    await store.write_bindings([])
    await store.write_prior_records([])
    await store.write_factor_param_records([])
    await store.write_param_sources_batch([])
    await store.write_import_status_batch([])
    mock_client.insert.assert_not_called()


# ── commit_ingest ───────────────────────────────────────────────────────────


async def test_commit_ingest_flips_status(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    var_cols = COLUMN_ORDER["lkm_local_variables"]
    var_row = (
        "pkg::v1",
        "claim",
        "public",
        "c",
        "h",
        "[]",
        "pkg",
        "0.1.0",
        "",
        "preparing",
    )
    factor_cols = COLUMN_ORDER["lkm_local_factors"]
    factor_row = (
        "lfac_1",
        "strategy",
        "infer",
        ["a", "b"],
        "c",
        "",
        "",
        "pkg",
        "0.1.0",
        "",
        "preparing",
    )

    queries = iter([_query_result([var_row], var_cols), _query_result([factor_row], factor_cols)])
    mock_client.query.side_effect = lambda *a, **kw: next(queries)

    await store.commit_ingest("pkg", "0.1.0")

    # 2 SELECTs and 2 INSERTs
    assert mock_client.query.call_count == 2
    assert mock_client.insert.call_count == 2
    for call in mock_client.insert.call_args_list:
        cols = call.kwargs["column_names"]
        data = call.args[1]
        assert data[0][cols.index("ingest_status")] == "merged"


async def test_commit_ingest_empty_skips_insert(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    mock_client.query.return_value = _query_result([], COLUMN_ORDER["lkm_local_variables"])
    await store.commit_ingest("pkg", "0.1.0")
    mock_client.insert.assert_not_called()


# ── Reads ───────────────────────────────────────────────────────────────────


async def test_get_local_variable_hit(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    cols = [
        "id",
        "type",
        "visibility",
        "content",
        "content_hash",
        "parameters",
        "source_package",
        "version",
        "metadata",
        "ingest_status",
    ]
    row = ("pkg::v1", "claim", "public", "c", "h", "[]", "pkg", "0.1.0", "", "merged")
    mock_client.query.return_value = _query_result([row], cols)
    result = await store.get_local_variable("pkg::v1")
    assert result is not None
    assert result.id == "pkg::v1"
    sql = mock_client.query.call_args.args[0]
    assert "ingest_status = 'merged'" in sql


async def test_get_local_variable_miss(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    mock_client.query.return_value = _query_result([], ["id"])
    assert await store.get_local_variable("missing") is None


async def test_get_local_factor_premises_array_to_json(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    cols = [
        "id",
        "factor_type",
        "subtype",
        "premises",
        "conclusion",
        "background",
        "steps",
        "source_package",
        "version",
        "metadata",
        "ingest_status",
    ]
    row = ("lfac_1", "strategy", "infer", ["a", "b"], "c", "", "", "pkg", "0.1.0", "", "merged")
    mock_client.query.return_value = _query_result([row], cols)
    result = await store.get_local_factor("lfac_1")
    assert result is not None
    assert result.premises == ["a", "b"]


async def test_get_global_factor_premises_round_trip(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    cols = [
        "id",
        "factor_type",
        "subtype",
        "premises",
        "conclusion",
        "representative_lfn",
        "source_package",
        "metadata",
    ]
    row = ("gfac_1", "strategy", "infer", ["g1", "g2"], "g3", "lfac_1", "pkg", "")
    mock_client.query.return_value = _query_result([row], cols)
    result = await store.get_global_factor("gfac_1")
    assert result is not None
    assert result.premises == ["g1", "g2"]


async def test_find_globals_by_content_hashes_batches(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    cols = [
        "id",
        "type",
        "visibility",
        "content_hash",
        "parameters",
        "representative_lcn",
        "local_members",
        "metadata",
    ]
    ref = json.dumps({"local_id": "pkg::v1", "package_id": "pkg", "version": "0.1.0"})
    row = ("gcn_1", "claim", "public", "hash1", "[]", ref, f"[{ref}]", "")
    mock_client.query.return_value = _query_result([row], cols)
    out = await store.find_globals_by_content_hashes({"hash1"})
    assert "hash1" in out
    sql = mock_client.query.call_args.args[0]
    params = mock_client.query.call_args.kwargs["parameters"]
    assert "IN %(hashes)s" in sql
    assert params == {"hashes": ["hash1"]}


async def test_find_global_factor_exact_memory_filter(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    cols = [
        "id",
        "factor_type",
        "subtype",
        "premises",
        "conclusion",
        "representative_lfn",
        "source_package",
        "metadata",
    ]
    rows = [
        ("gfac_a", "strategy", "infer", ["x", "y"], "c", "lfac_a", "pkg", ""),
        ("gfac_b", "strategy", "infer", ["a", "b"], "c", "lfac_b", "pkg", ""),
    ]
    mock_client.query.return_value = _query_result(rows, cols)
    result = await store.find_global_factor_exact(
        premises=["b", "a"], conclusion="c", factor_type="strategy", subtype="infer"
    )
    assert result is not None
    assert result.id == "gfac_b"


async def test_count_translates_lance_table_name(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    mock_client.query.return_value = _query_result([(42,)], ["n"])
    assert await store.count("local_variable_nodes") == 42
    sql = mock_client.query.call_args.args[0]
    assert "lkm_local_variables" in sql


async def test_count_unknown_table_raises(store: BytehouseLkmStore, mock_client: MagicMock) -> None:
    with pytest.raises(KeyError):
        await store.count("nonexistent")


async def test_list_ingested_package_ids_uses_distinct(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    """import_status is an attempt log — DISTINCT is required to dedupe."""
    mock_client.query.return_value = _query_result([("pkg-a",), ("pkg-b",)], ["package_id"])
    out = await store.list_ingested_package_ids()
    assert out == ["pkg-a", "pkg-b"]
    sql = mock_client.query.call_args.args[0]
    assert "status = 'ingested'" in sql
    assert "DISTINCT" in sql


async def test_get_import_status_picks_latest_attempt(
    store: BytehouseLkmStore, mock_client: MagicMock
) -> None:
    """get_import_status must ORDER BY started_at DESC to return the latest attempt."""
    cols = [
        "package_id",
        "status",
        "variable_count",
        "factor_count",
        "prior_count",
        "factor_param_count",
        "started_at",
        "completed_at",
        "error",
    ]
    latest_row = (
        "paper:retry",
        "ingested",
        5,
        0,
        0,
        0,
        "2026-04-08T07:00:00+00:00",
        "2026-04-08T07:00:10+00:00",
        "",
    )
    mock_client.query.return_value = _query_result([latest_row], cols)
    result = await store.get_import_status("paper:retry")
    assert result is not None
    assert result.status == "ingested"
    sql = mock_client.query.call_args.args[0]
    assert "ORDER BY started_at DESC" in sql
    assert "LIMIT 1" in sql


async def test_update_global_variable_members_id_mismatch(
    store: BytehouseLkmStore,
) -> None:
    gv = _global_var(1)
    with pytest.raises(ValueError, match="mismatch"):
        await store.update_global_variable_members("gcn_other", gv)
