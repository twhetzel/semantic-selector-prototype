from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.api.schemas import (
    ArtifactSelectionRequest,
    ArtifactSelectionResponse,
    CompareArtifactsRequest,
)

router = APIRouter(tags=["select"])


@router.post("/select/artifacts", response_model=ArtifactSelectionResponse)
def select_artifacts(
    payload: ArtifactSelectionRequest, request: Request
) -> ArtifactSelectionResponse:
    service = get_index_service(request)
    try:
        result = service.select_artifacts(
            query=payload.query,
            queries=payload.queries,
            filters=payload.filters.model_dump(),
            weights=payload.weights,
            limit=payload.limit,
        )
        return ArtifactSelectionResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/compare/artifacts")
def compare_artifacts(payload: CompareArtifactsRequest, request: Request) -> dict:
    service = get_index_service(request)
    try:
        return service.compare_artifacts(
            artifact_ids=payload.artifact_ids,
            query=payload.query,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
