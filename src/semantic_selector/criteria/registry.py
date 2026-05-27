from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CriterionConfig:
    id: str
    display_name: str
    description: str
    category: str | None
    source_criterion: str | None
    applies_to: list[str]
    role: str
    evaluation_stage: str
    enabled: bool
    table_aligned: bool
    default_weight: float
    evaluator: str | None = None
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_yaml_item(cls, item: dict[str, Any]) -> CriterionConfig:
        filter_keys = {
            "allowed_artifact_ids",
            "blocked_artifact_ids",
            "allowed_term_iris",
            "blocked_term_iris",
        }
        config = {k: item[k] for k in filter_keys if k in item}
        return cls(
            id=str(item["id"]),
            display_name=str(item.get("display_name", item["id"])),
            description=str(item.get("description", "")),
            category=item.get("category"),
            source_criterion=item.get("source_criterion"),
            applies_to=[str(v) for v in item.get("applies_to", [])],
            role=str(item.get("role", "evidence")),
            evaluation_stage=str(item.get("evaluation_stage", "index_build")),
            enabled=bool(item.get("enabled", True)),
            table_aligned=bool(item.get("table_aligned", False)),
            default_weight=float(item.get("default_weight", 0.0)),
            evaluator=item.get("evaluator"),
            config=config,
        )


def load_criteria_config(raw: dict[str, Any]) -> list[CriterionConfig]:
    return [CriterionConfig.from_yaml_item(item) for item in raw.get("criteria", [])]


def default_ranking_weights(configs: list[CriterionConfig]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for cfg in configs:
        if cfg.role in {"ranking", "ranking_and_evidence"} and cfg.default_weight > 0:
            weights[cfg.id] = cfg.default_weight
    if not weights:
        return {
            "term_match_frequency": 0.50,
            "definition_coverage": 0.35,
            "inbound_owl_import_count": 0.15,
        }
    return weights
