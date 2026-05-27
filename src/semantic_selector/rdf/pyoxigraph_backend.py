from __future__ import annotations

import shutil
import time
from collections.abc import Iterable, Mapping
from pathlib import Path

from pyoxigraph import Store

from semantic_selector.models import sha256_file
from semantic_selector.rdf.backend import BackendLoadResult, normalize_sparql_value
from semantic_selector.rdf.serialization import (
    directory_size_bytes,
    rdf_format_for_path,
    source_checksum_path,
)


class PyoxigraphBackend:
    backend_name = "pyoxigraph"

    def __init__(
        self,
        *,
        store_path: Path,
        retain_store: bool = False,
    ) -> None:
        self._store_path = store_path
        self._retain_store = retain_store
        self._store: Store | None = None

    @property
    def store_path(self) -> Path | None:
        return self._store_path

    def load_artifact(self, source_path: Path) -> BackendLoadResult:
        checksum = sha256_file(source_path)
        checksum_file = source_checksum_path(self._store_path)
        if (
            self._retain_store
            and self._store_path.exists()
            and checksum_file.exists()
            and checksum_file.read_text(encoding="utf-8").strip() == checksum
        ):
            self._store = Store(str(self._store_path))
            return BackendLoadResult(
                source_path=source_path,
                backend_name=self.backend_name,
                load_duration_seconds=0.0,
                triple_count=self.count_triples(),
                store_path=self._store_path,
                store_size_bytes=directory_size_bytes(self._store_path),
                reused_existing_store=True,
            )

        if self._store_path.exists():
            shutil.rmtree(self._store_path)
        self._store_path.mkdir(parents=True, exist_ok=True)

        started = time.perf_counter()
        store = Store(str(self._store_path))
        store.bulk_load(path=str(source_path), format=rdf_format_for_path(source_path))
        store.flush()
        self._store = store
        checksum_file.write_text(checksum, encoding="utf-8")
        duration = time.perf_counter() - started

        return BackendLoadResult(
            source_path=source_path,
            backend_name=self.backend_name,
            load_duration_seconds=duration,
            triple_count=self.count_triples(),
            store_path=self._store_path,
            store_size_bytes=directory_size_bytes(self._store_path),
        )

    def query(self, sparql: str) -> Iterable[Mapping[str, object]]:
        if self._store is None:
            raise RuntimeError("Pyoxigraph store is not loaded")
        results = self._store.query(sparql)
        variables = [variable.value for variable in results.variables]
        for row in results:
            yield {name: normalize_sparql_value(row[name]) for name in variables}

    def count_triples(self) -> int:
        if self._store is None:
            return 0
        return len(self._store)

    def close(self) -> None:
        self._store = None

    def cleanup_store(self) -> None:
        self.close()
        if self._store_path.exists():
            shutil.rmtree(self._store_path)
