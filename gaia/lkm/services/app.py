"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.services import deps as deps_module
from gaia.lkm.services.routes import graph, inference, knowledge, neo4j_stats, packages, tables


def create_app(dependencies: deps_module.Dependencies | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if dependencies:
            deps_module.deps = dependencies
        else:
            config = StorageConfig()
            storage = StorageManager(config)
            await storage.initialize()
            deps_module.deps = deps_module.Dependencies(storage=storage)
        yield

    app = FastAPI(title="Gaia LKM", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(packages.router, prefix="/api")
    app.include_router(knowledge.router, prefix="/api")
    app.include_router(inference.router, prefix="/api")
    app.include_router(tables.router, prefix="/api")
    app.include_router(neo4j_stats.router, prefix="/api")
    app.include_router(graph.router, prefix="/api")

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
