#!/usr/bin/env python3
"""Smoke test: run the full curation pipeline on the global_graph fixture.

Usage:
    uv run python scripts/smoke_curation.py

Loads the global_graph.json fixture into an in-memory StorageManager
and runs the full curation pipeline with real LLM + embedding APIs.

Requires .env with OPENAI_API_KEY, API_URL, ACCESS_KEY.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import libs.llm  # noqa: E402, F401 — initializes litellm config

from libs.curation.scheduler import run_curation  # noqa: E402
from libs.embedding import DPEmbeddingModel  # noqa: E402
from libs.global_graph.models import GlobalCanonicalNode, GlobalGraph  # noqa: E402
from libs.storage.models import FactorNode  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("smoke_curation")

FIXTURE_PATH = Path("tests/fixtures/global_graph/global_graph.json")


class InMemoryStorageStub:
    """Minimal StorageManager stub backed by in-memory dicts.

    Only implements the methods run_curation() actually calls:
    - list_global_nodes()
    - list_factors()
    - upsert_global_nodes()
    - write_factors()
    """

    def __init__(
        self,
        nodes: list[GlobalCanonicalNode],
        factors: list[FactorNode],
    ) -> None:
        self._nodes = {n.global_canonical_id: n for n in nodes}
        self._factors = {f.factor_id: f for f in factors}

    async def list_global_nodes(self) -> list[GlobalCanonicalNode]:
        return list(self._nodes.values())

    async def list_factors(self) -> list[FactorNode]:
        return list(self._factors.values())

    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None:
        for n in nodes:
            self._nodes[n.global_canonical_id] = n
        logger.info("Upserted %d global nodes", len(nodes))

    async def write_factors(self, factors: list[FactorNode]) -> None:
        self._factors = {f.factor_id: f for f in factors}
        logger.info("Wrote %d factors", len(factors))


def load_fixture() -> tuple[list[GlobalCanonicalNode], list[FactorNode]]:
    """Load nodes and factors from the global_graph.json fixture."""
    data = json.loads(FIXTURE_PATH.read_text())
    graph = GlobalGraph.model_validate(data)

    logger.info(
        "Loaded fixture: %d nodes, %d factors, %d bindings",
        len(graph.knowledge_nodes),
        len(graph.factor_nodes),
        len(graph.bindings),
    )

    # Log node type distribution
    type_counts: dict[str, int] = {}
    for n in graph.knowledge_nodes:
        kt = n.knowledge_type
        type_counts[kt] = type_counts.get(kt, 0) + 1
    logger.info("Node types: %s", type_counts)

    # Log factor type distribution
    factor_counts: dict[str, int] = {}
    for f in graph.factor_nodes:
        factor_counts[f.type] = factor_counts.get(f.type, 0) + 1
    logger.info("Factor types: %s", factor_counts)

    return graph.knowledge_nodes, graph.factor_nodes


async def main() -> None:
    logger.info("=== Curation Smoke Test ===")

    # Load fixture
    nodes, factors = load_fixture()
    storage = InMemoryStorageStub(nodes, factors)

    # Create embedding model (real API)
    embedding_model = DPEmbeddingModel()

    # Run pipeline
    logger.info("--- Running curation pipeline ---")
    result = await run_curation(
        storage=storage,
        embedding_model=embedding_model,
        similarity_threshold=0.85,  # Lower threshold for small dataset
        skip_conflict_detection=False,
        skip_abstraction=False,
        abstraction_model="chenkun/gpt-5-mini",
        reviewer_model="chenkun/gpt-5-mini",
        bp_max_iterations=30,
        bp_damping=0.5,
    )

    # Report
    logger.info("=== Results ===")
    logger.info("Executed suggestions: %d", len(result.executed))
    for s in result.executed:
        logger.info("  %s: %s (conf=%.2f)", s.operation, s.target_ids, s.confidence)

    logger.info("Skipped suggestions: %d", len(result.skipped))
    for s in result.skipped:
        logger.info("  %s: %s (conf=%.2f) — %s", s.operation, s.target_ids, s.confidence, s.reason)

    logger.info("Audit entries: %d", len(result.audit_entries))

    sr = result.structure_report
    logger.info(
        "Structure: %d errors, %d warnings, %d info",
        len(sr.errors),
        len(sr.warnings),
        len(sr.infos),
    )
    for issue in sr.issues:
        logger.info("  [%s] %s: %s", issue.severity, issue.issue_type, issue.detail[:100])

    # Final state
    final_nodes = await storage.list_global_nodes()
    final_factors = await storage.list_factors()
    logger.info(
        "Final graph: %d nodes, %d factors",
        len(final_nodes),
        len(final_factors),
    )

    logger.info("=== Smoke test complete ===")


if __name__ == "__main__":
    asyncio.run(main())
