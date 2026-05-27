from __future__ import annotations

from pathlib import Path
from typing import Protocol

from semantic_selector.models import SourceArtifact


class SourceAdapter(Protocol):
    def list_artifacts(self) -> list[SourceArtifact]: ...

    def materialize_artifact(self, artifact: SourceArtifact, target_dir: Path) -> Path: ...
