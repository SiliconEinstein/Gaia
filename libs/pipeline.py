"""Reusable async pipeline functions — no filesystem dependency.

Provides in-memory dataclass flow for: build → review → infer → publish.
Callable from both CLI and server-side batch processing.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from libs.graph_ir.adapter import AdaptedLocalInferenceGraph
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization, RawGraph
from libs.lang.elaborator import ElaboratedPackage
from libs.lang import models as lang_models
from libs.storage import models as storage_models

if TYPE_CHECKING:
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager


# ── Dataclasses ──────────────────────────────────────────


@dataclass
class BuildResult:
    package: lang_models.Package
    elaborated: ElaboratedPackage
    markdown: str
    raw_graph: RawGraph
    local_graph: LocalCanonicalGraph
    canonicalization_log: list
    source_files: dict[str, str] = field(default_factory=dict)


@dataclass
class ReviewResult:
    review: dict
    merged_package: lang_models.Package
    model: str
    source_fingerprint: str | None


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


@dataclass
class TypstBuildResult:
    graph_data: dict
    raw_graph: RawGraph
    local_graph: LocalCanonicalGraph
    canonicalization_log: list
    source_files: dict[str, str] = field(default_factory=dict)


# ── Pipeline Functions ───────────────────────────────────


async def pipeline_build(
    pkg_path: Path,
    source_files: dict[str, str] | None = None,
) -> BuildResult:
    """Load, resolve, elaborate, and build Graph IR — all in memory.

    Args:
        pkg_path: Path to the knowledge package directory.
        source_files: Optional pre-loaded source files {filename: content}.
                      If None, reads YAML files from pkg_path.
    """
    from libs.graph_ir.build import build_raw_graph, build_singleton_local_graph
    from libs.lang.build_store import render_package_md
    from libs.lang.elaborator import elaborate_package
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs

    # 1. Load and resolve (recursive dep loading)
    def _load_with_deps(p: Path):
        loaded = load_package(p)
        dep_map: dict[str, object] = {}
        for dep in loaded.dependencies:
            dep_path = p.parent / dep.package
            dep_map[dep.package] = _load_with_deps(dep_path)
        return resolve_refs(loaded, deps=dep_map or None)

    pkg = _load_with_deps(pkg_path)

    # 2. Elaborate
    elaborated = elaborate_package(pkg)

    # 3. Render markdown
    markdown = render_package_md(elaborated)

    # 4. Build Graph IR
    raw_graph = build_raw_graph(pkg)
    canonicalization = build_singleton_local_graph(raw_graph)

    # 5. Collect source files
    if source_files is None:
        source_files = {p.name: p.read_text() for p in pkg_path.glob("*.yaml") if p.is_file()}

    return BuildResult(
        package=pkg,
        elaborated=elaborated,
        markdown=markdown,
        raw_graph=raw_graph,
        local_graph=canonicalization.local_graph,
        canonicalization_log=canonicalization.log,
        source_files=source_files,
    )


async def pipeline_build_typst(pkg_path: Path) -> TypstBuildResult:
    """Load, compile, and canonicalize a Typst package — all in memory.

    Args:
        pkg_path: Path to the Typst package directory (contains typst.toml + lib.typ).
    """
    from libs.graph_ir.build_utils import build_singleton_local_graph
    from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph
    from libs.lang.typst_loader import load_typst_package

    graph_data = load_typst_package(pkg_path)
    raw_graph = compile_typst_to_raw_graph(graph_data)
    canonicalization = build_singleton_local_graph(raw_graph)
    source_files = {p.name: p.read_text() for p in pkg_path.glob("*.typ") if p.is_file()}

    return TypstBuildResult(
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
) -> ReviewResult:
    """Review the package chains via LLM or mock reviewer.

    Args:
        build: Result from pipeline_build.
        mock: If True, use MockReviewClient (no LLM calls).
        model: LLM model name for real reviews.
        source_fingerprint: Optional fingerprint for staleness detection.
    """
    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.review_store import merge_review

    package_data = {"package": build.package.name, "markdown": build.markdown}

    if mock:
        client = MockReviewClient()
        result = await client.areview_package(package_data)
        actual_model = "mock"
    else:
        client = ReviewClient(model=model)
        result = await client.areview_package(package_data)
        actual_model = model

    # Normalize review into sidecar format
    now = datetime.now(timezone.utc)
    review_data = {
        "package": build.package.name,
        "model": actual_model,
        "timestamp": now.isoformat(),
        "source_fingerprint": source_fingerprint,
        "summary": result.get("summary", ""),
        "chains": result.get("chains", []),
    }

    # Merge review into package
    merged_package = merge_review(build.package, review_data, source_fingerprint=source_fingerprint)

    return ReviewResult(
        review=review_data,
        merged_package=merged_package,
        model=actual_model,
        source_fingerprint=source_fingerprint,
    )


async def pipeline_infer(
    build: BuildResult,
    review: ReviewResult,
) -> InferResult:
    """Derive parameterization, adapt to factor graph, and run BP.

    Args:
        build: Result from pipeline_build.
        review: Result from pipeline_review.
    """
    from libs.graph_ir.adapter import adapt_local_graph_to_factor_graph
    from libs.graph_ir.build import derive_local_parameterization
    from libs.inference.bp import BeliefPropagation

    # 1. Derive parameterization from merged package + local graph
    local_parameterization = derive_local_parameterization(review.merged_package, build.local_graph)

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
    review: ReviewResult,
    infer: InferResult,
    *,
    storage_manager: "StorageManager | None" = None,
    storage_config: "StorageConfig | None" = None,
    db_path: str | None = None,
    embed_dim: int = 512,
) -> PublishResult:
    """Convert to storage models and ingest into StorageManager.

    Args:
        build: Result from pipeline_build.
        review: Result from pipeline_review.
        infer: Result from pipeline_infer.
        storage_manager: Pre-initialized StorageManager (server/batch use — not closed after).
        storage_config: StorageConfig to create a new manager (CLI use — closed after).
        db_path: LanceDB path shortcut (used if storage_config is None).
        embed_dim: Embedding dimension for stub embeddings.
    """
    from cli.lang_to_storage import convert_to_storage
    from libs.embedding import StubEmbeddingModel
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager
    from libs.storage.models import KnowledgeEmbedding

    pkg = review.merged_package

    # 1. Convert to v2 storage models
    data = convert_to_storage(
        pkg=pkg,
        review=review.review,
        beliefs=infer.beliefs,
        bp_run_id=infer.bp_run_id,
    )

    # 2. Map Graph IR factors (lcn → knowledge IDs)
    factors = _map_graph_ir_factors(build.local_graph, pkg.name)

    # 3. Build submission artifact (in-memory, no git)
    submission_artifact = _build_submission_artifact_in_memory(
        build=build,
        package_name=pkg.name,
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
            lcn_to_kid[node.local_canonical_id] = f"{sr.package}/{sr.knowledge_name}"

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
