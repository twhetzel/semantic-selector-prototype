from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

BuildProgressCallback = Callable[[str], None]


class BuildProgressReporter:
    def __init__(self, callback: BuildProgressCallback | None = None) -> None:
        self._callback = callback

    def emit(self, message: str) -> None:
        if self._callback is not None:
            self._callback(message)

    def build_started(self, *, artifact_count: int, rdf_backend: str, output_path: Path) -> None:
        self.emit(
            f"Building index ({artifact_count} artifacts, backend={rdf_backend}) "
            f"→ {output_path}"
        )

    def artifact_started(self, *, index: int, total: int, artifact_id: str) -> None:
        self.emit(f"[{index}/{total}] {artifact_id}")

    def artifact_phase(self, *, artifact_id: str, message: str) -> None:
        self.emit(f"  {artifact_id}: {message}")

    def artifact_finished(
        self,
        *,
        artifact_id: str,
        duration_seconds: float,
        term_count: int | None = None,
        status: str = "success",
    ) -> None:
        if status != "success":
            self.emit(f"  {artifact_id}: failed ({duration_seconds:.1f}s)")
            return
        terms = f", {term_count:,} terms" if term_count is not None else ""
        self.emit(f"  {artifact_id}: done in {duration_seconds:.1f}s{terms}")

    def post_build_step(self, message: str) -> None:
        self.emit(message)

    def build_finished(
        self,
        *,
        artifacts_indexed: int,
        artifacts_failed: int,
        terms_indexed: int,
        duration_seconds: float,
        output_path: Path,
    ) -> None:
        failed = f", {artifacts_failed} failed" if artifacts_failed else ""
        self.emit(
            f"Build complete: {artifacts_indexed} indexed{failed}, "
            f"{terms_indexed:,} terms, {duration_seconds:.1f}s → {output_path}"
        )
