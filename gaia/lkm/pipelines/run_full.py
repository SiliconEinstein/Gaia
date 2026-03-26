"""Full pipeline: ingest all packages → global BP."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from gaia.core.local_params import LocalParameterization
from gaia.libs.embedding import DPEmbeddingModel
from gaia.libs.models.graph_ir import LocalCanonicalGraph
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.pipelines.run_global_bp import run_global_bp
from gaia.lkm.pipelines.run_ingest import run_ingest


async def run(input_dir: Path, config: StorageConfig, clean: bool = False) -> None:
    storage = StorageManager(config)
    await storage.initialize()
    if clean:
        await storage.clean_all()
        print("Cleaned all storage.")

    embedding = DPEmbeddingModel()

    print("=== Stage 1: Ingest ===")
    for graph_path in sorted(input_dir.glob("*/local_canonical_graph.json")):
        package_name = graph_path.parent.name
        graph_data = json.loads(graph_path.read_text())
        local_graph = LocalCanonicalGraph.model_validate(graph_data)

        # Load params if available, else use empty
        params_path = graph_path.parent / "local_parameterization.json"
        if params_path.exists():
            params = LocalParameterization.model_validate_json(params_path.read_text())
        else:
            params = LocalParameterization(graph_hash=local_graph.graph_hash)

        print(f"  Ingesting {package_name}...")
        result = await run_ingest(
            local_graph=local_graph,
            local_params=params,
            package_id=package_name,
            version="1.0",
            storage=storage,
            embedding_model=embedding,
        )
        print(f"    → {len(result.new_global_nodes)} new nodes, {len(result.bindings)} bindings")

    print("\n=== Stage 2: Global BP ===")
    belief_state = await run_global_bp(storage)
    print(
        f"  converged={belief_state.converged},"
        f" iterations={belief_state.iterations},"
        f" beliefs={len(belief_state.beliefs)} claims"
    )
    print("\n=== Pipeline complete ===")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full LKM pipeline")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--lancedb-path", type=str, default="./data/lancedb/gaia")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args()
    config = StorageConfig(lancedb_path=args.lancedb_path)
    asyncio.run(run(args.input_dir, config, clean=args.clean))


if __name__ == "__main__":
    main()
