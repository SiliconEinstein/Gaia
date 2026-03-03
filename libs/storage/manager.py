"""StorageManager: container for all storage backends."""

from .config import StorageConfig
from .lance_store import LanceStore
from .neo4j_store import Neo4jGraphStore
from .vector_search import create_vector_client, VectorSearchClient
from .id_generator import IDGenerator


class StorageManager:
    """Creates all stores from a single config. No composite business logic."""

    lance: LanceStore
    graph: Neo4jGraphStore | None
    vector: VectorSearchClient
    ids: IDGenerator

    def __init__(self, config: StorageConfig):
        self.lance = LanceStore(db_path=config.lancedb_path)
        self.vector = create_vector_client(config)
        self.ids = IDGenerator(storage_path=config.lancedb_path + "/ids")

        # Neo4j: create lazily or handle missing connection gracefully
        self._driver = None
        self.graph = None
        try:
            import neo4j

            auth = (config.neo4j_user, config.neo4j_password) if config.neo4j_password else None
            self._driver = neo4j.AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=auth,
            )
            self.graph = Neo4jGraphStore(
                driver=self._driver,
                database=config.neo4j_database,
            )
        except Exception:
            pass

    async def close(self) -> None:
        await self.lance.close()
        if self.graph:
            await self.graph.close()
        if self._driver:
            await self._driver.close()
