from __future__ import annotations

from typing import Any


def split_pipe_text(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(" | ") if part.strip()]


def build_term_evidence(
    row: dict[str, Any],
    *,
    reuse_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    definitions = split_pipe_text(row.get("definitions_text"))
    synonyms = split_pipe_text(row.get("synonyms_text"))
    language_tags = split_pipe_text(row.get("language_tags_text"))
    reuse = reuse_info or {}
    artifact_ids = reuse.get("artifact_ids") or []
    return {
        "has_definition": bool(definitions),
        "definitions": definitions,
        "synonyms": synonyms,
        "parent_count": int(row.get("parent_count") or 0),
        "child_count": int(row.get("child_count") or 0),
        "mapping_count": int(row.get("mapping_count") or 0),
        "language_tags": language_tags,
        "term_reuse_count_by_iri": int(reuse.get("reuse_count") or 0),
        "term_reuse_artifact_ids": [a for a in artifact_ids if a != row.get("artifact_id")],
        "is_obsolete": bool(row.get("is_obsolete")),
    }


def compute_term_match_frequency(matched_queries: int, total_queries: int) -> float:
    if total_queries <= 0:
        return 0.0
    return round(matched_queries / total_queries, 4)
