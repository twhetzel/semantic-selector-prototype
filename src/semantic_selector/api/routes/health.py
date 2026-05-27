from __future__ import annotations

from fastapi import APIRouter, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.get("/v1/index/manifest")
def index_manifest(request: Request) -> dict:
    service = get_index_service(request)
    try:
        return service.get_manifest()
    except FileNotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=str(exc)) from exc
