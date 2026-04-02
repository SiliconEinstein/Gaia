"""Integrate local FactorGraph into global FactorGraph.

Per-package, synchronous. Includes content_hash dedup and CanonicalBinding creation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    ParameterizationSource,
    PriorRecord,
    new_gcn_id,
    new_gfac_id,
)
from gaia.lkm.storage import StorageManager


@dataclass
class IntegrateResult:
    """Output of integrating one package into the global graph."""

    bindings: list[CanonicalBinding] = field(default_factory=list)
    new_global_variables: list[GlobalVariableNode] = field(default_factory=list)
    new_global_factors: list[GlobalFactorNode] = field(default_factory=list)
    updated_global_variables: list[str] = field(default_factory=list)
    prior_records: list[PriorRecord] = field(default_factory=list)
    factor_param_records: list[FactorParamRecord] = field(default_factory=list)
    unresolved_cross_refs: list[dict] = field(default_factory=list)


async def integrate(
    storage: StorageManager,
    package_id: str,
    version: str,
    local_variables: list[LocalVariableNode],
    local_factors: list[LocalFactorNode],
    prior_records: list[PriorRecord] | None = None,
    factor_param_records: list[FactorParamRecord] | None = None,
    param_sources: list[ParameterizationSource] | None = None,
) -> IntegrateResult:
    """Integrate a package's local graph into the global graph.

    Flow:
    1. Write local nodes (preparing)
    2. Commit local nodes (merged)
    3. Dedup variables by content_hash → create/match global variables
    4. Map factor QIDs → gcn_ids → create/match global factors
    5. Replace param IDs (QID → gcn_id, lfac_id → gfac_id)
    6. Write global nodes + bindings + params
    """
    result = IntegrateResult()
    qid_to_gcn: dict[str, str] = {}
    lfac_to_gfac: dict[str, str] = {}

    # ── Step 1-2: Write and commit local nodes ──
    await storage.ingest_local_graph(package_id, version, local_variables, local_factors)
    await storage.commit_package(package_id, version)

    # ── Step 3: Variable integrate ──
    for lv in local_variables:
        ref = LocalCanonicalRef(local_id=lv.id, package_id=package_id, version=version)

        if lv.visibility == "public":
            existing = await storage.find_global_by_content_hash(lv.content_hash)
        else:
            existing = None  # private variables never dedup

        if existing is not None:
            # match_existing: append to local_members
            updated = GlobalVariableNode(
                id=existing.id,
                type=existing.type,
                visibility=existing.visibility,
                content_hash=existing.content_hash,
                parameters=existing.parameters,
                representative_lcn=existing.representative_lcn,
                local_members=existing.local_members + [ref],
            )
            await storage.update_global_variable_members(existing.id, updated)
            qid_to_gcn[lv.id] = existing.id
            result.updated_global_variables.append(existing.id)
            result.bindings.append(
                CanonicalBinding(
                    local_id=lv.id,
                    global_id=existing.id,
                    binding_type="variable",
                    package_id=package_id,
                    version=version,
                    decision="match_existing",
                    reason="content_hash exact match",
                )
            )
        else:
            gcn_id = new_gcn_id()
            gv = GlobalVariableNode(
                id=gcn_id,
                type=lv.type,
                visibility=lv.visibility,
                content_hash=lv.content_hash,
                parameters=lv.parameters,
                representative_lcn=ref,
                local_members=[ref],
            )
            result.new_global_variables.append(gv)
            qid_to_gcn[lv.id] = gcn_id
            result.bindings.append(
                CanonicalBinding(
                    local_id=lv.id,
                    global_id=gcn_id,
                    binding_type="variable",
                    package_id=package_id,
                    version=version,
                    decision="create_new",
                    reason="no matching global node",
                )
            )

    # ── Step 4: Factor integrate ──
    for lf in local_factors:
        # Map premises/conclusion QIDs to gcn_ids
        mapped_premises = []
        unresolved = False
        for p in lf.premises:
            if p in qid_to_gcn:
                mapped_premises.append(qid_to_gcn[p])
            else:
                # Try cross-package resolution
                binding = await storage.find_canonical_binding(p)
                if binding:
                    mapped_premises.append(binding.global_id)
                    qid_to_gcn[p] = binding.global_id
                else:
                    result.unresolved_cross_refs.append(
                        {"factor_id": lf.id, "unresolved_qid": p, "role": "premise"}
                    )
                    unresolved = True

        mapped_conclusion = qid_to_gcn.get(lf.conclusion)
        if not mapped_conclusion:
            binding = await storage.find_canonical_binding(lf.conclusion)
            if binding:
                mapped_conclusion = binding.global_id
                qid_to_gcn[lf.conclusion] = binding.global_id
            else:
                result.unresolved_cross_refs.append(
                    {"factor_id": lf.id, "unresolved_qid": lf.conclusion, "role": "conclusion"}
                )
                unresolved = True

        if unresolved:
            continue

        # Check for exact structure match
        existing_factor = await storage.find_global_factor_exact(
            mapped_premises, mapped_conclusion, lf.factor_type, lf.subtype
        )

        if existing_factor:
            lfac_to_gfac[lf.id] = existing_factor.id
            result.bindings.append(
                CanonicalBinding(
                    local_id=lf.id,
                    global_id=existing_factor.id,
                    binding_type="factor",
                    package_id=package_id,
                    version=version,
                    decision="match_existing",
                    reason="structure exact match",
                )
            )
        else:
            gfac_id = new_gfac_id()
            gf = GlobalFactorNode(
                id=gfac_id,
                factor_type=lf.factor_type,
                subtype=lf.subtype,
                premises=mapped_premises,
                conclusion=mapped_conclusion,
                representative_lfn=lf.id,
                source_package=package_id,
            )
            result.new_global_factors.append(gf)
            lfac_to_gfac[lf.id] = gfac_id
            result.bindings.append(
                CanonicalBinding(
                    local_id=lf.id,
                    global_id=gfac_id,
                    binding_type="factor",
                    package_id=package_id,
                    version=version,
                    decision="create_new",
                    reason="no matching global factor",
                )
            )

    # ── Step 5: Replace param IDs ──
    if prior_records:
        for pr in prior_records:
            gcn_id = qid_to_gcn.get(pr.variable_id)
            if gcn_id:
                result.prior_records.append(
                    PriorRecord(
                        variable_id=gcn_id,
                        value=pr.value,
                        source_id=pr.source_id,
                        created_at=pr.created_at,
                    )
                )

    if factor_param_records:
        for fpr in factor_param_records:
            gfac_id = lfac_to_gfac.get(fpr.factor_id)
            if gfac_id:
                result.factor_param_records.append(
                    FactorParamRecord(
                        factor_id=gfac_id,
                        conditional_probabilities=fpr.conditional_probabilities,
                        source_id=fpr.source_id,
                        created_at=fpr.created_at,
                    )
                )

    # ── Step 6: Write global nodes + bindings + params ──
    await storage.integrate_global_graph(
        result.new_global_variables,
        result.new_global_factors,
        result.bindings,
        result.prior_records or None,
        result.factor_param_records or None,
    )

    # Write param sources
    if param_sources:
        for ps in param_sources:
            await storage.write_param_source(ps)

    return result
