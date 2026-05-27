# Semantic Selector MVP

Local-first ontology artifact selection using version-controlled SPARQL extractors, SQLite/FTS5 indexing, FastAPI, and MCP.

End-to-end workflow (acquire → configure → build → query): [`docs/workflow.md`](docs/workflow.md).

## Quick start

```bash
uv sync
uv run semantic-selector build-index \
  --sources config/sources.example.yaml \
  --extractors config/extractors.example.yaml \
  --criteria config/criteria.example.yaml \
  --output data/indexes/selector-index.sqlite
uv run semantic-selector serve-api --index data/indexes/selector-index.sqlite
```

`build-index` prints **progress to stderr** and a **JSON report to stdout**. Use `--quiet` for JSON-only output. Details: [`docs/workflow.md` — Build output](docs/workflow.md#build-output).

### OBO Foundry test ontologies (MONDO, DOID, HPO, GO)

Download release OWL files from OBO Foundry PURLs, then build a larger demo index:

```bash
bash scripts/download_obo_foundry_ontologies.sh
uv run semantic-selector build-index \
  --sources config/sources.obo-foundry.example.yaml \
  --extractors config/extractors.example.yaml \
  --criteria config/criteria.example.yaml \
  --output data/indexes/selector-index.sqlite
```

Source URLs (also documented in `config/sources.obo-foundry.example.yaml`):

- http://purl.obolibrary.org/obo/mondo.owl
- http://purl.obolibrary.org/obo/doid.owl
- http://purl.obolibrary.org/obo/hp.owl
- http://purl.obolibrary.org/obo/go.owl

Files are stored under `data/input/` (gitignored). The four-ontology OBO Foundry build is ~450MB of OWL and may take several minutes.

For the larger demo index (seven OBO Foundry ontologies, pyoxigraph, ~1.6GB OWL total):

```bash
uv run semantic-selector build-index \
  --sources config/sources.demo.yaml \
  --extractors config/extractors.example.yaml \
  --criteria config/criteria.example.yaml \
  --output data/indexes/selector-index.sqlite
uv run semantic-selector serve-api --index data/indexes/selector-index.sqlite
```

Expect **~2 minutes** when pyoxigraph stores are already cached under `data/tmp/rdf-store/`; a **cold first build** takes much longer (progress on stderr shows which ontology is running). See [`docs/workflow.md`](docs/workflow.md).

Inspect or validate an existing index (no rebuild required; `build-index` already validates on success):

```bash
uv run semantic-selector inspect-index --index data/indexes/selector-index.sqlite
uv run semantic-selector validate-index --index data/indexes/selector-index.sqlite
```

## Selection criteria

Ontology selection uses OntoChoice-aligned criteria from `config/criteria.example.yaml`. By default, `/v1/select/artifacts` ranks ontologies with **term match frequency** (0.50), **definition coverage** (0.35), and **inbound ontology imports** (0.15, community reuse). Term search also prefers terms reused across more indexed ontologies when match quality ties.

The full criterion table (ID, OntoChoice source, applies-to scope, role, and default weight) is in [`docs/criterion-registry.md`](docs/criterion-registry.md). Live metadata from a built index: `GET /v1/criteria`.

### Querying the demo index

Search across all indexed ontologies by omitting `artifact_ids` (the default):

```bash
curl -s -X POST http://127.0.0.1:8000/v1/search/terms \
  -H 'Content-Type: application/json' \
  -d '{"query":"diabetes mellitus","limit":10}' | jq '.results[] | {artifact_id, label: .preferred_label, iri: .term_iri, score: .text_score}'
```

Filter to one ontology with `artifact_ids`:

```bash
# DOID only
curl -s -X POST http://127.0.0.1:8000/v1/search/terms \
  -H 'Content-Type: application/json' \
  -d '{"query":"diabetes mellitus","artifact_ids":["obo:doid"],"limit":10}' | jq

# MONDO only
curl -s -X POST http://127.0.0.1:8000/v1/search/terms \
  -H 'Content-Type: application/json' \
  -d '{"query":"diabetes mellitus","artifact_ids":["obo:mondo"],"limit":10}' | jq

# HP only
curl -s -X POST http://127.0.0.1:8000/v1/search/terms \
  -H 'Content-Type: application/json' \
  -d '{"query":"seizure","artifact_ids":["obo:hp"],"limit":10}' | jq
```

Rank which ontology best matches a query (OntoChoice-aligned criteria: term match, definition coverage, inbound imports):

```bash
curl -s -X POST http://127.0.0.1:8000/v1/select/artifacts \
  -H 'Content-Type: application/json' \
  -d '{"query":"diabetes mellitus","limit":5}' | jq '.ontology_results[] | {rank, artifact_id, overall_score, ontology_scores, matching_terms: [.matching_terms[0]]}'
```

Multi-concept ontology ranking:

```bash
curl -s -X POST http://127.0.0.1:8000/v1/select/artifacts \
  -H 'Content-Type: application/json' \
  -d '{"queries":["diabetes mellitus","seizure"],"limit":5}' | jq '.ontology_results[] | {artifact_id, ontology_scores}'
```

List criterion registry metadata (OntoChoice alignment):

```bash
curl -s http://127.0.0.1:8000/v1/criteria | jq '.criteria[] | {id: .criterion_id, applies_to, role, table_aligned, source_criterion}'
```

Confirm the API is serving the combined index:

```bash
curl -s http://127.0.0.1:8000/v1/index/manifest | jq '.snapshot_id, .artifacts[].artifact_id'
```

Open `http://127.0.0.1:8000/docs` for OpenAPI documentation.

## MCP (stdio)

```bash
uv run semantic-selector serve-mcp --index data/indexes/selector-index.sqlite --transport stdio
```

## Tests

```bash
uv run pytest
```

## Architecture

- **SPARQL extractors** (`.rq`) retrieve semantic evidence from parsed RDF graphs
- **Python evaluators** compute criterion scores from extracted facts
- **SQLite/FTS5** stores derived index content for fast lookup
- **FastAPI/MCP** expose search, ranking, comparison, and explanations

No ontology parsing or SPARQL execution occurs at query time.

## Documentation

| Doc | Contents |
|-----|----------|
| [`docs/workflow.md`](docs/workflow.md) | Acquire, configure, **build-index** (progress, flags, timing), serve, query |
| [`docs/criterion-registry.md`](docs/criterion-registry.md) | Selection criteria and default weights |
| [`docs/database.md`](docs/database.md) | SQLite schema and FTS |
| [`docs/api-examples.md`](docs/api-examples.md) | curl examples |
