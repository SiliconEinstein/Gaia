"""LKM-specific adapters for Gaia research loop artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaia.lkm_explorer.engine.landscape import LandscapeBatch, build_landscape
from gaia.research_loop.schemas import ARTIFACT_SCHEMA


def build_landscape_from_raw_results(
    pkg: str | Path,
    *,
    raw_results: list[tuple[str, Path]],
    round_number: int,
) -> dict[str, Any]:
    """Build a research-loop landscape artifact from saved LKM search JSON."""
    batches: list[LandscapeBatch] = []
    raw_refs: list[dict[str, str]] = []
    for query, path in raw_results:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected JSON object at {path}")
        batches.append(LandscapeBatch(search_results=payload, query=query, path=str(path)))
        raw_refs.append({"query": query, "path": str(path)})

    landscape = build_landscape(
        batches,
        materialized=set(),
        materialized_paper_ids=set(),
        exploration_map=None,
    ).to_dict()
    paper_leads = landscape.get("paper_leads", [])
    return {
        "schema": ARTIFACT_SCHEMA,
        "kind": "landscape",
        "round": round_number,
        "pkg": str(Path(pkg).resolve()),
        "raw_results": raw_refs,
        "paper_leads": paper_leads if isinstance(paper_leads, list) else [],
        "coverage": {
            "paper_count": len(paper_leads) if isinstance(paper_leads, list) else 0,
        },
        "source_landscape": landscape,
    }
