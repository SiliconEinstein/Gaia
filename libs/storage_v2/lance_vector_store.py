"""LanceDB-backed implementation of VectorStore."""

from __future__ import annotations

from datetime import datetime

import lancedb
import pyarrow as pa

from libs.storage_v2.models import ClosureEmbedding, Closure, ScoredClosure
from libs.storage_v2.vector_store import VectorStore

TABLE_NAME = "closure_vectors"

_PLACEHOLDER_DATETIME = datetime(2000, 1, 1)


def _make_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("closure_id", pa.string()),
            pa.field("version", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), list_size=dim)),
        ]
    )


def _q(s: str) -> str:
    """Escape single quotes for LanceDB SQL filter expressions."""
    return s.replace("'", "''")


class LanceVectorStore(VectorStore):
    """LanceDB-backed vector store for closure embedding search."""

    def __init__(self, db_path: str) -> None:
        self._db = lancedb.connect(db_path)
        self._table: lancedb.table.LanceTable | None = None

    def _get_table(self) -> lancedb.table.LanceTable | None:
        if self._table is not None:
            return self._table
        tables = self._db.list_tables().tables or []
        if TABLE_NAME in tables:
            self._table = self._db.open_table(TABLE_NAME)
        return self._table

    def _ensure_table(self, dim: int) -> lancedb.table.LanceTable:
        table = self._get_table()
        if table is None:
            self._table = self._db.create_table(TABLE_NAME, schema=_make_schema(dim))
            table = self._table
        return table

    async def write_embeddings(self, items: list[ClosureEmbedding]) -> None:
        if not items:
            return

        dim = len(items[0].embedding)
        table = self._ensure_table(dim)

        for item in items:
            existing = (
                table.search()
                .where(f"closure_id = '{_q(item.closure_id)}' AND version = {item.version}")
                .limit(1)
                .to_list()
            )
            if existing:
                table.delete(f"closure_id = '{_q(item.closure_id)}' AND version = {item.version}")

        rows = [
            {
                "closure_id": item.closure_id,
                "version": item.version,
                "vector": item.embedding,
            }
            for item in items
        ]
        table.add(rows)

    async def search(self, embedding: list[float], top_k: int) -> list[ScoredClosure]:
        table = self._get_table()
        if table is None or table.count_rows() == 0:
            return []

        results = table.search(embedding, vector_column_name="vector").limit(top_k).to_list()

        scored: list[ScoredClosure] = []
        for row in results:
            closure = Closure(
                closure_id=row["closure_id"],
                version=row["version"],
                type="claim",
                content="",
                prior=0.5,
                keywords=[],
                source_package_id="",
                source_module_id="",
                created_at=_PLACEHOLDER_DATETIME,
            )
            distance = row.get("_distance", 0.0)
            score = 1.0 / (1.0 + distance)
            scored.append(ScoredClosure(closure=closure, score=score))

        return scored
