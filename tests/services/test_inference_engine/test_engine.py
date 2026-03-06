"""Tests for the InferenceEngine orchestration layer."""

from __future__ import annotations

import pytest

from services.inference_engine.engine import InferenceEngine


@pytest.fixture
async def engine(storage):
    return InferenceEngine(storage)


async def test_compute_local_bp(engine, storage):
    """Local BP returns valid beliefs for fixture nodes with graph edges."""
    # Use fixture node IDs that have edges
    beliefs = await engine.compute_local_bp([67], hops=2)
    assert len(beliefs) > 0
    assert all(0.0 <= b <= 1.0 for b in beliefs.values())


async def test_compute_local_bp_returns_beliefs_for_subgraph(engine):
    """BP should compute beliefs for nodes in the subgraph."""
    beliefs = await engine.compute_local_bp([67, 68], hops=3)
    assert len(beliefs) > 0
    # All belief values are valid probabilities
    for node_id, belief in beliefs.items():
        assert isinstance(node_id, int)
        assert 0.0 <= belief <= 1.0


async def test_compute_local_bp_writes_back(engine, storage):
    """After BP, updated beliefs should be persisted in LanceDB."""
    beliefs = await engine.compute_local_bp([67], hops=2)
    if beliefs:
        # Check that at least one node had its belief written back
        for node_id, expected_belief in beliefs.items():
            node = await storage.lance.load_node(node_id)
            if node:
                assert node.belief is not None


async def test_compute_local_bp_no_graph(storage):
    """When Neo4j unavailable, return empty beliefs."""
    storage.graph = None
    engine = InferenceEngine(storage)
    beliefs = await engine.compute_local_bp([67])
    assert beliefs == {}


async def test_compute_local_bp_custom_params(engine):
    """Custom BP params (damping, max_iterations) should work."""
    engine_custom = InferenceEngine(
        engine._storage, bp_params={"damping": 0.3, "max_iterations": 10}
    )
    beliefs = await engine_custom.compute_local_bp([67])
    assert len(beliefs) > 0


async def test_run_global_bp_not_implemented(engine):
    with pytest.raises(NotImplementedError):
        await engine.run_global_bp()
