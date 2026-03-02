# tests/conftest.py
import pytest


def pytest_collection_modifyitems(config, items):
    """Skip neo4j tests if Neo4j is not available."""
    if not _neo4j_available():
        skip = pytest.mark.skip(reason="Neo4j not available")
        for item in items:
            if "neo4j" in item.keywords:
                item.add_marker(skip)


def _neo4j_available() -> bool:
    try:
        import neo4j
        driver = neo4j.GraphDatabase.driver(
            "bolt://localhost:7687", auth=("neo4j", "testpassword")
        )
        driver.verify_connectivity()
        driver.close()
        return True
    except Exception:
        return False
