"""JSON serialization for global graph artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from .models import GlobalGraph


def save_global_graph(global_graph: GlobalGraph, output_dir: Path) -> Path:
    """Save global graph to a directory as JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "global_graph.json"
    out_path.write_text(
        json.dumps(
            global_graph.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return out_path


def load_global_graph(path: Path) -> GlobalGraph:
    """Load global graph from a JSON file. Returns empty graph if file doesn't exist."""
    if not path.exists():
        return GlobalGraph()
    return GlobalGraph.model_validate_json(path.read_text())
