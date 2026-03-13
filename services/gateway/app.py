"""FastAPI application factory for Gaia."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import deps, Dependencies
from .routes.packages import router as packages_router


def create_app(dependencies: Dependencies | None = None) -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(title="Gaia", version="0.2.0", description="Large Knowledge Model API")

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

    @app.on_event("startup")
    async def startup():
        if active_deps.storage is None:
            await active_deps.initialize()

    @app.on_event("shutdown")
    async def shutdown():
        await active_deps.cleanup()

    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "0.2.0"}

    app.include_router(packages_router)

    return app
