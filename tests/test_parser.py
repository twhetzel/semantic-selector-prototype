from __future__ import annotations

import pytest
from rdflib.exceptions import ParserError

from semantic_selector.ingestion.parser import parse_rdf_file


def test_parse_demo_fixture(fixtures_dir) -> None:
    graph, fmt = parse_rdf_file(fixtures_dir / "demo-one.ttl")
    assert len(graph) > 0
    assert fmt == "turtle"


def test_malformed_fixture_raises(fixtures_dir) -> None:
    with pytest.raises((ParserError, Exception)):
        parse_rdf_file(fixtures_dir / "malformed.ttl")
