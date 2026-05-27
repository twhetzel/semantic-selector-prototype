# API Examples

Base URL: `http://127.0.0.1:8000`

## Search terms

```bash
curl -s -X POST http://127.0.0.1:8000/v1/search/terms \
  -H 'Content-Type: application/json' \
  -d '{"query":"myocardial infarction","limit":10}' | jq
```

## Select artifacts

```bash
curl -s -X POST http://127.0.0.1:8000/v1/select/artifacts \
  -H 'Content-Type: application/json' \
  -d '{
    "query":"myocardial infarction",
    "weights":{"term_match":0.4,"definition_coverage":0.2},
    "limit":5
  }' | jq
```

## Compare artifacts

```bash
curl -s -X POST http://127.0.0.1:8000/v1/compare/artifacts \
  -H 'Content-Type: application/json' \
  -d '{
    "artifact_ids":["demo:ontology:one","demo:ontology:two"],
    "query":"myocardial infarction"
  }' | jq
```

## Manifest

```bash
curl -s http://127.0.0.1:8000/v1/index/manifest | jq
```

Open `/docs` for interactive OpenAPI documentation.
