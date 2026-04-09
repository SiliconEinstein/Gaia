"""Unit tests for StorageManager LKM backend switching (Phase 2)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from gaia.lkm.storage import StorageConfig, StorageManager
from gaia.lkm.storage.bytehouse_lkm_store import BytehouseLkmStore
from gaia.lkm.storage.lance_store import LanceContentStore
from gaia.lkm.storage.protocol import LkmContentStore


async def test_default_backend_is_lance(tmp_path):
    """No explicit backend → LanceContentStore."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lkm"))
    mgr = StorageManager(config)
    await mgr.initialize()
    assert isinstance(mgr.content, LanceContentStore)
    assert isinstance(mgr.content, LkmContentStore)


async def test_bytehouse_backend_instantiates_bytehouse_store():
    """lkm_backend='bytehouse' → BytehouseLkmStore (clickhouse client mocked)."""
    config = StorageConfig(
        lkm_backend="bytehouse",
        bytehouse_host="bh.example.com",
        bytehouse_user="u",
        bytehouse_password="p",
        bytehouse_database="paper_data",
        bytehouse_replication_root="/clickhouse/test",
        bytehouse_table_prefix="lkm_test_",
    )
    mock_client = MagicMock()
    with patch("clickhouse_connect.get_client", return_value=mock_client):
        mgr = StorageManager(config)
        await mgr.initialize()
    assert isinstance(mgr.content, BytehouseLkmStore)
    assert isinstance(mgr.content, LkmContentStore)
    # initialize() should have issued the 9 DDL commands
    assert mock_client.command.call_count == 9


async def test_bytehouse_backend_requires_host():
    """Selecting bytehouse without BYTEHOUSE_HOST raises a clear error."""
    config = StorageConfig(lkm_backend="bytehouse")
    mgr = StorageManager(config)
    with pytest.raises(ValueError, match="BYTEHOUSE_HOST"):
        await mgr.initialize()


async def test_bytehouse_backend_uses_table_prefix():
    """The configured table_prefix flows through to the BytehouseLkmStore."""
    config = StorageConfig(
        lkm_backend="bytehouse",
        bytehouse_host="bh.example.com",
        bytehouse_user="u",
        bytehouse_password="p",
        bytehouse_replication_root="/clickhouse/test",
        bytehouse_table_prefix="lkm_alt_",
    )
    with patch("clickhouse_connect.get_client", return_value=MagicMock()):
        mgr = StorageManager(config)
        await mgr.initialize()
    assert mgr.content.t_lvars == "lkm_alt_local_variables"
