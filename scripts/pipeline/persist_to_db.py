#!/usr/bin/env python3
"""Persist Graph IR outputs to LanceDB + Graph DB via StorageManager.

Reads per-package Graph IR outputs (local_canonical_graph.json, local_parameterization.json,
local_beliefs.json) and the global graph, writes everything to storage. Saves local JSON
backups for debugging.

Usage:
    python scripts/pipeline/persist_to_db.py \
        --packages-dir output_typst \
        --global-graph-dir global_graph \
        --db-path ./data/lancedb/gaia \
        --graph-backend kuzu
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

from libs.global_graph.models import (  # noqa: E402
    CanonicalBinding as GGCanonicalBinding,
    GlobalCanonicalNode as GGGlobalCanonicalNode,
    GlobalGraph,
    GlobalInferenceState as GGInferenceState,
)
from libs.global_graph.serialize import load_global_graph  # noqa: E402
from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization  # noqa: E402
from libs.graph_ir.storage_converter import (  # noqa: E402
    _map_factor_type,
    convert_graph_ir_to_storage,
)
from libs.storage import models as storage  # noqa: E402
from libs.storage.config import StorageConfig  # noqa: E402
from libs.storage.manager import StorageManager  # noqa: E402

logger = logging.getLogger(__name__)


# ── Global graph model conversion ──


def _convert_global_canonical_node(
    gg_node: GGGlobalCanonicalNode,
) -> storage.GlobalCanonicalNode:
    """Convert global_graph GlobalCanonicalNode to storage GlobalCanonicalNode."""
    return storage.GlobalCanonicalNode(
        global_canonical_id=gg_node.global_canonical_id,
        knowledge_type=gg_node.knowledge_type,
        kind=gg_node.kind,
        representative_content=gg_node.representative_content,
        parameters=[
            storage.Parameter(name=p.name, constraint=p.constraint) for p in gg_node.parameters
        ],
        member_local_nodes=[
            storage.LocalCanonicalRef(
                package=m.package, version=m.version, local_canonical_id=m.local_canonical_id
            )
            for m in gg_node.member_local_nodes
        ],
        provenance=[
            storage.PackageRef(package=p.package, version=p.version) for p in gg_node.provenance
        ],
        metadata=gg_node.metadata,
    )


def _convert_canonical_binding(
    gg_binding: GGCanonicalBinding,
    now: datetime,
) -> storage.CanonicalBinding:
    """Convert global_graph CanonicalBinding to storage CanonicalBinding.

    Storage model requires decided_at (datetime) which global_graph model lacks.
    """
    return storage.CanonicalBinding(
        package=gg_binding.package,
        version=gg_binding.version,
        local_graph_hash=gg_binding.local_graph_hash,
        local_canonical_id=gg_binding.local_canonical_id,
        decision=gg_binding.decision,
        global_canonical_id=gg_binding.global_canonical_id,
        decided_at=now,
        decided_by=gg_binding.decided_by,
        reason=gg_binding.reason,
    )


def _convert_canonical_bindings_resolved(
    gg_bindings: list[GGCanonicalBinding],
    now: datetime,
    lcn_to_kid: dict[str, str],
) -> list[storage.CanonicalBinding]:
    """Convert bindings, resolving local_canonical_id to knowledge_id.

    Neo4j uses local_canonical_id to MERGE Knowledge nodes for CANONICAL_BINDING
    relationships. If we leave it as lcn_xxx, it creates phantom Knowledge nodes.
    Replacing with the actual knowledge_id (paper_xxx/name) links to existing nodes.
    """
    result = []
    for b in gg_bindings:
        # Resolve lcn_id → knowledge_id if mapping available
        resolved_lcn_id = lcn_to_kid.get(b.local_canonical_id, b.local_canonical_id)
        result.append(
            storage.CanonicalBinding(
                package=b.package,
                version=b.version,
                local_graph_hash=b.local_graph_hash,
                local_canonical_id=resolved_lcn_id,
                decision=b.decision,
                global_canonical_id=b.global_canonical_id,
                decided_at=now,
                decided_by=b.decided_by,
                reason=b.reason,
            )
        )
    return result


def _convert_inference_state(
    gg_state: GGInferenceState,
) -> storage.GlobalInferenceState:
    """Convert global_graph GlobalInferenceState to storage GlobalInferenceState.

    Storage model requires updated_at as datetime; global_graph uses str.
    """
    if gg_state.updated_at:
        try:
            updated_at = datetime.fromisoformat(gg_state.updated_at)
        except (ValueError, TypeError):
            updated_at = datetime.now(UTC)
    else:
        updated_at = datetime.now(UTC)

    factor_params = {
        fid: storage.FactorParams(conditional_probability=fp.conditional_probability)
        for fid, fp in gg_state.factor_parameters.items()
    }

    return storage.GlobalInferenceState(
        graph_hash=gg_state.graph_hash,
        node_priors=gg_state.node_priors,
        factor_parameters=factor_params,
        node_beliefs=gg_state.node_beliefs,
        updated_at=updated_at,
    )


def _convert_global_factors(
    global_graph: GlobalGraph,
) -> list[storage.FactorNode]:
    """Convert global graph factor nodes to storage FactorNode models."""
    factors: list[storage.FactorNode] = []
    for f in global_graph.factor_nodes:
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
                type=_map_factor_type(f.type),
                premises=list(f.premises),
                contexts=list(f.contexts),
                conclusion=f.conclusion,
                package_id=f.source_ref.package if f.source_ref else "unknown",
                source_ref=source_ref,
                metadata=f.metadata,
            )
        )
    return factors


# ── JSON backup helpers ──


def _save_backup(backup_dir: Path, data: dict, filename: str) -> None:
    """Write a JSON backup file."""
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / filename).write_text(
        json.dumps(data, ensure_ascii=False, default=str, sort_keys=True, indent=2)
    )


def _save_package_backups(pkg_dir: Path, ingest_data) -> None:
    """Save local JSON backups for a package's storage objects."""
    backup_dir = pkg_dir / "graph_ir" / "storage_backup"
    _save_backup(
        backup_dir,
        ingest_data.package.model_dump(mode="json"),
        "package.json",
    )
    _save_backup(
        backup_dir,
        [k.model_dump(mode="json") for k in ingest_data.knowledge_items],
        "knowledge.json",
    )
    _save_backup(
        backup_dir,
        [f.model_dump(mode="json") for f in ingest_data.factors],
        "factors.json",
    )
    _save_backup(
        backup_dir,
        [m.model_dump(mode="json") for m in ingest_data.modules],
        "modules.json",
    )


# ── Package discovery ──


def _discover_packages(packages_dir: Path) -> list[Path]:
    """Find all package directories that have graph_ir/local_canonical_graph.json."""
    found: list[Path] = []
    if not packages_dir.is_dir():
        return found
    for sub in sorted(packages_dir.iterdir()):
        if sub.is_dir() and (sub / "graph_ir" / "local_canonical_graph.json").exists():
            found.append(sub)
    return found


def _load_local_graph(pkg_dir: Path) -> LocalCanonicalGraph:
    """Load local canonical graph from a package directory."""
    path = pkg_dir / "graph_ir" / "local_canonical_graph.json"
    return LocalCanonicalGraph.model_validate_json(path.read_text())


def _load_local_params(pkg_dir: Path) -> LocalParameterization:
    """Load local parameterization from a package directory."""
    path = pkg_dir / "graph_ir" / "local_parameterization.json"
    if not path.exists():
        return LocalParameterization(package="", version="")
    return LocalParameterization.model_validate_json(path.read_text())


def _load_local_beliefs(pkg_dir: Path) -> dict[str, float] | None:
    """Load local beliefs if they exist."""
    path = pkg_dir / "graph_ir" / "local_beliefs.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # local_beliefs.json stores node_beliefs as a dict
    if isinstance(data, dict):
        return data.get("node_beliefs", data)
    return None


# ── Main pipeline ──


async def persist_packages(
    packages_dir: Path,
    mgr: StorageManager,
) -> tuple[int, dict[str, str]]:
    """Persist all per-package Graph IR to storage.

    Returns (count, lcn_to_kid) where lcn_to_kid maps local_canonical_id
    to knowledge_id across all packages (needed for binding resolution).
    """
    pkg_dirs = _discover_packages(packages_dir)
    if not pkg_dirs:
        logger.warning("No packages with graph_ir/ found in %s", packages_dir)
        return 0, {}

    all_lcn_to_kid: dict[str, str] = {}
    count = 0
    for pkg_dir in pkg_dirs:
        pkg_name = pkg_dir.name
        logger.info("Persisting package: %s", pkg_name)

        lcg = _load_local_graph(pkg_dir)
        params = _load_local_params(pkg_dir)
        beliefs = _load_local_beliefs(pkg_dir)

        reasoning_steps_path = pkg_dir / "graph_ir" / "reasoning_steps.json"
        reasoning_steps = (
            json.loads(reasoning_steps_path.read_text()) if reasoning_steps_path.exists() else None
        )

        ingest_data = convert_graph_ir_to_storage(
            lcg, params, beliefs, reasoning_steps=reasoning_steps
        )
        all_lcn_to_kid.update(ingest_data.lcn_to_kid)

        # Save local backups before writing to DB
        _save_package_backups(pkg_dir, ingest_data)

        # Write to storage (no factors — only global factors go to factors table)
        await mgr.ingest_package(
            package=ingest_data.package,
            modules=ingest_data.modules,
            knowledge_items=ingest_data.knowledge_items,
            chains=ingest_data.chains,
        )

        # Write beliefs if present
        if ingest_data.belief_snapshots:
            await mgr.write_beliefs(ingest_data.belief_snapshots)

        count += 1
        logger.info(
            "  -> %d knowledge, %d factors, %d beliefs",
            len(ingest_data.knowledge_items),
            len(ingest_data.factors),
            len(ingest_data.belief_snapshots),
        )

    return count, all_lcn_to_kid


async def persist_global_graph(
    global_graph_dir: Path,
    mgr: StorageManager,
    lcn_to_kid: dict[str, str] | None = None,
) -> bool:
    """Persist global graph to storage. Returns True if persisted.

    Args:
        global_graph_dir: Directory containing global_graph.json.
        mgr: Initialized StorageManager.
        lcn_to_kid: Mapping from local_canonical_id → knowledge_id
            (from per-package persist). Used to resolve binding IDs so
            Neo4j links Knowledge nodes correctly.
    """
    gg_path = global_graph_dir / "global_graph.json"
    if not gg_path.exists():
        logger.info("No global_graph.json found at %s — skipping", gg_path)
        return False

    logger.info("Loading global graph from %s", gg_path)
    global_graph = load_global_graph(gg_path)

    now = datetime.now(UTC)
    lcn_to_kid = lcn_to_kid or {}

    # Convert models
    storage_nodes = [_convert_global_canonical_node(n) for n in global_graph.knowledge_nodes]
    storage_bindings = _convert_canonical_bindings_resolved(global_graph.bindings, now, lcn_to_kid)
    storage_state = _convert_inference_state(global_graph.inference_state)
    storage_factors = _convert_global_factors(global_graph)

    logger.info(
        "Global graph: %d nodes, %d bindings, %d factors",
        len(storage_nodes),
        len(storage_bindings),
        len(storage_factors),
    )

    # Write canonical bindings + global nodes
    if storage_bindings or storage_nodes:
        await mgr.write_canonical_bindings(storage_bindings, storage_nodes)

    # Write global factors to LanceDB ONLY (not Neo4j).
    # Global factors reference gcn_ IDs which are GlobalCanonicalNode, not Knowledge.
    # Writing them to Neo4j's factor topology would create phantom Knowledge nodes.
    if storage_factors and mgr.content_store is not None:
        await mgr.content_store.write_factors(storage_factors)

    # Write inference state
    if storage_state.graph_hash:
        await mgr.update_inference_state(storage_state)

    # Save backup
    backup_dir = global_graph_dir / "storage_backup"
    _save_backup(
        backup_dir,
        [n.model_dump(mode="json") for n in storage_nodes],
        "global_nodes.json",
    )
    _save_backup(
        backup_dir,
        [b.model_dump(mode="json") for b in storage_bindings],
        "bindings.json",
    )
    _save_backup(
        backup_dir,
        storage_state.model_dump(mode="json"),
        "inference_state.json",
    )

    return True


async def main(args: argparse.Namespace) -> None:
    """Run the persist-to-db pipeline."""
    # StorageConfig reads GAIA_* env vars automatically.
    # GAIA_LANCEDB_URI takes precedence over GAIA_LANCEDB_PATH.
    # CLI --db-path overrides GAIA_LANCEDB_PATH but not GAIA_LANCEDB_URI.
    config = StorageConfig(
        lancedb_path=args.db_path,
        graph_backend=args.graph_backend,
    )
    conn = config.effective_lancedb_connection
    logger.info("LanceDB connection: %s", conn)

    mgr = StorageManager(config)
    await mgr.initialize()

    try:
        # Clean existing data if requested
        if args.clean:
            logger.info("Cleaning all existing data before persist...")
            await mgr.clean_all()

        # Per-package persistence
        pkg_count, lcn_to_kid = await persist_packages(Path(args.packages_dir), mgr)
        logger.info("Persisted %d packages (%d lcn→kid mappings)", pkg_count, len(lcn_to_kid))

        # Global graph persistence
        if args.global_graph_dir:
            gg_dir = Path(args.global_graph_dir)
            persisted = await persist_global_graph(gg_dir, mgr, lcn_to_kid)
            if persisted:
                logger.info("Global graph persisted successfully")
        else:
            logger.info("No --global-graph-dir specified — skipping global graph")

    finally:
        await mgr.close()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Persist Graph IR outputs to LanceDB + Graph DB via StorageManager."
    )
    parser.add_argument(
        "--packages-dir",
        required=True,
        help="Directory containing packages with graph_ir/ subdirs.",
    )
    parser.add_argument(
        "--global-graph-dir",
        default=None,
        help="Directory containing global_graph.json (optional).",
    )
    parser.add_argument(
        "--db-path",
        default="./data/lancedb/gaia",
        help="LanceDB path (default: ./data/lancedb/gaia).",
    )
    parser.add_argument(
        "--graph-backend",
        choices=["kuzu", "neo4j", "none"],
        default="none",
        help="Graph backend: kuzu, neo4j, or none (default: none).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Drop all existing data before persisting.",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    asyncio.run(main(parse_args()))
