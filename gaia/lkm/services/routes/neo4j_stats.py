"""Neo4j stats routes — node/factor/edge counts."""

from __future__ import annotations

from fastapi import APIRouter

from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["neo4j"])


@router.get("/neo4j/stats")
async def get_stats():
    """Return node and factor counts from Neo4j."""
    gs = deps_module.deps.storage.graph_store
    if gs is None:
        return {"knowledge_nodes": 0, "factor_nodes": 0, "edges": 0, "available": False}

    async with gs._driver.session(database=gs._database) as session:
        kn = await session.run("MATCH (n:KnowledgeNode) RETURN count(n) AS cnt")
        kn_count = (await kn.single())["cnt"]

        fn = await session.run("MATCH (n:FactorNode) RETURN count(n) AS cnt")
        fn_count = (await fn.single())["cnt"]

        edges = await session.run("MATCH ()-[r]->() RETURN count(r) AS cnt")
        edge_count = (await edges.single())["cnt"]

    return {
        "knowledge_nodes": kn_count,
        "factor_nodes": fn_count,
        "edges": edge_count,
        "available": True,
    }
