from __future__ import annotations

import sqlite3

import pytest

from semantic_selector.db.connection import connect, init_database, transaction
from semantic_selector.db.schema import rebuild_fts
from semantic_selector.db.writer import insert_artifact, insert_term
from semantic_selector.ingestion.provenance import utc_now_iso
from semantic_selector.services import build_index, validate_index
from semantic_selector.build.progress import BuildProgressReporter


def test_schema_and_fts5(index_path) -> None:
    init_database(index_path)
    conn = connect(index_path)
    now = utc_now_iso()
    with transaction(conn):
        insert_artifact(
            conn,
            artifact_id="test:one",
            repository_id="test",
            name="Test",
            canonical_uri=None,
            source_type="local_file",
            source_reference="demo.ttl",
            access_scope="local",
            declared_version=None,
            version_iri=None,
            content_sha256="abc",
            retrieved_at=now,
            parsed_at=now,
            triple_count=1,
            parse_status="success",
            parse_message=None,
        )
        insert_term(
            conn,
            artifact_id="test:one",
            term_iri="http://example.org/T1",
            preferred_label="myocardial infarction",
            normalized_label="myocardial infarction",
            synonyms_text="heart attack",
            definitions_text="Example definition",
            is_obsolete=False,
            parent_count=0,
            child_count=0,
            mapping_count=0,
        )
    rebuild_fts(conn)
    conn.commit()
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM terms_fts WHERE terms_fts MATCH 'myocardial'"
    ).fetchone()
    assert row["c"] == 1

    conn.execute(
        "UPDATE terms SET preferred_label = 'cardiac event' WHERE term_iri = 'http://example.org/T1'"
    )
    conn.commit()
    old = conn.execute(
        "SELECT COUNT(*) AS c FROM terms_fts WHERE terms_fts MATCH 'myocardial'"
    ).fetchone()
    new = conn.execute(
        "SELECT COUNT(*) AS c FROM terms_fts WHERE terms_fts MATCH 'cardiac'"
    ).fetchone()
    assert old["c"] == 0
    assert new["c"] == 1
    conn.close()


def test_build_index_from_fixtures(config_dir, index_path) -> None:
    report = build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    assert report.artifacts_indexed == 2
    assert report.terms_indexed > 0
    validate_index(index_path)


def test_build_index_emits_progress(config_dir, index_path) -> None:
    messages: list[str] = []
    report = build_index(
        sources_path=config_dir / "sources.example.yaml",
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
        progress=BuildProgressReporter(messages.append),
    )
    assert report.artifacts_indexed == 2
    joined = "\n".join(messages)
    assert "[1/2]" in joined
    assert "Rebuilding full-text search index" in joined
    assert "Build complete:" in joined


def test_malformed_source_logged(config_dir, index_path, tmp_path) -> None:
    import yaml

    sources = yaml.safe_load((config_dir / "sources.example.yaml").read_text(encoding="utf-8"))
    sources["sources"].append(
        {
            "artifact_id": "demo:malformed",
            "name": "Malformed",
            "source_type": "local_file",
            "path": "data/fixtures/malformed.ttl",
            "repository_id": "local-demo",
            "access_scope": "local",
        }
    )
    sources_path = tmp_path / "sources.yaml"
    sources_path.write_text(yaml.dump(sources), encoding="utf-8")
    report = build_index(
        sources_path=sources_path,
        extractors_path=config_dir / "extractors.example.yaml",
        criteria_path=config_dir / "criteria.example.yaml",
        output_path=index_path,
    )
    assert report.artifacts_failed >= 1
    conn = connect(index_path)
    events = conn.execute(
        "SELECT COUNT(*) AS c FROM processing_events WHERE severity = 'error'"
    ).fetchone()
    conn.close()
    assert events["c"] >= 1
