from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from semantic_selector.settings import resolve_path

SUPPORTED_RDF_BACKENDS = frozenset({"rdflib", "pyoxigraph"})


@dataclass(frozen=True)
class BuildConfig:
    rdf_backend: str
    temporary_store_dir: Path
    retain_rdf_store_after_build: bool
    instrumentation_enabled: bool

    @classmethod
    def from_sources_config(cls, raw: dict[str, Any]) -> BuildConfig:
        build = raw.get("build") or {}
        backend = str(build.get("rdf_backend", "rdflib")).strip().lower()
        if backend not in SUPPORTED_RDF_BACKENDS:
            supported = ", ".join(sorted(SUPPORTED_RDF_BACKENDS))
            raise ValueError(
                f"Unsupported build.rdf_backend {backend!r}; expected one of: {supported}"
            )
        return cls(
            rdf_backend=backend,
            temporary_store_dir=resolve_path(
                build.get("temporary_store_dir", "data/tmp/rdf-store")
            ),
            retain_rdf_store_after_build=bool(build.get("retain_rdf_store_after_build", False)),
            instrumentation_enabled=bool(build.get("instrumentation_enabled", True)),
        )
