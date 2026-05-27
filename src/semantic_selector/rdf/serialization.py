from __future__ import annotations

from pathlib import Path

from pyoxigraph import RdfFormat

from semantic_selector.ingestion.parser import infer_format

RDFLIB_TO_PYOXIGRAPH = {
    "turtle": RdfFormat.TURTLE,
    "xml": RdfFormat.RDF_XML,
    "json-ld": RdfFormat.JSON_LD,
    "nt": RdfFormat.N_TRIPLES,
    "n3": RdfFormat.N3,
}


def rdf_format_for_path(path: Path) -> RdfFormat:
    fmt = infer_format(path)
    if fmt is None:
        raise ValueError(f"Unable to infer RDF format for {path}")
    mapped = RDFLIB_TO_PYOXIGRAPH.get(fmt)
    if mapped is None:
        raise ValueError(f"Unsupported RDF format {fmt!r} for Pyoxigraph loading of {path}")
    return mapped


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def artifact_store_path(base_dir: Path, artifact_id: str) -> Path:
    safe = artifact_id.replace(":", "_").replace("/", "_")
    return base_dir / safe


def source_checksum_path(store_path: Path) -> Path:
    return store_path / ".source_checksum"
