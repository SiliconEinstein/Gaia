"""Vector search subsystem — factory + public API."""

from .base import VectorSearchClient
from ..config import StorageConfig


def create_vector_client(config: StorageConfig) -> VectorSearchClient:
    """Instantiate the appropriate vector search backend.

    - **local** mode  -> LanceDB on-disk
    - **production** mode -> ByteHouse (not yet implemented)
    """
    if config.deployment_mode == "production":
        raise NotImplementedError("ByteHouse vector client not yet implemented")

    from .lancedb_client import LanceDBVectorClient

    return LanceDBVectorClient(
        db_path=config.lancedb_path,
        index_type=config.local_vector_index_type,
    )


__all__ = ["VectorSearchClient", "create_vector_client"]
