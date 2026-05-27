from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class BackendLoadResult:
    source_path: Path
    backend_name: str
    load_duration_seconds: float
    triple_count: int
    store_path: Path | None
    store_size_bytes: int | None
    reused_existing_store: bool = False


class RdfQueryBackend(Protocol):
    @property
    def backend_name(self) -> str: ...

    @property
    def store_path(self) -> Path | None: ...

    def load_artifact(self, source_path: Path) -> BackendLoadResult: ...

    def query(self, sparql: str) -> Iterable[Mapping[str, object]]: ...

    def count_triples(self) -> int: ...

    def close(self) -> None: ...


def normalize_sparql_value(value: Any) -> object:
    if value is None:
        return None
    if hasattr(value, "toPython"):
        return value.toPython()
    value_type = type(value).__name__
    if value_type == "Literal":
        literal_value = getattr(value, "value", value)
        language = getattr(value, "language", None)
        if language:
            return str(literal_value)
        return literal_value
    if value_type in {"NamedNode", "BlankNode"}:
        return getattr(value, "value", str(value))
    if hasattr(value, "n3"):
        return str(value)
    return str(value)
