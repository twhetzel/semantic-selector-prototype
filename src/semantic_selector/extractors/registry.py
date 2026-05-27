from __future__ import annotations

from pathlib import Path

import yaml

from semantic_selector.extractors.base import ExtractorDefinition
from semantic_selector.models import sha256_text
from semantic_selector.settings import resolve_path


class ExtractorRegistry:
    def __init__(self, definitions: list[ExtractorDefinition]) -> None:
        self._definitions = {d.id: d for d in definitions}

    @classmethod
    def from_yaml(cls, path: Path) -> ExtractorRegistry:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        definitions: list[ExtractorDefinition] = []
        for item in data.get("extractors", []):
            if not item.get("enabled", True):
                continue
            query_file = resolve_path(item["query_file"])
            definitions.append(
                ExtractorDefinition(
                    id=item["id"],
                    query_file=query_file,
                    enabled=True,
                    version=item.get("version", "0.1.0"),
                )
            )
        return cls(definitions)

    @property
    def enabled(self) -> list[ExtractorDefinition]:
        return list(self._definitions.values())

    def get(self, extractor_id: str) -> ExtractorDefinition | None:
        return self._definitions.get(extractor_id)

    def queries_hash(self) -> str:
        parts: list[str] = []
        for definition in sorted(self.enabled, key=lambda d: d.id):
            query_text = definition.query_file.read_text(encoding="utf-8")
            parts.append(f"{definition.id}:{definition.version}:{query_text}")
        return sha256_text("\n---\n".join(parts))

    def config_hash(self, raw_config: dict) -> str:
        from semantic_selector.models import sha256_json

        return sha256_json(raw_config)

    def query_hash(self, definition: ExtractorDefinition) -> str:
        query_text = definition.query_file.read_text(encoding="utf-8")
        return sha256_text(f"{definition.id}:{definition.version}:{query_text}")
