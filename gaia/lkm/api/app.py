"""FastAPI application for LKM."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from gaia.lkm.api.routes import router
from gaia.lkm.storage import StorageConfig, StorageManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize storage on startup, close on shutdown."""
    config = StorageConfig()
    mgr = StorageManager(config)
    await mgr.initialize()
    app.state.storage = mgr
    yield
    await mgr.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Gaia LKM", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app
