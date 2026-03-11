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
from libs.storage_v2 import models as v2


@dataclass
class V2IngestData:
    """Result of converting a Language package to v2 storage models."""

    package: v2.Package
    modules: list[v2.Module] = field(default_factory=list)
    knowledge_items: list[v2.Knowledge] = field(default_factory=list)
    chains: list[v2.Chain] = field(default_factory=list)
    probabilities: list[v2.ProbabilityRecord] = field(default_factory=list)
    belief_snapshots: list[v2.BeliefSnapshot] = field(default_factory=list)


def convert_to_v2(
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

    # 1. Package -> v2.Package
    v2_package = _convert_package(pkg, now)

    # 2. Build a unified knowledge index resolving Refs
    #    Maps (module_name, decl_name) -> (resolved Knowledge, owning module name)
    decls_by_name: dict[str, tuple[Knowledge, str]] = {}
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            actual = _resolve(decl)
            decls_by_name[decl.name] = (actual, mod.name)

    # 3. Modules -> v2.Module[]
    v2_modules = []
    for mod in pkg.loaded_modules:
        v2_mod = _convert_module(pkg.name, mod)
        v2_modules.append(v2_mod)

    # 4. Knowledge -> v2.Knowledge[] (deduped)
    seen_knowledge_ids: set[str] = set()
    v2_knowledge_items: list[v2.Knowledge] = []

    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            actual = _resolve(decl)
            if not _is_knowledge_type(actual):
                continue
            # Check if the actual declaration belongs to this package
            if not _belongs_to_package(actual, decl, pkg):
                continue
            knowledge_id = f"{pkg.name}/{actual.name}"
            if knowledge_id in seen_knowledge_ids:
                continue
            seen_knowledge_ids.add(knowledge_id)

            knowledge_item = _convert_knowledge(
                actual=actual,
                knowledge_id=knowledge_id,
                package_id=pkg.name,
                module_id=f"{pkg.name}.{mod.name}",
                now=now,
            )
            v2_knowledge_items.append(knowledge_item)

    # 5. ChainExpr -> v2.Chain[] + collect chain_ids per module
    v2_chains: list[v2.Chain] = []
    module_chain_ids: dict[str, list[str]] = {mod.name: [] for mod in pkg.loaded_modules}

    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, ChainExpr):
                chain = _convert_chain_expr(
                    chain=decl,
                    module_name=mod.name,
                    package_name=pkg.name,
                    decls_by_name=decls_by_name,
                    pkg=pkg,
                )
                if chain is not None:
                    v2_chains.append(chain)
                    module_chain_ids[mod.name].append(chain.chain_id)

    # 6. Relation -> v2.Chain[] (single-step chains)
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, Relation) and not isinstance(decl, (Equivalence, Subsumption)):
                chain = _convert_relation_to_chain(
                    rel=decl,
                    module_name=mod.name,
                    package_name=pkg.name,
                    decls_by_name=decls_by_name,
                    pkg=pkg,
                )
                if chain is not None:
                    v2_chains.append(chain)
                    module_chain_ids[mod.name].append(chain.chain_id)

    # Update module chain_ids and export_ids
    for v2_mod in v2_modules:
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
    v2_probabilities = _convert_review(review, pkg.name, now)

    # 8. Beliefs -> BeliefSnapshot[]
    v2_snapshots = _convert_beliefs(beliefs, pkg.name, bp_run_id, seen_knowledge_ids, now)

    return V2IngestData(
        package=v2_package,
        modules=v2_modules,
        knowledge_items=v2_knowledge_items,
        chains=v2_chains,
        probabilities=v2_probabilities,
        belief_snapshots=v2_snapshots,
    )


# ── Internal helpers ──────────────────────────────────────


def _resolve(decl: Knowledge) -> Knowledge:
    """Follow Ref._resolved to the actual Knowledge object."""
    if isinstance(decl, Ref) and decl._resolved is not None:
        return decl._resolved
    return decl


def _is_knowledge_type(k: Knowledge) -> bool:
    """Return True if the knowledge object should become a v2.Knowledge."""
    return isinstance(k, (Claim, Setting, Question, Contradiction))


def _belongs_to_package(actual: Knowledge, decl: Knowledge, pkg: Package) -> bool:
    """Check if a knowledge object belongs to this package (not imported).

    For a Ref, we check whether its target path starts with an external package.
    If the Ref's target contains a dot and the prefix before the dot is not a
    module name in this package, it's cross-package.
    """
    if not isinstance(decl, Ref):
        return True  # Non-ref declarations always belong to current package

    target = decl.target
    if "." in target:
        prefix = target.split(".")[0]
        module_names = {m.name for m in pkg.loaded_modules}
        if prefix not in module_names:
            # Target is in a different package
            return False
    return True


def _convert_package(pkg: Package, now: datetime) -> v2.Package:
    """Convert Language Package to v2.Package."""
    return v2.Package(
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


def _convert_module(package_name: str, mod: Module) -> v2.Module:
    """Convert Language Module to v2.Module."""
    role = _MODULE_ROLE_MAP.get(mod.type, "other")
    return v2.Module(
        module_id=f"{package_name}.{mod.name}",
        package_id=package_name,
        name=mod.name,
        role=role,
    )


def _knowledge_type(k: Knowledge) -> str:
    """Map Knowledge subclass to v2 Knowledge type literal."""
    if isinstance(k, Setting):
        return "setting"
    if isinstance(k, Question):
        return "question"
    if isinstance(k, Contradiction):
        return "claim"  # contradictions stored as claims
    return "claim"


def _convert_knowledge(
    actual: Knowledge,
    knowledge_id: str,
    package_id: str,
    module_id: str,
    now: datetime,
) -> v2.Knowledge:
    """Convert a Knowledge object to a v2.Knowledge."""
    raw_prior = actual.prior if actual.prior is not None else 0.5
    # Clamp to (0, 1] — prior must be > 0
    prior = max(raw_prior, 1e-6)
    prior = min(prior, 1.0)

    content = getattr(actual, "content", "") or ""

    return v2.Knowledge(
        knowledge_id=knowledge_id,
        version=1,
        type=_knowledge_type(actual),
        content=content.strip(),
        prior=prior,
        keywords=[],
        source_package_id=package_id,
        source_module_id=module_id,
        created_at=now,
    )


def _make_knowledge_ref(
    name: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
) -> v2.KnowledgeRef | None:
    """Create a KnowledgeRef for a declaration name, resolving the package-qualified ID."""
    entry = decls_by_name.get(name)
    if entry is None:
        return None
    actual, _mod_name = entry
    actual = _resolve(actual) if isinstance(actual, Ref) else actual

    # Determine which package the actual declaration belongs to
    # Check if the name was a Ref to an external package
    knowledge_id = f"{pkg.name}/{actual.name}"

    # Check all modules for this name to see if it's a cross-package ref
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if decl.name == name and isinstance(decl, Ref):
                target = decl.target
                if "." in target:
                    prefix = target.split(".")[0]
                    module_names = {m.name for m in pkg.loaded_modules}
                    if prefix not in module_names:
                        # Cross-package: use the external package name
                        knowledge_id = f"{prefix}/{actual.name}"
                        break

    return v2.KnowledgeRef(knowledge_id=knowledge_id, version=1)


def _convert_chain_expr(
    chain: ChainExpr,
    module_name: str,
    package_name: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
) -> v2.Chain | None:
    """Convert a ChainExpr to a v2.Chain with ChainStep entries."""
    chain_id = f"{package_name}.{module_name}.{chain.name}"
    module_id = f"{package_name}.{module_name}"

    # Determine chain type from edge_type or default to deduction
    edge_type = chain.edge_type or "deduction"
    valid_types = {"deduction", "induction", "abstraction", "contradiction", "retraction"}
    if edge_type not in valid_types:
        edge_type = "deduction"

    # Walk steps, create ChainStep for StepApply and StepLambda
    v2_steps: list[v2.ChainStep] = []
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
            premises: list[v2.KnowledgeRef] = []
            for arg in step.args:
                kref = _make_knowledge_ref(arg.ref, decls_by_name, pkg)
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

            conclusion_ref = _make_knowledge_ref(conclusion_name, decls_by_name, pkg)
            if conclusion_ref is None:
                continue

            v2_steps.append(
                v2.ChainStep(
                    step_index=step_index,
                    premises=premises,
                    reasoning=reasoning,
                    conclusion=conclusion_ref,
                )
            )
            step_index += 1

        elif isinstance(step, StepLambda):
            # Lambda step: reasoning is the lambda text, premises from previous StepRef
            premises = []
            # Look back for the preceding StepRef
            if i > 0:
                prev_step = chain.steps[i - 1]
                if isinstance(prev_step, StepRef):
                    kref = _make_knowledge_ref(prev_step.ref, decls_by_name, pkg)
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

            conclusion_ref = _make_knowledge_ref(conclusion_name, decls_by_name, pkg)
            if conclusion_ref is None:
                continue

            v2_steps.append(
                v2.ChainStep(
                    step_index=step_index,
                    premises=premises,
                    reasoning=reasoning,
                    conclusion=conclusion_ref,
                )
            )
            step_index += 1

    if not v2_steps:
        return None

    return v2.Chain(
        chain_id=chain_id,
        module_id=module_id,
        package_id=package_name,
        type=edge_type,
        steps=v2_steps,
    )


def _convert_relation_to_chain(
    rel: Relation,
    module_name: str,
    package_name: str,
    decls_by_name: dict[str, tuple[Knowledge, str]],
    pkg: Package,
) -> v2.Chain | None:
    """Convert a Relation (e.g. Contradiction) to a single-step v2.Chain."""
    chain_id = f"{package_name}.{module_name}.{rel.name}"
    module_id = f"{package_name}.{module_name}"

    # Map relation type to chain type
    rel_type = rel.type
    valid_types = {"deduction", "induction", "abstraction", "contradiction", "retraction"}
    if rel_type not in valid_types:
        rel_type = "deduction"

    # Members become premises
    premises: list[v2.KnowledgeRef] = []
    for member_name in rel.between:
        kref = _make_knowledge_ref(member_name, decls_by_name, pkg)
        if kref is not None:
            premises.append(kref)

    if not premises:
        return None

    # The Relation itself is the conclusion (if it was created as a Knowledge item)
    conclusion_id = f"{pkg.name}/{rel.name}"
    conclusion_ref = v2.KnowledgeRef(knowledge_id=conclusion_id, version=1)

    reasoning = (rel.content or "").strip()

    return v2.Chain(
        chain_id=chain_id,
        module_id=module_id,
        package_id=package_name,
        type=rel_type,
        steps=[
            v2.ChainStep(
                step_index=0,
                premises=premises,
                reasoning=reasoning,
                conclusion=conclusion_ref,
            )
        ],
    )


def _convert_review(
    review: dict,
    package_name: str,
    now: datetime,
) -> list[v2.ProbabilityRecord]:
    """Convert review dict to ProbabilityRecord entries."""
    records: list[v2.ProbabilityRecord] = []
    chains_data = review.get("chains", [])

    for chain_entry in chains_data:
        chain_name = chain_entry.get("name", "")
        steps = chain_entry.get("steps", [])
        for step_data in steps:
            step_id = step_data.get("step_id", "")
            # Step ID format: "chain_name.N" -> extract N
            step_index = 0
            if "." in step_id:
                try:
                    step_index = int(step_id.rsplit(".", 1)[1])
                except (ValueError, IndexError):
                    pass

            value = step_data.get("conditional_prior") or step_data.get("suggested_prior")
            if value is None:
                continue

            # Clamp to (0, 1]
            value = max(value, 1e-6)
            value = min(value, 1.0)

            records.append(
                v2.ProbabilityRecord(
                    chain_id=chain_name,
                    step_index=step_index,
                    value=value,
                    source="llm_review",
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
) -> list[v2.BeliefSnapshot]:
    """Convert BP belief values to BeliefSnapshot entries."""
    snapshots: list[v2.BeliefSnapshot] = []

    for var_name, belief_value in beliefs.items():
        knowledge_id = f"{package_name}/{var_name}"
        if knowledge_id not in seen_knowledge_ids:
            continue

        # Clamp to [0, 1]
        belief_value = max(belief_value, 0.0)
        belief_value = min(belief_value, 1.0)

        snapshots.append(
            v2.BeliefSnapshot(
                knowledge_id=knowledge_id,
                version=1,
                belief=belief_value,
                bp_run_id=bp_run_id,
                computed_at=now,
            )
        )

    return snapshots
