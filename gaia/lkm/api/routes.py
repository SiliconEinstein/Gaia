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
    table = storage.content._db.open_table("global_variable_nodes")
    where = f"visibility = '{visibility}'"
    if type:
        where += f" AND type = '{type}'"
    rows = table.search().where(where).limit(limit).to_list()

    results = []
    for r in rows:
        import json

        # Resolve content via representative_lcn
        lcn = json.loads(r["representative_lcn"])
        local = await storage.get_local_variable(lcn["local_id"])
        content = local.content if local else None

        results.append(
            {
                "id": r["id"],
                "type": r["type"],
                "visibility": r["visibility"],
                "content": content,
                "content_hash": r["content_hash"],
                "parameters": json.loads(r["parameters"]),
                "local_members": json.loads(r["local_members"]),
                "representative_lcn": lcn,
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

    # Resolve content
    local = await storage.get_local_variable(gvar.representative_lcn.local_id)
    content = local.content if local else None

    # Find connected factors (where this variable is premise or conclusion)
    import json

    factor_table = storage.content._db.open_table("global_factor_nodes")
    all_factors = factor_table.search().limit(10000).to_list()

    connected_factors = []
    for f in all_factors:
        premises = json.loads(f["premises"])
        if gcn_id in premises or f["conclusion"] == gcn_id:
            # Resolve steps via representative_lfn
            local_factor = await storage.content.get_local_factor(f["representative_lfn"])
            connected_factors.append(
                {
                    "id": f["id"],
                    "factor_type": f["factor_type"],
                    "subtype": f["subtype"],
                    "premises": premises,
                    "conclusion": f["conclusion"],
                    "steps": [s.model_dump() for s in local_factor.steps]
                    if local_factor and local_factor.steps
                    else None,
                    "role": "premise" if gcn_id in premises else "conclusion",
                }
            )

    # Find bindings
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
    import json

    table = storage.content._db.open_table("global_factor_nodes")
    if factor_type:
        rows = table.search().where(f"factor_type = '{factor_type}'").limit(limit).to_list()
    else:
        rows = table.search().limit(limit).to_list()

    results = []
    for r in rows:
        local_factor = await storage.content.get_local_factor(r["representative_lfn"])
        results.append(
            {
                "id": r["id"],
                "factor_type": r["factor_type"],
                "subtype": r["subtype"],
                "premises": json.loads(r["premises"]),
                "conclusion": r["conclusion"],
                "source_package": r["source_package"],
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

    # Resolve steps
    local_factor = await storage.content.get_local_factor(gfac.representative_lfn)
    steps = (
        [s.model_dump() for s in local_factor.steps]
        if local_factor and local_factor.steps
        else None
    )

    # Resolve premise/conclusion content
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
    table = storage.content._db.open_table("canonical_bindings")
    conditions = []
    if package_id:
        conditions.append(f"package_id = '{package_id}'")
    if binding_type:
        conditions.append(f"binding_type = '{binding_type}'")

    if conditions:
        where = " AND ".join(conditions)
        rows = table.search().where(where).limit(limit).to_list()
    else:
        rows = table.search().limit(limit).to_list()

    return [
        {
            "local_id": r["local_id"],
            "global_id": r["global_id"],
            "binding_type": r["binding_type"],
            "package_id": r["package_id"],
            "version": r["version"],
            "decision": r["decision"],
            "reason": r["reason"],
        }
        for r in rows
    ]


@router.get("/graph")
async def get_graph(
    storage: StorageManager = Depends(get_storage),
):
    """Get full graph structure for visualization — nodes + edges."""
    import json

    # All global variables
    var_table = storage.content._db.open_table("global_variable_nodes")
    var_rows = var_table.search().limit(10000).to_list()

    nodes = []
    for r in var_rows:
        lcn = json.loads(r["representative_lcn"])
        local = await storage.get_local_variable(lcn["local_id"])
        nodes.append(
            {
                "id": r["id"],
                "type": "variable",
                "subtype": r["type"],
                "visibility": r["visibility"],
                "content": local.content if local else None,
                "local_members_count": len(json.loads(r["local_members"])),
            }
        )

    # All global factors
    fac_table = storage.content._db.open_table("global_factor_nodes")
    fac_rows = fac_table.search().limit(10000).to_list()

    edges = []
    for r in fac_rows:
        premises = json.loads(r["premises"])
        factor_node = {
            "id": r["id"],
            "type": "factor",
            "subtype": r["subtype"],
            "factor_type": r["factor_type"],
        }
        nodes.append(factor_node)
        # premise → factor edges
        for p in premises:
            edges.append({"source": p, "target": r["id"], "type": "premise"})
        # factor → conclusion edge
        edges.append({"source": r["id"], "target": r["conclusion"], "type": "conclusion"})

    return {"nodes": nodes, "edges": edges}
