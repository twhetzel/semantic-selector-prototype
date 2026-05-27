PRAGMA foreign_keys = ON;

CREATE TABLE index_manifest (
    snapshot_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    selector_version TEXT NOT NULL,
    evaluator_config_hash TEXT NOT NULL,
    extractor_config_hash TEXT NOT NULL,
    extractor_queries_hash TEXT NOT NULL,
    source_config_hash TEXT NOT NULL,
    notes TEXT
);

CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    repository_id TEXT NOT NULL,
    name TEXT NOT NULL,
    canonical_uri TEXT,
    source_type TEXT NOT NULL,
    source_reference TEXT NOT NULL,
    access_scope TEXT NOT NULL DEFAULT 'local',
    declared_version TEXT,
    version_iri TEXT,
    content_sha256 TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    parsed_at TEXT NOT NULL,
    triple_count INTEGER NOT NULL DEFAULT 0,
    parse_status TEXT NOT NULL,
    parse_message TEXT
);

CREATE TABLE terms (
    term_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    term_iri TEXT NOT NULL,
    preferred_label TEXT,
    normalized_label TEXT,
    synonyms_text TEXT NOT NULL DEFAULT '',
    definitions_text TEXT NOT NULL DEFAULT '',
    is_obsolete INTEGER NOT NULL DEFAULT 0,
    parent_count INTEGER NOT NULL DEFAULT 0,
    child_count INTEGER NOT NULL DEFAULT 0,
    mapping_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (artifact_id, term_iri)
);

CREATE TABLE criterion_definitions (
    criterion_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    description TEXT NOT NULL,
    value_type TEXT NOT NULL,
    evaluator_id TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    default_weight REAL NOT NULL DEFAULT 0.0
);

CREATE TABLE artifact_criterion_values (
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    criterion_id TEXT NOT NULL REFERENCES criterion_definitions(criterion_id),
    numeric_value REAL,
    text_value TEXT,
    evidence_json TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    PRIMARY KEY (artifact_id, criterion_id)
);

CREATE TABLE term_relations (
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    subject_iri TEXT NOT NULL,
    predicate_iri TEXT NOT NULL,
    object_iri TEXT NOT NULL,
    relation_type TEXT NOT NULL,
    PRIMARY KEY (artifact_id, subject_iri, predicate_iri, object_iri)
);

CREATE TABLE artifact_relationships (
    source_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    target_artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    confidence REAL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (source_artifact_id, target_artifact_id, relationship_type)
);

CREATE TABLE processing_events (
    event_pk INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id TEXT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE terms_fts USING fts5(
    preferred_label,
    synonyms_text,
    definitions_text,
    content='terms',
    content_rowid='term_pk',
    tokenize='unicode61 remove_diacritics 2',
    prefix='2 3 4'
);

CREATE TRIGGER terms_ai AFTER INSERT ON terms BEGIN
    INSERT INTO terms_fts(rowid, preferred_label, synonyms_text, definitions_text)
    VALUES (new.term_pk, new.preferred_label, new.synonyms_text, new.definitions_text);
END;

CREATE TRIGGER terms_ad AFTER DELETE ON terms BEGIN
    INSERT INTO terms_fts(terms_fts, rowid, preferred_label, synonyms_text, definitions_text)
    VALUES ('delete', old.term_pk, old.preferred_label, old.synonyms_text, old.definitions_text);
END;

CREATE TRIGGER terms_au AFTER UPDATE ON terms BEGIN
    INSERT INTO terms_fts(terms_fts, rowid, preferred_label, synonyms_text, definitions_text)
    VALUES ('delete', old.term_pk, old.preferred_label, old.synonyms_text, old.definitions_text);
    INSERT INTO terms_fts(rowid, preferred_label, synonyms_text, definitions_text)
    VALUES (new.term_pk, new.preferred_label, new.synonyms_text, new.definitions_text);
END;

CREATE INDEX idx_terms_artifact ON terms(artifact_id);
CREATE INDEX idx_terms_normalized_label ON terms(normalized_label);
CREATE INDEX idx_criterion_artifact ON artifact_criterion_values(artifact_id);
CREATE INDEX idx_relations_subject ON term_relations(artifact_id, subject_iri);
