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
class PublishResult:
    package_id: str
    stats: dict


# ── Pipeline Functions ───────────────────────────────────


async def pipeline_build(pkg_path: Path) -> BuildResult:
    """Load, compile, and canonicalize a Typst package — all in memory.

    Tries v4 (label-based) loader first; falls back to v3 (string-based).
    """
    from libs.graph_ir.build_utils import build_singleton_local_graph
    from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph, compile_v4_to_raw_graph
    from libs.lang.typst_loader import load_typst_package, load_typst_package_v4

    # Try v4 first: query figure.where(kind: "gaia-node")
    try:
        graph_data = load_typst_package_v4(pkg_path)
        if not graph_data["nodes"]:
            raise ValueError("No v4 nodes found")
    except Exception as exc:
        logger.debug(
            "v4 loader did not produce nodes for %s (%s), falling back to v3", pkg_path, exc
        )
        graph_data = load_typst_package(pkg_path)
        raw_graph = compile_typst_to_raw_graph(graph_data)
    else:
        # v4 loaded successfully — compile outside try/except so bugs are not swallowed
        logger.info("Building %s via v4 loader", pkg_path.name)
        raw_graph = compile_v4_to_raw_graph(graph_data)

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
        md = render_markdown_from_graph_data(graph_data)
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
    from libs.graph_ir.storage_converter import convert_graph_ir_to_storage
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager
    from libs.storage.models import KnowledgeEmbedding

    package_name = build.local_graph.package
    local_graph = build.local_graph

    # 1. Convert LocalCanonicalGraph → storage models via unified converter.
    # Local BP beliefs remain author-local preview artifacts and are not published.
    data = convert_graph_ir_to_storage(local_graph, infer.local_parameterization)

    # 2. Patch package fields for CLI publish context
    data.package.submitter = "cli"
    data.package.status = "merged"
    desc = build.graph_data.get("module_titles", {}).get("lib")
    if desc:
        data.package.description = desc

    # 3. Build ProbabilityRecords from review factor_params
    probabilities = _build_probability_records(local_graph, review, package_name)

    # 4. Build submission artifact (in-memory, no git)
    submission_artifact = _build_submission_artifact_in_memory(
        build=build,
        package_name=package_name,
    )

    # 5. Generate embeddings
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

    # 6. Resolve StorageManager — external (batch/server) or self-managed (CLI)
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
        # 7. Ingest
        await mgr.ingest_package(
            package=data.package,
            modules=data.modules,
            knowledge_items=data.knowledge_items,
            chains=data.chains,
            factors=data.factors or None,
            submission_artifact=submission_artifact,
            embeddings=embeddings,
        )

        # 8. Write supplementary data
        if probabilities:
            await mgr.add_probabilities(probabilities)
    finally:
        if _owns_mgr:
            await mgr.close()

    stats = {
        "knowledge_items": len(data.knowledge_items),
        "chains": len(data.chains),
        "factors": len(data.factors),
        "probabilities": len(probabilities),
        "belief_snapshots": 0,
    }

    return PublishResult(
        package_id=data.package.package_id,
        stats=stats,
    )


# ── Internal helpers ─────────────────────────────────────

# Default priors by knowledge_type
_DEFAULT_PRIORS: dict[str, float] = {
    "setting": 1.0,
    "observation": 0.5,
    "question": 0.5,
    "action": 0.5,
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


def render_markdown_from_graph_data(graph_data: dict) -> str:
    """Render in-memory markdown from graph_data for LLM review (no filesystem)."""
    lines: list[str] = []
    package_name = graph_data.get("package", "unknown")
    lines.append(f"# Package: {package_name}\n")

    for node in graph_data.get("nodes", []):
        label = node.get("type", "claim")
        if node.get("kind"):
            label = f"{label}, kind={node['kind']}"
        if node.get("external"):
            ext_pkg = node.get("ext_package", "unknown")
            ext_ver = node.get("ext_version", "") or "unknown"
            label = f"{label}, external from {ext_pkg}@{ext_ver}"
        lines.append(f"### {node['name']} [{label}]")
        lines.append(f"> {node.get('content', '')}\n")

    for factor in graph_data.get("factors", []):
        if factor.get("type") != "reasoning":
            continue
        conclusion = factor["conclusion"]
        premises = factor.get("premises") or factor.get("premise", [])
        lines.append(f"### {conclusion} [proof]")
        lines.append(f"**Premises:** {', '.join(premises)}")
        lines.append(f"**[step:{conclusion}.1]** (prior=0.85)\n")

    return "\n".join(lines)


def _build_probability_records(
    local_graph: LocalCanonicalGraph,
    review: ReviewOutput,
    package_name: str,
) -> list[storage_models.ProbabilityRecord]:
    """Build ProbabilityRecords from review factor_params."""
    from libs.graph_ir.storage_converter import _make_chain_id

    now = datetime.now(timezone.utc)
    factor_to_chain: dict[str, str] = {}
    for factor in local_graph.factor_nodes:
        factor_to_chain[factor.factor_id] = _make_chain_id(package_name, factor)

    probabilities: list[storage_models.ProbabilityRecord] = []
    for factor_id, params in review.factor_params.items():
        chain_id = factor_to_chain.get(factor_id)
        if chain_id is None:
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
    return probabilities


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
