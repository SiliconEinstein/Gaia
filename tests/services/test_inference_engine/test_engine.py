"""Tests for the InferenceEngine orchestration layer."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from libs.models import Node, HyperEdge
from services.inference_engine.engine import InferenceEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_storage():
    storage = MagicMock()

    # Mock graph store
    storage.graph = MagicMock()
    storage.graph.get_subgraph = AsyncMock(return_value=({1, 2, 3}, {100}))
    storage.graph.get_hyperedge = AsyncMock(
        return_value=HyperEdge(id=100, type="induction", tail=[1, 2], head=[3], probability=0.8)
    )

    # Mock lance store
    storage.lance = MagicMock()
    storage.lance.load_nodes_bulk = AsyncMock(
        return_value=[
            Node(id=1, type="paper-extract", content="premise 1", prior=0.9),
            Node(id=2, type="paper-extract", content="premise 2", prior=0.85),
            Node(id=3, type="paper-extract", content="conclusion", prior=1.0),
        ]
    )
    storage.lance.update_beliefs = AsyncMock()

    return storage


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_compute_local_bp():
    storage = _mock_storage()
    engine = InferenceEngine(storage)
    beliefs = await engine.compute_local_bp([1], hops=2)

    assert len(beliefs) == 3
    assert all(0.0 <= b <= 1.0 for b in beliefs.values())
    # Beliefs should have been written back
    storage.lance.update_beliefs.assert_called_once()


async def test_compute_local_bp_calls_subgraph():
    storage = _mock_storage()
    engine = InferenceEngine(storage)
    await engine.compute_local_bp([1, 2], hops=3)
    storage.graph.get_subgraph.assert_called_once_with([1, 2], hops=3)


async def test_compute_local_bp_loads_edges():
    storage = _mock_storage()
    engine = InferenceEngine(storage)
    await engine.compute_local_bp([1])
    storage.graph.get_hyperedge.assert_called()


async def test_compute_local_bp_no_graph():
    """When Neo4j unavailable, return empty beliefs."""
    storage = _mock_storage()
    storage.graph = None
    engine = InferenceEngine(storage)
    beliefs = await engine.compute_local_bp([1])
    assert beliefs == {}


async def test_compute_local_bp_custom_params():
    storage = _mock_storage()
    engine = InferenceEngine(storage, bp_params={"damping": 0.3, "max_iterations": 10})
    beliefs = await engine.compute_local_bp([1])
    assert len(beliefs) > 0


async def test_run_global_bp_not_implemented():
    storage = _mock_storage()
    engine = InferenceEngine(storage)
    with pytest.raises(NotImplementedError):
        await engine.run_global_bp()
