from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.api.routes import artifacts, criteria, health, search, select
from semantic_selector.api.schemas import (
    ArtifactSelectionRequest,
    CompareArtifactsRequest,
    TermSearchRequest,
)
from semantic_selector.services import IndexService


def create_app(index_path: Path | None = None) -> FastAPI:
    app = FastAPI(title="Semantic Selector MVP", version="0.1.0")
    app.state.index_path = index_path

    @app.middleware("http")
    async def attach_service(request: Request, call_next):
        path = index_path or getattr(request.app.state, "index_path", None)
        if path is not None:
            request.state.index_service = IndexService(Path(path))
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(artifacts.router, prefix="/v1")
    app.include_router(criteria.router, prefix="/v1")
    app.include_router(search.router, prefix="/v1")
    app.include_router(select.router, prefix="/v1")
    return app


app = create_app()
