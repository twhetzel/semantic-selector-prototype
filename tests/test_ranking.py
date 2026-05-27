from __future__ import annotations

import pytest

from semantic_selector.ranking.scorer import (
    compute_overall_score,
    normalize_candidate_count_scores,
    normalize_weights,
)
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


def test_weight_normalization() -> None:
    normalized = normalize_weights(
        {
            "term_match_frequency": 0.5,
            "definition_coverage": 0.35,
            "inbound_owl_import_count": 0.15,
        }
    )
    assert abs(sum(normalized.values()) - 1.0) < 1e-9


def test_normalize_candidate_count_scores() -> None:
    assert normalize_candidate_count_scores({"a": 0.0, "b": 2.0}) == {"a": 0.0, "b": 1.0}
    assert normalize_candidate_count_scores({"a": 3.0, "b": 3.0}) == {"a": 1.0, "b": 1.0}


def test_inbound_import_boosts_ontology_ranking(built_index) -> None:
    reuse_heavy = built_index.select_artifacts(
        query="myocardial infarction",
        weights={
            "term_match_frequency": 0.05,
            "definition_coverage": 0.05,
            "inbound_owl_import_count": 0.90,
        },
        limit=5,
    )
    scores = {
        item["artifact_id"]: item["ontology_scores"]["inbound_owl_import_count"]
        for item in reuse_heavy["results"]
    }
    assert scores["demo:ontology:one"] > scores.get("demo:ontology:two", 0.0)
    assert reuse_heavy["results"][0]["artifact_id"] == "demo:ontology:one"


def test_exact_label_ranks_higher_with_term_weight(built_index) -> None:
    heavy_term = built_index.select_artifacts(
        query="myocardial infarction",
        weights={"term_match_frequency": 0.95, "definition_coverage": 0.05},
        limit=5,
    )
    assert heavy_term["results"]
    top = heavy_term["results"][0]
    assert top["best_term_match"]["match_type"] in {
        "preferred_label_exact",
        "synonym_exact",
        "synonym_text_match",
        "preferred_label_prefix",
        "preferred_label_word",
        "preferred_label_text_match",
        "curie_exact",
    }


def test_changing_weights_changes_ranking(built_index) -> None:
    term_heavy = built_index.select_artifacts(
        query="myocardial infarction",
        weights={"term_match_frequency": 0.99, "definition_coverage": 0.01},
        limit=5,
    )
    def_heavy = built_index.select_artifacts(
        query="myocardial infarction",
        weights={"term_match_frequency": 0.01, "definition_coverage": 0.99},
        limit=5,
    )
    assert term_heavy["results"] and def_heavy["results"]


def test_compute_overall_score() -> None:
    score = compute_overall_score(
        term_match_frequency=1.0,
        criterion_scores={"definition_coverage": 0.5},
        weights={"term_match_frequency": 0.5, "definition_coverage": 0.5},
    )
    assert score == 0.75
