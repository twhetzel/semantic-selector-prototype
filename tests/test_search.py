from __future__ import annotations

import pytest

from semantic_selector.services import IndexService, build_index


@pytest.fixture
def built_index(config_dir, index_path):
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    return IndexService(index_path)


def test_search_returns_shared_label_groups(built_index) -> None:
    result = built_index.search_terms(query="myocardial infarction", limit=20)
    assert len(result["results"]) >= 2
    artifact_ids = {r["artifact_id"] for r in result["results"]}
    assert len(artifact_ids) >= 2
    exact_matches = [
        r for r in result["results"] if r["normalized_label"] == "myocardial infarction"
    ]
    assert len(exact_matches) >= 2
    for row in result["results"]:
        assert row["shared_label_group"] == row["normalized_label"]


def test_obsolete_excluded_by_default(built_index) -> None:
    result = built_index.search_terms(query="old cardiac", include_obsolete=False)
    assert result["results"] == []
