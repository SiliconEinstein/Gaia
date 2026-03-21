"""Storage configuration."""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """Environment-driven storage configuration. Values read at instantiation time.

    Supports both local and remote LanceDB:
      - Local: set lancedb_path (default)
      - Remote (S3/TOS): set lancedb_uri (s3://bucket/path) + TOS credentials

    All fields can be set via environment variables with GAIA_ prefix.
    TOS credentials use TOS_ prefix (shared with other TOS services).
    """

    # LanceDB — local path or remote S3/TOS URI
    lancedb_path: str = "/data/lancedb/gaia"
    lancedb_uri: str | None = None  # e.g. "s3://datainfra-prod/propositional_logic_analysis"

    # Graph backend
    graph_backend: Literal["neo4j", "kuzu", "none"] = "kuzu"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"
    kuzu_path: str | None = None

    # Vector index
    vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"

    model_config = {"env_prefix": "GAIA_"}

    @property
    def is_remote_lancedb(self) -> bool:
        """True if using remote S3/TOS-backed LanceDB."""
        return self.lancedb_uri is not None and self.lancedb_uri.startswith("s3://")

    @property
    def effective_lancedb_connection(self) -> str:
        """Return the LanceDB connection string: remote URI if set, else local path."""
        return self.lancedb_uri or self.lancedb_path
