from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from semantic_selector.api.dependencies import get_index_service
from semantic_selector.db.connection import connect
from semantic_selector.db.queries import get_artifact, get_artifact_criteria, list_artifacts

router = APIRouter(tags=["artifacts"])


@router.get("/artifacts")
def list_all_artifacts(request: Request) -> dict:
    service = get_index_service(request)
    conn = connect(service.index_path, read_only=True)
    try:
        return {"artifacts": list_artifacts(conn)}
    finally:
        conn.close()


@router.get("/artifacts/{artifact_id}")
def get_one_artifact(artifact_id: str, request: Request) -> dict:
    service = get_index_service(request)
    conn = connect(service.index_path, read_only=True)
    try:
        artifact = get_artifact(conn, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return artifact
    finally:
        conn.close()


@router.get("/artifacts/{artifact_id}/criteria")
def get_artifact_criterion_values(artifact_id: str, request: Request) -> dict:
    service = get_index_service(request)
    conn = connect(service.index_path, read_only=True)
    try:
        if get_artifact(conn, artifact_id) is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return {"artifact_id": artifact_id, "criteria": get_artifact_criteria(conn, artifact_id)}
    finally:
        conn.close()
