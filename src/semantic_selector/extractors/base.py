from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_selector.rdf.backend import RdfQueryBackend


@dataclass(frozen=True)
class ExtractorDefinition:
    id: str
    query_file: Path
    enabled: bool
    version: str


@dataclass(frozen=True)
class ExtractorResult:
    extractor_id: str
    version: str
    rows: list[dict[str, Any]]


def load_query_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def execute_extractor(
    backend: RdfQueryBackend,
    definition: ExtractorDefinition,
) -> ExtractorResult:
    query_text = load_query_text(definition.query_file)
    rows = [dict(row) for row in backend.query(query_text)]
    return ExtractorResult(extractor_id=definition.id, version=definition.version, rows=rows)
