"""Storage configuration — reads from environment variables with GAIA_ prefix."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """Environment-driven storage configuration.

    Supports local LanceDB (default) and remote S3/TOS URI.
    Graph backend: Neo4j (server) or none. Kuzu left for CLI collaborator.
    """

    # LanceDB
    lancedb_path: str = "./data/lancedb/gaia"
    lancedb_uri: str | None = None  # e.g. "s3://bucket/path"

    # Neo4j (optional)
    neo4j_uri: str | None = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    # Vector index
    vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"

    model_config = {"env_prefix": "GAIA_"}

    @property
    def has_neo4j(self) -> bool:
        return self.neo4j_uri is not None

    @property
    def effective_lancedb_connection(self) -> str:
        return self.lancedb_uri or self.lancedb_path
