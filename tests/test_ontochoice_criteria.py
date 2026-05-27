from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from semantic_selector.db.connection import connect
from semantic_selector.db.queries import list_criteria
from semantic_selector.services import IndexService, build_index


@pytest.fixture
def ontochoice_index(config_dir, index_path):
    build_index(
        sources_path=config_dir / "sources.ontochoice-test.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    return IndexService(index_path)


def test_criteria_registry_metadata(ontochoice_index) -> None:
    conn = connect(ontochoice_index.index_path, read_only=True)
    try:
        criteria = list_criteria(conn, enabled_only=False)
    finally:
        conn.close()
    by_id = {item["criterion_id"]: item for item in criteria}
    assert "hierarchy_presence" not in by_id
    definition = by_id["definition_coverage"]
    assert definition["source_criterion"] == "Ont: Term Details"
    assert "ontology" in definition["applies_to"]
    assert definition["table_aligned"] == 1
    assert by_id["has_version_metadata"]["table_aligned"] == 0
    assert by_id["inbound_owl_import_count"]["role"] == "ranking_and_evidence"
    assert by_id["inbound_owl_import_count"]["default_weight"] == 0.15
    assert by_id["term_match_frequency"]["evaluation_stage"] == "query_time"


def test_term_match_frequency_multi_query_ranking(ontochoice_index) -> None:
    result = ontochoice_index.select_artifacts(
        queries=["myocardial infarction", "cardiovascular disorder", "unrelated concept"],
        limit=10,
    )
    scores = {item["artifact_id"]: item["ontology_scores"]["term_match_frequency"] for item in result["results"]}
    assert scores["demo:ontology:one"] >= scores.get("demo:ontology:two", 0)


def test_definition_coverage_ranking_when_frequency_equal(ontochoice_index) -> None:
    heavy_definition = ontochoice_index.select_artifacts(
        query="myocardial infarction",
        weights={"term_match_frequency": 0.01, "definition_coverage": 0.99},
        limit=5,
    )
    assert heavy_definition["results"]
    assert "definition_coverage" in heavy_definition["results"][0]["ontology_scores"] or (
        "definition_coverage" in heavy_definition["results"][0]["criterion_scores"]
    )


def test_inbound_owl_import_count(ontochoice_index) -> None:
    conn = connect(ontochoice_index.index_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT numeric_value, evidence_json
            FROM artifact_criterion_values
            WHERE artifact_id = 'demo:ontology:one'
              AND criterion_id = 'inbound_owl_import_count'
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert int(row["numeric_value"]) >= 1
    evidence = json.loads(row["evidence_json"])
    assert "demo:ontology:two" in evidence.get("importing_artifact_ids", [])


def test_multilanguage_annotations(ontochoice_index) -> None:
    conn = connect(ontochoice_index.index_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT evidence_json
            FROM artifact_criterion_values
            WHERE artifact_id = 'demo:ontology:two'
              AND criterion_id = 'multilanguage_annotations'
            """
        ).fetchone()
    finally:
        conn.close()
    evidence = json.loads(row["evidence_json"])
    languages = set(evidence.get("languages", []))
    assert "en" in languages
    assert "la" in languages


def test_matching_term_evidence_in_search(ontochoice_index) -> None:
    result = ontochoice_index.search_terms(query="myocardial infarction", limit=5)
    assert result["results"]
    evidence = result["results"][0]["term_evidence"]
    assert "has_definition" in evidence
    assert "parent_count" in evidence
    assert "language_tags" in evidence


def test_term_reuse_by_identifier(ontochoice_index) -> None:
    conn = connect(ontochoice_index.index_path, read_only=True)
    try:
        row = conn.execute(
            """
            SELECT reuse_count, artifact_ids_json
            FROM term_iri_reuse
            WHERE term_iri = 'http://example.org/shared#SharedConcept'
            """
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert int(row["reuse_count"]) == 1
    artifact_ids = json.loads(row["artifact_ids_json"])
    assert "demo:shared:a" in artifact_ids
    assert "demo:shared:b" in artifact_ids

    search = ontochoice_index.search_terms(query="shared disease concept", limit=5)
    reuse_counts = {hit["term_iri"]: hit["term_evidence"]["term_reuse_count_by_iri"] for hit in search["results"]}
    assert reuse_counts["http://example.org/shared#SharedConcept"] == 1


def test_enforced_selection_list_allowlist(config_dir, index_path, tmp_path: Path) -> None:
    criteria = yaml.safe_load((config_dir / "criteria.example.yaml").read_text(encoding="utf-8"))
    for item in criteria["criteria"]:
        if item["id"] == "enforced_selection_list":
            item["enabled"] = True
            item["allowed_artifact_ids"] = ["demo:ontology:one"]
    criteria_path = tmp_path / "criteria.yaml"
    criteria_path.write_text(yaml.dump(criteria), encoding="utf-8")
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=criteria_path,
        output_path=index_path,
    )
    service = IndexService(index_path)
    result = service.select_artifacts(query="myocardial infarction", limit=10)
    artifact_ids = {item["artifact_id"] for item in result["results"]}
    assert artifact_ids == {"demo:ontology:one"}


def test_enforced_selection_list_blocklist(config_dir, index_path, tmp_path: Path) -> None:
    criteria = yaml.safe_load((config_dir / "criteria.example.yaml").read_text(encoding="utf-8"))
    for item in criteria["criteria"]:
        if item["id"] == "enforced_selection_list":
            item["enabled"] = True
            item["blocked_artifact_ids"] = ["demo:ontology:two"]
    criteria_path = tmp_path / "criteria.yaml"
    criteria_path.write_text(yaml.dump(criteria), encoding="utf-8")
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=criteria_path,
        output_path=index_path,
    )
    service = IndexService(index_path)
    result = service.select_artifacts(query="myocardial infarction", limit=10)
    artifact_ids = {item["artifact_id"] for item in result["results"]}
    assert "demo:ontology:two" not in artifact_ids


def test_hierarchy_relations_still_indexed(ontochoice_index) -> None:
    conn = connect(ontochoice_index.index_path, read_only=True)
    try:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM term_relations WHERE relation_type = 'hierarchy'"
        ).fetchone()["c"]
    finally:
        conn.close()
    assert count > 0
