from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExtractorBuildMetric:
    extractor_id: str
    query_file: str
    query_hash: str
    duration_seconds: float
    row_count: int
    status: str
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "extractor_id": self.extractor_id,
            "query_file": self.query_file,
            "query_hash": self.query_hash,
            "duration_seconds": round(self.duration_seconds, 4),
            "row_count": self.row_count,
            "status": self.status,
        }
        if self.message:
            payload["message"] = self.message
        return payload


@dataclass
class ArtifactBuildReport:
    artifact_id: str
    source_filename: str
    source_file_size_bytes: int
    rdf_backend: str
    store_path: str | None
    retain_rdf_store_after_build: bool
    load_duration_seconds: float
    triple_count: int
    store_size_bytes: int | None
    extractors: list[ExtractorBuildMetric] = field(default_factory=list)
    extraction_duration_seconds: float = 0.0
    evaluation_duration_seconds: float = 0.0
    sqlite_write_duration_seconds: float = 0.0
    total_build_duration_seconds: float = 0.0
    status: str = "success"
    message: str | None = None
    reused_existing_store: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "artifact_id": self.artifact_id,
            "source_filename": self.source_filename,
            "source_file_size_bytes": self.source_file_size_bytes,
            "rdf_backend": self.rdf_backend,
            "store_path": self.store_path,
            "retain_rdf_store_after_build": self.retain_rdf_store_after_build,
            "load_duration_seconds": round(self.load_duration_seconds, 4),
            "triple_count": self.triple_count,
            "store_size_bytes": self.store_size_bytes,
            "reused_existing_store": self.reused_existing_store,
            "extractors": [item.to_dict() for item in self.extractors],
            "extraction_duration_seconds": round(self.extraction_duration_seconds, 4),
            "evaluation_duration_seconds": round(self.evaluation_duration_seconds, 4),
            "sqlite_write_duration_seconds": round(self.sqlite_write_duration_seconds, 4),
            "total_build_duration_seconds": round(self.total_build_duration_seconds, 4),
            "status": self.status,
        }
        if self.message:
            payload["message"] = self.message
        return payload
