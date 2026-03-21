"""LanceDB-backed implementation of VectorStore."""

from __future__ import annotations

from datetime import datetime

import lancedb
import pyarrow as pa

from libs.storage.models import KnowledgeEmbedding, Knowledge, ScoredKnowledge
from libs.storage.vector_store import VectorStore

TABLE_NAME = "knowledge_vectors"

_PLACEHOLDER_DATETIME = datetime(2000, 1, 1)


def _make_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("knowledge_id", pa.string()),
            pa.field("version", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), list_size=dim)),
        ]
    )


def _q(s: str) -> str:
    """Escape single quotes for LanceDB SQL filter expressions."""
    return s.replace("'", "''")


class LanceVectorStore(VectorStore):
    """LanceDB-backed vector store for knowledge embedding search."""

    def __init__(self, db_path: str, storage_options: dict[str, str] | None = None) -> None:
        if storage_options:
            self._db = lancedb.connect(db_path, storage_options=storage_options)
        else:
            self._db = lancedb.connect(db_path)
        self._table: lancedb.table.LanceTable | None = None
        self._dim: int | None = None

    def _get_table(self) -> lancedb.table.LanceTable | None:
        if self._table is not None:
            return self._table
        tables = self._db.list_tables().tables or []
        if TABLE_NAME in tables:
            self._table = self._db.open_table(TABLE_NAME)
            vector_field = self._table.schema.field("vector")
            self._dim = vector_field.type.list_size
        return self._table

    def _ensure_table(self, dim: int) -> lancedb.table.LanceTable:
        table = self._get_table()
        if table is None:
            self._table = self._db.create_table(TABLE_NAME, schema=_make_schema(dim))
            self._dim = dim
            table = self._table
        return table

    @staticmethod
    def _validate_embedding(embedding: list[float], label: str = "embedding") -> int:
        if not embedding:
            raise ValueError(f"{label} must not be empty")
        return len(embedding)

    def _validate_dim(self, dim: int, label: str = "embedding") -> None:
        if self._dim is not None and dim != self._dim:
            raise ValueError(f"{label} dimension {dim} does not match stored dimension {self._dim}")

    async def write_embeddings(self, items: list[KnowledgeEmbedding]) -> None:
        if not items:
            return

        # Validate all embeddings and check dimension consistency
        dim = self._validate_embedding(items[0].embedding, "items[0].embedding")
        for i, item in enumerate(items):
            item_dim = self._validate_embedding(item.embedding, f"items[{i}].embedding")
            if item_dim != dim:
                raise ValueError(
                    f"inconsistent embedding dimensions in batch: "
                    f"items[0] has {dim}, items[{i}] has {item_dim}"
                )
        self._validate_dim(dim, "write embedding")

        # Deduplicate within the batch — last occurrence wins
        deduped: dict[tuple[str, int], KnowledgeEmbedding] = {}
        for item in items:
            deduped[(item.knowledge_id, item.version)] = item
        unique_items = list(deduped.values())

        table = self._ensure_table(dim)
        rows = [
            {
                "knowledge_id": item.knowledge_id,
                "version": item.version,
                "vector": item.embedding,
            }
            for item in unique_items
        ]
        (
            table.merge_insert(["knowledge_id", "version"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    async def search(self, embedding: list[float], top_k: int) -> list[ScoredKnowledge]:
        dim = self._validate_embedding(embedding, "search query")
        self._validate_dim(dim, "search query")

        table = self._get_table()
        if table is None or table.count_rows() == 0:
            return []

        results = table.search(embedding, vector_column_name="vector").limit(top_k).to_list()

        scored: list[ScoredKnowledge] = []
        for row in results:
            knowledge = Knowledge(
                knowledge_id=row["knowledge_id"],
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
            scored.append(ScoredKnowledge(knowledge=knowledge, score=score))

        return scored
