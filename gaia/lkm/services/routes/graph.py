"""Graph routes — serve Graph IR for frontend visualization."""

from __future__ import annotations

from fastapi import APIRouter, Query

from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["graph"])


@router.get("/graph")
async def get_graph(
    scope: str = Query("global", description="global or local"),
    package_id: str | None = Query(None, description="Package ID for local scope"),
):
    """Return knowledge nodes + factor nodes for visualization.

    scope=global: return gcn_ nodes + gcf_ factors
    scope=local: return lcn_ nodes + lcf_ factors for a specific package
    """
    storage = deps_module.deps.storage

    if scope == "global":
        nodes = await storage.get_knowledge_nodes(prefix="gcn_")
        factors = await storage.get_factor_nodes(scope="global")

        # Get latest belief state for belief values
        belief_states = await storage.get_belief_states(limit=1)
        beliefs = belief_states[0].beliefs if belief_states else {}
    else:
        # Local: filter by package via bindings
        nodes = await storage.get_knowledge_nodes(prefix="lcn_")
        factors = await storage.get_factor_nodes(scope="local")
        beliefs = {}

        if package_id:
            bindings = await storage.get_bindings(package_id=package_id)
            local_ids = {b.local_canonical_id for b in bindings}
            # Deduplicate nodes by id (same lcn_ can appear from multiple packages)
            seen_ids: set[str] = set()
            deduped_nodes = []
            for n in nodes:
                if n.id in local_ids and n.id not in seen_ids:
                    deduped_nodes.append(n)
                    seen_ids.add(n.id)
            nodes = deduped_nodes
            # Filter factors: all premises must be in this package's local_ids
            filtered_factors = []
            for f in factors:
                if all(p in local_ids for p in f.premises):
                    if f.conclusion is None or f.conclusion in local_ids:
                        filtered_factors.append(f)
            factors = filtered_factors

    # Also get prior records for display
    priors = {}
    prior_records = await storage.get_prior_records()
    for pr in prior_records:
        priors[pr.gcn_id] = pr.value  # latest overwrites older

    # Build response
    node_list = []
    for n in nodes:
        node_list.append(
            {
                "id": n.id,
                "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                "content": n.content or "(via representative_lcn)",
                "belief": beliefs.get(n.id),
                "prior": priors.get(n.id),
            }
        )

    factor_list = []
    for f in factors:
        factor_list.append(
            {
                "id": f.factor_id,
                "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                "stage": f.stage.value if hasattr(f.stage, "value") else str(f.stage),
                "reasoning_type": (
                    f.reasoning_type.value
                    if f.reasoning_type and hasattr(f.reasoning_type, "value")
                    else str(f.reasoning_type)
                    if f.reasoning_type
                    else None
                ),
                "premises": f.premises,
                "conclusion": f.conclusion,
            }
        )

    # Build edges from factors (premise→factor, factor→conclusion)
    # Also add factor nodes to the node list for bipartite graph rendering
    edge_list = []
    for f_data in factor_list:
        fid = f_data["id"]
        # Add factor as a node
        node_list.append(
            {
                "id": fid,
                "type": "factor",
                "content": f_data["reasoning_type"] or f_data["category"],
                "belief": None,
                "prior": None,
                "reasoning_type": f_data["reasoning_type"],
            }
        )
        # Premise → factor edges
        for p in f_data["premises"]:
            edge_list.append({"from": p, "to": fid, "role": "premise"})
        # Factor → conclusion edge
        if f_data["conclusion"]:
            edge_list.append({"from": fid, "to": f_data["conclusion"], "role": "conclusion"})

    # Get distinct package IDs for the package selector
    all_bindings = await storage.get_bindings()
    package_ids = sorted({b.package_id for b in all_bindings})

    return {
        "scope": scope,
        "package_id": package_id,
        "nodes": node_list,
        "factors": factor_list,
        "edges": edge_list,
        "packages": package_ids,
    }
