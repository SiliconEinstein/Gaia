"""JSON serialization helpers for Graph IR artifacts."""

from __future__ import annotations

from pathlib import Path

from .models import CanonicalizationLogEntry, LocalCanonicalGraph, LocalParameterization, RawGraph


def save_raw_graph(raw_graph: RawGraph, graph_dir: Path) -> Path:
    graph_dir.mkdir(parents=True, exist_ok=True)
    out_path = graph_dir / "raw_graph.json"
    out_path.write_text(raw_graph.canonical_json())
    return out_path


def load_raw_graph(path: Path) -> RawGraph:
    return RawGraph.model_validate_json(Path(path).read_text())


def save_local_canonical_graph(local_graph: LocalCanonicalGraph, graph_dir: Path) -> Path:
    graph_dir.mkdir(parents=True, exist_ok=True)
    out_path = graph_dir / "local_canonical_graph.json"
    out_path.write_text(local_graph.canonical_json())
    return out_path


def load_local_canonical_graph(path: Path) -> LocalCanonicalGraph:
    return LocalCanonicalGraph.model_validate_json(Path(path).read_text())


def save_canonicalization_log(entries: list[CanonicalizationLogEntry], graph_dir: Path) -> Path:
    import json

    graph_dir.mkdir(parents=True, exist_ok=True)
    out_path = graph_dir / "canonicalization_log.json"
    out_path.write_text(
        json.dumps(
            {"canonicalization_log": [entry.model_dump(mode="json") for entry in entries]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return out_path


def save_local_parameterization(
    parameterization: LocalParameterization,
    inference_dir: Path,
) -> Path:
    inference_dir.mkdir(parents=True, exist_ok=True)
    out_path = inference_dir / "local_parameterization.json"
    out_path.write_text(parameterization.model_dump_json(indent=2))
    return out_path


def load_local_parameterization(path: Path) -> LocalParameterization:
    return LocalParameterization.model_validate_json(Path(path).read_text())
