# Architecture

## Layers

1. **Ingestion** — local RDF files parsed with RDFLib; provenance and checksums recorded.
2. **SPARQL extractors** — version-controlled `.rq` files retrieve explicit semantic facts.
3. **Normalization** — Python joins extractor rows into term/relation records.
4. **Evaluators** — Python computes ontology-level criterion scores from extracted facts; term evidence is assembled at query time.
5. **SQLite/FTS5 index** — derived content only; no source ontology redistribution.
6. **Service layer** — search, rank, compare, explain (shared by REST and MCP).
7. **Interfaces** — FastAPI REST API and read-only MCP server.

## Runtime principle

Query-time behavior reads the precomputed index only. No RDF parsing or SPARQL execution during search or selection requests.

## Traceability

Each index snapshot records:

- `snapshot_id`
- extractor configuration and query content hashes
- evaluator configuration hash
- source configuration hash
- per-artifact content SHA-256

## Future extensions

- BioPortal source adapter (stub present)
- Multiple index federation via `IndexCollection`
- Optional UI over REST
