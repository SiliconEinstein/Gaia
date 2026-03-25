"""Neo4j graph store — topology backend for KnowledgeNode and FactorNode traversal.

Implements :class:`GraphStore` using the neo4j async driver.
"""

from __future__ import annotations

import neo4j
import neo4j.exceptions

from gaia.libs.models.graph_ir import FactorNode, KnowledgeNode
from gaia.libs.storage.base import GraphStore


class Neo4jGraphStore(GraphStore):
    """GraphStore backed by a Neo4j instance via the async driver.

    Args:
        uri: Bolt URI, e.g. ``"bolt://localhost:7687"``.
        user: Neo4j username.
        password: Neo4j password.
        database: Neo4j database name (default ``"neo4j"``).
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
    ) -> None:
        self._uri = uri
        self._user = user
        self._password = password
        self._database = database
        self._driver: neo4j.AsyncDriver | None = None

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Create the driver, verify connectivity, and create uniqueness constraints."""
        auth = (self._user, self._password) if self._password else None
        self._driver = neo4j.AsyncGraphDatabase.driver(self._uri, auth=auth)
        await self._driver.verify_connectivity()

        async with self._driver.session(database=self._database) as session:
            # Uniqueness constraints also create an index automatically
            await session.run(
                "CREATE CONSTRAINT knowledge_node_id IF NOT EXISTS "
                "FOR (n:KnowledgeNode) REQUIRE n.id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT factor_node_id IF NOT EXISTS "
                "FOR (f:FactorNode) REQUIRE f.factor_id IS UNIQUE"
            )

    async def close(self) -> None:
        """Close the driver."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    # ── Write ──

    async def write_nodes(self, nodes: list[KnowledgeNode]) -> None:
        """MERGE KnowledgeNode by id, setting type property."""
        if not nodes:
            return
        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                UNWIND $rows AS row
                MERGE (n:KnowledgeNode {id: row.id})
                SET n.type = row.type
                """,
                rows=[{"id": n.id, "type": str(n.type)} for n in nodes],
            )

    async def write_factors(self, factors: list[FactorNode]) -> None:
        """MERGE FactorNode by factor_id, create PREMISE/CONCLUSION edges.

        For each factor:
        - MERGE (:KnowledgeNode)-[:PREMISE]->(:FactorNode) for each premise.
        - MERGE (:FactorNode)-[:CONCLUSION]->(:KnowledgeNode) for the conclusion
          (if non-null). Bilateral factors (equivalent/contradict) have no conclusion.
        """
        if not factors:
            return
        async with self._driver.session(database=self._database) as session:
            for factor in factors:
                # MERGE the FactorNode itself
                await session.run(
                    """
                    MERGE (f:FactorNode {factor_id: $factor_id})
                    SET f.scope = $scope,
                        f.category = $category,
                        f.stage = $stage,
                        f.reasoning_type = $reasoning_type
                    """,
                    factor_id=factor.factor_id,
                    scope=factor.scope,
                    category=str(factor.category),
                    stage=str(factor.stage),
                    reasoning_type=str(factor.reasoning_type) if factor.reasoning_type else None,
                )

                # Create PREMISE edges
                for premise_id in factor.premises:
                    await session.run(
                        """
                        MERGE (kn:KnowledgeNode {id: $node_id})
                        MERGE (f:FactorNode {factor_id: $factor_id})
                        MERGE (kn)-[:PREMISE]->(f)
                        """,
                        node_id=premise_id,
                        factor_id=factor.factor_id,
                    )

                # Create CONCLUSION edge if conclusion is present
                if factor.conclusion is not None:
                    await session.run(
                        """
                        MERGE (kn:KnowledgeNode {id: $node_id})
                        MERGE (f:FactorNode {factor_id: $factor_id})
                        MERGE (f)-[:CONCLUSION]->(kn)
                        """,
                        node_id=factor.conclusion,
                        factor_id=factor.factor_id,
                    )

    # ── Read ──

    async def get_neighbors(self, node_id: str) -> list[str]:
        """Return IDs of KnowledgeNodes connected via any factor (1-hop).

        Traverses both PREMISE and CONCLUSION edges in any direction to find
        all KnowledgeNodes reachable through a single FactorNode.
        """
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                """
                MATCH (start:KnowledgeNode {id: $node_id})
                MATCH (start)-[:PREMISE|CONCLUSION*1..2]-(neighbor:KnowledgeNode)
                WHERE neighbor.id <> $node_id
                RETURN DISTINCT neighbor.id AS id
                """,
                node_id=node_id,
            )
            records = await result.data()
            return [record["id"] for record in records]

    async def get_subgraph(
        self, node_ids: list[str], depth: int = 1
    ) -> tuple[list[str], list[str]]:
        """BFS to given depth, return (node_ids, factor_ids) reachable from seed nodes.

        Traverses PREMISE and CONCLUSION edges in any direction up to ``depth``
        factor hops from the seed nodes.
        """
        if not node_ids:
            return [], []

        async with self._driver.session(database=self._database) as session:
            # Build a variable-length path query. Each "hop" in graph terms
            # crosses one KnowledgeNode–FactorNode edge pair. We use a path of
            # length up to 2*depth (alternating KnowledgeNode ↔ FactorNode).
            max_length = depth * 2
            result = await session.run(
                f"""
                MATCH (start:KnowledgeNode)
                WHERE start.id IN $node_ids
                MATCH path = (start)-[:PREMISE|CONCLUSION*1..{max_length}]-(end)
                WITH nodes(path) AS path_nodes, relationships(path) AS path_rels
                UNWIND path_nodes AS n
                WITH n, path_rels
                UNWIND path_rels AS r
                WITH collect(DISTINCT
                    CASE WHEN n:KnowledgeNode THEN n.id ELSE NULL END
                ) AS all_nodes,
                collect(DISTINCT
                    CASE WHEN startNode(r):FactorNode THEN startNode(r).factor_id
                         WHEN endNode(r):FactorNode THEN endNode(r).factor_id
                         ELSE NULL END
                ) AS all_factors
                RETURN all_nodes, all_factors
                """,
                node_ids=node_ids,
            )
            records = await result.data()

        if not records:
            return list(node_ids), []

        row = records[0]
        collected_nodes = [nid for nid in (row.get("all_nodes") or []) if nid is not None]
        collected_factors = [fid for fid in (row.get("all_factors") or []) if fid is not None]

        # Always include seed nodes
        all_nodes = list({*node_ids, *collected_nodes})
        return all_nodes, collected_factors

    # ── Maintenance ──

    async def clean_all(self) -> None:
        """Delete all nodes and relationships."""
        async with self._driver.session(database=self._database) as session:
            await session.run("MATCH (n) DETACH DELETE n")
