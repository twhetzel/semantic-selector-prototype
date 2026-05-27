from __future__ import annotations

from fastapi import HTTPException, Request

from semantic_selector.services import IndexService


def get_index_service(request: Request) -> IndexService:
    service = getattr(request.state, "index_service", None)
    if service is None:
        raise HTTPException(status_code=503, detail="Index not configured")
    return service
