"""Shared test fixtures — real storage backends seeded with fixture data."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.embedding import StubEmbeddingModel
from libs.models import HyperEdge, Node
from libs.storage import StorageConfig, StorageManager

FIXTURES_DIR = Path(__file__).parent / "fixtures"

_embedding_model = StubEmbeddingModel()


def load_fixture_nodes() -> list[Node]:
    """Load nodes from tests/fixtures/nodes.json."""
    with open(FIXTURES_DIR / "nodes.json") as f:
        raw = json.load(f)
    return [Node.model_validate(n) for n in raw]


def load_fixture_edges() -> list[HyperEdge]:
    """Load edges from tests/fixtures/edges.json."""
    with open(FIXTURES_DIR / "edges.json") as f:
        raw = json.load(f)
    return [HyperEdge.model_validate(e) for e in raw]


@pytest.fixture
async def storage(tmp_path: Path) -> StorageManager:
    """Real StorageManager seeded with fixture data (LanceDB + vector + Neo4j)."""
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    manager = StorageManager(config)
    assert manager.graph is not None, "Neo4j must be available — check that it's running"

    # Clean Neo4j before seeding to avoid constraint violations from other tests
    async with manager.graph._driver.session(database=manager.graph._db) as session:
        await session.run("MATCH (n) DETACH DELETE n")

    # Seed nodes
    nodes = load_fixture_nodes()
    await manager.lance.save_nodes(nodes)

    # Seed edges into Neo4j
    edges = load_fixture_edges()
    for edge in edges:
        await manager.graph.create_hyperedge(edge)

    # Seed embeddings via StubEmbeddingModel (matches search-time dimensions)
    texts = [n.content if isinstance(n.content, str) else str(n.content) for n in nodes]
    vectors = await _embedding_model.embed(texts)
    node_ids = [n.id for n in nodes]
    await manager.vector.insert_batch(node_ids, vectors)

    yield manager

    # Teardown: clean Neo4j data so tests are isolated
    if manager.graph:
        async with manager.graph._driver.session(database=manager.graph._db) as session:
            await session.run("MATCH (n) DETACH DELETE n")
    await manager.close()


@pytest.fixture
async def storage_empty(tmp_path: Path) -> StorageManager:
    """Empty real StorageManager — no fixture data loaded."""
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        neo4j_password="",
    )
    manager = StorageManager(config)
    yield manager
    await manager.close()
