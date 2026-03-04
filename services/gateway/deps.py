"""Dependency injection — singleton services created at startup."""

from __future__ import annotations

import logging
import os

from libs.embedding import EmbeddingModel, StubEmbeddingModel
from libs.storage import StorageConfig, StorageManager
from services.commit_engine.engine import CommitEngine
from services.commit_engine.store import CommitStore
from services.inference_engine.engine import InferenceEngine
from services.job_manager.manager import JobManager
from services.job_manager.store import InMemoryJobStore
from services.review_pipeline.base import Pipeline
from services.review_pipeline.operators.bp import BPOperator
from services.review_pipeline.operators.embedding import EmbeddingOperator
from services.review_pipeline.operators.join import (
    CCJoinOperator,
    CPJoinOperator,
    JoinLLM,
    LiteLLMJoinClient,
    StubJoinLLM,
)
from services.review_pipeline.operators.nn_search import NNSearchOperator
from services.review_pipeline.operators.verify import (
    JoinTreeVerifyOperator,
    LiteLLMVerifyClient,
    RefineOperator,
    StubVerifyLLM,
    VerifyAgainOperator,
    VerifyLLM,
)
from services.search_engine.engine import SearchEngine

log = logging.getLogger(__name__)


def _build_embedding_model() -> EmbeddingModel:
    """Build embedding model based on environment variables.

    Uses DashScope when API_URL + ACCESS_KEY are set, otherwise falls back to stub.
    """
    api_url = os.environ.get("API_URL")
    access_key = os.environ.get("ACCESS_KEY")
    if api_url and access_key:
        from services.review_pipeline.operators.embedding_dashscope import (
            DashScopeEmbeddingModel,
        )

        log.info("Using DashScope embedding model (url=%s)", api_url)
        return DashScopeEmbeddingModel(api_url=api_url, access_key=access_key)
    log.info("No embedding API configured, using StubEmbeddingModel")
    return StubEmbeddingModel()


def _build_llm_clients() -> tuple[JoinLLM, VerifyLLM]:
    """Build join/verify LLM clients based on environment variables.

    Uses LiteLLM when DP_INTERNAL_BASE_URL + DP_INTERNAL_API_KEY are set.
    """
    base_url = os.environ.get("DP_INTERNAL_BASE_URL")
    api_key = os.environ.get("DP_INTERNAL_API_KEY")
    if base_url and api_key:
        from services.review_pipeline.config import LLMModelConfig
        from services.review_pipeline.llm_client import LLMClient

        config = LLMModelConfig(provider="dptech_internal", name="gpt-5-mini")
        llm_client = LLMClient(config)
        log.info("Using dptech_internal LLM for join/verify (url=%s)", base_url)
        return LiteLLMJoinClient(llm_client), LiteLLMVerifyClient(llm_client)
    log.info("No LLM configured, using stub join/verify")
    return StubJoinLLM(), StubVerifyLLM()


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

        embedding_model = _build_embedding_model()
        join_llm, verify_llm = _build_llm_clients()

        self.search_engine = SearchEngine(self.storage, embedding_model=embedding_model)
        commit_store = CommitStore(storage_path=config.lancedb_path + "/commits")
        pipeline = Pipeline(
            steps=[
                EmbeddingOperator(embedding_model),
                NNSearchOperator(self.storage.vector, k=20),
                CCJoinOperator(join_llm, self.storage),
                CPJoinOperator(join_llm, self.storage),
                JoinTreeVerifyOperator(verify_llm),
                RefineOperator(),
                VerifyAgainOperator(verify_llm),
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
