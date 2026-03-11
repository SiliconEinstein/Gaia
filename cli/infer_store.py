"""Infer result serialization/deserialization."""

from __future__ import annotations

import json
from pathlib import Path


def save_infer_result(
    pkg_name: str,
    variables: dict[str, dict],
    factors: list[dict],
    bp_run_id: str,
    review_file: str | None,
    source_fingerprint: str,
    infer_dir: Path,
) -> Path:
    """Save inference results to infer_result.json."""
    infer_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "version": 1,
        "package": pkg_name,
        "source_fingerprint": source_fingerprint,
        "review_file": review_file,
        "bp_run_id": bp_run_id,
        "variables": variables,
        "factors": factors,
    }

    out_path = infer_dir / "infer_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return out_path


def load_infer_result(path: Path) -> dict:
    """Load infer result from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Infer result not found: {path}")
    return json.loads(path.read_text())
