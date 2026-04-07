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
    async def test_embed_batch_returns_results(self, config):
        """embed_batch calls on_result for each successful embedding."""
        vector = [0.1] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        results = []

        async def on_result(record):
            results.append(record)

        async def on_error(gcn_id, exc):
            pass

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            embedder = Embedder(config, access_key="test-key")
            await embedder.embed_batch([("gcn_1", "some text", "claim")], on_result, on_error)

        assert len(results) == 1
        assert results[0]["gcn_id"] == "gcn_1"
        assert len(results[0]["embedding"]) == 512
        await embedder.close()

    async def test_embed_batch_sends_correct_payload(self, config):
        """embed_batch sends correct text, provider, and accessKey header."""
        vector = [0.2] * 512
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"data": {"vector": vector}}

        async def on_result(record):
            pass

        async def on_error(gcn_id, exc):
            pass

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            embedder = Embedder(config, access_key="my-secret-key")
            await embedder.embed_batch([("gcn_1", "hello world", "claim")], on_result, on_error)

        mock_post.assert_called()
        call_kwargs = mock_post.call_args
        sent_json = call_kwargs[1].get("json") or call_kwargs.kwargs.get("json")
        assert sent_json["text"] == "hello world"
        assert sent_json["provider"] == "dashscope"
        sent_headers = call_kwargs[1].get("headers") or call_kwargs.kwargs.get("headers")
        assert sent_headers["accessKey"] == "my-secret-key"
        await embedder.close()

    async def test_embed_batch_retries_on_failure(self, config):
        """embed_batch retries up to max_retries on HTTP error."""
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

        results = []

        async def on_result(record):
            results.append(record)

        async def on_error(gcn_id, exc):
            pass

        with patch("httpx.AsyncClient.post", side_effect=flaky_post):
            embedder = Embedder(config, access_key="key")
            await embedder.embed_batch([("gcn_1", "retry test", "claim")], on_result, on_error)

        assert len(results) == 1
        assert call_count == 3
        await embedder.close()

    async def test_embed_batch_calls_on_error(self, config):
        """embed_batch calls on_error after exhausting retries."""
        errors = []

        async def on_result(record):
            pass

        async def on_error(gcn_id, exc):
            errors.append((gcn_id, exc))

        async def always_fail(*args, **kwargs):
            raise httpx.HTTPError("always fails")

        with patch("httpx.AsyncClient.post", side_effect=always_fail):
            embedder = Embedder(config, access_key="key")
            await embedder.embed_batch([("gcn_1", "will fail", "claim")], on_result, on_error)

        assert len(errors) == 1
        assert errors[0][0] == "gcn_1"
        await embedder.close()


class TestComputeEmbeddings:
    def _make_storage(self, globals_list):
        """Build a mock StorageManager returning given globals."""
        storage = MagicMock()
        storage.list_all_public_global_ids = AsyncMock(return_value=globals_list)

        async def get_local_variables_by_ids(local_ids, concurrency=4):
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
        bh.TABLE = "node_embeddings"
        bh._client = MagicMock()
        bh._client.query.return_value.result_rows = [(0,)]
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
        bytehouse = self._make_bytehouse(existing_ids={"gcn1"})

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

    async def test_private_variables_excluded(self, config):
        """list_all_public_global_ids only returns public globals — mock returns empty."""
        storage = self._make_storage([])
        bytehouse = self._make_bytehouse()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock):
            stats = await compute_embeddings(storage, bytehouse, config, access_key="key")

        assert stats["total"] == 0
        assert stats["computed"] == 0
        bytehouse.upsert_embeddings.assert_not_called()

    async def test_failed_embeddings_counted(self, config):
        """Failures are counted in stats['failed'] without crashing."""
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
