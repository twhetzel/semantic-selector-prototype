from __future__ import annotations

from pathlib import Path

import pytest

from semantic_selector.services import IndexService
from semantic_selector.settings import PROJECT_ROOT

MONDO_INDEX = PROJECT_ROOT / "data/indexes/mondo-index.sqlite"


@pytest.mark.skipif(not MONDO_INDEX.exists(), reason="MONDO index not built locally")
def test_mondo_diabetes_prefers_diabetes_mellitus() -> None:
    service = IndexService(MONDO_INDEX)
    result = service.search_terms(query="diabetes", limit=10)
    assert result["results"]
    top = result["results"][0]
    assert top["term_iri"].endswith("MONDO_0005015")
    assert top["preferred_label"] == "diabetes mellitus"
    assert top["match_type"] == "synonym_exact"


@pytest.mark.skipif(not MONDO_INDEX.exists(), reason="MONDO index not built locally")
def test_mondo_diabetes_mellitus_query_is_exact_label() -> None:
    service = IndexService(MONDO_INDEX)
    result = service.search_terms(query="diabetes mellitus", limit=5)
    assert result["results"][0]["term_iri"].endswith("MONDO_0005015")
    assert result["results"][0]["match_type"] == "preferred_label_exact"


@pytest.mark.skipif(not MONDO_INDEX.exists(), reason="MONDO index not built locally")
def test_mondo_curie_lookup() -> None:
    service = IndexService(MONDO_INDEX)
    result = service.search_terms(query="MONDO:0005015", limit=5)
    assert result["results"][0]["term_iri"].endswith("MONDO_0005015")
    assert result["results"][0]["match_type"] == "curie_exact"
