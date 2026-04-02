"""Pipeline A adapter: thin wrapper around core lowering."""

from __future__ import annotations

from gaia.ir.graphs import LocalCanonicalGraph
from gaia.lkm.core.lower import LoweringResult, lower


def run_pipeline_a(
    graph: LocalCanonicalGraph,
    package_id: str | None = None,
    version: str = "",
) -> LoweringResult:
    """Run Pipeline A: lower a Gaia IR package to LKM local nodes.

    Thin adapter — delegates to core.lower().
    """
    return lower(graph, package_id=package_id, version=version)
