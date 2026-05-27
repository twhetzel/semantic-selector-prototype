from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_json(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    return sha256_text(payload)


@dataclass(frozen=True)
class SourceArtifact:
    artifact_id: str
    name: str
    source_type: str
    path: str | None = None
    repository_id: str = "local"
    declared_version: str | None = None
    access_scope: str = "local"


@dataclass(frozen=True)
class ExtractedArtifactFacts:
    artifact_id: str
    terms: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    metadata: dict[str, list[Any]]
    extractor_versions: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CriterionResult:
    criterion_id: str
    numeric_value: float | None
    text_value: str | None
    evidence: dict[str, Any]


class ArtifactEvaluator(Protocol):
    criterion_id: str
    display_name: str
    description: str
    evaluator_version: str

    def evaluate(self, facts: ExtractedArtifactFacts) -> CriterionResult: ...
