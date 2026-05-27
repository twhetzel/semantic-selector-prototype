from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from semantic_selector.db.connection import connect
from semantic_selector.db.queries import get_artifact, list_artifacts, list_criteria
from semantic_selector.services import IndexService

_mcp: FastMCP | None = None
_index_path: Path | None = None


def create_mcp_server(index_path: Path) -> FastMCP:
    global _mcp, _index_path
    _index_path = index_path
    mcp = FastMCP("Semantic Selector", json_response=True)

    def service() -> IndexService:
        if _index_path is None:
            raise RuntimeError("Index path not configured")
        return IndexService(_index_path)

    @mcp.tool()
    def search_semantic_terms(
        query: str,
        artifact_ids: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Find terms across indexed ontology artifacts."""
        return service().search_terms(query=query, artifact_ids=artifact_ids, limit=limit)

    @mcp.tool()
    def recommend_semantic_artifacts(
        query: str | None = None,
        queries: list[str] | None = None,
        weights: dict[str, float] | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Rank ontology artifacts for one or more concept queries."""
        return service().select_artifacts(
            query=query,
            queries=queries,
            weights=weights,
            limit=limit,
        )

    @mcp.tool()
    def compare_semantic_artifacts(
        artifact_ids: list[str],
        query: str | None = None,
    ) -> dict[str, Any]:
        """Compare specified artifacts with optional concept query overlap."""
        return service().compare_artifacts(artifact_ids=artifact_ids, query=query)

    @mcp.tool()
    def get_selector_index_manifest() -> dict[str, Any]:
        """Return snapshot metadata for the active selector index."""
        manifest = service().get_manifest()
        conn = connect(_index_path, read_only=True)
        try:
            artifacts = list_artifacts(conn)
        finally:
            conn.close()
        return {"manifest": manifest, "artifacts": artifacts}

    @mcp.resource("selector://criteria")
    def criteria_resource() -> str:
        conn = connect(_index_path, read_only=True)
        try:
            return json.dumps({"criteria": list_criteria(conn)}, indent=2)
        finally:
            conn.close()

    @mcp.resource("selector://index/manifest")
    def manifest_resource() -> str:
        return json.dumps(service().get_manifest(), indent=2)

    @mcp.resource("selector://artifact/{artifact_id}")
    def artifact_resource(artifact_id: str) -> str:
        conn = connect(_index_path, read_only=True)
        try:
            artifact = get_artifact(conn, artifact_id)
            if artifact is None:
                return json.dumps({"error": "Artifact not found"})
            return json.dumps(dict(artifact), indent=2)
        finally:
            conn.close()

    _mcp = mcp
    return mcp


def run_mcp_stdio(index_path: Path) -> None:
    server = create_mcp_server(index_path)
    server.run(transport="stdio")
