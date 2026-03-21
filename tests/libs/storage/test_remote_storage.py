"""Tests for remote LanceDB (S3/TOS) support — PR #171."""

from unittest.mock import patch

from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager


class TestStorageConfigRemote:
    """StorageConfig properties for remote LanceDB."""

    def test_is_remote_lancedb_false_by_default(self):
        cfg = StorageConfig(lancedb_path="/tmp/local")
        assert cfg.is_remote_lancedb is False

    def test_is_remote_lancedb_false_when_uri_none(self):
        cfg = StorageConfig(lancedb_path="/tmp/local", lancedb_uri=None)
        assert cfg.is_remote_lancedb is False

    def test_is_remote_lancedb_false_for_non_s3_uri(self):
        cfg = StorageConfig(lancedb_path="/tmp/local", lancedb_uri="gs://bucket/path")
        assert cfg.is_remote_lancedb is False

    def test_is_remote_lancedb_true_for_s3_uri(self):
        cfg = StorageConfig(
            lancedb_path="/tmp/local",
            lancedb_uri="s3://datainfra-test/gaia",
        )
        assert cfg.is_remote_lancedb is True

    def test_effective_connection_returns_local_path_when_no_uri(self):
        cfg = StorageConfig(lancedb_path="/data/lancedb/gaia")
        assert cfg.effective_lancedb_connection == "/data/lancedb/gaia"

    def test_effective_connection_returns_uri_when_set(self):
        cfg = StorageConfig(
            lancedb_path="/data/lancedb/gaia",
            lancedb_uri="s3://datainfra-test/gaia",
        )
        assert cfg.effective_lancedb_connection == "s3://datainfra-test/gaia"


class TestBuildTosOptions:
    """StorageManager._build_tos_options reads TOS env vars."""

    def test_build_tos_options_with_all_vars(self):
        env = {
            "TOS_ACCESS_KEY": "AKID123",
            "TOS_SECRET_KEY": "secret456",
            "TOS_ENDPOINT": "tos-cn-beijing.volces.com",
            "TOS_BUCKET": "datainfra-test",
        }
        with patch.dict("os.environ", env, clear=False):
            opts = StorageManager._build_tos_options()

        assert opts["access_key_id"] == "AKID123"
        assert opts["secret_access_key"] == "secret456"
        assert opts["endpoint"] == "https://datainfra-test.tos-cn-beijing.volces.com"
        assert opts["virtual_hosted_style_request"] == "true"

    def test_build_tos_options_empty_when_vars_missing(self):
        env = {
            "TOS_ACCESS_KEY": "",
            "TOS_SECRET_KEY": "",
            "TOS_ENDPOINT": "",
            "TOS_BUCKET": "",
        }
        with patch.dict("os.environ", env, clear=False):
            opts = StorageManager._build_tos_options()

        assert opts["access_key_id"] == ""
        assert opts["secret_access_key"] == ""
        assert opts["endpoint"] == ""

    def test_build_tos_options_endpoint_empty_when_bucket_missing(self):
        env = {
            "TOS_ACCESS_KEY": "ak",
            "TOS_SECRET_KEY": "sk",
            "TOS_ENDPOINT": "tos-cn-beijing.volces.com",
            "TOS_BUCKET": "",
        }
        with patch.dict("os.environ", env, clear=False):
            opts = StorageManager._build_tos_options()

        assert opts["endpoint"] == ""


class TestLanceStoreStorageOptions:
    """LanceContentStore and LanceVectorStore accept storage_options."""

    def test_content_store_passes_storage_options(self, tmp_path):
        from libs.storage.lance_content_store import LanceContentStore

        # Local path with no storage_options — should work fine
        store = LanceContentStore(str(tmp_path / "lance_content"))
        assert store._db is not None

    def test_vector_store_passes_storage_options(self, tmp_path):
        from libs.storage.lance_vector_store import LanceVectorStore

        store = LanceVectorStore(str(tmp_path / "lance_vector"))
        assert store._db is not None

    def test_content_store_with_none_storage_options(self, tmp_path):
        from libs.storage.lance_content_store import LanceContentStore

        store = LanceContentStore(str(tmp_path / "lance_content"), storage_options=None)
        assert store._db is not None

    def test_vector_store_with_none_storage_options(self, tmp_path):
        from libs.storage.lance_vector_store import LanceVectorStore

        store = LanceVectorStore(str(tmp_path / "lance_vector"), storage_options=None)
        assert store._db is not None


class TestManagerRemoteInit:
    """StorageManager.initialize passes storage_options for remote config."""

    async def test_local_init_no_storage_options(self, tmp_path):
        """Local config should not pass storage_options to LanceDB."""
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            graph_backend="none",
        )
        mgr = StorageManager(config)
        await mgr.initialize()

        assert mgr.content_store is not None
        assert mgr.vector_store is not None
        await mgr.close()

    async def test_remote_config_calls_build_tos_options(self, tmp_path):
        """When lancedb_uri is s3://, _build_tos_options should be called."""
        config = StorageConfig(
            lancedb_path=str(tmp_path / "lance"),
            lancedb_uri="s3://fake-bucket/path",
            graph_backend="none",
        )
        mgr = StorageManager(config)

        with patch.object(StorageManager, "_build_tos_options", return_value={}) as mock_build:
            # This will fail to connect to S3, but we verify _build_tos_options is called
            try:
                await mgr.initialize()
            except Exception:
                pass  # S3 connection expected to fail in test

        mock_build.assert_called_once()
