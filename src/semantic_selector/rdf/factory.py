from __future__ import annotations

import importlib.metadata
from pathlib import Path

from semantic_selector.rdf.build_config import BuildConfig
from semantic_selector.rdf.pyoxigraph_backend import PyoxigraphBackend
from semantic_selector.rdf.rdflib_backend import RDFLibBackend
from semantic_selector.rdf.serialization import artifact_store_path


def get_pyoxigraph_version() -> str | None:
    try:
        return importlib.metadata.version("pyoxigraph")
    except importlib.metadata.PackageNotFoundError:
        return None


def create_rdf_backend(
    build_config: BuildConfig,
    *,
    artifact_id: str | None = None,
) -> RDFLibBackend | PyoxigraphBackend:
    if build_config.rdf_backend == "rdflib":
        return RDFLibBackend()
    if artifact_id is None:
        raise ValueError("artifact_id is required when using the pyoxigraph backend")
    store_path = artifact_store_path(build_config.temporary_store_dir, artifact_id)
    return PyoxigraphBackend(
        store_path=store_path,
        retain_store=build_config.retain_rdf_store_after_build,
    )
