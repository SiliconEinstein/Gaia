"""LanceDB-backed vector search client for local / development use."""

from __future__ import annotations

import asyncio
from typing import Literal

import lancedb
import pyarrow as pa

from .base import VectorSearchClient


def _make_schema(dim: int) -> pa.Schema:
    """Build a PyArrow schema with a fixed-size vector column."""
    return pa.schema(
        [
            pa.field("node_id", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), list_size=dim)),
        ]
    )


class LanceDBVectorClient(VectorSearchClient):
    """Local vector search powered by LanceDB (on-disk)."""

    TABLE_NAME = "node_vectors"

    def __init__(
        self,
        db_path: str,
        index_type: Literal["diskann", "ivf_pq"] = "diskann",
    ) -> None:
        self._db = lancedb.connect(db_path)
        self._index_type = index_type
        self._table: lancedb.table.LanceTable | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_table(self) -> lancedb.table.LanceTable | None:
        """Return the cached table handle, or open it if it exists."""
        if self._table is not None:
            return self._table
        if self.TABLE_NAME in (self._db.list_tables().tables or []):
            self._table = self._db.open_table(self.TABLE_NAME)
        return self._table

    def _ensure_table(self, dim: int) -> lancedb.table.LanceTable:
        """Return the table, creating it (empty) on the first call."""
        table = self._get_table()
        if table is None:
            schema = _make_schema(dim)
            self._table = self._db.create_table(self.TABLE_NAME, schema=schema)
            table = self._table
        return table

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def insert_batch(self, node_ids: list[int], embeddings: list[list[float]]) -> None:
        if len(node_ids) != len(embeddings):
            raise ValueError(
                f"node_ids length ({len(node_ids)}) != embeddings length ({len(embeddings)})"
            )
        if not node_ids:
            return

        dim = len(embeddings[0])
        records = [{"node_id": nid, "vector": emb} for nid, emb in zip(node_ids, embeddings)]

        def _insert() -> None:
            table = self._ensure_table(dim)
            table.add(records)

        await asyncio.to_thread(_insert)

    async def search(self, query: list[float], k: int = 50) -> list[tuple[int, float]]:
        def _search() -> list[tuple[int, float]]:
            table = self._get_table()
            if table is None:
                return []
            results = table.search(query, vector_column_name="vector").limit(k).to_list()
            return [(row["node_id"], row["_distance"]) for row in results]

        return await asyncio.to_thread(_search)

    async def search_batch(
        self, queries: list[list[float]], k: int = 50
    ) -> list[list[tuple[int, float]]]:
        # Sequential search per query — good enough for local use.
        results: list[list[tuple[int, float]]] = []
        for q in queries:
            results.append(await self.search(q, k=k))
        return results
