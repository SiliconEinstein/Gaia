"""KuzuGraphStore — embedded graph backend using Kùzu."""

import asyncio
from functools import partial
from pathlib import Path

import kuzu

from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    ResourceAttachment,
    ScoredClosure,
    Subgraph,
)

_SCHEMA_STATEMENTS = [
    (
        "CREATE NODE TABLE IF NOT EXISTS Closure("
        "closure_id STRING, version INT64, type STRING, "
        "prior DOUBLE, belief DOUBLE, "
        "PRIMARY KEY(closure_id))"
    ),
    (
        "CREATE NODE TABLE IF NOT EXISTS Chain("
        "chain_id STRING, type STRING, probability DOUBLE, "
        "PRIMARY KEY(chain_id))"
    ),
    "CREATE REL TABLE IF NOT EXISTS PREMISE(FROM Closure TO Chain, step_index INT64)",
    "CREATE REL TABLE IF NOT EXISTS CONCLUSION(FROM Chain TO Closure, step_index INT64)",
]


class KuzuGraphStore(GraphStore):
    """Graph topology backend backed by an embedded Kùzu database.

    Kùzu's Python API is synchronous, so all public methods offload work to
    a thread via ``asyncio.to_thread``.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db = kuzu.Database(str(db_path))
        self._conn = kuzu.Connection(self._db)

    # ── helpers ──

    def _execute(self, query: str) -> kuzu.QueryResult:
        """Run a Cypher query synchronously on the internal connection."""
        return self._conn.execute(query)

    # ── Schema setup ──

    async def initialize_schema(self) -> None:
        """Create node/rel tables if they do not already exist."""
        loop = asyncio.get_running_loop()
        for stmt in _SCHEMA_STATEMENTS:
            await loop.run_in_executor(None, partial(self._execute, stmt))

    # ── Write (stubs) ──

    async def write_topology(self, closures: list[Closure], chains: list[Chain]) -> None:
        raise NotImplementedError

    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
        raise NotImplementedError

    async def update_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        raise NotImplementedError

    async def update_probability(self, chain_id: str, step_index: int, value: float) -> None:
        raise NotImplementedError

    # ── Query (stubs) ──

    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        raise NotImplementedError

    async def get_subgraph(self, closure_id: str, max_closures: int = 500) -> Subgraph:
        raise NotImplementedError

    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredClosure]:
        raise NotImplementedError

    # ── Lifecycle ──

    async def close(self) -> None:
        """Release the Kùzu connection."""
        self._conn.close()
