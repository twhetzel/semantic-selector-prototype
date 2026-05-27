from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class EnforcedSelectionConfig:
    enabled: bool
    allowed_artifact_ids: frozenset[str]
    blocked_artifact_ids: frozenset[str]
    allowed_term_iris: frozenset[str]
    blocked_term_iris: frozenset[str]


def parse_enforced_selection_config(config_json: str | None) -> EnforcedSelectionConfig:
    if not config_json:
        return EnforcedSelectionConfig(False, frozenset(), frozenset(), frozenset(), frozenset())
    import json

    raw = json.loads(config_json)
    return EnforcedSelectionConfig(
        enabled=True,
        allowed_artifact_ids=frozenset(raw.get("allowed_artifact_ids") or []),
        blocked_artifact_ids=frozenset(raw.get("blocked_artifact_ids") or []),
        allowed_term_iris=frozenset(raw.get("allowed_term_iris") or []),
        blocked_term_iris=frozenset(raw.get("blocked_term_iris") or []),
    )


def apply_enforced_selection(
    *,
    artifact_id: str,
    term_iri: str | None,
    config: EnforcedSelectionConfig,
) -> str | None:
    if not config.enabled:
        return None
    if config.allowed_artifact_ids and artifact_id not in config.allowed_artifact_ids:
        return f"artifact {artifact_id!r} not in allowed_artifact_ids"
    if artifact_id in config.blocked_artifact_ids:
        return f"artifact {artifact_id!r} is blocked"
    if term_iri:
        if config.allowed_term_iris and term_iri not in config.allowed_term_iris:
            return f"term {term_iri!r} not in allowed_term_iris"
        if term_iri in config.blocked_term_iris:
            return f"term {term_iri!r} is blocked"
    return None
