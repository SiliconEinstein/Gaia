from fastapi import APIRouter
from pydantic import BaseModel
from services.gateway.deps import deps
from services.search_engine.models import NodeFilters, EdgeFilters

router = APIRouter(prefix="/search", tags=["search"])


class TextSearchRequest(BaseModel):
    query: str
    k: int = 50


@router.post("/text")
async def search_text(request: TextSearchRequest):
    """BM25-only text search — no embedding required."""
    results = await deps.storage.lance.fts_search(request.query, k=request.k)
    node_ids = [nid for nid, _ in results]
    nodes = await deps.storage.lance.load_nodes_bulk(node_ids)
    scores = {nid: score for nid, score in results}
    return [{"node": n.model_dump(), "score": scores.get(n.id, 0.0)} for n in nodes]


class SearchNodesRequest(BaseModel):
    query: str
    embedding: list[float]
    k: int = 50
    filters: NodeFilters | None = None
    paths: list[str] | None = None


class SearchEdgesRequest(BaseModel):
    query: str
    embedding: list[float]
    k: int = 50
    filters: EdgeFilters | None = None
    paths: list[str] | None = None


@router.post("/nodes")
async def search_nodes(request: SearchNodesRequest):
    results = await deps.search_engine.search_nodes(
        query=request.query,
        embedding=request.embedding,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
    return [r.model_dump() for r in results]


@router.post("/hyperedges")
async def search_hyperedges(request: SearchEdgesRequest):
    results = await deps.search_engine.search_edges(
        query=request.query,
        embedding=request.embedding,
        k=request.k,
        filters=request.filters,
        paths=request.paths,
    )
    return [r.model_dump() for r in results]
