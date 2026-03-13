"""Storage configuration."""

from typing import Literal

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """Environment-driven storage configuration. Values read at instantiation time."""

    lancedb_path: str = "/data/lancedb/gaia"
    graph_backend: Literal["neo4j", "kuzu", "none"] = "kuzu"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    kuzu_path: str | None = None
    vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"

    model_config = {"env_prefix": "GAIA_"}
