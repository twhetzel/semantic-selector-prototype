# Extractor Library

SPARQL extractors live under `src/semantic_selector/extractors/sparql/`.

| ID | File | Purpose |
|---|---|---|
| `artifact_metadata` | `artifact_metadata.rq` | Ontology title/description/license candidates |
| `version_metadata` | `version_metadata.rq` | Version IRI/info signals |
| `terms_and_labels` | `terms_and_labels.rq` | Typed terms and label literals |
| `definitions` | `definitions.rq` | Definition annotations |
| `synonyms` | `synonyms.rq` | Synonym/alternative labels |
| `hierarchy_relations` | `hierarchy_relations.rq` | Direct hierarchy edges |
| `mappings` | `mappings.rq` | Explicit mapping/equivalence edges |
| `obsolete_terms` | `obsolete_terms.rq` | Deprecation evidence |

Extractors are registered in `config/extractors.example.yaml`. Enabled query file contents are hashed into `index_manifest.extractor_queries_hash`.

## Term candidates

Resources typed as `owl:Class`, `rdfs:Class`, or `skos:Concept` are treated as term candidates. No OWL reasoning is applied.

## Post-processing in Python

- English-first literal preference
- Label normalization for lookup/grouping
- Joining definitions, synonyms, hierarchy counts, and obsolescence flags
