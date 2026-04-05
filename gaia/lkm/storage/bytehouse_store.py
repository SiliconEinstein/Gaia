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

    # ── Discovery results persistence ──

    _RUNS_TABLE = "discovery_runs_v2"
    _CLUSTERS_TABLE = "discovery_clusters_v2"

    def ensure_discovery_tables(self) -> None:
        """Create discovery_runs and discovery_clusters tables if not exist."""
        if not self._replication_root:
            raise ValueError(
                "bytehouse_replication_root is required for HaUniqueMergeTree DDL. "
                "Set BYTEHOUSE_REPLICATION_ROOT env var."
            )
        db = self._database
        root = self._replication_root

        self._client.command(f"""
        CREATE TABLE IF NOT EXISTS {self._RUNS_TABLE} (
            run_id          String,
            threshold       Float32,
            faiss_k         UInt32,
            scope           String,
            embedding_count UInt32,
            type_counts     String,
            total_scanned   UInt32,
            total_computed  UInt32,
            total_clusters  UInt32,
            elapsed_seconds Float32,
            created_at      DateTime DEFAULT now()
        )
        ENGINE = HaUniqueMergeTree(
            '{root}/{db}.{self._RUNS_TABLE}/{{shard}}',
            '{{replica}}'
        )
        ORDER BY run_id
        UNIQUE KEY run_id
        SETTINGS index_granularity = 128
        """)

        self._client.command(f"""
        CREATE TABLE IF NOT EXISTS {self._CLUSTERS_TABLE} (
            run_id          String,
            cluster_id      String,
            node_type       String,
            gcn_ids         Array(String),
            centroid_gcn_id String,
            avg_similarity  Float32,
            min_similarity  Float32
        )
        ENGINE = HaUniqueMergeTree(
            '{root}/{db}.{self._CLUSTERS_TABLE}/{{shard}}',
            '{{replica}}'
        )
        ORDER BY (run_id, cluster_id)
        UNIQUE KEY (run_id, cluster_id)
        SETTINGS index_granularity = 128
        """)

    def save_discovery_result(
        self,
        result,
        config,
        scope: str = "full",
        type_counts: dict[str, int] | None = None,
    ) -> str:
        """Persist a ClusteringResult to ByteHouse.

        Args:
            result: ClusteringResult from run_semantic_discovery().
            config: DiscoveryConfig used for this run.
            scope: Data scope label, e.g. "full", "subset:10000".
            type_counts: Per-type embedding counts, e.g. {"claim": 9385, "question": 615}.

        Returns:
            The run_id assigned to this result.
        """
        import json as _json
        import uuid

        run_id = uuid.uuid4().hex[:16]
        embedding_count = sum((type_counts or {}).values())
        type_counts_json = _json.dumps(type_counts or {})

        # Write run metadata
        self._client.insert(
            self._RUNS_TABLE,
            [
                [
                    run_id,
                    config.similarity_threshold,
                    config.faiss_k,
                    scope,
                    embedding_count,
                    type_counts_json,
                    result.stats.total_variables_scanned,
                    result.stats.total_embeddings_computed,
                    result.stats.total_clusters,
                    result.stats.elapsed_seconds,
                ]
            ],
            column_names=[
                "run_id",
                "threshold",
                "faiss_k",
                "scope",
                "embedding_count",
                "type_counts",
                "total_scanned",
                "total_computed",
                "total_clusters",
                "elapsed_seconds",
            ],
        )

        # Write clusters in batches
        if result.clusters:
            rows = [
                [
                    run_id,
                    c.cluster_id,
                    c.node_type,
                    c.gcn_ids,
                    c.centroid_gcn_id,
                    c.avg_similarity,
                    c.min_similarity,
                ]
                for c in result.clusters
            ]
            for i in range(0, len(rows), 500):
                self._client.insert(
                    self._CLUSTERS_TABLE,
                    rows[i : i + 500],
                    column_names=[
                        "run_id",
                        "cluster_id",
                        "node_type",
                        "gcn_ids",
                        "centroid_gcn_id",
                        "avg_similarity",
                        "min_similarity",
                    ],
                )

        return run_id

    def load_latest_clusters(self) -> list[dict]:
        """Load clusters from the most recent discovery run.

        Returns list of dicts with cluster fields, or [] if no runs exist.
        """
        run_result = self._client.query(
            f"SELECT run_id FROM {self._RUNS_TABLE} ORDER BY created_at DESC LIMIT 1"
        )
        if not run_result.result_rows:
            return []
        run_id = run_result.result_rows[0][0]
        return self.load_clusters_by_run(run_id)

    def load_clusters_by_run(self, run_id: str) -> list[dict]:
        """Load all clusters for a specific run_id."""
        result = self._client.query(
            f"SELECT cluster_id, node_type, gcn_ids, centroid_gcn_id, "
            f"avg_similarity, min_similarity "
            f"FROM {self._CLUSTERS_TABLE} WHERE run_id = %(run_id)s",
            parameters={"run_id": run_id},
        )
        return [
            {
                "cluster_id": r[0],
                "node_type": r[1],
                "gcn_ids": r[2],
                "centroid_gcn_id": r[3],
                "avg_similarity": r[4],
                "min_similarity": r[5],
            }
            for r in result.result_rows
        ]

    def close(self) -> None:
        """Close the underlying ClickHouse connection."""
        self._client.close()
