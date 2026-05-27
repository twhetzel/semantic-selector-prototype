from __future__ import annotations

from pathlib import Path

from rdflib import Graph
from rdflib.util import guess_format

FORMAT_BY_EXTENSION = {
    ".ttl": "turtle",
    ".rdf": "xml",
    ".owl": "xml",
    ".jsonld": "json-ld",
    ".nt": "nt",
    ".n3": "n3",
}


def infer_format(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in FORMAT_BY_EXTENSION:
        return FORMAT_BY_EXTENSION[ext]
    return guess_format(str(path))


def parse_rdf_file(path: Path) -> tuple[Graph, str]:
    graph = Graph()
    fmt = infer_format(path)
    if fmt:
        graph.parse(path, format=fmt)
    else:
        graph.parse(path)
    return graph, fmt or "unknown"
