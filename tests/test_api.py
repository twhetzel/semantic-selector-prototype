from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from semantic_selector.api.app import create_app
from semantic_selector.services import build_index


@pytest.fixture
def client(config_dir, index_path):
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    app = create_app(index_path=index_path)
    with TestClient(app) as test_client:
        yield test_client


def test_health(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_search_terms(client) -> None:
    response = client.post(
        "/v1/search/terms",
        json={"query": "myocardial infarction", "limit": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_id"]
    assert len(body["results"]) >= 2


def test_select_artifacts(client) -> None:
    response = client.post(
        "/v1/select/artifacts",
        json={"query": "myocardial infarction", "limit": 5},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["results"][0]["explanation"]


def test_compare_artifacts(client) -> None:
    response = client.post(
        "/v1/compare/artifacts",
        json={
            "artifact_ids": ["demo:ontology:one", "demo:ontology:two"],
            "query": "myocardial infarction",
        },
    )
    assert response.status_code == 200
    assert len(response.json()["artifacts"]) == 2
