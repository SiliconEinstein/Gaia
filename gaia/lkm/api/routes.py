"""LKM API routes — minimal read endpoints for browsing storage."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from gaia.lkm.api.deps import get_storage
from gaia.lkm.storage import StorageManager

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/stats")
async def stats(storage: StorageManager = Depends(get_storage)):
    """Table row counts."""
    tables = [
        "local_variable_nodes",
        "local_factor_nodes",
        "global_variable_nodes",
        "global_factor_nodes",
        "canonical_bindings",
        "prior_records",
        "factor_param_records",
        "param_sources",
    ]
    counts = {}
    for t in tables:
        try:
            counts[t] = await storage.content.count(t)
        except Exception:
            counts[t] = 0
    return counts


@router.get("/variables")
async def list_variables(
    type: str | None = None,
    visibility: str = "public",
    limit: int = 100,
    storage: StorageManager = Depends(get_storage),
):
    """List global variables with content resolved via representative_lcn."""
    global_vars = await storage.content.list_global_variables(
        type_filter=type, visibility=visibility, limit=limit
    )
    results = []
    for gv in global_vars:
        local = await storage.get_local_variable(gv.representative_lcn.local_id)
        results.append(
            {
                "id": gv.id,
                "type": gv.type,
                "visibility": gv.visibility,
                "content": local.content if local else None,
                "content_hash": gv.content_hash,
                "parameters": [p.model_dump() for p in gv.parameters],
                "local_members": [m.model_dump() for m in gv.local_members],
                "representative_lcn": gv.representative_lcn.model_dump(),
            }
        )
    return results


@router.get("/variables/{gcn_id}")
async def get_variable(
    gcn_id: str,
    storage: StorageManager = Depends(get_storage),
):
    """Get a global variable by gcn_id, with content and connected factors."""
    gvar = await storage.get_global_variable(gcn_id)
    if not gvar:
        raise HTTPException(404, f"Variable {gcn_id} not found")

    local = await storage.get_local_variable(gvar.representative_lcn.local_id)
    content = local.content if local else None

    # Find connected factors
    all_factors = await storage.content.list_global_factors(limit=10000)
    connected_factors = []
    for gf in all_factors:
        if gcn_id in gf.premises or gf.conclusion == gcn_id:
            local_factor = await storage.content.get_local_factor(gf.representative_lfn)
            connected_factors.append(
                {
                    "id": gf.id,
                    "factor_type": gf.factor_type,
                    "subtype": gf.subtype,
                    "premises": gf.premises,
                    "conclusion": gf.conclusion,
                    "steps": [s.model_dump() for s in local_factor.steps]
                    if local_factor and local_factor.steps
                    else None,
                    "role": "premise" if gcn_id in gf.premises else "conclusion",
                }
            )

    bindings = await storage.find_bindings_by_global_id(gcn_id)

    return {
        "id": gvar.id,
        "type": gvar.type,
        "visibility": gvar.visibility,
        "content": content,
        "content_hash": gvar.content_hash,
        "parameters": [p.model_dump() for p in gvar.parameters],
        "representative_lcn": gvar.representative_lcn.model_dump(),
        "local_members": [m.model_dump() for m in gvar.local_members],
        "connected_factors": connected_factors,
        "bindings": [b.model_dump() for b in bindings],
    }


@router.get("/factors")
async def list_factors(
    factor_type: str | None = None,
    limit: int = 100,
    storage: StorageManager = Depends(get_storage),
):
    """List global factors with steps resolved."""
    global_factors = await storage.content.list_global_factors(factor_type=factor_type, limit=limit)
    results = []
    for gf in global_factors:
        local_factor = await storage.content.get_local_factor(gf.representative_lfn)
        results.append(
            {
                "id": gf.id,
                "factor_type": gf.factor_type,
                "subtype": gf.subtype,
                "premises": gf.premises,
                "conclusion": gf.conclusion,
                "source_package": gf.source_package,
                "steps": [s.model_dump() for s in local_factor.steps]
                if local_factor and local_factor.steps
                else None,
            }
        )
    return results


@router.get("/factors/{gfac_id}")
async def get_factor(
    gfac_id: str,
    storage: StorageManager = Depends(get_storage),
):
    """Get a global factor by gfac_id, with steps and resolved variable content."""
    gfac = await storage.get_global_factor(gfac_id)
    if not gfac:
        raise HTTPException(404, f"Factor {gfac_id} not found")

    local_factor = await storage.content.get_local_factor(gfac.representative_lfn)
    steps = (
        [s.model_dump() for s in local_factor.steps]
        if local_factor and local_factor.steps
        else None
    )

    async def resolve_var(gcn_id: str) -> dict:
        gv = await storage.get_global_variable(gcn_id)
        if not gv:
            return {"id": gcn_id, "content": None}
        local = await storage.get_local_variable(gv.representative_lcn.local_id)
        return {"id": gcn_id, "type": gv.type, "content": local.content if local else None}

    premises_resolved = [await resolve_var(p) for p in gfac.premises]
    conclusion_resolved = await resolve_var(gfac.conclusion)

    return {
        "id": gfac.id,
        "factor_type": gfac.factor_type,
        "subtype": gfac.subtype,
        "premises": premises_resolved,
        "conclusion": conclusion_resolved,
        "source_package": gfac.source_package,
        "steps": steps,
    }


@router.get("/bindings")
async def list_bindings(
    package_id: str | None = None,
    binding_type: str | None = None,
    limit: int = 200,
    storage: StorageManager = Depends(get_storage),
):
    """List canonical bindings with optional filters."""
    bindings = await storage.content.list_bindings(
        package_id=package_id, binding_type=binding_type, limit=limit
    )
    return [b.model_dump() for b in bindings]


@router.get("/graph")
async def get_graph(
    storage: StorageManager = Depends(get_storage),
):
    """Get full graph structure for visualization — nodes + edges."""
    global_vars = await storage.content.list_global_variables(limit=10000)
    global_factors = await storage.content.list_global_factors(limit=10000)

    nodes = []
    for gv in global_vars:
        local = await storage.get_local_variable(gv.representative_lcn.local_id)
        nodes.append(
            {
                "id": gv.id,
                "type": "variable",
                "subtype": gv.type,
                "visibility": gv.visibility,
                "content": local.content if local else None,
                "local_members_count": len(gv.local_members),
            }
        )

    edges = []
    for gf in global_factors:
        nodes.append(
            {
                "id": gf.id,
                "type": "factor",
                "subtype": gf.subtype,
                "factor_type": gf.factor_type,
            }
        )
        for p in gf.premises:
            edges.append({"source": p, "target": gf.id, "type": "premise"})
        edges.append({"source": gf.id, "target": gf.conclusion, "type": "conclusion"})

    return {"nodes": nodes, "edges": edges}
