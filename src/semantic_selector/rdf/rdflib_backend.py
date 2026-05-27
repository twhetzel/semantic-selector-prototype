from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from rdflib import Graph
from rdflib.query import ResultRow

from semantic_selector.ingestion.parser import infer_format, parse_rdf_file
from semantic_selector.rdf.backend import BackendLoadResult, normalize_sparql_value


class RDFLibBackend:
    backend_name = "rdflib"

    def __init__(self, graph: Graph | None = None) -> None:
        self._graph = graph or Graph()
        self._store_path: Path | None = None

    @property
    def store_path(self) -> Path | None:
        return self._store_path

    def load_artifact(self, source_path: Path) -> BackendLoadResult:
        started = time.perf_counter()
        fmt = infer_format(source_path)
        if fmt:
            self._graph.parse(source_path, format=fmt)
        else:
            self._graph.parse(source_path)
        duration = time.perf_counter() - started
        return BackendLoadResult(
            source_path=source_path,
            backend_name=self.backend_name,
            load_duration_seconds=duration,
            triple_count=len(self._graph),
            store_path=None,
            store_size_bytes=None,
        )

    def query(self, sparql: str) -> Iterable[Mapping[str, object]]:
        result = self._graph.query(sparql)
        for row in result:
            if isinstance(row, ResultRow):
                yield {str(k): normalize_sparql_value(v) for k, v in row.asdict().items()}
            else:
                yield {"value": normalize_sparql_value(row)}

    def count_triples(self) -> int:
        return len(self._graph)

    def close(self) -> None:
        self._graph.close()
