from __future__ import annotations

import pytest

from semantic_selector.mcp.server import create_mcp_server
from semantic_selector.services import IndexService, build_index


@pytest.fixture
def built_service(config_dir, index_path):
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    return IndexService(index_path)


def test_mcp_server_creation(built_service, index_path) -> None:
    server = create_mcp_server(index_path)
    assert server.name == "Semantic Selector"


def test_mcp_matches_service_output(built_service) -> None:
    service_result = built_service.search_terms(query="myocardial infarction", limit=5)
    mcp_result = built_service.search_terms(query="myocardial infarction", limit=5)
    assert service_result["results"] == mcp_result["results"]
