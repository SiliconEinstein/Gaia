"""StorageManager: container for all storage backends."""

from .config import StorageConfig
from .graph_store import GraphStore
from .lance_store import LanceStore
from .vector_search import VectorSearchClient, create_vector_client
from .id_generator import IDGenerator


class StorageManager:
    """Creates all stores from a single config. No composite business logic."""

    lance: LanceStore
    graph: GraphStore | None
    vector: VectorSearchClient
    ids: IDGenerator

    def __init__(self, config: StorageConfig):
        self.lance = LanceStore(db_path=config.lancedb_path)
        self.vector = create_vector_client(config)
        self.ids = IDGenerator(storage_path=config.lancedb_path + "/ids")

        self._driver = None
        self.graph = None

        if config.graph_backend == "neo4j":
            self._init_neo4j(config)
        elif config.graph_backend == "kuzu":
            self._init_kuzu(config)

    def _init_neo4j(self, config: StorageConfig) -> None:
        try:
            import neo4j

            auth = (config.neo4j_user, config.neo4j_password) if config.neo4j_password else None
            self._driver = neo4j.AsyncGraphDatabase.driver(
                config.neo4j_uri,
                auth=auth,
            )
            from .neo4j_store import Neo4jGraphStore

            self.graph = Neo4jGraphStore(
                driver=self._driver,
                database=config.neo4j_database,
            )
        except Exception:
            pass

    def _init_kuzu(self, config: StorageConfig) -> None:
        from .kuzu_store import KuzuGraphStore

        kuzu_path = config.kuzu_path or (config.lancedb_path + "/kuzu")
        store = KuzuGraphStore(db_path=kuzu_path)
        store._ensure_schema()
        self.graph = store

    async def close(self) -> None:
        await self.lance.close()
        if self.graph:
            await self.graph.close()
        if self._driver:
            await self._driver.close()
