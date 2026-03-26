"""Dependency injection for FastAPI."""

from __future__ import annotations

from gaia.libs.embedding import EmbeddingModel
from gaia.libs.storage.manager import StorageManager


class Dependencies:
    def __init__(self, storage: StorageManager, embedding: EmbeddingModel | None = None):
        self.storage = storage
        self.embedding = embedding


# Global singleton, initialized at startup
deps: Dependencies | None = None
