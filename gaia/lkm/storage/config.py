"""LKM storage configuration."""

from __future__ import annotations

import os

from pydantic_settings import BaseSettings


class StorageConfig(BaseSettings):
    """LKM storage layer configuration.

    All fields overrideable via LKM_ prefixed environment variables.
    TOS credentials also fall back to TOS_* env vars (shared with source_lance).
    """

    # LanceDB
    lancedb_path: str = "/data/lancedb/lkm"
    lancedb_uri: str | None = None  # s3:// or tos:// remote URI

    # TOS credentials (for S3-compatible remote LanceDB)
    tos_access_key: str = ""
    tos_secret_key: str = ""
    tos_endpoint: str = "tos-s3-cn-beijing.volces.com"

    # Graph backend
    graph_backend: str = "none"  # "neo4j" | "none"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    neo4j_database: str = "neo4j"

    model_config = {"env_prefix": "LKM_"}

    def model_post_init(self, __context: object) -> None:
        """Fall back to TOS_* env vars if LKM_TOS_* not set."""
        if not self.tos_access_key:
            self.tos_access_key = os.environ.get("TOS_ACCESS_KEY", "")
        if not self.tos_secret_key:
            self.tos_secret_key = os.environ.get("TOS_SECRET_KEY", "")
        if self.tos_endpoint == "tos-s3-cn-beijing.volces.com":
            self.tos_endpoint = os.environ.get("TOS_ENDPOINT", self.tos_endpoint)

    @property
    def effective_lancedb_uri(self) -> str:
        return self.lancedb_uri or self.lancedb_path

    @property
    def storage_options(self) -> dict[str, str] | None:
        """S3-compatible storage options for remote LanceDB, or None for local."""
        uri = self.effective_lancedb_uri
        if not uri.startswith("s3://"):
            return None
        bucket = uri.split("/")[2]
        return {
            "access_key_id": self.tos_access_key,
            "secret_access_key": self.tos_secret_key,
            "endpoint": f"https://{bucket}.{self.tos_endpoint}",
            "virtual_hosted_style_request": "true",
        }
