"""Kuzu-backed embedded graph store for local Gaia CLI.

Graph model
-----------
Identical to Neo4jGraphStore:
- ``Proposition`` nodes with ``{id: int}`` represent graph nodes (propositions).
- ``Hyperedge`` nodes with ``{id, type, subtype, probability, verified, reasoning}``
  represent hyperedges.
- ``(Proposition)-[TAIL]->(Hyperedge)`` — tail relationship.
- ``(Hyperedge)-[HEAD]->(Proposition)`` — head relationship.

Kuzu is an embedded graph database (like SQLite for graphs). Zero-config:
``pip install kuzu``. Its Python API is synchronous; we wrap in async methods
to satisfy the GraphStore ABC.
"""

from __future__ import annotations

import json
from typing import Any

import kuzu

from libs.models import HyperEdge
from libs.storage.graph_store import GraphStore


class KuzuGraphStore(GraphStore):
    """Embedded graph store using Kuzu. Zero-config, pip install kuzu."""

    def __init__(self, db_path: str) -> None:
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)

    # ── Schema ───────────────────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Synchronously create node/rel tables (idempotent).

        Called by StorageManager._init_kuzu() so the schema is ready
        before any async operations.
        """
        self._conn.execute("CREATE NODE TABLE IF NOT EXISTS Proposition(id INT64, PRIMARY KEY(id))")
        self._conn.execute(
            "CREATE NODE TABLE IF NOT EXISTS Hyperedge("
            "id INT64, type STRING, subtype STRING, "
            "probability DOUBLE, verified BOOLEAN, reasoning STRING, "
            "PRIMARY KEY(id))"
        )
        self._conn.execute("CREATE REL TABLE IF NOT EXISTS TAIL(FROM Proposition TO Hyperedge)")
        self._conn.execute("CREATE REL TABLE IF NOT EXISTS HEAD(FROM Hyperedge TO Proposition)")

    async def initialize_schema(self) -> None:
        """Create node/rel tables (idempotent)."""
        self._ensure_schema()

    # ── Create ───────────────────────────────────────────────────────────

    async def create_hyperedge(self, edge: HyperEdge) -> int:
        """Persist a single hyperedge and return its id."""
        for nid in set(edge.tail + edge.head):
            self._conn.execute("MERGE (p:Proposition {id: $id})", {"id": nid})

        self._conn.execute(
            "CREATE (h:Hyperedge {id: $id, type: $type, subtype: $subtype, "
            "probability: $prob, verified: $verified, reasoning: $reasoning})",
            {
                "id": edge.id,
                "type": edge.type,
                "subtype": edge.subtype or "",
                "prob": edge.probability if edge.probability is not None else 0.0,
                "verified": edge.verified,
                "reasoning": json.dumps(edge.reasoning),
            },
        )

        for nid in edge.tail:
            self._conn.execute(
                "MATCH (p:Proposition {id: $nid}), (h:Hyperedge {id: $eid}) "
                "CREATE (p)-[:TAIL]->(h)",
                {"nid": nid, "eid": edge.id},
            )

        for nid in edge.head:
            self._conn.execute(
                "MATCH (h:Hyperedge {id: $eid}), (p:Proposition {id: $nid}) "
                "CREATE (h)-[:HEAD]->(p)",
                {"eid": edge.id, "nid": nid},
            )

        return edge.id

    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        """Persist many hyperedges and return their ids."""
        for edge in edges:
            await self.create_hyperedge(edge)
        return [e.id for e in edges]

    # ── Read ─────────────────────────────────────────────────────────────

    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        """Load a hyperedge by id, or return None."""
        result = self._conn.execute(
            "MATCH (h:Hyperedge {id: $eid}) "
            "RETURN h.id, h.type, h.subtype, h.probability, h.verified, h.reasoning",
            {"eid": edge_id},
        )
        if not result.has_next():
            return None
        row = result.get_next()

        tail_result = self._conn.execute(
            "MATCH (p:Proposition)-[:TAIL]->(h:Hyperedge {id: $eid}) RETURN p.id",
            {"eid": edge_id},
        )
        tail_ids = [r[0] for r in tail_result.get_as_df().values]

        head_result = self._conn.execute(
            "MATCH (h:Hyperedge {id: $eid})-[:HEAD]->(p:Proposition) RETURN p.id",
            {"eid": edge_id},
        )
        head_ids = [r[0] for r in head_result.get_as_df().values]

        return HyperEdge(
            id=row[0],
            type=row[1],
            subtype=row[2] if row[2] else None,
            tail=tail_ids,
            head=head_ids,
            probability=row[3] if row[3] != 0.0 else None,
            verified=row[4],
            reasoning=json.loads(row[5]),
        )

    # ── Update ───────────────────────────────────────────────────────────

    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None:
        """Update scalar fields on an existing Hyperedge node."""
        if not fields:
            return
        set_parts: list[str] = []
        params: dict[str, Any] = {"eid": edge_id}
        for key, value in fields.items():
            param_name = f"f_{key}"
            if key == "reasoning":
                value = json.dumps(value)
            set_parts.append(f"h.{key} = ${param_name}")
            params[param_name] = value

        query = f"MATCH (h:Hyperedge {{id: $eid}}) SET {', '.join(set_parts)}"
        self._conn.execute(query, params)

    # ── Subgraph ─────────────────────────────────────────────────────────

    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]:
        """Return (node_ids, edge_ids) reachable within *hops* knowledge hops."""
        visited_nodes: set[int] = set(node_ids)
        visited_edges: set[int] = set()
        frontier: set[int] = set(node_ids)

        for _ in range(hops):
            if not frontier or len(visited_nodes) >= max_nodes:
                break

            new_edge_ids: set[int] = set()

            if direction in ("both", "downstream"):
                for nid in frontier:
                    res = self._conn.execute(
                        "MATCH (p:Proposition {id: $nid})-[:TAIL]->(h:Hyperedge) RETURN h.id",
                        {"nid": nid},
                    )
                    for row in res.get_as_df().values:
                        eid = int(row[0])
                        if edge_types is None or self._get_edge_type(eid) in edge_types:
                            new_edge_ids.add(eid)

            if direction in ("both", "upstream"):
                for nid in frontier:
                    res = self._conn.execute(
                        "MATCH (h:Hyperedge)-[:HEAD]->(p:Proposition {id: $nid}) RETURN h.id",
                        {"nid": nid},
                    )
                    for row in res.get_as_df().values:
                        eid = int(row[0])
                        if edge_types is None or self._get_edge_type(eid) in edge_types:
                            new_edge_ids.add(eid)

            new_edge_ids -= visited_edges
            if not new_edge_ids:
                break
            visited_edges |= new_edge_ids

            new_nodes: set[int] = set()
            for eid in new_edge_ids:
                if direction in ("both", "downstream"):
                    res = self._conn.execute(
                        "MATCH (h:Hyperedge {id: $eid})-[:HEAD]->(p:Proposition) RETURN p.id",
                        {"eid": eid},
                    )
                    for row in res.get_as_df().values:
                        new_nodes.add(int(row[0]))
                if direction in ("both", "upstream"):
                    res = self._conn.execute(
                        "MATCH (p:Proposition)-[:TAIL]->(h:Hyperedge {id: $eid}) RETURN p.id",
                        {"eid": eid},
                    )
                    for row in res.get_as_df().values:
                        new_nodes.add(int(row[0]))

            frontier = new_nodes - visited_nodes
            visited_nodes |= new_nodes

            if len(visited_nodes) >= max_nodes:
                break

        return visited_nodes, visited_edges

    def _get_edge_type(self, edge_id: int) -> str | None:
        """Helper: fetch the type of a hyperedge by id."""
        res = self._conn.execute("MATCH (h:Hyperedge {id: $eid}) RETURN h.type", {"eid": edge_id})
        if res.has_next():
            return res.get_next()[0]
        return None

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """No-op — Kuzu handles cleanup on garbage collection."""
