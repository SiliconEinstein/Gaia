import asyncio

from fastapi import APIRouter, HTTPException, Query
from services.gateway.deps import deps

router = APIRouter(tags=["read"])


@router.get("/nodes/{node_id}")
async def get_node(node_id: int):
    node = await deps.storage.lance.load_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node.model_dump()


@router.get("/hyperedges/{edge_id}")
async def get_hyperedge(edge_id: int):
    if not deps.storage.graph:
        raise HTTPException(status_code=503, detail="Graph store not available")
    edge = await deps.storage.graph.get_hyperedge(edge_id)
    if not edge:
        raise HTTPException(status_code=404, detail="HyperEdge not found")
    return edge.model_dump()


@router.get("/nodes/{node_id}/subgraph")
async def get_node_subgraph(node_id: int, hops: int = 1):
    if not deps.storage.graph:
        raise HTTPException(status_code=503, detail="Graph store not available")
    node_ids, edge_ids = await deps.storage.graph.get_subgraph([node_id], hops=hops)
    return {"node_ids": list(node_ids), "edge_ids": list(edge_ids)}


@router.get("/nodes/{node_id}/subgraph/hydrated")
async def get_node_subgraph_hydrated(node_id: int, hops: int = 1):
    """Return full Node[] + HyperEdge[] for a subgraph, avoiding N+1 requests."""
    if not deps.storage.graph:
        raise HTTPException(status_code=503, detail="Graph store not available")

    node_ids, edge_ids = await deps.storage.graph.get_subgraph([node_id], hops=hops)

    # Load nodes and edges in parallel
    nodes_task = deps.storage.lance.load_nodes_bulk(list(node_ids))
    edges_task = asyncio.gather(*[deps.storage.graph.get_hyperedge(eid) for eid in edge_ids])
    nodes, edges = await asyncio.gather(nodes_task, edges_task)
    edges = [e for e in edges if e is not None]

    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@router.get("/nodes")
async def list_nodes(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    type: str | None = None,
):
    """Paginated node listing with optional type filter."""
    nodes = await deps.storage.lance.list_nodes(page=page, size=size, node_type=type)
    total = await deps.storage.lance.count_nodes(node_type=type)
    return {
        "items": [n.model_dump() for n in nodes],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/hyperedges")
async def list_hyperedges(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
):
    """Paginated hyperedge listing. Requires Neo4j."""
    if not deps.storage.graph:
        raise HTTPException(status_code=503, detail="Graph store not available")

    # Use Neo4j to list edges with pagination
    async with deps.storage.graph._driver.session(database=deps.storage.graph._db) as session:
        skip = (page - 1) * size
        result = await session.run(
            "MATCH (h:Hyperedge) RETURN h.id AS id ORDER BY h.id SKIP $skip LIMIT $limit",
            skip=skip,
            limit=size,
        )
        edge_ids = [record["id"] async for record in result]

        count_result = await session.run("MATCH (h:Hyperedge) RETURN count(h) AS total")
        count_record = await count_result.single()
        total = count_record["total"] if count_record else 0

    edges = await asyncio.gather(*[deps.storage.graph.get_hyperedge(eid) for eid in edge_ids])
    edges = [e for e in edges if e is not None]

    return {
        "items": [e.model_dump() for e in edges],
        "total": total,
        "page": page,
        "size": size,
    }


@router.get("/contradictions")
async def list_contradictions():
    """List contradiction hyperedges."""
    if not deps.storage.graph:
        raise HTTPException(status_code=503, detail="Graph store not available")

    async with deps.storage.graph._driver.session(database=deps.storage.graph._db) as session:
        result = await session.run(
            "MATCH (h:Hyperedge {type: 'contradiction'}) RETURN h.id AS id ORDER BY h.id"
        )
        edge_ids = [record["id"] async for record in result]

    edges = await asyncio.gather(*[deps.storage.graph.get_hyperedge(eid) for eid in edge_ids])
    edges = [e for e in edges if e is not None]
    return [e.model_dump() for e in edges]


@router.get("/stats")
async def get_stats():
    """System statistics overview."""
    node_count = await deps.storage.lance.count_nodes()
    graph_available = deps.storage.graph is not None

    stats = {
        "node_count": node_count,
        "graph_available": graph_available,
        "edge_count": 0,
        "node_types": {},
    }

    if graph_available:
        async with deps.storage.graph._driver.session(database=deps.storage.graph._db) as session:
            result = await session.run("MATCH (h:Hyperedge) RETURN count(h) AS total")
            record = await result.single()
            stats["edge_count"] = record["total"] if record else 0

    # Count nodes by type
    for ntype in ["paper-extract", "join", "deduction", "conjecture"]:
        count = await deps.storage.lance.count_nodes(node_type=ntype)
        if count > 0:
            stats["node_types"][ntype] = count

    return stats
