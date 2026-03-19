"""Graph IR viewer routes — serve raw and local canonical graph fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/graph-ir", tags=["graph-ir"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
PACKAGES_DIR = _REPO_ROOT / "tests/fixtures/gaia_language_packages"
GLOBAL_GRAPH_DIR = _REPO_ROOT / "tests/fixtures/global_graph"


@router.get("")
def list_graph_ir_packages() -> list[dict]:
    """List packages that have graph_ir/ fixtures."""
    if not PACKAGES_DIR.exists():
        return []
    results = []
    for d in sorted(PACKAGES_DIR.iterdir()):
        if not d.is_dir():
            continue
        graph_dir = d / "graph_ir"
        if graph_dir.is_dir() and (graph_dir / "raw_graph.json").exists():
            results.append(
                {
                    "slug": d.name,
                    "has_raw": True,
                    "has_local": (graph_dir / "local_canonical_graph.json").exists(),
                    "has_parameterization": (graph_dir / "local_parameterization.json").exists(),
                }
            )
    return results


@router.get("/{slug}/raw")
def get_raw_graph(slug: str) -> dict:
    """Return raw graph IR for a package."""
    path = PACKAGES_DIR / slug / "graph_ir" / "raw_graph.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Raw graph not found: {slug}")
    return json.loads(path.read_text())


@router.get("/{slug}/local")
def get_local_canonical_graph(slug: str) -> dict:
    """Return local canonical graph IR for a package."""
    path = PACKAGES_DIR / slug / "graph_ir" / "local_canonical_graph.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Local canonical graph not found: {slug}")
    return json.loads(path.read_text())


@router.get("/{slug}/parameterization")
def get_local_parameterization(slug: str) -> dict:
    """Return local parameterization for a package."""
    path = PACKAGES_DIR / slug / "graph_ir" / "local_parameterization.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Parameterization not found: {slug}")
    return json.loads(path.read_text())


@router.get("/global")
def get_global_graph() -> dict:
    """Return the global canonical graph."""
    path = GLOBAL_GRAPH_DIR / "global_graph.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Global graph not found")
    return json.loads(path.read_text())


@router.get("/{slug}/beliefs")
def get_local_beliefs(slug: str) -> dict:
    """Return BP-computed local beliefs for a package."""
    path = PACKAGES_DIR / slug / "graph_ir" / "local_beliefs.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Beliefs not found: {slug}")
    return json.loads(path.read_text())
