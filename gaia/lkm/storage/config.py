"""LKM storage configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """LKM storage layer configuration.

    All fields overrideable via LKM_ prefixed environment variables.
    """

    # LanceDB
    lancedb_path: str = "/data/lancedb/lkm"
    lancedb_uri: str | None = None  # s3:// or tos:// remote URI

    # Graph backend (deferred — placeholder for M6/M8)
    graph_backend: str = "none"  # "neo4j" | "kuzu" | "none"

    model_config = {"env_prefix": "LKM_"}

    @property
    def effective_lancedb_uri(self) -> str:
        return self.lancedb_uri or self.lancedb_path
