"""Storage layer configuration."""

import os
from typing import Literal

from pydantic import BaseModel


class StorageConfig(BaseModel):
    deployment_mode: Literal["production", "local"] = "local"

    # LanceDB
    lancedb_path: str = os.environ.get("GAIA_LANCEDB_PATH", "/data/lancedb/gaia")

    # Neo4j
    neo4j_uri: str = os.environ.get("GAIA_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.environ.get("GAIA_NEO4J_USER", "neo4j")
    neo4j_password: str = os.environ.get("GAIA_NEO4J_PASSWORD", "")
    neo4j_database: str = os.environ.get("GAIA_NEO4J_DATABASE", "neo4j")

    # ByteHouse (production only)
    bytehouse_host: str | None = None
    bytehouse_port: int = 19000
    bytehouse_database: str = "gaia"
    bytehouse_api_key: str | None = None

    # Local fallback
    local_vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"
