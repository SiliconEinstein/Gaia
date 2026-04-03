"""Neo4j graph store for LKM — global layer topology only.

Stores GlobalVariableNode and GlobalFactorNode as graph nodes,
with PREMISE and CONCLUSION edges. Content is NOT stored here —
always retrieved from LanceDB.

All writes use UNWIND batch operations (no per-node loops).
"""

from __future__ import annotations

from typing import Any

import neo4j

from gaia.lkm.models import GlobalFactorNode, GlobalVariableNode


class Neo4jGraphStore:
    """Neo4j-backed graph store for LKM global layer."""

    def __init__(self, driver: neo4j.AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    async def initialize_schema(self) -> None:
        """Create indexes and constraints."""
        async with self._driver.session(database=self._database) as session:
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (v:Variable) REQUIRE v.gcn_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Factor) REQUIRE f.gfac_id IS UNIQUE"
            )

    async def close(self) -> None:
        await self._driver.close()

    # ── Writes (UNWIND batch) ──

    async def write_variables(self, nodes: list[GlobalVariableNode]) -> None:
        """Batch write global variable nodes."""
        if not nodes:
            return
        records = [{"gcn_id": n.id, "type": n.type, "visibility": n.visibility} for n in nodes]
        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                UNWIND $nodes AS n
                MERGE (v:Variable {gcn_id: n.gcn_id})
                SET v.type = n.type, v.visibility = n.visibility
                """,
                nodes=records,
            )

    async def write_factors(self, nodes: list[GlobalFactorNode]) -> None:
        """Batch write global factor nodes."""
        if not nodes:
            return
        records = [
            {
                "gfac_id": n.id,
                "factor_type": n.factor_type,
                "subtype": n.subtype,
                "source_package": n.source_package,
            }
            for n in nodes
        ]
        async with self._driver.session(database=self._database) as session:
            await session.run(
                """
                UNWIND $nodes AS n
                MERGE (f:Factor {gfac_id: n.gfac_id})
                SET f.factor_type = n.factor_type,
                    f.subtype = n.subtype,
                    f.source_package = n.source_package
                """,
                nodes=records,
            )

    async def write_edges(
        self,
        variable_nodes: list[GlobalVariableNode],
        factor_nodes: list[GlobalFactorNode],
    ) -> None:
        """Batch write PREMISE and CONCLUSION edges for the given factors."""
        if not factor_nodes:
            return

        premise_edges = []
        conclusion_edges = []
        for f in factor_nodes:
            for p in f.premises:
                premise_edges.append({"var_id": p, "fac_id": f.id})
            conclusion_edges.append({"fac_id": f.id, "var_id": f.conclusion})

        async with self._driver.session(database=self._database) as session:
            if premise_edges:
                await session.run(
                    """
                    UNWIND $edges AS e
                    MATCH (v:Variable {gcn_id: e.var_id})
                    MATCH (f:Factor {gfac_id: e.fac_id})
                    MERGE (v)-[:PREMISE]->(f)
                    """,
                    edges=premise_edges,
                )
            if conclusion_edges:
                await session.run(
                    """
                    UNWIND $edges AS e
                    MATCH (f:Factor {gfac_id: e.fac_id})
                    MATCH (v:Variable {gcn_id: e.var_id})
                    MERGE (f)-[:CONCLUSION]->(v)
                    """,
                    edges=conclusion_edges,
                )

    async def write_global_graph(
        self,
        variable_nodes: list[GlobalVariableNode],
        factor_nodes: list[GlobalFactorNode],
    ) -> None:
        """Write variables, factors, and all edges in one call."""
        await self.write_variables(variable_nodes)
        await self.write_factors(factor_nodes)
        await self.write_edges(variable_nodes, factor_nodes)

    # ── Reads ──

    async def get_subgraph(self, gcn_id: str, hops: int = 2) -> dict[str, Any]:
        """Get N-hop subgraph around a variable node.

        Returns the seed node even if it has no edges (isolated variable).
        The hops bound is inlined into the Cypher text because Neo4j does not
        support parameterized variable-length path bounds.
        """
        hops = int(hops)  # sanitize — must be a literal integer in Cypher
        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                f"""
                MATCH (start:Variable {{gcn_id: $gcn_id}})
                OPTIONAL MATCH path = (start)-[*1..{hops}]-(n)
                WITH start,
                     CASE WHEN path IS NOT NULL THEN nodes(path) ELSE [start] END AS ns,
                     CASE WHEN path IS NOT NULL THEN relationships(path) ELSE [] END AS rs
                UNWIND ns AS node
                UNWIND CASE WHEN size(rs) > 0 THEN rs ELSE [null] END AS rel
                WITH COLLECT(DISTINCT node) AS all_nodes,
                     COLLECT(DISTINCT rel) AS all_rels_raw
                RETURN all_nodes,
                       [r IN all_rels_raw WHERE r IS NOT NULL] AS all_rels
                """,
                gcn_id=gcn_id,
            )
            record = await result.single()
            if not record:
                return {"nodes": [], "edges": []}

            nodes = []
            for node in record["all_nodes"]:
                labels = list(node.labels)
                if "Variable" in labels:
                    nodes.append(
                        {
                            "id": node["gcn_id"],
                            "type": "variable",
                            "subtype": node.get("type", "claim"),
                            "visibility": node.get("visibility", "public"),
                        }
                    )
                elif "Factor" in labels:
                    nodes.append(
                        {
                            "id": node["gfac_id"],
                            "type": "factor",
                            "subtype": node.get("subtype", ""),
                            "factor_type": node.get("factor_type", ""),
                        }
                    )

            edges = []
            for rel in record["all_rels"]:
                start_node = rel.start_node
                end_node = rel.end_node
                source = start_node.get("gcn_id") or start_node.get("gfac_id")
                target = end_node.get("gcn_id") or end_node.get("gfac_id")
                if source and target:
                    edges.append(
                        {
                            "source": source,
                            "target": target,
                            "type": rel.type.lower(),
                        }
                    )

            return {"nodes": nodes, "edges": edges}

    async def get_neighbors(self, gcn_id: str, direction: str = "both") -> list[dict]:
        """Get direct neighbors of a variable node."""
        if direction == "upstream":
            pattern = "(n)-[]->(v:Variable {gcn_id: $gcn_id})"
        elif direction == "downstream":
            pattern = "(v:Variable {gcn_id: $gcn_id})-[]->(n)"
        else:
            pattern = "(v:Variable {gcn_id: $gcn_id})-[]-(n)"

        async with self._driver.session(database=self._database) as session:
            result = await session.run(
                f"MATCH {pattern} RETURN DISTINCT n",
                gcn_id=gcn_id,
            )
            neighbors = []
            async for record in result:
                node = record["n"]
                labels = list(node.labels)
                if "Variable" in labels:
                    neighbors.append(
                        {
                            "id": node["gcn_id"],
                            "type": "variable",
                            "subtype": node.get("type", ""),
                        }
                    )
                elif "Factor" in labels:
                    neighbors.append(
                        {
                            "id": node["gfac_id"],
                            "type": "factor",
                            "subtype": node.get("subtype", ""),
                        }
                    )
            return neighbors

    async def count_nodes(self) -> dict[str, int]:
        """Count variable and factor nodes."""
        async with self._driver.session(database=self._database) as session:
            var_result = await session.run("MATCH (v:Variable) RETURN count(v) AS c")
            var_record = await var_result.single()
            fac_result = await session.run("MATCH (f:Factor) RETURN count(f) AS c")
            fac_record = await fac_result.single()
            return {
                "variables": var_record["c"] if var_record else 0,
                "factors": fac_record["c"] if fac_record else 0,
            }
