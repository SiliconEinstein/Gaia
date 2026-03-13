"""Convert a Gaia Language package into v2 storage models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from libs.lang.models import (
    ChainExpr,
    Claim,
    Contradiction,
    Equivalence,
    Knowledge,
    Module,
    Package,
    Question,
    Ref,
    Relation,
    Setting,
    StepApply,
    StepLambda,
    StepRef,
    Subsumption,
)
from libs.storage import models as storage_models


@dataclass
class V2IngestData:
    """Result of converting a Language package to v2 storage models."""

    package: storage_models.Package
    modules: list[storage_models.Module] = field(default_factory=list)
    knowledge_items: list[storage_models.Knowledge] = field(default_factory=list)
    chains: list[storage_models.Chain] = field(default_factory=list)
    probabilities: list[storage_models.ProbabilityRecord] = field(default_factory=list)
    belief_snapshots: list[storage_models.BeliefSnapshot] = field(default_factory=list)


def convert_to_storage(
    pkg: Package,
    review: dict,
    beliefs: dict[str, float],
    bp_run_id: str,
) -> V2IngestData:
    """Convert a loaded+resolved Language package to v2 storage models.

    Args:
        pkg: A loaded and resolved Gaia Language package.
        review: review_*.yaml contents (chain step probabilities).
        beliefs: BP results {var_name: belief_value}.
        bp_run_id: BP run identifier.

    Returns:
        V2IngestData with package, modules, knowledge_items, chains, probabilities,
        and belief snapshots.
    """
    now = datetime.now(timezone.utc)
    pkg_version = pkg.version or "0.1.0"

    # 1. Package -> storage_models.Package
    storage_package = _convert_package(pkg, now)
    module_decl_index = _build_module_decl_index(pkg)

    # 2. Build a unified knowledge index resolving Refs
    #    Maps decl name -> resolved Knowledge.
    decls_by_name: dict[str, tuple[Knowledge, str]] = {}
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            actual = _resolve(decl)
            decls_by_name[decl.name] = (actual, mod.name)

    # 3. Modules -> storage_models.Module[]
    storage_modules = []
    for mod in pkg.loaded_modules:
        v2_mod = _convert_module(pkg.name, mod, pkg_version)
        storage_modules.append(v2_mod)

    # 4. Knowledge -> storage_models.Knowledge[] (deduped)
    seen_knowledge_ids: set[str] = set()
    storage_knowledge: list[storage_models.Knowledge] = []

    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            actual = _resolve(decl)
            if not _is_knowledge_type(actual):
                continue

            origin_package, origin_module = _resolve_decl_origin(
                decl=decl,
                module_name=mod.name,
                pkg=pkg,
                module_decl_index=module_decl_index,
            )
            if origin_package != pkg.name:
                continue
            knowledge_id = f"{pkg.name}/{actual.name}"
            if knowledge_id in seen_knowledge_ids:
                continue
            seen_knowledge_ids.add(knowledge_id)

            knowledge_item = _convert_knowledge(
                actual=actual,
                knowledge_id=knowledge_id,
                package_id=pkg.name,
                package_version=pkg_version,
                module_id=f"{pkg.name}.{origin_module}",
                now=now,
            )
            storage_knowledge.append(knowledge_item)

    # 5. ChainExpr -> storage_models.Chain[] + collect chain_ids per module
    storage_chains: list[storage_models.Chain] = []
    module_chain_ids: dict[str, list[str]] = {mod.name: [] for mod in pkg.loaded_modules}
    review_step_index: dict[str, tuple[str, int]] = {}

    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, ChainExpr):
                chain = _convert_chain_expr(
                    chain=decl,
                    module_name=mod.name,
                    package_name=pkg.name,
                    package_version=pkg_version,
                    decls_by_name=decls_by_name,
                    pkg=pkg,
                    module_decl_index=module_decl_index,
                    review_step_index=review_step_index,
                )
                if chain is not None:
                    storage_chains.append(chain)
                    module_chain_ids[mod.name].append(chain.chain_id)

    # 6. Relation -> storage_models.Chain[] (single-step chains)
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, Relation) and not isinstance(decl, (Equivalence, Subsumption)):
                chain = _convert_relation_to_chain(
                    rel=decl,
                    module_name=mod.name,
                    package_name=pkg.name,
                    package_version=pkg_version,
                    decls_by_name=decls_by_name,
                    pkg=pkg,
                    module_decl_index=module_decl_index,
                )
                if chain is not None:
                    storage_chains.append(chain)
                    module_chain_ids[mod.name].append(chain.chain_id)

    # Update module chain_ids and export_ids
    for v2_mod in storage_modules:
        mod_short_name = v2_mod.module_id.split(".", 1)[1] if "." in v2_mod.module_id else ""
        v2_mod.chain_ids = module_chain_ids.get(mod_short_name, [])
        # Export IDs: knowledge items from this module's exports
        src_mod = next((m for m in pkg.loaded_modules if m.name == mod_short_name), None)
        if src_mod and src_mod.export:
            v2_mod.export_ids = [
                f"{pkg.name}/{name}"
                for name in src_mod.export
                if f"{pkg.name}/{name}" in seen_knowledge_ids
            ]

    # 7. Review -> ProbabilityRecord[]
    storage_probabilities = _convert_review(review, review_step_index, now)

    # 8. Beliefs -> BeliefSnapshot[]
    storage_snapshots = _convert_beliefs(beliefs, pkg.name, bp_run_id, seen_knowledge_ids, now)

    return V2IngestData(
        package=storage_package,
        modules=storage_modules,
        knowledge_items=storage_knowledge,
        chains=storage_chains,
        probabilities=storage_probabilities,
        belief_snapshots=storage_snapshots,
    )


# ── Internal helpers ──────────────────────────────────────


def _resolve(decl: Knowledge) -> Knowledge:
    """Follow Ref._resolved to the actual Knowledge object."""
    if isinstance(decl, Ref) and decl._resolved is not None:
        return decl._resolved
    return decl


def _is_knowledge_type(k: Knowledge) -> bool:
    """Return True if the knowledge object should become a storage_models.Knowledge."""
    return isinstance(k, (Claim, Setting, Question, Contradiction, Equivalence, Subsumption))


def _build_module_decl_index(pkg: Package) -> dict[str, dict[str, Knowledge]]:
    """Index declarations by module and local name for ref provenance tracing."""
    return {mod.name: {decl.name: decl for decl in mod.knowledge} for mod in pkg.loaded_modules}


def _resolve_decl_origin(
    decl: Knowledge,
    module_name: str,
    pkg: Package,
    module_decl_index: dict[str, dict[str, Knowledge]],
    seen: set[tuple[str, str]] | None = None,
) -> tuple[str, str]:
    """Resolve the owning package/module for a declaration or ref alias."""
    if not isinstance(decl, Ref):
        return pkg.name, module_name

    if seen is None:
        seen = set()

    target = decl.target
    if "." not in target:
        return pkg.name, module_name

    prefix, local_name = target.split(".", 1)
    if prefix not in module_decl_index:
        return prefix, module_name

    marker = (prefix, local_name)
    if marker in seen:
        return pkg.name, prefix

    target_decl = module_decl_index[prefix].get(local_name)
    if target_decl is None:
        return pkg.name, prefix

    seen.add(marker)
    return _resolve_decl_origin(target_decl, prefix, pkg, module_decl_index, seen)


def _convert_package(pkg: Package, now: datetime) -> storage_models.Package:
    """Convert Language Package to storage_models.Package."""
    return storage_models.Package(
        package_id=pkg.name,
        name=pkg.name,
        version=pkg.version or "0.1.0",
        description=pkg.manifest.description.strip()
        if pkg.manifest and pkg.manifest.description
        else None,
        modules=[f"{pkg.name}.{m}" for m in pkg.modules_list],
        exports=[f"{pkg.name}/{name}" for name in pkg.export],
        submitter="cli",
        submitted_at=now,
        status="merged",
    )


_MODULE_ROLE_MAP: dict[str, str] = {
    "reasoning_module": "reasoning",
    "setting_module": "setting",
    "motivation_module": "motivation",
    "follow_up_module": "follow_up_question",
}


def _convert_module(package_name: str, mod: Module, package_version: str) -> storage_models.Module:
    """Convert Language Module to storage_models.Module."""
    role = _MODULE_ROLE_MAP.get(mod.type, "other")
    return storage_models.Module(
        module_id=f"{package_name}.{mod.name}",
        package_id=package_name,
        package_version=package_version,
        name=mod.name,
        role=role,
    )


def _knowledge_type(k: Knowledge) -> str:
    """Map Knowledge subclass to v2 Knowledge type literal."""
    if isinstance(k, Setting):
        return "setting"
    if isinstance(k, Question):
        return "question"
    if isinstance(k, (Contradiction, Equivalence, Subsumption)):
        return "claim"  # contradictions stored as claims
    return "claim"


def _convert_knowledge(
    actual: Knowledge,
    knowledge_id: str,
    package_id: str,
    package_version: str,
    module_id: str,
    now: datetime,
) -> storage_models.Knowledge:
    """Convert a Knowledge object to a storage_models.Knowledge."""
    raw_prior = actual.prior if actual.prior is not None else 0.5
    # Clamp to (0, 1] — prior must be > 0
    prior = max(raw_prior, 1e-6)
    prior = min(prior, 1.0)

    content = getattr(actual, "content", "") or ""

    return storage_models.Knowledge(
        knowledge_id=knowledge_id,
        version=1,
        type=_knowledge_type(actual),
        content=content.strip(),
        prior=prior,
        keywords=[],
        source_package_id=package_id,
        source_package_version=package_version,
        source_module_id=module_id,
        created_at=now,
    )


def _make_knowledge_ref(
    name: str,
    module_name: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
    module_decl_index: dict[str, dict[str, Knowledge]],
) -> storage_models.KnowledgeRef | None:
    """Create a KnowledgeRef for a declaration name, resolving the package-qualified ID."""
    entry = decls_by_name.get(name)
    if entry is None:
        return None
    actual, _mod_name = entry
    actual = _resolve(actual) if isinstance(actual, Ref) else actual

    decl = module_decl_index.get(module_name, {}).get(name)
    if decl is None:
        knowledge_id = f"{pkg.name}/{actual.name}"
    else:
        origin_package, _origin_module = _resolve_decl_origin(
            decl=decl,
            module_name=module_name,
            pkg=pkg,
            module_decl_index=module_decl_index,
        )
        knowledge_id = f"{origin_package}/{actual.name}"

    return storage_models.KnowledgeRef(knowledge_id=knowledge_id, version=1)


def _convert_chain_expr(
    chain: ChainExpr,
    module_name: str,
    package_name: str,
    package_version: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
    module_decl_index: dict[str, dict[str, Knowledge]],
    review_step_index: dict[str, tuple[str, int]],
) -> storage_models.Chain | None:
    """Convert a ChainExpr to a storage_models.Chain with ChainStep entries."""
    chain_id = f"{package_name}.{module_name}.{chain.name}"
    module_id = f"{package_name}.{module_name}"

    # Determine chain type from edge_type or default to deduction
    edge_type = chain.edge_type or "deduction"
    valid_types = {"deduction", "induction", "abstraction", "contradiction", "retraction"}
    if edge_type not in valid_types:
        edge_type = "deduction"

    # Walk steps, create ChainStep for StepApply and StepLambda
    storage_steps: list[storage_models.ChainStep] = []
    step_index = 0

    # Find the final StepRef as the chain conclusion
    final_ref_name: str | None = None
    if chain.steps:
        last_step = chain.steps[-1]
        if isinstance(last_step, StepRef):
            final_ref_name = last_step.ref

    for i, step in enumerate(chain.steps):
        if isinstance(step, StepApply):
            # Premises from args
            premises: list[storage_models.KnowledgeRef] = []
            for arg in step.args:
                kref = _make_knowledge_ref(
                    arg.ref,
                    module_name=module_name,
                    decls_by_name=decls_by_name,
                    pkg=pkg,
                    module_decl_index=module_decl_index,
                )
                if kref is not None:
                    premises.append(kref)

            # Reasoning text from the InferAction's content
            reasoning = ""
            action_entry = decls_by_name.get(step.apply)
            if action_entry is not None:
                action_decl, _ = action_entry
                reasoning = getattr(action_decl, "content", "") or ""
                reasoning = reasoning.strip()

            # Conclusion: if the next step is a StepRef, use that; otherwise use final ref
            conclusion_name = final_ref_name
            if i + 1 < len(chain.steps):
                next_step = chain.steps[i + 1]
                if isinstance(next_step, StepRef):
                    conclusion_name = next_step.ref

            if conclusion_name is None:
                continue

            conclusion_ref = _make_knowledge_ref(
                conclusion_name,
                module_name=module_name,
                decls_by_name=decls_by_name,
                pkg=pkg,
                module_decl_index=module_decl_index,
            )
            if conclusion_ref is None:
                continue

            storage_steps.append(
                storage_models.ChainStep(
                    step_index=step_index,
                    premises=premises,
                    reasoning=reasoning,
                    conclusion=conclusion_ref,
                )
            )
            review_step_index[f"{chain.name}.{step.step}"] = (chain_id, step_index)
            step_index += 1

        elif isinstance(step, StepLambda):
            # Lambda step: reasoning is the lambda text, premises from previous StepRef
            premises = []
            # Look back for the preceding StepRef
            if i > 0:
                prev_step = chain.steps[i - 1]
                if isinstance(prev_step, StepRef):
                    kref = _make_knowledge_ref(
                        prev_step.ref,
                        module_name=module_name,
                        decls_by_name=decls_by_name,
                        pkg=pkg,
                        module_decl_index=module_decl_index,
                    )
                    if kref is not None:
                        premises.append(kref)

            reasoning = step.lambda_.strip() if step.lambda_ else ""

            # Conclusion: next StepRef
            conclusion_name = final_ref_name
            if i + 1 < len(chain.steps):
                next_step = chain.steps[i + 1]
                if isinstance(next_step, StepRef):
                    conclusion_name = next_step.ref

            if conclusion_name is None:
                continue

            conclusion_ref = _make_knowledge_ref(
                conclusion_name,
                module_name=module_name,
                decls_by_name=decls_by_name,
                pkg=pkg,
                module_decl_index=module_decl_index,
            )
            if conclusion_ref is None:
                continue

            storage_steps.append(
                storage_models.ChainStep(
                    step_index=step_index,
                    premises=premises,
                    reasoning=reasoning,
                    conclusion=conclusion_ref,
                )
            )
            review_step_index[f"{chain.name}.{step.step}"] = (chain_id, step_index)
            step_index += 1

    if not storage_steps:
        return None

    return storage_models.Chain(
        chain_id=chain_id,
        module_id=module_id,
        package_id=package_name,
        package_version=package_version,
        type=edge_type,
        steps=storage_steps,
    )


def _convert_relation_to_chain(
    rel: Relation,
    module_name: str,
    package_name: str,
    package_version: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
    module_decl_index: dict[str, dict[str, Knowledge]],
) -> storage_models.Chain | None:
    """Convert a Relation (e.g. Contradiction) to a single-step storage_models.Chain."""
    chain_id = f"{package_name}.{module_name}.{rel.name}"
    module_id = f"{package_name}.{module_name}"

    # Map relation type to chain type
    rel_type = rel.type
    valid_types = {"deduction", "induction", "abstraction", "contradiction", "retraction"}
    if rel_type not in valid_types:
        rel_type = "deduction"

    # Members become premises
    premises: list[storage_models.KnowledgeRef] = []
    for member_name in rel.between:
        kref = _make_knowledge_ref(
            member_name,
            module_name=module_name,
            decls_by_name=decls_by_name,
            pkg=pkg,
            module_decl_index=module_decl_index,
        )
        if kref is not None:
            premises.append(kref)

    if not premises:
        return None

    # The Relation itself is the conclusion (if it was created as a Knowledge item)
    conclusion_id = f"{pkg.name}/{rel.name}"
    conclusion_ref = storage_models.KnowledgeRef(knowledge_id=conclusion_id, version=1)

    reasoning = (rel.content or "").strip()

    return storage_models.Chain(
        chain_id=chain_id,
        module_id=module_id,
        package_id=package_name,
        package_version=package_version,
        type=rel_type,
        steps=[
            storage_models.ChainStep(
                step_index=0,
                premises=premises,
                reasoning=reasoning,
                conclusion=conclusion_ref,
            )
        ],
    )


def _convert_review(
    review: dict,
    review_step_index: dict[str, tuple[str, int]],
    now: datetime,
) -> list[storage_models.ProbabilityRecord]:
    """Convert review dict to ProbabilityRecord entries."""
    records: list[storage_models.ProbabilityRecord] = []
    chains_data = review.get("chains", [])

    for chain_entry in chains_data:
        chain_name = chain_entry.get("chain") or chain_entry.get("name") or ""
        steps = chain_entry.get("steps", [])
        for step_data in steps:
            raw_step_id = step_data.get("step") or step_data.get("step_id") or ""
            step_id = str(raw_step_id)
            if "." not in step_id and chain_name:
                step_id = f"{chain_name}.{step_id}"

            step_ref = review_step_index.get(step_id)
            if step_ref is None:
                continue
            chain_id, step_index = step_ref

            value = step_data.get("conditional_prior") or step_data.get("suggested_prior")
            if value is None:
                continue

            # Clamp to (0, 1]
            value = max(value, 1e-6)
            value = min(value, 1.0)

            records.append(
                storage_models.ProbabilityRecord(
                    chain_id=chain_id,
                    step_index=step_index,
                    value=value,
                    source="llm_review",
                    source_detail=step_data.get("explanation") or None,
                    recorded_at=now,
                )
            )

    return records


def _convert_beliefs(
    beliefs: dict[str, float],
    package_name: str,
    bp_run_id: str,
    seen_knowledge_ids: set[str],
    now: datetime,
) -> list[storage_models.BeliefSnapshot]:
    """Convert BP belief values to BeliefSnapshot entries."""
    snapshots: list[storage_models.BeliefSnapshot] = []

    for var_name, belief_value in beliefs.items():
        knowledge_id = f"{package_name}/{var_name}"
        if knowledge_id not in seen_knowledge_ids:
            continue

        # Clamp to [0, 1]
        belief_value = max(belief_value, 0.0)
        belief_value = min(belief_value, 1.0)

        snapshots.append(
            storage_models.BeliefSnapshot(
                knowledge_id=knowledge_id,
                version=1,
                belief=belief_value,
                bp_run_id=bp_run_id,
                computed_at=now,
            )
        )

    return snapshots
