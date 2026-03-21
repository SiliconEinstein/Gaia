"""Convert Graph IR outputs to storage models for ingest.

Converts LocalCanonicalGraph + LocalParameterization + beliefs into
storage models that StorageManager.ingest_package() accepts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization
from libs.storage import models as storage

_FACTOR_TYPE_MAP: dict[str, str] = {
    "reasoning": "infer",
    "infer": "infer",
    "abstraction": "abstraction",
    "instantiation": "instantiation",
    "mutex_constraint": "contradiction",
    "equiv_constraint": "equivalence",
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}

_KNOWLEDGE_TYPE_MAP: dict[str, str] = {
    "claim": "claim",
    "observation": "claim",
    "corroboration": "claim",
    "question": "question",
    "setting": "setting",
    "action": "action",
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}

_MODULE_ROLE_MAP: dict[str, str] = {
    "setting": "setting",
    "motivation": "motivation",
    "follow_up": "follow_up_question",
}


@dataclass
class GraphIRIngestData:
    """All storage objects produced from a Graph IR conversion."""

    package: storage.Package
    modules: list[storage.Module]
    knowledge_items: list[storage.Knowledge]
    chains: list[storage.Chain] = field(default_factory=list)
    factors: list[storage.FactorNode] = field(default_factory=list)
    belief_snapshots: list[storage.BeliefSnapshot] = field(default_factory=list)
    probabilities: list[storage.ProbabilityRecord] = field(default_factory=list)
    # Mapping from local_canonical_id → knowledge_id (for binding ID resolution)
    lcn_to_kid: dict[str, str] = field(default_factory=dict)


def _infer_module_role(module_name: str) -> str:
    """Infer module role from its name."""
    lower = module_name.lower()
    for prefix, role in _MODULE_ROLE_MAP.items():
        if prefix in lower:
            return role
    return "reasoning"


def _map_knowledge_type(
    knowledge_type: str,
) -> str:
    """Map Graph IR knowledge type to storage Knowledge type."""
    mapped = _KNOWLEDGE_TYPE_MAP.get(knowledge_type)
    if mapped is not None:
        return mapped
    return "claim"


def _map_knowledge_kind(
    knowledge_type: str,
    kind: str | None,
) -> str | None:
    """Preserve evidence-like subtyping when storage lacks a root observation type."""
    if knowledge_type == "observation" and kind is None:
        return "observation"
    return kind


def _map_factor_type(
    factor_type: str,
) -> str:
    """Map Graph IR factor type to storage FactorNode type."""
    mapped = _FACTOR_TYPE_MAP.get(factor_type)
    if mapped is not None:
        return mapped
    return "infer"


def _make_knowledge_id(package: str, knowledge_name: str) -> str:
    """Build a knowledge_id from package and knowledge name."""
    return f"{package}/{knowledge_name}"


def _make_chain_id(package_id: str, factor) -> str:
    """Build a published chain ID from author-facing provenance when available."""
    if factor.source_ref:
        return (
            f"{package_id}.{factor.source_ref.module}.{factor.source_ref.knowledge_name}"
        )
    return f"{package_id}.{factor.factor_id}"


def convert_graph_ir_to_storage(
    lcg: LocalCanonicalGraph,
    params: LocalParameterization,
    beliefs: dict[str, float] | None = None,
    bp_run_id: str = "local_bp",
) -> GraphIRIngestData:
    """Convert Graph IR outputs into storage models.

    Args:
        lcg: Local canonical graph with nodes and factors.
        params: Parameterization with node priors and factor parameters.
        beliefs: Optional dict mapping local_canonical_id to belief value.
        bp_run_id: Identifier for the BP run that produced beliefs.

    Returns:
        GraphIRIngestData with all storage objects ready for ingest.
    """
    now = datetime.now(UTC)
    package_id = lcg.package
    package_version = lcg.version

    # -- Build knowledge items --
    module_names: dict[str, set[str]] = {}  # module_name -> set of knowledge_ids
    knowledge_items: list[storage.Knowledge] = []
    # Map from lcn_id to knowledge_id for factor rewiring (includes external nodes)
    lcn_to_kid: dict[str, str] = {}
    # Map from local, materialized lcn_id to knowledge_id for publishable artifacts
    materialized_lcn_to_kid: dict[str, str] = {}

    for node in lcg.knowledge_nodes:
        # Use first source_ref's knowledge_name for the id, fallback to lcn_id
        if node.source_refs:
            k_name = node.source_refs[0].knowledge_name
            module_name = node.source_refs[0].module
            ref_package = node.source_refs[0].package
        else:
            k_name = node.local_canonical_id
            module_name = "default"
            ref_package = None

        # External nodes use their source package prefix
        is_external = ref_package is not None and ref_package != package_id
        kid_package = ref_package if is_external else package_id
        knowledge_id = _make_knowledge_id(kid_package, k_name)
        lcn_to_kid[node.local_canonical_id] = knowledge_id

        # External nodes are referenced in chains but not materialized locally
        if is_external:
            continue

        prior = params.node_priors.get(node.local_canonical_id, 0.5)
        # Ensure prior > 0 (storage model constraint: gt=0)
        if prior <= 0:
            prior = 0.01

        k_type = _map_knowledge_type(node.knowledge_type)

        # Convert parameters
        k_params = [
            storage.Parameter(name=p.name, constraint=p.constraint) for p in node.parameters
        ]

        # Track knowledge in its module
        if module_name not in module_names:
            module_names[module_name] = set()
        module_names[module_name].add(knowledge_id)

        module_id = f"{package_id}.{module_name}"
        materialized_lcn_to_kid[node.local_canonical_id] = knowledge_id

        knowledge_items.append(
            storage.Knowledge(
                knowledge_id=knowledge_id,
                version=1,
                type=k_type,
                kind=_map_knowledge_kind(node.knowledge_type, node.kind),
                content=node.representative_content,
                parameters=k_params,
                prior=prior,
                keywords=[],
                source_package_id=package_id,
                source_package_version=package_version,
                source_module_id=module_id,
                created_at=now,
            )
        )

    # -- Build modules --
    modules: list[storage.Module] = []
    for mod_name in sorted(module_names):
        module_id = f"{package_id}.{mod_name}"
        modules.append(
            storage.Module(
                module_id=module_id,
                package_id=package_id,
                package_version=package_version,
                name=mod_name,
                role=_infer_module_role(mod_name),
                export_ids=sorted(module_names[mod_name]),
            )
        )

    # -- Build factors --
    factors: list[storage.FactorNode] = []
    for f in lcg.factor_nodes:
        f_type = _map_factor_type(f.type)

        # Rewrite premise/conclusion IDs from lcn_id to knowledge_id
        premises = [lcn_to_kid[p] for p in f.premises if p in lcn_to_kid]
        contexts = [lcn_to_kid[c] for c in f.contexts if c in lcn_to_kid]
        conclusion = lcn_to_kid.get(f.conclusion) if f.conclusion else None

        source_ref = None
        if f.source_ref:
            source_ref = storage.SourceRef(
                package=f.source_ref.package,
                version=f.source_ref.version,
                module=f.source_ref.module,
                knowledge_name=f.source_ref.knowledge_name,
            )

        factors.append(
            storage.FactorNode(
                factor_id=f.factor_id,
                type=f_type,
                premises=premises,
                contexts=contexts,
                conclusion=conclusion,
                package_id=package_id,
                source_ref=source_ref,
                metadata=f.metadata,
            )
        )

    # -- Build chains from reasoning factors --
    # Each reasoning factor becomes a single-step chain: premises → conclusion
    chains: list[storage.Chain] = []
    module_chain_ids: dict[str, list[str]] = {m.module_id: [] for m in modules}
    # Map factor type → chain type
    _FACTOR_TO_CHAIN_TYPE: dict[str, str] = {
        "reasoning": "deduction",
        "infer": "deduction",
        "abstraction": "abstraction",
        "contradiction": "contradiction",
        "equivalence": "equivalence",
    }
    for f in lcg.factor_nodes:
        chain_type = _FACTOR_TO_CHAIN_TYPE.get(f.type, "deduction")

        premises_kid = [lcn_to_kid[p] for p in f.premises if p in lcn_to_kid]
        conclusion_kid = lcn_to_kid.get(f.conclusion) if f.conclusion else None
        if not premises_kid or conclusion_kid is None:
            continue

        # Determine module from source_ref
        mod_name = f.source_ref.module if f.source_ref else "unknown"
        module_id = f"{package_id}.{mod_name}"
        chain_id = _make_chain_id(package_id, f)

        chains.append(
            storage.Chain(
                chain_id=chain_id,
                module_id=module_id,
                package_id=package_id,
                package_version=package_version,
                type=chain_type,
                steps=[
                    storage.ChainStep(
                        step_index=0,
                        premises=[
                            storage.KnowledgeRef(knowledge_id=kid, version=1)
                            for kid in premises_kid
                        ],
                        reasoning="",
                        conclusion=storage.KnowledgeRef(knowledge_id=conclusion_kid, version=1),
                    )
                ],
            )
        )
        if module_id in module_chain_ids:
            module_chain_ids[module_id].append(chain_id)

    # Update module chain_ids
    for m in modules:
        m.chain_ids = module_chain_ids.get(m.module_id, [])

    # -- Build belief snapshots --
    belief_snapshots: list[storage.BeliefSnapshot] = []
    if beliefs:
        for lcn_id, belief_value in beliefs.items():
            kid = materialized_lcn_to_kid.get(lcn_id)
            if kid is not None:
                belief_snapshots.append(
                    storage.BeliefSnapshot(
                        knowledge_id=kid,
                        version=1,
                        belief=belief_value,
                        bp_run_id=bp_run_id,
                        computed_at=now,
                    )
                )

    # -- Build package --
    package = storage.Package(
        package_id=package_id,
        name=package_id,
        version=package_version,
        modules=[m.module_id for m in modules],
        exports=[k.knowledge_id for k in knowledge_items],
        submitter="graph_ir_converter",
        submitted_at=now,
        status="preparing",
    )

    return GraphIRIngestData(
        package=package,
        modules=modules,
        knowledge_items=knowledge_items,
        chains=chains,
        factors=factors,
        belief_snapshots=belief_snapshots,
        probabilities=[],
        lcn_to_kid=dict(lcn_to_kid),
    )
