"""StorageManager — unified facade for ContentStore, GraphStore, and VectorStore."""

from __future__ import annotations

import logging

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.vector_store import VectorStore

logger = logging.getLogger(__name__)


class StorageManager:
    """Unified storage facade. Domain services only touch this class."""

    def __init__(self, config: StorageConfig) -> None:
        self._config = config
        self.content_store: ContentStore | None = None
        self.graph_store: GraphStore | None = None
        self.vector_store: VectorStore | None = None

    async def initialize(self) -> None:
        """Instantiate and initialize all configured stores."""
        from libs.storage_v2.lance_content_store import LanceContentStore
        from libs.storage_v2.lance_vector_store import LanceVectorStore

        # ContentStore — always required
        cs = LanceContentStore(self._config.lancedb_path)
        await cs.initialize()
        self.content_store = cs

        # GraphStore — optional
        if self._config.graph_backend == "kuzu":
            from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

            kuzu_path = self._config.kuzu_path or (self._config.lancedb_path + "_kuzu")
            gs = KuzuGraphStore(kuzu_path)
            await gs.initialize_schema()
            self.graph_store = gs
        elif self._config.graph_backend == "neo4j":
            logger.warning("Neo4j graph backend not yet implemented in v2; skipping")
        # else: "none" — graph_store stays None

        # VectorStore — always created (same LanceDB path, separate table)
        vs = LanceVectorStore(self._config.lancedb_path)
        self.vector_store = vs

    async def close(self) -> None:
        """Release connections held by stores."""
        if self.graph_store is not None:
            await self.graph_store.close()
