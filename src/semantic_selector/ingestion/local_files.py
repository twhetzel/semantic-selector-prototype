from __future__ import annotations

from pathlib import Path

import yaml

from semantic_selector.ingestion.sources import SourceAdapter
from semantic_selector.models import SourceArtifact
from semantic_selector.settings import resolve_path


class LocalFileSourceAdapter:
    def __init__(self, sources_config: dict) -> None:
        self._sources = sources_config.get("sources", [])

    @classmethod
    def from_yaml(cls, path: Path) -> LocalFileSourceAdapter:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(data)

    def list_artifacts(self) -> list[SourceArtifact]:
        artifacts: list[SourceArtifact] = []
        for item in self._sources:
            if item.get("source_type") != "local_file":
                continue
            artifacts.append(
                SourceArtifact(
                    artifact_id=item["artifact_id"],
                    name=item["name"],
                    source_type=item["source_type"],
                    path=item["path"],
                    repository_id=item.get("repository_id", "local"),
                    declared_version=item.get("declared_version"),
                    access_scope=item.get("access_scope", "local"),
                )
            )
        return artifacts

    def materialize_artifact(self, artifact: SourceArtifact, target_dir: Path) -> Path:
        if not artifact.path:
            raise ValueError(f"No path configured for artifact {artifact.artifact_id}")
        source_path = resolve_path(artifact.path)
        if not source_path.exists():
            raise FileNotFoundError(f"Ontology file not found: {source_path}")
        return source_path


class BioPortalSourceAdapter:
    """Stub for future BioPortal integration."""

    def list_artifacts(self) -> list[SourceArtifact]:
        raise NotImplementedError("BioPortalSourceAdapter is not implemented in the MVP")

    def materialize_artifact(self, artifact: SourceArtifact, target_dir: Path) -> Path:
        raise NotImplementedError("BioPortalSourceAdapter is not implemented in the MVP")
