"""Dependency injection — singleton services created at startup."""

from __future__ import annotations

import logging

from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager

log = logging.getLogger(__name__)


class Dependencies:
    """Holds all service singletons."""

    def __init__(self, config: StorageConfig | None = None):
        self.config = config
        self.storage: StorageManager | None = None

    async def initialize(self, config: StorageConfig | None = None):
        """Create storage manager. Call once at startup."""
        cfg = config or self.config or StorageConfig()
        self.storage = StorageManager(cfg)
        await self.storage.initialize()

    async def cleanup(self):
        """Shut down services gracefully."""
        if self.storage:
            await self.storage.close()


# Global instance
deps = Dependencies()
