from __future__ import annotations

from semantic_selector.evaluators.registry import create_evaluator
from semantic_selector.extractors.base import execute_extractor
from semantic_selector.extractors.normalization import join_extractor_results
from semantic_selector.extractors.registry import ExtractorRegistry
from semantic_selector.rdf.rdflib_backend import RDFLibBackend
from semantic_selector.settings import PROJECT_ROOT


def _facts_for(path: str):
    backend = RDFLibBackend()
    backend.load_artifact(PROJECT_ROOT / path)
    registry = ExtractorRegistry.from_yaml(PROJECT_ROOT / "config/extractors.example.yaml")
    results = {d.id: execute_extractor(backend, d) for d in registry.enabled}
    backend.close()
    return join_extractor_results("demo:ontology:one", results)


def test_has_version_metadata() -> None:
    facts = _facts_for("data/fixtures/demo-one.ttl")
    result = create_evaluator("metadata.has_version_metadata").evaluate(facts)
    assert result.numeric_value == 1.0


def test_definition_coverage() -> None:
    facts = _facts_for("data/fixtures/demo-one.ttl")
    result = create_evaluator("term_annotations.definition_coverage").evaluate(facts)
    assert 0.0 <= (result.numeric_value or 0) <= 1.0
    assert "numerator" in result.evidence


def test_multilanguage_annotations() -> None:
    facts = _facts_for("data/fixtures/demo-two.ttl")
    result = create_evaluator("i18n.multilanguage_annotations").evaluate(facts)
    assert "en" in result.evidence.get("languages", [])
