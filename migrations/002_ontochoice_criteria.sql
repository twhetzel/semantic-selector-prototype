-- OntoChoice criteria alignment: extended criterion metadata, term languages, imports, reuse

ALTER TABLE criterion_definitions ADD COLUMN category TEXT;
ALTER TABLE criterion_definitions ADD COLUMN source_criterion TEXT;
ALTER TABLE criterion_definitions ADD COLUMN applies_to_json TEXT NOT NULL DEFAULT '[]';
ALTER TABLE criterion_definitions ADD COLUMN role TEXT;
ALTER TABLE criterion_definitions ADD COLUMN table_aligned INTEGER NOT NULL DEFAULT 0;
ALTER TABLE criterion_definitions ADD COLUMN evaluation_stage TEXT NOT NULL DEFAULT 'index_build';
ALTER TABLE criterion_definitions ADD COLUMN config_json TEXT NOT NULL DEFAULT '{}';

ALTER TABLE terms ADD COLUMN language_tags_text TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS artifact_owl_imports (
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id) ON DELETE CASCADE,
    imported_ontology_iri TEXT NOT NULL,
    PRIMARY KEY (artifact_id, imported_ontology_iri)
);

CREATE TABLE IF NOT EXISTS term_iri_reuse (
    term_iri TEXT PRIMARY KEY,
    reuse_count INTEGER NOT NULL,
    artifact_ids_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_artifact_owl_imports_target
    ON artifact_owl_imports(imported_ontology_iri);
