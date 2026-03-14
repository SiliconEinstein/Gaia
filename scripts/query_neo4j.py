#!/usr/bin/env python3
"""Quick peek at Neo4j v2 graph data.

Usage:
    python scripts/query_neo4j.py                              # defaults
    NEO4J_URI=bolt://localhost:7687 python scripts/query_neo4j.py
"""

from __future__ import annotations

import asyncio
import os

import neo4j


URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
PASSWORD = os.environ.get("NEO4J_PASSWORD", "")
DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")


def section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


async def run_query(session: neo4j.AsyncSession, title: str, cypher: str) -> None:
    section(title)
    result = await session.run(cypher)
    records = [dict(r) async for r in result]
    if not records:
        print("  (empty)")
        return
    for r in records:
        parts = [f"{k}={v}" for k, v in r.items()]
        print(f"  {', '.join(parts)}")


async def main() -> None:
    auth = ("neo4j", PASSWORD) if PASSWORD else None
    driver = neo4j.AsyncGraphDatabase.driver(URI, auth=auth)
    print(f"Neo4j: {URI}  db={DATABASE}")

    async with driver.session(database=DATABASE) as s:
        await run_query(s, "Node counts by label", """
            MATCH (n)
            RETURN labels(n)[0] AS label, count(*) AS count
            ORDER BY count DESC
        """)

        await run_query(s, "Relationship counts by type", """
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(*) AS count
            ORDER BY count DESC
        """)

        await run_query(s, "Knowledge nodes (sample)", """
            MATCH (k:Knowledge)
            RETURN k.knowledge_id AS id, k.type AS type, k.belief AS belief
            ORDER BY k.knowledge_id
            LIMIT 10
        """)

        await run_query(s, "Chain nodes (sample)", """
            MATCH (c:Chain)
            RETURN c.chain_id AS id, c.type AS type
            ORDER BY c.chain_id
            LIMIT 10
        """)

        await run_query(s, "Chain topology: PREMISE -> Chain -> CONCLUSION", """
            MATCH (p:Knowledge)-[r1:PREMISE]->(c:Chain)-[r2:CONCLUSION]->(q:Knowledge)
            RETURN DISTINCT p.knowledge_id AS premise,
                   c.chain_id AS chain,
                   r1.step_index AS step,
                   q.knowledge_id AS conclusion
            ORDER BY chain, step
            LIMIT 20
        """)

        await run_query(s, "Most connected Knowledge nodes (by degree)", """
            MATCH (k:Knowledge)-[r]-()
            RETURN k.knowledge_id AS id, count(r) AS degree
            ORDER BY degree DESC
            LIMIT 10
        """)

    await driver.close()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
