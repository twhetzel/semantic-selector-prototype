from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from semantic_selector.db.connection import connect
from semantic_selector.extractors.base import execute_extractor
from semantic_selector.extractors.normalization import join_extractor_results
from semantic_selector.extractors.registry import ExtractorRegistry
from semantic_selector.rdf.build_config import BuildConfig
from semantic_selector.rdf.factory import create_rdf_backend
from semantic_selector.rdf.pyoxigraph_backend import PyoxigraphBackend
from semantic_selector.rdf.serialization import artifact_store_path
from semantic_selector.services import build_index, validate_index
from semantic_selector.settings import PROJECT_ROOT


def _extract_facts(path: Path, artifact_id: str, backend_name: str, store_dir: Path):
    build_config = BuildConfig(
        rdf_backend=backend_name,
        temporary_store_dir=store_dir,
        retain_rdf_store_after_build=False,
        instrumentation_enabled=True,
    )
    backend = create_rdf_backend(build_config, artifact_id=artifact_id)
    backend.load_artifact(path)
    registry = ExtractorRegistry.from_yaml(PROJECT_ROOT / "config/extractors.example.yaml")
    results = {d.id: execute_extractor(backend, d) for d in registry.enabled}
    facts = join_extractor_results(artifact_id, results)
    backend.close()
    return facts


def _normalize_facts(facts) -> dict:
    return {
        "terms": sorted(
            [
                {
                    "term_iri": t["term_iri"],
                    "preferred_label": t.get("preferred_label"),
                    "normalized_label": t.get("normalized_label"),
                    "synonyms_text": t.get("synonyms_text"),
                    "definitions_text": t.get("definitions_text"),
                    "is_obsolete": t.get("is_obsolete"),
                    "parent_count": t.get("parent_count"),
                    "child_count": t.get("child_count"),
                    "mapping_count": t.get("mapping_count"),
                }
                for t in facts.terms
            ],
            key=lambda item: item["term_iri"],
        ),
        "relations": sorted(
            [
                {
                    "subject_iri": r["subject_iri"],
                    "predicate_iri": r["predicate_iri"],
                    "object_iri": r["object_iri"],
                    "relation_type": r["relation_type"],
                }
                for r in facts.relations
            ],
            key=lambda item: (
                item["subject_iri"],
                item["predicate_iri"],
                item["object_iri"],
            ),
        ),
        "metadata_keys": sorted(facts.metadata.keys()),
    }


def _sources_with_build(tmp_path: Path, build: dict) -> Path:
    sources = yaml.safe_load(
        (PROJECT_ROOT / "config/sources.example.yaml").read_text(encoding="utf-8")
    )
    sources["build"] = build
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(yaml.dump(sources), encoding="utf-8")
    return sources_path


def test_build_config_rejects_invalid_backend() -> None:
    with pytest.raises(ValueError, match="Unsupported build.rdf_backend"):
        BuildConfig.from_sources_config({"build": {"rdf_backend": "not-a-backend"}})


def test_build_config_selects_backend_from_yaml() -> None:
    config = BuildConfig.from_sources_config({"build": {"rdf_backend": "pyoxigraph"}})
    assert config.rdf_backend == "pyoxigraph"


def test_fixture_extractor_equivalence(fixtures_dir, tmp_path) -> None:
    store_dir = tmp_path / "rdf-store"
    for fixture_name in ("demo-one.ttl", "demo-two.ttl"):
        path = fixtures_dir / fixture_name
        artifact_id = f"demo:{fixture_name}"
        rdflib_facts = _extract_facts(path, artifact_id, "rdflib", store_dir)
        pyoxigraph_facts = _extract_facts(path, artifact_id, "pyoxigraph", store_dir)
        assert _normalize_facts(rdflib_facts) == _normalize_facts(pyoxigraph_facts)


def test_build_fixture_index_with_rdflib(config_dir, index_path) -> None:
    report = build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    assert report.rdf_backend == "rdflib"
    assert report.artifacts_indexed == 2
    assert report.terms_indexed > 0
    validate_index(index_path)


def test_build_fixture_index_with_pyoxigraph(config_dir, tmp_path, index_path) -> None:
    sources_path = _sources_with_build(
        tmp_path,
        {
            "rdf_backend": "pyoxigraph",
            "temporary_store_dir": str(tmp_path / "rdf-store"),
            "retain_rdf_store_after_build": False,
            "instrumentation_enabled": True,
        },
    )
    report = build_index(
        sources_path=sources_path,
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    assert report.rdf_backend == "pyoxigraph"
    assert report.artifacts_indexed == 2
    validate_index(index_path)


def test_pyoxigraph_store_removed_when_not_retained(fixtures_dir, tmp_path) -> None:
    store_dir = tmp_path / "rdf-store"
    store_path = artifact_store_path(store_dir, "demo:fixture")
    backend = PyoxigraphBackend(store_path=store_path, retain_store=False)
    backend.load_artifact(fixtures_dir / "demo-one.ttl")
    assert store_path.exists()
    backend.cleanup_store()
    assert not store_path.exists()


def test_pyoxigraph_store_retained_when_configured(fixtures_dir, tmp_path) -> None:
    store_dir = tmp_path / "rdf-store"
    store_path = artifact_store_path(store_dir, "demo:fixture")
    backend = PyoxigraphBackend(store_path=store_path, retain_store=True)
    backend.load_artifact(fixtures_dir / "demo-one.ttl")
    backend.close()
    assert store_path.exists()


def test_pyoxigraph_query_handles_non_select_results(fixtures_dir, tmp_path) -> None:
    store_path = artifact_store_path(tmp_path / "rdf-store", "demo:fixture")
    backend = PyoxigraphBackend(store_path=store_path, retain_store=False)
    backend.load_artifact(fixtures_dir / "demo-one.ttl")

    select_rows = list(backend.query("SELECT ?s WHERE { ?s ?p ?o } LIMIT 1"))
    assert select_rows
    assert "s" in select_rows[0]

    ask_rows = list(backend.query("ASK { ?s ?p ?o }"))
    assert ask_rows == [{"value": True}]

    construct_rows = list(
        backend.query("CONSTRUCT { ?s ?p ?o } WHERE { ?s ?p ?o } LIMIT 1")
    )
    assert construct_rows
    assert {"subject", "predicate", "object"} <= set(construct_rows[0])

    backend.cleanup_store()


def test_build_report_records_extractor_metrics(config_dir, tmp_path, index_path) -> None:
    report_path = tmp_path / "build-report.json"
    report = build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
        report_path=report_path,
    )
    assert report.artifact_reports
    first = report.artifact_reports[0]
    assert first.extractors
    assert all(metric.row_count >= 0 for metric in first.extractors)
    assert all(metric.duration_seconds >= 0 for metric in first.extractors)
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["artifact_reports"][0]["extractors"]


def test_failed_build_does_not_replace_existing_index(config_dir, tmp_path) -> None:
    good_index = tmp_path / "good.sqlite"
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=good_index,
    )
    original_mtime = good_index.stat().st_mtime
    original_size = good_index.stat().st_size

    bad_sources = yaml.safe_load(
        (config_dir / "sources.example.yaml").read_text(encoding="utf-8")
    )
    bad_sources["build"] = {"rdf_backend": "invalid-backend"}
    bad_sources_path = tmp_path / "bad-sources.yaml"
    bad_sources_path.write_text(yaml.dump(bad_sources), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported build.rdf_backend"):
        build_index(
            sources_path=bad_sources_path,
            extractors_path=config_dir / "extractors.example.yaml",
            criteria_path=config_dir / "criteria.example.yaml",
            output_path=good_index,
        )

    assert good_index.exists()
    assert good_index.stat().st_size == original_size
    assert good_index.stat().st_mtime == original_mtime


def test_rdflib_and_pyoxigraph_fixture_indexes_match(config_dir, tmp_path) -> None:
    rdflib_index = tmp_path / "rdflib.sqlite"
    pyoxigraph_index = tmp_path / "pyoxigraph.sqlite"
    build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=rdflib_index,
    )
    sources_path = _sources_with_build(
        tmp_path,
        {
            "rdf_backend": "pyoxigraph",
            "temporary_store_dir": str(tmp_path / "rdf-store"),
            "retain_rdf_store_after_build": False,
        },
    )
    build_index(
        sources_path=sources_path,
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=pyoxigraph_index,
    )

    def _term_snapshot(path: Path) -> list[tuple]:
        conn = connect(path)
        try:
            rows = conn.execute(
                """
                SELECT artifact_id, term_iri, preferred_label, normalized_label,
                       synonyms_text, definitions_text, is_obsolete
                FROM terms
                ORDER BY artifact_id, term_iri
                """
            ).fetchall()
            return [tuple(row) for row in rows]
        finally:
            conn.close()

    assert _term_snapshot(rdflib_index) == _term_snapshot(pyoxigraph_index)
