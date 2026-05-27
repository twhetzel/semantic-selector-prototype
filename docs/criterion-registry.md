# OntoChoice-aligned criterion registry (see config/criteria.example.yaml)

Demonstrator and table-aligned criteria:

| ID | OntoChoice source | Applies to | Role | Weight (default) |
|---|---|---|---|---:|
| `term_match_frequency` | Ont: Term Match Frequency | ontology | ranking (query-time) | 0.50 |
| `definition_coverage` | Ont: Term Details | ontology | ranking_and_evidence | 0.35 |
| `inbound_owl_import_count` | Includes | ontology | ranking_and_evidence | 0.15 |
| `enforced_selection_list` | Enforced Selection List | ontology, term | filter (query-time) | 0.0 |
| `multilanguage_annotations` | Multi-language annotations | ontology, term | descriptive_evidence | 0.0 |
| `term_definitions_and_annotations` | Term: Definitions and Other Annotations | term | evidence (query-time) | 0.0 |
| `term_reuse_by_identifier` | Term Reuse | term | evidence (query-time ranking tie-break) | 0.0 |
| `synonym_coverage` | Supporting evidence for Ont: Term Details | ontology | supporting_evidence | 0.0 |
| `has_version_metadata` | (provenance only) | ontology | provenance_evidence | 0.0 |

**Default ontology ranking** combines query match (50%), definition coverage (35%), and community reuse via inbound `owl:imports` (15%). Import counts are min–max normalized across candidate ontologies before scoring.

**Term search ranking** prefers exact preferred-label matches, then exact synonym matches, then weaker lexical matches. Within each match tier, results are ordered by the same OntoChoice ontology ranking score used for `/v1/select/artifacts` (default weights: definition coverage 35%, inbound `owl:imports` 15%, with query match treated as satisfied for all candidates). FTS5 BM25 is used only to gather partial-match candidates and as a final tie-breaker.

Criteria metadata (`applies_to`, `role`, `table_aligned`, `category`, `source_criterion`) is stored in `criterion_definitions` and exposed via `GET /v1/criteria`.
