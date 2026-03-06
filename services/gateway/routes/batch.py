"""Batch API routes -- all async via JobManager."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from libs.models import CommitRequest
from services.gateway.deps import deps
from services.job_manager.models import JobType

router = APIRouter(tags=["batch"])


# -- Batch Commit (#9) -------------------------------------------------------


class BatchCommitRequest(BaseModel):
    commits: list[CommitRequest]
    auto_review: bool = True
    auto_merge: bool = True


@router.post("/commits/batch")
async def batch_commit(request: BatchCommitRequest):
    async def work(job_id: str) -> dict:
        results = []
        for req in request.commits:
            commit_resp = await deps.commit_engine.submit(req)
            entry = {
                "commit_id": commit_resp.commit_id,
                "message": req.message,
                "status": commit_resp.status,
            }
            if commit_resp.status == "rejected":
                results.append(entry)
                continue

            if request.auto_review:
                job = await deps.commit_engine.submit_review(commit_resp.commit_id)
                timed_out = True
                for _ in range(100):
                    status = await deps.commit_engine.job_manager.get_status(job.job_id)
                    if status.status.value in ("completed", "failed"):
                        timed_out = False
                        break
                    await asyncio.sleep(0.05)

                approved = False
                if timed_out:
                    entry["status"] = "review_timeout"
                else:
                    review_result = await deps.commit_engine.job_manager.get_result(job.job_id)
                    approved = (
                        review_result.get("overall_verdict") == "pass"
                        if isinstance(review_result, dict)
                        else False
                    )
                    entry["status"] = "reviewed" if approved else "rejected"

                if approved and request.auto_merge:
                    merge_result = await deps.commit_engine.merge(commit_resp.commit_id)
                    entry["status"] = "merged" if merge_result.success else "merge_failed"
                    entry["merge_result"] = merge_result.model_dump()

            results.append(entry)
        return {"commits": results, "total": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_COMMIT,
        reference_id=f"batch_{len(request.commits)}",
        work_fn=work,
    )
    return {
        "job_id": job.job_id,
        "total_commits": len(request.commits),
        "status": job.status,
    }


@router.get("/commits/batch/{batch_id}")
async def get_batch_progress(batch_id: str):
    job = await deps.job_manager.get_status(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    result = job.result or {}
    commits = result.get("commits", [])
    progress = {}
    for c in commits:
        s = c.get("status", "unknown")
        progress[s] = progress.get(s, 0) + 1
    return {
        "job_id": job.job_id,
        "status": job.status,
        "total_commits": result.get("total", 0),
        "progress": progress,
        "commits": commits,
    }


@router.delete("/commits/batch/{batch_id}")
async def cancel_batch(batch_id: str):
    job = await deps.job_manager.get_status(batch_id)
    if not job:
        raise HTTPException(status_code=404, detail="Batch job not found")
    await deps.job_manager.cancel(batch_id)
    return {"job_id": job.job_id, "status": "cancelled"}


# -- Batch Read Nodes (#10) ---------------------------------------------------


class BatchReadNodesRequest(BaseModel):
    node_ids: list[int]


@router.post("/nodes/batch")
async def batch_read_nodes(request: BatchReadNodesRequest):
    async def work(job_id: str) -> dict:
        nodes = await deps.storage.lance.load_nodes_bulk(request.node_ids)
        return {"nodes": [n.model_dump() for n in nodes]}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"read_nodes_{len(request.node_ids)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# -- Batch Read Hyperedges (#10) ----------------------------------------------


class BatchReadEdgesRequest(BaseModel):
    edge_ids: list[int]


@router.post("/hyperedges/batch")
async def batch_read_edges(request: BatchReadEdgesRequest):
    async def work(job_id: str) -> dict:
        if not deps.storage.graph:
            return {"edges": [], "error": "Graph store not available"}
        edges = []
        for eid in request.edge_ids:
            edge = await deps.storage.graph.get_hyperedge(eid)
            if edge:
                edges.append(edge.model_dump())
        return {"edges": edges}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"read_edges_{len(request.edge_ids)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# -- Batch Subgraph (#10) -----------------------------------------------------


class SubgraphQuery(BaseModel):
    node_id: int
    hops: int = 3
    direction: str = "both"


class BatchSubgraphRequest(BaseModel):
    queries: list[SubgraphQuery]


@router.post("/nodes/subgraph/batch")
async def batch_subgraph(request: BatchSubgraphRequest):
    async def work(job_id: str) -> dict:
        if not deps.storage.graph:
            return {"subgraphs": [], "error": "Graph store not available"}
        results = []
        for q in request.queries:
            node_ids, edge_ids = await deps.storage.graph.get_subgraph(
                [q.node_id],
                hops=q.hops,
                direction=q.direction,
            )
            results.append(
                {
                    "center_node_id": q.node_id,
                    "node_ids": sorted(node_ids),
                    "edge_ids": sorted(edge_ids),
                }
            )
        return {"subgraphs": results}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_READ,
        reference_id=f"subgraph_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# -- Batch Search Nodes (#11) -------------------------------------------------


class BatchSearchQuery(BaseModel):
    text: str
    top_k: int = 50


class BatchSearchNodesRequest(BaseModel):
    queries: list[BatchSearchQuery]


@router.post("/search/nodes/batch")
async def batch_search_nodes(request: BatchSearchNodesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_nodes(text=q.text, k=q.top_k)
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}


# -- Batch Search Hyperedges (#11) --------------------------------------------


class BatchSearchEdgesRequest(BaseModel):
    queries: list[BatchSearchQuery]


@router.post("/search/hyperedges/batch")
async def batch_search_edges(request: BatchSearchEdgesRequest):
    async def work(job_id: str) -> dict:
        results = []
        for q in request.queries:
            scored = await deps.search_engine.search_edges(text=q.text, k=q.top_k)
            results.append([s.model_dump() for s in scored])
        return {"results": results, "total_queries": len(results)}

    job = await deps.job_manager.submit(
        job_type=JobType.BATCH_SEARCH,
        reference_id=f"edge_search_batch_{len(request.queries)}",
        work_fn=work,
    )
    return {"job_id": job.job_id, "status": job.status}
