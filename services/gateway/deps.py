"""Dependency injection — singleton services created at startup."""

from __future__ import annotations

from libs.embedding import StubEmbeddingModel
from libs.storage import StorageConfig, StorageManager
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.inference_engine.engine import InferenceEngine
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.review_pipeline.base import Pipeline
from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.operators.embedding import EmbeddingOperator
from services.review_pipeline.operators.join import CCJoinOperator, CPJoinOperator, StubJoinLLM
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.operators.verify import (
    JoinTreeVerifyOperator,
    RefineOperator,
    StubVerifyLLM,
    VerifyAgainOperator,
)
from services.search_engine.engine import SearchEngine


class Dependencies:
    """Holds all service singletons."""

    def __init__(self, config: StorageConfig | None = None):
        self.config = config or StorageConfig()
        self.storage: StorageManager | None = None
        self.search_engine: SearchEngine | None = None
        self.commit_engine: CommitEngine | None = None
        self.inference_engine: InferenceEngine | None = None
        self.job_manager: JobManager | None = None

    def initialize(self, storage_config: StorageConfig | None = None):
        """Create all services. Call once at startup."""
        config = storage_config or self.config
        self.storage = StorageManager(config)
        embedding_model = StubEmbeddingModel()
        self.search_engine = SearchEngine(self.storage, embedding_model=embedding_model)
        commit_store = CommitStore(storage_path=config.lancedb_path + "/commits")
        pipeline = Pipeline(
            steps=[
                EmbeddingOperator(embedding_model),
                NNSearchOperator(self.storage.vector, k=20),
                CCJoinOperator(StubJoinLLM(), self.storage),
                CPJoinOperator(StubJoinLLM(), self.storage),
                JoinTreeVerifyOperator(StubVerifyLLM()),
                RefineOperator(),
                VerifyAgainOperator(StubVerifyLLM()),
                BPOperator(self.storage),
            ]
        )
        self.job_manager = JobManager(store=InMemoryJobStore())
        self.commit_engine = CommitEngine(
            storage=self.storage,
            commit_store=commit_store,
            search_engine=self.search_engine,
            pipeline=pipeline,
            job_manager=self.job_manager,
        )
        self.inference_engine = InferenceEngine(self.storage)

    async def cleanup(self):
        """Shut down services gracefully."""
        if self.storage:
            await self.storage.close()


# Global instance
deps = Dependencies()
