from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.api.schemas import TermSearchRequest, TermSearchResponse

router = APIRouter(tags=["search"])


@router.post("/search/terms", response_model=TermSearchResponse)
def search_terms(payload: TermSearchRequest, request: Request) -> TermSearchResponse:
    service = get_index_service(request)
    try:
        result = service.search_terms(
            query=payload.query,
            artifact_ids=payload.artifact_ids,
            repository_ids=payload.repository_ids,
            include_obsolete=payload.include_obsolete,
            limit=payload.limit,
        )
        return TermSearchResponse(**result)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
