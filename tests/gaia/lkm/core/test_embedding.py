"""Unit tests for embedding computer — mocked httpx and ByteHouse."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gaia.lkm.core._embedding import Embedder, compute_embeddings
from gaia.lkm.models.discovery import DiscoveryConfig


@pytest.fixture
def config():
    return DiscoveryConfig(
        embedding_api_url="https://fake-api.example.com/v1/vectorize",
        embedding_provider="dashscope",
        embedding_concurrency=4,
        embedding_max_retries=3,
        embedding_http_timeout=10,
    )


class TestEmbedder:
    async def test_embed_returns_vector(self, config):
        """embed() returns a list of floats from the API response."""
        vector = [0.1] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            embedder = Embedder(config, access_key="test-key")
            result = await embedder.embed("some text")

        assert result == vector
        assert len(result) == 512
        assert isinstance(result[0], float)
        await embedder.close()

    async def test_embed_sends_correct_payload(self, config):
        """embed() sends the correct text, provider, and accessKey header."""
        vector = [0.2] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            embedder = Embedder(config, access_key="my-secret-key")
            await embedder.embed("hello world")

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args

        # Verify URL
        url = (
            call_kwargs[0][0]
            if call_kwargs[0]
            else call_kwargs[1].get("url") or call_kwargs.args[0]
        )
        assert url == config.embedding_api_url

        # Verify JSON body
        sent_json = call_kwargs[1].get("json") or call_kwargs.kwargs.get("json")
        assert sent_json["text"] == "hello world"
        assert sent_json["provider"] == "dashscope"

        # Verify headers
        sent_headers = call_kwargs[1].get("headers") or call_kwargs.kwargs.get("headers")
        assert sent_headers["accessKey"] == "my-secret-key"

        await embedder.close()

    async def test_embed_retries_on_failure(self, config):
        """embed() retries up to embedding_max_retries times on HTTP error."""
        vector = [0.3] * 512
        success_response = MagicMock()
        success_response.raise_for_status = MagicMock()
        success_response.json.return_value = {"data": {"vector": vector}}

        call_count = 0

        async def flaky_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.HTTPError("connection error")
            return success_response

        with patch("httpx.AsyncClient.post", side_effect=flaky_post):
            embedder = Embedder(config, access_key="key")
            result = await embedder.embed("retry test")

        assert result == vector
        assert call_count == 3
        await embedder.close()

    async def test_embed_raises_after_max_retries(self, config):
        """embed() raises after exhausting all retries."""

        async def always_fail(*args, **kwargs):
            raise httpx.HTTPError("always fails")

        with patch("httpx.AsyncClient.post", side_effect=always_fail):
            embedder = Embedder(config, access_key="key")
            with pytest.raises(httpx.HTTPError):
                await embedder.embed("will fail")

        await embedder.close()


class TestComputeEmbeddings:
    def _make_storage(self, globals_list):
        """Build a mock StorageManager returning given globals."""
        storage = MagicMock()
        storage.list_all_public_global_ids = AsyncMock(return_value=globals_list)

        async def get_local_variables_by_ids(local_ids):
            result = {}
            for lid in local_ids:
                node = MagicMock()
                node.content = f"content for {lid}"
                result[lid] = node
            return result

        storage.get_local_variables_by_ids = get_local_variables_by_ids
        return storage

    def _make_bytehouse(self, existing_ids=None):
        """Build a mock ByteHouseEmbeddingStore."""
        bh = MagicMock()
        bh.get_existing_gcn_ids = MagicMock(return_value=set(existing_ids or []))
        bh.upsert_embeddings = MagicMock()
        return bh

    def _make_global_meta(self, gcn_id, node_type="claim", pkg="pkg1"):
        """Build a dict mimicking list_all_public_global_ids output."""
        local_id = f"{pkg}::label_{gcn_id}"
        rep_lcn = json.dumps({"local_id": local_id, "package_id": pkg, "version": "1.0"})
        return {
            "id": gcn_id,
            "type": node_type,
            "representative_lcn": rep_lcn,
        }

    async def test_skips_already_embedded(self, config):
        """Only computes embeddings for gcn_ids not yet in ByteHouse."""
        globals_list = [
            self._make_global_meta("gcn1"),
            self._make_global_meta("gcn2"),
        ]
        storage = self._make_storage(globals_list)
        bytehouse = self._make_bytehouse(existing_ids={"gcn1"})  # gcn1 already done

        vector = [0.5] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            stats = await compute_embeddings(storage, bytehouse, config, access_key="key")

        assert stats["total"] == 2
        assert stats["computed"] == 1
        assert stats["skipped"] == 1
        assert stats["failed"] == 0

        # ByteHouse should have been called with exactly 1 record (gcn2)
        bytehouse.upsert_embeddings.assert_called()
        all_records = []
        for call in bytehouse.upsert_embeddings.call_args_list:
            all_records.extend(call[0][0])
        assert len(all_records) == 1
        assert all_records[0]["gcn_id"] == "gcn2"

    async def test_private_variables_excluded(self, config):
        """list_all_public_global_ids only returns public globals — mock returns empty."""
        storage = self._make_storage([])  # no public globals
        bytehouse = self._make_bytehouse()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock):
            stats = await compute_embeddings(storage, bytehouse, config, access_key="key")

        assert stats["total"] == 0
        assert stats["computed"] == 0
        assert stats["skipped"] == 0
        bytehouse.upsert_embeddings.assert_not_called()

    async def test_failed_embeddings_counted(self, config):
        """Failures are counted in stats['failed'] without crashing the pipeline."""
        globals_list = [
            self._make_global_meta("gcn1"),
            self._make_global_meta("gcn2"),
        ]
        storage = self._make_storage(globals_list)
        bytehouse = self._make_bytehouse()

        async def always_fail(*args, **kwargs):
            raise httpx.HTTPError("api down")

        with patch("httpx.AsyncClient.post", side_effect=always_fail):
            stats = await compute_embeddings(storage, bytehouse, config, access_key="key")

        assert stats["total"] == 2
        assert stats["failed"] == 2
        assert stats["computed"] == 0

    async def test_batch_size_200(self, config):
        """Records are flushed in batches of 200."""
        n = 250
        globals_list = [self._make_global_meta(f"gcn{i}") for i in range(n)]
        storage = self._make_storage(globals_list)
        bytehouse = self._make_bytehouse()

        vector = [0.1] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            stats = await compute_embeddings(storage, bytehouse, config, access_key="key")

        assert stats["computed"] == n
        # Should have been called at least twice: batches of 200 + 50
        assert bytehouse.upsert_embeddings.call_count >= 2
        all_records = []
        for call in bytehouse.upsert_embeddings.call_args_list:
            batch = call[0][0]
            assert len(batch) <= 200
            all_records.extend(batch)
        assert len(all_records) == n
