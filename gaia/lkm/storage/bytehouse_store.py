"""ByteHouse (ClickHouse-compatible) store for node embeddings.

All methods are synchronous — the ClickHouse driver is sync.
Callers must wrap with asyncio.get_event_loop().run_in_executor() when
calling from async contexts.
"""

from __future__ import annotations

import logging

import numpy as np

import clickhouse_connect

logger = logging.getLogger(__name__)


class ByteHouseEmbeddingStore:
    """ClickHouse/ByteHouse store for GlobalVariableNode embeddings.

    Uses HaUniqueMergeTree so that re-inserting a record with an existing
    gcn_id performs an upsert (deduplication on primary key).
    """

    TABLE = "gcn_embeddings"

    _COLUMNS = ["gcn_id", "package_id", "content", "node_type", "role", "embedding", "source_id"]

    _EMBEDDING_STATUS_TABLE = "embedding_status"

    def __init__(
        self,
        host: str,
        user: str,
        password: str,
        database: str = "paper_data",
        secure: bool = True,
        replication_root: str = "",
    ) -> None:
        self._database = database
        self._replication_root = replication_root
        self._client = clickhouse_connect.get_client(
            host=host,
            user=user,
            password=password,
            database=database,
            secure=secure,
            compress=False,
        )

    def _require_replication_root(self) -> None:
        if not self._replication_root:
            raise ValueError(
                "bytehouse_replication_root is required for HaUniqueMergeTree DDL. "
                "Set BYTEHOUSE_REPLICATION_ROOT env var."
            )

    def _engine_ddl(self, table_fqn: str) -> str:
        return (
            f"ENGINE = HaUniqueMergeTree("
            f"'{self._replication_root}/{table_fqn}/{{shard}}', '{{replica}}')"
        )

    # ── Table creation ──

    def ensure_table(self) -> None:
        """Create node_embeddings table with package_id and role columns."""
        self._require_replication_root()
        table_fqn = f"{self._database}.{self.TABLE}"
        self._client.command(f"""
        CREATE TABLE IF NOT EXISTS {self.TABLE} (
            gcn_id      String,
            package_id  String DEFAULT '',
            content     String,
            node_type   String,
            role        String DEFAULT '',
            embedding   Array(Float32),
            source_id   String,
            created_at  DateTime DEFAULT now()
        )
        {self._engine_ddl(table_fqn)}
        ORDER BY gcn_id
        UNIQUE KEY gcn_id
        SETTINGS index_granularity = 128
        """)

    def ensure_embedding_status_table(self) -> None:
        """Create embedding_status table for per-package tracking."""
        self._require_replication_root()
        table_fqn = f"{self._database}.{self._EMBEDDING_STATUS_TABLE}"
        self._client.command(f"""
        CREATE TABLE IF NOT EXISTS {self._EMBEDDING_STATUS_TABLE} (
            package_id      String,
            status          String DEFAULT 'pending',
            total_variables UInt32 DEFAULT 0,
            embedded_count  UInt32 DEFAULT 0,
            failed_count    UInt32 DEFAULT 0,
            updated_at      DateTime DEFAULT now()
        )
        {self._engine_ddl(table_fqn)}
        ORDER BY package_id
        UNIQUE KEY package_id
        SETTINGS index_granularity = 128
        """)

    def ensure_all_tables(self) -> None:
        """Create all required tables."""
        self.ensure_table()
        self.ensure_embedding_status_table()
        self.ensure_discovery_tables()

    # ── Embedding CRUD ──

    def get_existing_gcn_ids(self) -> set[str]:
        """Return the set of all gcn_ids already stored."""
        result = self._client.query(f"SELECT gcn_id FROM {self.TABLE}")
        return {row[0] for row in result.result_rows}

    def upsert_embeddings(self, records: list[dict]) -> None:
        """Batch insert embedding records.

        Each record: {gcn_id, package_id, content, node_type, embedding, source_id}.
        package_id is optional (defaults to '').
        """
        if not records:
            return
        data = [
            [
                r["gcn_id"],
                r.get("package_id", ""),
                r["content"],
                r["node_type"],
                r.get("role", ""),
                r["embedding"],
                r["source_id"],
            ]
            for r in records
        ]
        self._client.insert(self.TABLE, data, column_names=self._COLUMNS)

    def load_embeddings_by_type(self, node_type: str) -> tuple[list[str], np.ndarray]:
        """Load all embeddings for a given node type."""
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

    # ── Embedding status tracking ──

    def refresh_embedding_status(self) -> dict:
        """Refresh embedding_status from node_embeddings.

        Groups by package_id, counts embedded variables, writes to
        embedding_status table. Returns summary stats.
        """
        # Get per-package counts from embeddings
        result = self._client.query(f"""
        SELECT package_id, count() as cnt
        FROM {self.TABLE}
        WHERE package_id != ''
        GROUP BY package_id
        """)

        if not result.result_rows:
            return {"packages": 0, "updated": 0}

        rows = [[row[0], "completed", 0, row[1], 0] for row in result.result_rows]

        # Batch insert (HaUniqueMergeTree deduplicates on package_id)
        for i in range(0, len(rows), 500):
            self._client.insert(
                self._EMBEDDING_STATUS_TABLE,
                rows[i : i + 500],
                column_names=[
                    "package_id",
                    "status",
                    "total_variables",
                    "embedded_count",
                    "failed_count",
                ],
            )

        logger.info("Refreshed embedding_status: %d packages", len(rows))
        return {"packages": len(rows), "updated": len(rows)}

    def get_embedding_status_summary(self) -> dict:
        """Get summary of embedding status."""
        result = self._client.query(f"""
        SELECT
            count() as total_packages,
            sum(embedded_count) as total_embedded,
            countIf(status = 'completed') as completed_packages
        FROM {self._EMBEDDING_STATUS_TABLE}
        """)
        if not result.result_rows:
            return {"total_packages": 0, "total_embedded": 0, "completed_packages": 0}
        r = result.result_rows[0]
        return {
            "total_packages": r[0],
            "total_embedded": r[1],
            "completed_packages": r[2],
        }

    # ── Discovery results persistence ──

    _RUNS_TABLE = "clustering_runs"
    _CLUSTERS_TABLE = "clustering_results"

    def ensure_discovery_tables(self) -> None:
        """Create discovery_runs and discovery_clusters tables if not exist."""
        self._require_replication_root()
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
        """Persist a ClusteringResult to ByteHouse."""
        import json as _json
        import uuid

        run_id = uuid.uuid4().hex[:16]
        embedding_count = sum((type_counts or {}).values())
        type_counts_json = _json.dumps(type_counts or {})

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
        """Load clusters from the most recent discovery run."""
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
