"""Reusable async pipeline functions — no filesystem dependency.

Provides in-memory dataclass flow for: build → review → infer → publish.
Callable from both CLI and server-side batch processing.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from libs.graph_ir.adapter import AdaptedLocalInferenceGraph
from libs.graph_ir.models import FactorParams, LocalCanonicalGraph, LocalParameterization, RawGraph
from libs.storage import models as storage_models

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager


# ── Dataclasses ──────────────────────────────────────────


@dataclass
class BuildResult:
    """Unified build result for Typst packages."""

    graph_data: dict  # typst_loader output (for renderer, proof_state)
    raw_graph: RawGraph
    local_graph: LocalCanonicalGraph
    canonicalization_log: list
    source_files: dict[str, str] = field(default_factory=dict)


@dataclass
class ReviewOutput:
    """Result of reviewing a knowledge package (v3 Typst)."""

    review: dict  # raw LLM/mock review data
    node_priors: dict[str, float]  # lcn_id → prior π
    factor_params: dict[str, FactorParams]  # factor_id → FactorParams
    model: str
    source_fingerprint: str | None = None


@dataclass
class InferResult:
    beliefs: dict[str, float]
    bp_run_id: str
    local_parameterization: LocalParameterization
    adapted_graph: AdaptedLocalInferenceGraph


@dataclass
class V2IngestData:
    """Result of converting to v2 storage models."""

    package: storage_models.Package
    modules: list[storage_models.Module] = field(default_factory=list)
    knowledge_items: list[storage_models.Knowledge] = field(default_factory=list)
    chains: list[storage_models.Chain] = field(default_factory=list)
    probabilities: list[storage_models.ProbabilityRecord] = field(default_factory=list)
    belief_snapshots: list[storage_models.BeliefSnapshot] = field(default_factory=list)


@dataclass
class PublishResult:
    package_id: str
    stats: dict


# ── Pipeline Functions ───────────────────────────────────


async def pipeline_build(pkg_path: Path) -> BuildResult:
    """Load, compile, and canonicalize a Typst package — all in memory."""
    from libs.graph_ir.build_utils import build_singleton_local_graph
    from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph
    from libs.lang.typst_loader import load_typst_package

    graph_data = load_typst_package(pkg_path)
    raw_graph = compile_typst_to_raw_graph(graph_data)
    canonicalization = build_singleton_local_graph(raw_graph)
    source_files = {p.name: p.read_text() for p in pkg_path.glob("*.typ") if p.is_file()}

    return BuildResult(
        graph_data=graph_data,
        raw_graph=raw_graph,
        local_graph=canonicalization.local_graph,
        canonicalization_log=canonicalization.log,
        source_files=source_files,
    )


async def pipeline_review(
    build: BuildResult,
    *,
    mock: bool = False,
    model: str = "gpt-5-mini",
    source_fingerprint: str | None = None,
) -> ReviewOutput:
    """Review the package via LLM or mock reviewer (v3 Typst graph_data).

    Args:
        build: Result from pipeline_build (must contain graph_data and local_graph).
        mock: If True, use MockReviewClient (no LLM calls).
        model: LLM model name for real reviews.
        source_fingerprint: Optional fingerprint for staleness detection.
    """
    from cli.llm_client import MockReviewClient, ReviewClient

    graph_data = build.graph_data

    if mock:
        client = MockReviewClient()
        result = client.review_from_graph_data(graph_data)
        actual_model = "mock"
    else:
        md = _render_markdown_from_graph_data(graph_data)
        client = ReviewClient(model=model)
        result = await client.areview_package({"markdown": md})
        actual_model = model

    # Normalize review into sidecar format
    now = datetime.now(timezone.utc)
    review_data = {
        "package": graph_data.get("package", "unknown"),
        "model": actual_model,
        "timestamp": now.isoformat(),
        "source_fingerprint": source_fingerprint,
        "summary": result.get("summary", ""),
        "chains": result.get("chains", []),
    }

    # Build node_priors: lcn_id → default prior by knowledge_type
    node_priors = _build_node_priors(build.local_graph)

    # Build factor_params: factor_id → FactorParams from review chains
    factor_params = _build_factor_params(build.local_graph, graph_data, review_data)

    return ReviewOutput(
        review=review_data,
        node_priors=node_priors,
        factor_params=factor_params,
        model=actual_model,
        source_fingerprint=source_fingerprint,
    )


async def pipeline_infer(
    build: BuildResult,
    review: ReviewOutput,
) -> InferResult:
    """Adapt local graph to factor graph and run Belief Propagation.

    Args:
        build: Result from pipeline_build.
        review: Result from pipeline_review (v3 Typst ReviewOutput).
    """
    from libs.graph_ir.adapter import adapt_local_graph_to_factor_graph
    from libs.inference.bp import BeliefPropagation

    # 1. Build LocalParameterization from ReviewOutput
    local_parameterization = LocalParameterization(
        graph_hash=build.local_graph.graph_hash(),
        node_priors=review.node_priors,
        factor_parameters=review.factor_params,
    )

    # 2. Adapt to factor graph
    adapted = adapt_local_graph_to_factor_graph(build.local_graph, local_parameterization)

    # 3. Run BP
    bp = BeliefPropagation()
    raw_beliefs = bp.run(adapted.factor_graph)

    # 4. Map var IDs back to names
    var_id_to_local = {var_id: local_id for local_id, var_id in adapted.local_id_to_var_id.items()}
    named_beliefs = {
        adapted.local_id_to_label[var_id_to_local[var_id]]: belief
        for var_id, belief in raw_beliefs.items()
    }

    bp_run_id = str(uuid.uuid4())

    return InferResult(
        beliefs=named_beliefs,
        bp_run_id=bp_run_id,
        local_parameterization=local_parameterization,
        adapted_graph=adapted,
    )


async def pipeline_publish(
    build: BuildResult,
    review: ReviewOutput,
    infer: InferResult,
    *,
    storage_manager: "StorageManager | None" = None,
    storage_config: "StorageConfig | None" = None,
    db_path: str | None = None,
    embed_dim: int = 512,
) -> PublishResult:
    """Convert LocalCanonicalGraph to storage models and ingest into StorageManager.

    Args:
        build: Result from pipeline_build (Typst v3).
        review: Result from pipeline_review (v3 ReviewOutput).
        infer: Result from pipeline_infer.
        storage_manager: Pre-initialized StorageManager (server/batch use — not closed after).
        storage_config: StorageConfig to create a new manager (CLI use — closed after).
        db_path: LanceDB path shortcut (used if storage_config is None).
        embed_dim: Embedding dimension for stub embeddings.
    """
    from libs.embedding import StubEmbeddingModel
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager
    from libs.storage.models import KnowledgeEmbedding

    package_name = build.local_graph.package

    # 1. Convert LocalCanonicalGraph + ReviewOutput → V2IngestData
    data = _convert_local_graph_to_storage(build, review, infer.beliefs, infer.bp_run_id)

    # 2. Map Graph IR factors (lcn → knowledge IDs)
    factors = _map_graph_ir_factors(build.local_graph, package_name)

    # 3. Build submission artifact (in-memory, no git)
    submission_artifact = _build_submission_artifact_in_memory(
        build=build,
        package_name=package_name,
    )

    # 4. Generate embeddings
    embed_model = StubEmbeddingModel(dim=embed_dim)
    texts = [k.content for k in data.knowledge_items]
    vectors = await embed_model.embed(texts) if texts else []
    embeddings = [
        KnowledgeEmbedding(
            knowledge_id=k.knowledge_id,
            version=k.version,
            embedding=vec,
        )
        for k, vec in zip(data.knowledge_items, vectors)
    ]

    # 5. Resolve StorageManager — external (batch/server) or self-managed (CLI)
    _owns_mgr = storage_manager is None
    if _owns_mgr:
        if storage_config is None:
            if db_path is None:
                raise ValueError("Provide storage_manager, storage_config, or db_path")
            storage_config = StorageConfig(
                lancedb_path=db_path,
                graph_backend="kuzu",
                kuzu_path=f"{db_path}/kuzu",
            )
        mgr = StorageManager(storage_config)
        await mgr.initialize()
    else:
        mgr = storage_manager

    try:
        # 6. Ingest
        await mgr.ingest_package(
            package=data.package,
            modules=data.modules,
            knowledge_items=data.knowledge_items,
            chains=data.chains,
            factors=factors or None,
            submission_artifact=submission_artifact,
            embeddings=embeddings,
        )

        # 7. Write supplementary data
        if data.probabilities:
            await mgr.add_probabilities(data.probabilities)
        if data.belief_snapshots:
            await mgr.write_beliefs(data.belief_snapshots)
    finally:
        if _owns_mgr:
            await mgr.close()

    stats = {
        "knowledge_items": len(data.knowledge_items),
        "chains": len(data.chains),
        "factors": len(factors),
        "probabilities": len(data.probabilities),
        "belief_snapshots": len(data.belief_snapshots),
    }

    return PublishResult(
        package_id=data.package.package_id,
        stats=stats,
    )


# ── Internal helpers ─────────────────────────────────────

# Default priors by knowledge_type
_DEFAULT_PRIORS: dict[str, float] = {
    "setting": 1.0,
    "observation": 1.0,
    "question": 0.5,
    "contradiction": 0.5,
    "equivalence": 0.5,
    "corroboration": 0.5,
    "claim": 0.5,
}


def _build_node_priors(local_graph: LocalCanonicalGraph) -> dict[str, float]:
    """Build node_priors dict: lcn_id → default prior based on knowledge_type."""
    priors: dict[str, float] = {}
    for node in local_graph.knowledge_nodes:
        priors[node.local_canonical_id] = _DEFAULT_PRIORS.get(node.knowledge_type, 0.5)
    return priors


def _build_factor_params(
    local_graph: LocalCanonicalGraph,
    graph_data: dict,
    review_data: dict,
) -> dict[str, FactorParams]:
    """Build factor_params dict: factor_id → FactorParams from review chain results.

    Maps review chain conclusions (knowledge names) → factor_ids via local_graph,
    then extracts conditional_probability from review steps.
    """
    # Build mapping: knowledge_name → lcn_id from knowledge nodes
    name_to_lcn: dict[str, str] = {}
    for node in local_graph.knowledge_nodes:
        if node.source_refs:
            name_to_lcn[node.source_refs[0].knowledge_name] = node.local_canonical_id

    # Build mapping: conclusion_lcn_id → factor_id from factor nodes (infer type only)
    conclusion_to_factor: dict[str, str] = {}
    for factor in local_graph.factor_nodes:
        if factor.type == "infer" and factor.conclusion:
            conclusion_to_factor[factor.conclusion] = factor.factor_id

    # Build mapping: conclusion_knowledge_name → factor_id
    name_to_factor: dict[str, str] = {}
    for name, lcn_id in name_to_lcn.items():
        if lcn_id in conclusion_to_factor:
            name_to_factor[name] = conclusion_to_factor[lcn_id]

    # Parse review chains and extract conditional_probability
    review_probs: dict[str, float] = {}
    for chain_entry in review_data.get("chains", []):
        conclusion_name = chain_entry.get("chain", "")
        if conclusion_name not in name_to_factor:
            continue
        factor_id = name_to_factor[conclusion_name]
        steps = chain_entry.get("steps", [])
        if steps:
            prob = steps[0].get("conditional_prior", 1.0)
            review_probs[factor_id] = float(prob)

    # Build final factor_params: all infer factors get params, default 1.0 if not in review
    factor_params: dict[str, FactorParams] = {}
    for factor in local_graph.factor_nodes:
        if factor.type == "infer":
            prob = review_probs.get(factor.factor_id, 1.0)
            factor_params[factor.factor_id] = FactorParams(conditional_probability=prob)

    return factor_params


def _render_markdown_from_graph_data(graph_data: dict) -> str:
    """Render in-memory markdown from graph_data for LLM review (no filesystem)."""
    lines: list[str] = []
    package_name = graph_data.get("package", "unknown")
    lines.append(f"# Package: {package_name}\n")

    for node in graph_data.get("nodes", []):
        lines.append(f"### {node['name']} [{node.get('type', 'claim')}]")
        lines.append(f"> {node.get('content', '')}\n")

    for factor in graph_data.get("factors", []):
        if factor.get("type") != "reasoning":
            continue
        conclusion = factor["conclusion"]
        premises = factor.get("premise", [])
        lines.append(f"### {conclusion} [proof]")
        lines.append(f"**Premises:** {', '.join(premises)}")
        lines.append(f"**[step:{conclusion}.1]** (prior=0.85)\n")

    return "\n".join(lines)


# ── Knowledge type mapping ───────────────────────────────

# Map graph_data knowledge_type → valid storage Knowledge.type
_KNOWLEDGE_TYPE_MAP: dict[str, str] = {
    "claim": "claim",
    "question": "question",
    "setting": "setting",
    "action": "action",
    "observation": "setting",  # observation → setting
    "corroboration": "claim",  # corroboration → claim
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}

# Map factor type → Chain.type
_FACTOR_TO_CHAIN_TYPE: dict[str, str] = {
    "infer": "deduction",
    "abstraction": "abstraction",
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}

# Map module name → Module.role
_MODULE_ROLE_MAP: dict[str, str] = {
    "motivation": "motivation",
    "setting": "setting",
    "reasoning": "reasoning",
    "follow_up": "follow_up_question",
}


def _convert_local_graph_to_storage(
    build: BuildResult,
    review: ReviewOutput,
    beliefs: dict[str, float],
    bp_run_id: str,
) -> V2IngestData:
    """Convert LocalCanonicalGraph + ReviewOutput to V2IngestData for storage.

    Builds Knowledge, Chain, Module, Package, ProbabilityRecord, and BeliefSnapshot
    from the local canonical graph structure and BP results.
    """
    now = datetime.now(timezone.utc)
    local_graph = build.local_graph
    graph_data = build.graph_data
    package_name = local_graph.package
    package_version = local_graph.version

    # ── 1. Knowledge items ──
    knowledge_items: list[storage_models.Knowledge] = []
    seen_kids: set[str] = set()

    for node in local_graph.knowledge_nodes:
        if not node.source_refs:
            logger.warning(
                "Knowledge node %s has no source_refs; skipping storage conversion",
                node.local_canonical_id,
            )
            continue
        sr = node.source_refs[0]
        knowledge_id = f"{package_name}/{sr.knowledge_name}"
        if knowledge_id in seen_kids:
            continue
        seen_kids.add(knowledge_id)

        # Map knowledge_type to valid storage type
        k_type = _KNOWLEDGE_TYPE_MAP.get(node.knowledge_type, "claim")

        # Prior from review.node_priors (lcn_id → prior)
        raw_prior = review.node_priors.get(node.local_canonical_id, 0.5)
        prior = max(min(raw_prior, 1.0), 1e-6)  # clamp to (0, 1]

        knowledge_items.append(
            storage_models.Knowledge(
                knowledge_id=knowledge_id,
                version=1,
                type=k_type,
                content=node.representative_content.strip(),
                prior=prior,
                keywords=[],
                source_package_id=package_name,
                source_package_version=package_version,
                source_module_id=f"{package_name}.{sr.module}",
                created_at=now,
            )
        )

    # ── 2. Chains from factor nodes ──
    # Build lcn_id → knowledge_id mapping
    lcn_to_kid: dict[str, str] = {}
    for node in local_graph.knowledge_nodes:
        if node.source_refs:
            sr = node.source_refs[0]
            lcn_to_kid[node.local_canonical_id] = f"{package_name}/{sr.knowledge_name}"

    chains: list[storage_models.Chain] = []
    for factor in local_graph.factor_nodes:
        chain_type = _FACTOR_TO_CHAIN_TYPE.get(factor.type)
        if chain_type is None:
            continue  # skip unknown factor types (e.g. instantiation)

        # Build chain_id from source_ref
        if factor.source_ref:
            sr = factor.source_ref
            chain_id = f"{package_name}.{sr.module}.{sr.knowledge_name}"
            module_id = f"{package_name}.{sr.module}"
        else:
            logger.warning(
                "Factor %s has no source_ref; chain will not be associated with a module",
                factor.factor_id,
            )
            chain_id = f"{package_name}.{factor.factor_id}"
            module_id = package_name

        # Premises → KnowledgeRef
        premises: list[storage_models.KnowledgeRef] = []
        for p_lcn in factor.premises:
            kid = lcn_to_kid.get(p_lcn)
            if kid:
                premises.append(storage_models.KnowledgeRef(knowledge_id=kid, version=1))

        # Conclusion → KnowledgeRef
        if factor.conclusion is None:
            continue
        conclusion_kid = lcn_to_kid.get(factor.conclusion)
        if conclusion_kid is None:
            continue
        conclusion_ref = storage_models.KnowledgeRef(knowledge_id=conclusion_kid, version=1)

        chains.append(
            storage_models.Chain(
                chain_id=chain_id,
                module_id=module_id,
                package_id=package_name,
                package_version=package_version,
                type=chain_type,
                steps=[
                    storage_models.ChainStep(
                        step_index=0,
                        premises=premises,
                        reasoning="",
                        conclusion=conclusion_ref,
                    )
                ],
            )
        )

    # ── 3. Modules from graph_data ──
    modules_list = graph_data.get("modules", [])
    storage_modules: list[storage_models.Module] = []
    # Build per-module chain IDs
    module_chain_ids: dict[str, list[str]] = {m: [] for m in modules_list}
    for chain in chains:
        mod_name = chain.module_id.split(".", 1)[1] if "." in chain.module_id else ""
        if mod_name in module_chain_ids:
            module_chain_ids[mod_name].append(chain.chain_id)

    for mod_name in modules_list:
        role = _MODULE_ROLE_MAP.get(mod_name, "other")
        storage_modules.append(
            storage_models.Module(
                module_id=f"{package_name}.{mod_name}",
                package_id=package_name,
                package_version=package_version,
                name=mod_name,
                role=role,
                chain_ids=module_chain_ids.get(mod_name, []),
            )
        )

    # ── 4. Package ──
    exports_list = graph_data.get("exports", [])
    storage_package = storage_models.Package(
        package_id=package_name,
        name=package_name,
        version=package_version,
        description=graph_data.get("module_titles", {}).get("lib", None),
        modules=[f"{package_name}.{m}" for m in modules_list],
        exports=[f"{package_name}/{name}" for name in exports_list],
        submitter="cli",
        submitted_at=now,
        status="merged",
    )

    # ── 5. ProbabilityRecord from review factor_params ──
    probabilities: list[storage_models.ProbabilityRecord] = []
    # Map factor_id → chain_id for probability records
    factor_to_chain: dict[str, str] = {}
    for factor in local_graph.factor_nodes:
        if factor.source_ref:
            sr = factor.source_ref
            factor_to_chain[factor.factor_id] = f"{package_name}.{sr.module}.{sr.knowledge_name}"

    for factor_id, params in review.factor_params.items():
        chain_id = factor_to_chain.get(factor_id)
        if chain_id is None:
            logger.warning(
                "Factor %s has review params but no matching chain; skipping ProbabilityRecord",
                factor_id,
            )
            continue
        prob_value = max(min(params.conditional_probability, 1.0), 1e-6)
        probabilities.append(
            storage_models.ProbabilityRecord(
                chain_id=chain_id,
                step_index=0,
                value=prob_value,
                source="llm_review",
                recorded_at=now,
            )
        )

    # ── 6. BeliefSnapshot from BP results ──
    # Build label → knowledge_id mapping
    # Beliefs use "module.knowledge_name" format (from adapter._display_label)
    label_to_kid: dict[str, str] = {}
    for node in local_graph.knowledge_nodes:
        if node.source_refs:
            sr = node.source_refs[0]
            label = f"{sr.module}.{sr.knowledge_name}"
            label_to_kid[label] = f"{package_name}/{sr.knowledge_name}"

    belief_snapshots: list[storage_models.BeliefSnapshot] = []
    for label, belief_value in beliefs.items():
        kid = label_to_kid.get(label)
        if kid is None or kid not in seen_kids:
            continue
        clamped = max(min(belief_value, 1.0), 0.0)
        belief_snapshots.append(
            storage_models.BeliefSnapshot(
                knowledge_id=kid,
                version=1,
                belief=clamped,
                bp_run_id=bp_run_id,
                computed_at=now,
            )
        )

    return V2IngestData(
        package=storage_package,
        modules=storage_modules,
        knowledge_items=knowledge_items,
        chains=chains,
        probabilities=probabilities,
        belief_snapshots=belief_snapshots,
    )


def _map_graph_ir_factors(
    local_graph: LocalCanonicalGraph,
    package_name: str,
) -> list[storage_models.FactorNode]:
    """Map local canonical graph factors to storage FactorNodes with knowledge IDs."""
    # Build lcn_id → knowledge_id mapping
    lcn_to_kid: dict[str, str] = {}
    for node in local_graph.knowledge_nodes:
        if node.source_refs:
            sr = node.source_refs[0]
            lcn_to_kid[node.local_canonical_id] = f"{package_name}/{sr.knowledge_name}"

    factors: list[storage_models.FactorNode] = []
    for f in local_graph.factor_nodes:
        mapped_premises = [lcn_to_kid[p] for p in f.premises if p in lcn_to_kid]
        mapped_contexts = [lcn_to_kid[c] for c in f.contexts if c in lcn_to_kid]
        mapped_conclusion = lcn_to_kid.get(f.conclusion)
        if mapped_conclusion is None:
            continue

        source_ref = None
        if f.source_ref is not None:
            source_ref = storage_models.SourceRef(
                package=f.source_ref.package,
                version=f.source_ref.version,
                module=f.source_ref.module,
                knowledge_name=f.source_ref.knowledge_name,
            )

        factors.append(
            storage_models.FactorNode(
                factor_id=f.factor_id,
                type=f.type,
                premises=mapped_premises,
                contexts=mapped_contexts,
                conclusion=mapped_conclusion,
                package_id=package_name,
                source_ref=source_ref,
                metadata=f.metadata,
            )
        )

    return factors


def _build_submission_artifact_in_memory(
    build: BuildResult,
    package_name: str,
) -> storage_models.PackageSubmissionArtifact:
    """Build a PackageSubmissionArtifact from in-memory build results."""
    raw_graph_dict = json.loads(build.raw_graph.model_dump_json())
    local_graph_dict = json.loads(build.local_graph.model_dump_json())
    canon_log = [
        entry.model_dump() if hasattr(entry, "model_dump") else entry
        for entry in build.canonicalization_log
    ]

    return storage_models.PackageSubmissionArtifact(
        package_name=package_name,
        commit_hash="in-memory",
        source_files=build.source_files,
        raw_graph=raw_graph_dict,
        local_canonical_graph=local_graph_dict,
        canonicalization_log=canon_log,
        submitted_at=datetime.now(timezone.utc),
    )
