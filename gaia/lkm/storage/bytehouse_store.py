"""ByteHouse (ClickHouse-compatible) store for node embeddings.

All methods are synchronous — the ClickHouse driver is sync.
Callers must wrap with asyncio.get_event_loop().run_in_executor() when
calling from async contexts.
"""

from __future__ import annotations

import numpy as np

import clickhouse_connect


class ByteHouseEmbeddingStore:
    """ClickHouse/ByteHouse store for GlobalVariableNode embeddings.

    Uses HaUniqueMergeTree so that re-inserting a record with an existing
    gcn_id performs an upsert (deduplication on primary key).
    """

    TABLE = "node_embeddings"

    _COLUMNS = ["gcn_id", "content", "node_type", "embedding", "source_id"]

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str = "paper_data",
        secure: bool = True,
        replication_root: str = "",
    ) -> None:
        """Connect to ByteHouse/ClickHouse.

        Args:
            host: ClickHouse server hostname.
            user: Username for authentication.
            password: Password for authentication.
            database: Target database name.
            secure: Whether to use TLS.
            replication_root: ZooKeeper path prefix for HaUniqueMergeTree DDL.
                Set via BYTEHOUSE_REPLICATION_ROOT env var.
        """
        self._database = database
        self._replication_root = replication_root
        self._client = clickhouse_connect.get_client(
            host=host,
            user=user,
            password=password,
            database=database,
            secure=secure,
            compress=False,  # ByteHouse doesn't support lz4
        )

    def ensure_table(self) -> None:
        """Create the node_embeddings table if it does not exist.

        Uses HaUniqueMergeTree so that gcn_id acts as a unique key —
        duplicate inserts are deduplicated automatically.

        ByteHouse requires explicit shard/replica path args for
        HaUniqueMergeTree (it's backed by ReplicatedMergeTree).
        """
        if not self._replication_root:
            raise ValueError(
                "bytehouse_replication_root is required for HaUniqueMergeTree DDL. "
                "Set BYTEHOUSE_REPLICATION_ROOT env var."
            )
        # Pattern: HaUniqueMergeTree('<root>/<db>.<table>/{shard}', '{replica}')
        table_fqn = f"{self._database}.{self.TABLE}"
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE} (
            gcn_id      String,
            content     String,
            node_type   String,
            embedding   Array(Float32),
            source_id   String,
            created_at  DateTime DEFAULT now()
        )
        ENGINE = HaUniqueMergeTree(
            '{self._replication_root}/{table_fqn}/{{shard}}',
            '{{replica}}'
        )
        ORDER BY gcn_id
        UNIQUE KEY gcn_id
        SETTINGS index_granularity = 128
        """
        self._client.command(ddl)

    def get_existing_gcn_ids(self) -> set[str]:
        """Return the set of all gcn_ids already stored in the table.

        Returns:
            Set of gcn_id strings currently in the table.
        """
        result = self._client.query(f"SELECT gcn_id FROM {self.TABLE}")
        return {row[0] for row in result.result_rows}

    def upsert_embeddings(self, records: list[dict]) -> None:
        """Batch insert embedding records.

        HaUniqueMergeTree handles deduplication on gcn_id, so re-inserting
        an existing gcn_id will overwrite the old record.

        Args:
            records: List of dicts, each with keys:
                gcn_id, content, node_type, embedding, source_id.
        """
        if not records:
            return
        data = [
            [r["gcn_id"], r["content"], r["node_type"], r["embedding"], r["source_id"]]
            for r in records
        ]
        self._client.insert(self.TABLE, data, column_names=self._COLUMNS)

    def load_embeddings_by_type(self, node_type: str) -> tuple[list[str], np.ndarray]:
        """Load all embeddings for a given node type.

        Args:
            node_type: Node type to filter by (e.g. "claim", "question").

        Returns:
            Tuple of (gcn_ids, matrix) where matrix has shape (N, dim) and
            dtype float32. Returns ([], np.array([])) when no rows exist.
        """
        result = self._client.query(
            f"SELECT gcn_id, embedding FROM {self.TABLE} WHERE node_type = %(node_type)s",
            parameters={"node_type": node_type},
        )
        rows = result.result_rows
        if not rows:
            return [], np.array([])

        gcn_ids = [row[0] for row in rows]
        matrix = np.array([row[1] for row in rows], dtype=np.float32)
        return gcn_ids, matrix

    def close(self) -> None:
        """Close the underlying ClickHouse connection."""
        self._client.close()
