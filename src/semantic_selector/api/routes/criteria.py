from __future__ import annotations

from fastapi import APIRouter, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.db.connection import connect
from semantic_selector.db.queries import list_criteria

router = APIRouter(tags=["criteria"])


@router.get("/criteria")
def get_criteria(request: Request) -> dict:
    service = get_index_service(request)
    conn = connect(service.index_path, read_only=True)
    try:
        return {"criteria": list_criteria(conn, enabled_only=False)}
    finally:
        conn.close()
