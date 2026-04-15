"""Integrate local FactorGraph into global FactorGraph.

Per-package and batch integration with content_hash dedup and CanonicalBinding creation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from gaia.lkm.core.extract import ExtractionResult
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

logger = logging.getLogger(__name__)


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

    logger.info(
        "Integrated %s: %d new globals, %d matched, %d new factors, %d unresolved",
        package_id,
        len(result.new_global_variables),
        len(result.updated_global_variables),
        len(result.new_global_factors),
        len(result.unresolved_cross_refs),
    )
    return result


@dataclass
class BatchIntegrateResult:
    """Output of batch-integrating multiple papers."""

    packages: int = 0
    total_local_variables: int = 0
    total_local_factors: int = 0
    new_global_variables: int = 0
    new_global_factors: int = 0
    dedup_within_batch: int = 0
    dedup_with_existing: int = 0
    bindings: int = 0
    unresolved_cross_refs: list[dict] = field(default_factory=list)


async def batch_integrate(
    storage: StorageManager,
    results: list[ExtractionResult],
) -> BatchIntegrateResult:
    """Integrate multiple papers at once with in-batch dedup.

    Unlike per-paper integrate(), this deduplicates variables across the entire
    batch before writing globals, avoiding race conditions under concurrency
    and reducing storage queries.

    Flow:
    1. Batch upsert all local nodes (directly as merged)
    2. Group variables by content_hash → one global per unique hash
    3. Check storage for existing globals (cross-batch dedup)
    4. Build global factors with resolved gcn_ids
    5. Write globals + bindings + params in one pass
    """
    stats = BatchIntegrateResult(packages=len(results))

    # ── Step 1: Batch upsert all local nodes ──
    all_variables: list[LocalVariableNode] = []
    all_factors: list[LocalFactorNode] = []
    for r in results:
        all_variables.extend(r.local_variables)
        all_factors.extend(r.local_factors)
        stats.total_local_variables += len(r.local_variables)
        stats.total_local_factors += len(r.local_factors)
    await storage.batch_upsert_local_nodes(all_variables, all_factors)

    # ── Step 2: In-batch variable dedup by content_hash ──
    hash_to_locals: dict[str, list[tuple[LocalVariableNode, str, str]]] = {}
    for r in results:
        for lv in r.local_variables:
            hash_to_locals.setdefault(lv.content_hash, []).append((lv, r.package_id, r.version))

    # Batch fetch existing globals for all content_hashes (one query)
    public_hashes = {
        h for h, entries in hash_to_locals.items() if entries[0][0].visibility == "public"
    }
    existing_globals_map = await storage.find_globals_by_content_hashes(public_hashes)

    all_bindings: list[CanonicalBinding] = []
    all_new_globals: list[GlobalVariableNode] = []
    updated_globals: list[GlobalVariableNode] = []
    qid_to_gcn: dict[str, str] = {}

    for content_hash, entries in hash_to_locals.items():
        first_var = entries[0][0]

        # Private helper claims (structural encoding artifacts) are stored
        # locally but must not create or match global nodes.
        if first_var.visibility != "public":
            continue

        if len(entries) > 1:
            stats.dedup_within_batch += len(entries) - 1

        existing = existing_globals_map.get(content_hash)

        if existing is not None:
            stats.dedup_with_existing += len(entries)
            new_members = [
                LocalCanonicalRef(local_id=lv.id, package_id=pkg, version=ver)
                for lv, pkg, ver in entries
            ]
            updated = GlobalVariableNode(
                id=existing.id,
                type=existing.type,
                visibility=existing.visibility,
                content_hash=existing.content_hash,
                parameters=existing.parameters,
                representative_lcn=existing.representative_lcn,
                local_members=existing.local_members + new_members,
            )
            updated_globals.append(updated)
            for lv, pkg, ver in entries:
                qid_to_gcn[lv.id] = existing.id
                all_bindings.append(
                    CanonicalBinding(
                        local_id=lv.id,
                        global_id=existing.id,
                        binding_type="variable",
                        package_id=pkg,
                        version=ver,
                        decision="match_existing",
                        reason="content_hash exact match (batch)",
                    )
                )
        else:
            gcn_id = new_gcn_id()
            refs = [
                LocalCanonicalRef(local_id=lv.id, package_id=pkg, version=ver)
                for lv, pkg, ver in entries
            ]
            gv = GlobalVariableNode(
                id=gcn_id,
                type=first_var.type,
                visibility=first_var.visibility,
                content_hash=content_hash,
                parameters=first_var.parameters,
                representative_lcn=refs[0],
                local_members=refs,
            )
            all_new_globals.append(gv)
            for lv, pkg, ver in entries:
                qid_to_gcn[lv.id] = gcn_id
                all_bindings.append(
                    CanonicalBinding(
                        local_id=lv.id,
                        global_id=gcn_id,
                        binding_type="variable",
                        package_id=pkg,
                        version=ver,
                        decision="create_new" if lv is first_var else "match_batch",
                        reason="batch dedup by content_hash",
                    )
                )

    stats.new_global_variables = len(all_new_globals)

    # ── Step 3: Factor integration ──
    # Batch fetch bindings for cross-package refs (one query)
    all_qids_in_factors: set[str] = set()
    for r in results:
        for lf in r.local_factors:
            for p in lf.premises:
                if p not in qid_to_gcn:
                    all_qids_in_factors.add(p)
            if lf.conclusion not in qid_to_gcn:
                all_qids_in_factors.add(lf.conclusion)
    existing_bindings_map = await storage.find_bindings_by_local_ids(all_qids_in_factors)
    for lid, binding in existing_bindings_map.items():
        qid_to_gcn[lid] = binding.global_id

    # Batch fetch existing factors by conclusion (one query)
    all_conclusions: set[str] = set()
    for r in results:
        for lf in r.local_factors:
            mapped_c = qid_to_gcn.get(lf.conclusion)
            if mapped_c:
                all_conclusions.add(mapped_c)
    existing_factors_list = await storage.find_global_factors_by_conclusions(all_conclusions)
    # Index by (sorted_premises, conclusion, factor_type, subtype) for exact match
    existing_factors_index: dict[tuple, GlobalFactorNode] = {}
    for gf in existing_factors_list:
        key = (tuple(sorted(gf.premises)), gf.conclusion, gf.factor_type, gf.subtype)
        existing_factors_index[key] = gf

    all_new_factors: list[GlobalFactorNode] = []
    all_prior_records: list[PriorRecord] = []
    all_factor_params: list[FactorParamRecord] = []
    lfac_to_gfac: dict[str, str] = {}

    for r in results:
        for lf in r.local_factors:
            mapped_premises = []
            unresolved = False
            for p in lf.premises:
                if p in qid_to_gcn:
                    mapped_premises.append(qid_to_gcn[p])
                else:
                    stats.unresolved_cross_refs.append(
                        {"factor_id": lf.id, "unresolved_qid": p, "role": "premise"}
                    )
                    unresolved = True

            mapped_conclusion = qid_to_gcn.get(lf.conclusion)
            if not mapped_conclusion:
                stats.unresolved_cross_refs.append(
                    {"factor_id": lf.id, "unresolved_qid": lf.conclusion, "role": "conclusion"}
                )
                unresolved = True

            if unresolved:
                continue

            factor_key = (
                tuple(sorted(mapped_premises)),
                mapped_conclusion,
                lf.factor_type,
                lf.subtype,
            )
            existing_factor = existing_factors_index.get(factor_key)
            if existing_factor:
                lfac_to_gfac[lf.id] = existing_factor.id
                all_bindings.append(
                    CanonicalBinding(
                        local_id=lf.id,
                        global_id=existing_factor.id,
                        binding_type="factor",
                        package_id=r.package_id,
                        version=r.version,
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
                    source_package=r.package_id,
                )
                all_new_factors.append(gf)
                # Also index newly created factor for within-batch dedup
                existing_factors_index[factor_key] = gf
                lfac_to_gfac[lf.id] = gfac_id
                all_bindings.append(
                    CanonicalBinding(
                        local_id=lf.id,
                        global_id=gfac_id,
                        binding_type="factor",
                        package_id=r.package_id,
                        version=r.version,
                        decision="create_new",
                        reason="no matching global factor",
                    )
                )

    stats.new_global_factors = len(all_new_factors)

    # ── Step 4: Remap param IDs (QID → gcn, lfac → gfac) ──
    for r in results:
        for pr in r.prior_records:
            gcn_id = qid_to_gcn.get(pr.variable_id)
            if gcn_id:
                all_prior_records.append(
                    PriorRecord(
                        variable_id=gcn_id,
                        value=pr.value,
                        source_id=pr.source_id,
                        created_at=pr.created_at,
                    )
                )
        for fpr in r.factor_param_records:
            gfac_id = lfac_to_gfac.get(fpr.factor_id)
            if gfac_id:
                all_factor_params.append(
                    FactorParamRecord(
                        factor_id=gfac_id,
                        conditional_probabilities=fpr.conditional_probabilities,
                        source_id=fpr.source_id,
                        created_at=fpr.created_at,
                    )
                )

    # ── Step 5: Write everything ──
    # Combine new + updated globals into one write (upsert handles both)
    all_globals_to_write = all_new_globals + updated_globals
    await storage.integrate_global_graph(
        all_globals_to_write,
        all_new_factors,
        all_bindings,
        all_prior_records or None,
        all_factor_params or None,
    )

    all_param_sources = [ps for r in results for ps in r.param_sources]
    if all_param_sources:
        await storage.write_param_sources_batch(all_param_sources)

    stats.bindings = len(all_bindings)
    logger.info(
        "Batch integrated %d packages: %d new global vars, %d new global factors, "
        "%d dedup within batch, %d dedup with existing, %d unresolved",
        stats.packages,
        stats.new_global_variables,
        stats.new_global_factors,
        stats.dedup_within_batch,
        stats.dedup_with_existing,
        len(stats.unresolved_cross_refs),
    )
    return stats
