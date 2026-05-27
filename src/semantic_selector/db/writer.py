from __future__ import annotations

import json
import sqlite3
from typing import Any

from semantic_selector.models import utc_now_iso


def log_processing_event(
    conn: sqlite3.Connection,
    *,
    artifact_id: str | None,
    event_type: str,
    severity: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO processing_events
            (artifact_id, event_type, severity, message, details_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            event_type,
            severity,
            message,
            json.dumps(details or {}),
            utc_now_iso(),
        ),
    )


def insert_manifest(
    conn: sqlite3.Connection,
    *,
    snapshot_id: str,
    selector_version: str,
    evaluator_config_hash: str,
    extractor_config_hash: str,
    extractor_queries_hash: str,
    source_config_hash: str,
    notes: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO index_manifest (
            snapshot_id, created_at, selector_version,
            evaluator_config_hash, extractor_config_hash,
            extractor_queries_hash, source_config_hash, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            snapshot_id,
            utc_now_iso(),
            selector_version,
            evaluator_config_hash,
            extractor_config_hash,
            extractor_queries_hash,
            source_config_hash,
            notes,
        ),
    )


def insert_artifact(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    repository_id: str,
    name: str,
    canonical_uri: str | None,
    source_type: str,
    source_reference: str,
    access_scope: str,
    declared_version: str | None,
    version_iri: str | None,
    content_sha256: str,
    retrieved_at: str,
    parsed_at: str,
    triple_count: int,
    parse_status: str,
    parse_message: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO artifacts (
            artifact_id, repository_id, name, canonical_uri, source_type,
            source_reference, access_scope, declared_version, version_iri,
            content_sha256, retrieved_at, parsed_at, triple_count,
            parse_status, parse_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            repository_id,
            name,
            canonical_uri,
            source_type,
            source_reference,
            access_scope,
            declared_version,
            version_iri,
            content_sha256,
            retrieved_at,
            parsed_at,
            triple_count,
            parse_status,
            parse_message,
        ),
    )


def insert_term(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    term_iri: str,
    preferred_label: str | None,
    normalized_label: str | None,
    synonyms_text: str,
    definitions_text: str,
    language_tags_text: str = "",
    is_obsolete: bool,
    parent_count: int,
    child_count: int,
    mapping_count: int,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO terms (
            artifact_id, term_iri, preferred_label, normalized_label,
            synonyms_text, definitions_text, language_tags_text, is_obsolete,
            parent_count, child_count, mapping_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            term_iri,
            preferred_label,
            normalized_label,
            synonyms_text,
            definitions_text,
            language_tags_text,
            1 if is_obsolete else 0,
            parent_count,
            child_count,
            mapping_count,
        ),
    )
    return int(cur.lastrowid)


def insert_artifact_owl_import(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    imported_ontology_iri: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO artifact_owl_imports (artifact_id, imported_ontology_iri)
        VALUES (?, ?)
        """,
        (artifact_id, imported_ontology_iri),
    )


def insert_term_relation(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    subject_iri: str,
    predicate_iri: str,
    object_iri: str,
    relation_type: str,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO term_relations
            (artifact_id, subject_iri, predicate_iri, object_iri, relation_type)
        VALUES (?, ?, ?, ?, ?)
        """,
        (artifact_id, subject_iri, predicate_iri, object_iri, relation_type),
    )


def upsert_criterion_definition(
    conn: sqlite3.Connection,
    *,
    criterion_id: str,
    display_name: str,
    description: str,
    value_type: str,
    evaluator_id: str | None,
    evaluator_version: str,
    enabled: bool,
    default_weight: float,
    category: str | None = None,
    source_criterion: str | None = None,
    applies_to: list[str] | None = None,
    role: str | None = None,
    table_aligned: bool = False,
    evaluation_stage: str = "index_build",
    config: dict[str, Any] | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO criterion_definitions (
            criterion_id, display_name, description, value_type,
            evaluator_id, evaluator_version, enabled, default_weight,
            category, source_criterion, applies_to_json, role,
            table_aligned, evaluation_stage, config_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(criterion_id) DO UPDATE SET
            display_name=excluded.display_name,
            description=excluded.description,
            value_type=excluded.value_type,
            evaluator_id=excluded.evaluator_id,
            evaluator_version=excluded.evaluator_version,
            enabled=excluded.enabled,
            default_weight=excluded.default_weight,
            category=excluded.category,
            source_criterion=excluded.source_criterion,
            applies_to_json=excluded.applies_to_json,
            role=excluded.role,
            table_aligned=excluded.table_aligned,
            evaluation_stage=excluded.evaluation_stage,
            config_json=excluded.config_json
        """,
        (
            criterion_id,
            display_name,
            description,
            value_type,
            evaluator_id or "",
            evaluator_version,
            1 if enabled else 0,
            default_weight,
            category,
            source_criterion,
            json.dumps(applies_to or []),
            role,
            1 if table_aligned else 0,
            evaluation_stage,
            json.dumps(config or {}),
        ),
    )


def insert_criterion_value(
    conn: sqlite3.Connection,
    *,
    artifact_id: str,
    criterion_id: str,
    numeric_value: float | None,
    text_value: str | None,
    evidence: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO artifact_criterion_values (
            artifact_id, criterion_id, numeric_value, text_value,
            evidence_json, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            artifact_id,
            criterion_id,
            numeric_value,
            text_value,
            json.dumps(evidence),
            utc_now_iso(),
        ),
    )
