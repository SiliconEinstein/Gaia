"""FastAPI application factory for Gaia."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import deps, Dependencies
from .routes.commits import router as commits_router
from .routes.read import router as read_router
from .routes.search import router as search_router
from .routes.batch import router as batch_router
from .routes.jobs import router as jobs_router
from .routes.v2 import router as v2_router


def create_app(dependencies: Dependencies | None = None) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(title="Gaia", version="0.1.0", description="Large Knowledge Model API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Load .env for production/local dev (not in tests where deps are injected)
    if dependencies is None:
        from dotenv import load_dotenv

        load_dotenv()

    active_deps = dependencies or deps

    # When custom dependencies are injected (e.g. in tests), propagate
    # them to the module-level singleton so route handlers can use them.
    if dependencies is not None:
        deps.storage = dependencies.storage
        deps.search_engine = dependencies.search_engine
        deps.commit_engine = dependencies.commit_engine
        deps.inference_engine = dependencies.inference_engine
        deps.job_manager = dependencies.job_manager
        deps.storage_v2 = dependencies.storage_v2

    @app.on_event("startup")
    async def startup():
        if active_deps.storage is None:
            active_deps.initialize()
        await active_deps.initialize_v2()

    @app.on_event("shutdown")
    async def shutdown():
        await active_deps.cleanup()

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.1.0"}

    app.include_router(batch_router)
    app.include_router(commits_router)
    app.include_router(read_router)
    app.include_router(search_router)
    app.include_router(jobs_router)
    app.include_router(v2_router)

    return app
