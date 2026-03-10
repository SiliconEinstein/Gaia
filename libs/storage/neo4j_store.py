"""Neo4j-backed hypergraph store.

Graph model
-----------
- `:Proposition` nodes with ``{id: int}`` represent graph nodes (propositions).
- `:Hyperedge` nodes with ``{id, type, subtype, probability, verified, reasoning}``
  represent hyperedges.
- ``(:Proposition)-[:PREMISE]->(:Hyperedge)`` — premise relationship.
- ``(:Hyperedge)-[:CONCLUSION]->(:Proposition)`` — conclusion relationship.

One *knowledge hop* (proposition -> hyperedge -> proposition) equals **two**
Neo4j hops.
"""

from __future__ import annotations

import json
from typing import Any

import neo4j

from libs.models import HyperEdge
from libs.storage.graph_store import GraphStore


class Neo4jGraphStore(GraphStore):
    """Async Neo4j store for the Gaia hypergraph."""

    def __init__(self, driver: neo4j.AsyncDriver, database: str = "gaia") -> None:
        self._driver = driver
        self._db = database

    # ── Schema ───────────────────────────────────────────────────────────

    async def initialize_schema(self) -> None:
        """Create uniqueness constraints and migrate legacy relationships (idempotent)."""
        async with self._driver.session(database=self._db) as session:
            await session.run(
                "CREATE CONSTRAINT prop_id IF NOT EXISTS FOR (p:Proposition) REQUIRE p.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT he_id IF NOT EXISTS FOR (h:Hyperedge) REQUIRE h.id IS UNIQUE"
            )
            # Migrate legacy TAIL→PREMISE and HEAD→CONCLUSION relationships
            await session.run(
                "MATCH (p:Proposition)-[r:TAIL]->(h:Hyperedge) CREATE (p)-[:PREMISE]->(h) DELETE r"
            )
            await session.run(
                "MATCH (h:Hyperedge)-[r:HEAD]->(p:Proposition) "
                "CREATE (h)-[:CONCLUSION]->(p) "
                "DELETE r"
            )

    # ── Create ───────────────────────────────────────────────────────────

    async def create_hyperedge(self, edge: HyperEdge) -> int:
        """Persist a single hyperedge and return its id."""
        async with self._driver.session(database=self._db) as session:
            await session.execute_write(self._tx_create_hyperedge, edge)
        return edge.id

    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        """Persist many hyperedges in one transaction and return their ids."""
        async with self._driver.session(database=self._db) as session:
            for edge in edges:
                await session.execute_write(self._tx_create_hyperedge, edge)
        return [e.id for e in edges]

    @staticmethod
    async def _tx_create_hyperedge(tx: neo4j.AsyncManagedTransaction, edge: HyperEdge) -> None:
        """Transaction function: create one hyperedge with its relationships."""
        # 1. Create the Hyperedge node
        await tx.run(
            "CREATE (h:Hyperedge {"
            "  id: $id, type: $type, subtype: $subtype,"
            "  probability: $probability, verified: $verified,"
            "  reasoning: $reasoning"
            "})",
            id=edge.id,
            type=edge.type,
            subtype=edge.subtype or "",
            probability=edge.probability if edge.probability is not None else 0.0,
            verified=edge.verified,
            reasoning=json.dumps(edge.reasoning),
        )
        # 2. MERGE premise Proposition nodes and create PREMISE relationships
        for nid in edge.premises:
            await tx.run(
                "MERGE (p:Proposition {id: $nid}) "
                "WITH p "
                "MATCH (h:Hyperedge {id: $eid}) "
                "CREATE (p)-[:PREMISE]->(h)",
                nid=nid,
                eid=edge.id,
            )
        # 3. MERGE conclusion Proposition nodes and create CONCLUSION relationships
        for nid in edge.conclusions:
            await tx.run(
                "MERGE (p:Proposition {id: $nid}) "
                "WITH p "
                "MATCH (h:Hyperedge {id: $eid}) "
                "CREATE (h)-[:CONCLUSION]->(p)",
                nid=nid,
                eid=edge.id,
            )

    # ── Read ─────────────────────────────────────────────────────────────

    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        """Load a hyperedge by id, or return None."""
        async with self._driver.session(database=self._db) as session:
            result = await session.execute_read(self._tx_get_hyperedge, edge_id)
        return result

    @staticmethod
    async def _tx_get_hyperedge(
        tx: neo4j.AsyncManagedTransaction, edge_id: int
    ) -> HyperEdge | None:
        """Transaction function: read one hyperedge with premises/conclusions."""
        # Fetch the hyperedge properties
        res = await tx.run("MATCH (h:Hyperedge {id: $eid}) RETURN h", eid=edge_id)
        record = await res.single()
        if record is None:
            return None
        h = record["h"]

        # Fetch premise node ids
        premise_res = await tx.run(
            "MATCH (p:Proposition)-[:PREMISE]->(h:Hyperedge {id: $eid}) RETURN p.id AS nid",
            eid=edge_id,
        )
        premise_records = await premise_res.values()
        premise_ids = [r[0] for r in premise_records]

        # Fetch conclusion node ids
        conclusion_res = await tx.run(
            "MATCH (h:Hyperedge {id: $eid})-[:CONCLUSION]->(p:Proposition) RETURN p.id AS nid",
            eid=edge_id,
        )
        conclusion_records = await conclusion_res.values()
        conclusion_ids = [r[0] for r in conclusion_records]

        return HyperEdge(
            id=h["id"],
            type=h["type"],
            subtype=h["subtype"] if h["subtype"] else None,
            premises=premise_ids,
            conclusions=conclusion_ids,
            probability=h["probability"] if h["probability"] != 0.0 else None,
            verified=h["verified"],
            reasoning=json.loads(h["reasoning"]),
        )

    # ── Update ───────────────────────────────────────────────────────────

    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None:
        """Update scalar fields on an existing Hyperedge node."""
        if not fields:
            return
        # Build SET clause dynamically
        set_parts: list[str] = []
        params: dict[str, Any] = {"eid": edge_id}
        for key, value in fields.items():
            param_name = f"f_{key}"
            if key == "reasoning":
                value = json.dumps(value)
            set_parts.append(f"h.{key} = ${param_name}")
            params[param_name] = value

        query = f"MATCH (h:Hyperedge {{id: $eid}}) SET {', '.join(set_parts)}"
        async with self._driver.session(database=self._db) as session:
            await session.run(query, **params)

    # ── Subgraph ─────────────────────────────────────────────────────────

    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]:
        """Return (node_ids, edge_ids) reachable within *hops* knowledge hops.

        One knowledge hop = Proposition -> Hyperedge -> Proposition, which is
        two Neo4j hops.  We expand iteratively so that edge-type filtering
        is applied at every step.

        Args:
            node_ids: Seed proposition ids.
            hops: Number of knowledge hops to expand.
            edge_types: Optional list of edge types to include.
            direction: Traversal direction — ``"both"`` (default), ``"upstream"``
                (follow edges where node is in conclusions, going backward to premises),
                or ``"downstream"`` (follow edges where node is in premises, going
                forward to conclusions).
            max_nodes: Maximum total nodes in the returned subgraph.
        """
        async with self._driver.session(database=self._db) as session:
            result = await session.execute_read(
                self._tx_get_subgraph, node_ids, hops, edge_types, direction, max_nodes
            )
        return result

    @staticmethod
    async def _tx_get_subgraph(
        tx: neo4j.AsyncManagedTransaction,
        seed_ids: list[int],
        hops: int,
        edge_types: list[str] | None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]:
        """Iteratively expand the subgraph one knowledge hop at a time.

        Direction controls which edges are discovered from frontier nodes:
        - ``"downstream"``: only edges where frontier nodes are premises (forward).
        - ``"upstream"``: only edges where frontier nodes are conclusions (backward).
        - ``"both"``: edges in either direction (default, original behaviour).
        """
        visited_nodes: set[int] = set(seed_ids)
        visited_edges: set[int] = set()
        frontier: set[int] = set(seed_ids)

        for _ in range(hops):
            if not frontier:
                break
            if len(visited_nodes) >= max_nodes:
                break

            new_edge_ids: set[int] = set()

            # --- Downstream: frontier nodes appear as PREMISE ----------------
            if direction in ("both", "downstream"):
                if edge_types is not None:
                    he_query = (
                        "MATCH (p:Proposition)-[:PREMISE]->(h:Hyperedge) "
                        "WHERE p.id IN $frontier AND h.type IN $etypes "
                        "RETURN DISTINCT h.id AS hid"
                    )
                    he_res = await tx.run(he_query, frontier=list(frontier), etypes=edge_types)
                else:
                    he_query = (
                        "MATCH (p:Proposition)-[:PREMISE]->(h:Hyperedge) "
                        "WHERE p.id IN $frontier "
                        "RETURN DISTINCT h.id AS hid"
                    )
                    he_res = await tx.run(he_query, frontier=list(frontier))

                async for record in he_res:
                    new_edge_ids.add(record["hid"])

            # --- Upstream: frontier nodes appear as CONCLUSION ----------------
            if direction in ("both", "upstream"):
                if edge_types is not None:
                    he_rev_query = (
                        "MATCH (h:Hyperedge)-[:CONCLUSION]->(p:Proposition) "
                        "WHERE p.id IN $frontier AND h.type IN $etypes "
                        "RETURN DISTINCT h.id AS hid"
                    )
                    he_rev_res = await tx.run(
                        he_rev_query, frontier=list(frontier), etypes=edge_types
                    )
                else:
                    he_rev_query = (
                        "MATCH (h:Hyperedge)-[:CONCLUSION]->(p:Proposition) "
                        "WHERE p.id IN $frontier "
                        "RETURN DISTINCT h.id AS hid"
                    )
                    he_rev_res = await tx.run(he_rev_query, frontier=list(frontier))

                async for record in he_rev_res:
                    new_edge_ids.add(record["hid"])

            # Remove already-visited edges
            new_edge_ids -= visited_edges
            if not new_edge_ids:
                break
            visited_edges |= new_edge_ids

            # Collect propositions from the discovered edges.
            # Direction determines which side of the edge we follow into:
            # - downstream: collect CONCLUSION propositions (the outputs)
            # - upstream: collect PREMISE propositions (the inputs)
            # - both: collect from both sides
            node_query_parts: list[str] = []
            if direction in ("both", "downstream"):
                node_query_parts.append(
                    "MATCH (h:Hyperedge)-[:CONCLUSION]->(p:Proposition) "
                    "WHERE h.id IN $eids "
                    "RETURN DISTINCT p.id AS nid"
                )
            if direction in ("both", "upstream"):
                node_query_parts.append(
                    "MATCH (p:Proposition)-[:PREMISE]->(h:Hyperedge) "
                    "WHERE h.id IN $eids "
                    "RETURN DISTINCT p.id AS nid"
                )
            # For "both" we also need the other sides so full context is kept
            if direction == "both":
                node_query = (
                    "MATCH (p:Proposition)-[:PREMISE]->(h:Hyperedge) "
                    "WHERE h.id IN $eids "
                    "RETURN DISTINCT p.id AS nid "
                    "UNION "
                    "MATCH (h:Hyperedge)-[:CONCLUSION]->(p:Proposition) "
                    "WHERE h.id IN $eids "
                    "RETURN DISTINCT p.id AS nid"
                )
            else:
                node_query = " UNION ".join(node_query_parts)

            node_res = await tx.run(node_query, eids=list(new_edge_ids))
            new_nodes: set[int] = set()
            async for record in node_res:
                new_nodes.add(record["nid"])

            frontier = new_nodes - visited_nodes
            visited_nodes |= new_nodes

            # Enforce max_nodes cap
            if len(visited_nodes) >= max_nodes:
                break

        return visited_nodes, visited_edges

    # ── Lifecycle ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying driver."""
        await self._driver.close()
