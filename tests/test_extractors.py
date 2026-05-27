from __future__ import annotations

from semantic_selector.extractors.base import execute_extractor
from semantic_selector.extractors.normalization import join_extractor_results, normalize_label
from semantic_selector.extractors.registry import ExtractorRegistry
from semantic_selector.rdf.rdflib_backend import RDFLibBackend
from semantic_selector.settings import PROJECT_ROOT


def test_terms_and_labels_extractor(fixtures_dir) -> None:
    backend = RDFLibBackend()
    backend.load_artifact(fixtures_dir / "demo-one.ttl")
    registry = ExtractorRegistry.from_yaml(PROJECT_ROOT / "config/extractors.example.yaml")
    definition = registry.get("terms_and_labels")
    assert definition is not None
    result = execute_extractor(backend, definition)
    labels = {row["term"]: row.get("label") for row in result.rows if row.get("label")}
    assert any("myocardial infarction" in str(v).lower() for v in labels.values())
    backend.close()


def test_shared_labels_remain_separate(fixtures_dir) -> None:
    registry = ExtractorRegistry.from_yaml(PROJECT_ROOT / "config/extractors.example.yaml")
    results = {}
    for artifact_path, artifact_id in [
        (fixtures_dir / "demo-one.ttl", "demo:ontology:one"),
        (fixtures_dir / "demo-two.ttl", "demo:ontology:two"),
    ]:
        backend = RDFLibBackend()
        backend.load_artifact(artifact_path)
        extracted = {
            d.id: execute_extractor(backend, d) for d in registry.enabled if d.id != "artifact_metadata"
        }
        extracted["artifact_metadata"] = execute_extractor(
            backend, registry.get("artifact_metadata")
        )
        facts = join_extractor_results(artifact_id, extracted)
        mi_terms = [
            t for t in facts.terms if t.get("normalized_label") == normalize_label("myocardial infarction")
        ]
        assert mi_terms
        results[artifact_id] = mi_terms
        backend.close()

    assert results["demo:ontology:one"][0]["term_iri"] != results["demo:ontology:two"][0]["term_iri"]


def test_extractor_queries_hash_changes_with_content(config_dir, tmp_path) -> None:
    registry = ExtractorRegistry.from_yaml(config_dir / "extractors.example.yaml")
    h1 = registry.queries_hash()
    rq = PROJECT_ROOT / "src/semantic_selector/extractors/sparql/terms_and_labels.rq"
    original = rq.read_text(encoding="utf-8")
    try:
        rq.write_text(original + "\n# test mutation\n", encoding="utf-8")
        registry2 = ExtractorRegistry.from_yaml(config_dir / "extractors.example.yaml")
        assert registry2.queries_hash() != h1
    finally:
        rq.write_text(original, encoding="utf-8")
