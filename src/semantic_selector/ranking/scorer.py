from __future__ import annotations

from typing import Any

COUNT_BASED_RANKING_CRITERIA = frozenset({"inbound_owl_import_count"})


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    filtered = {k: max(0.0, float(v)) for k, v in weights.items()}
    total = sum(filtered.values())
    if total <= 0:
        raise ValueError("Weights must sum to a positive value")
    return {k: v / total for k, v in filtered.items()}


def compute_overall_score(
    *,
    term_match_frequency: float,
    criterion_scores: dict[str, float],
    weights: dict[str, float],
) -> float:
    normalized = normalize_weights(weights)
    score = normalized.get("term_match_frequency", 0.0) * term_match_frequency
    for criterion_id, criterion_value in criterion_scores.items():
        if criterion_id in normalized:
            score += normalized[criterion_id] * criterion_value
    return round(score, 4)


def normalize_candidate_count_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    if not raw_scores:
        return {}
    min_s = min(raw_scores.values())
    max_s = max(raw_scores.values())
    if max_s == min_s:
        return {key: (1.0 if max_s > 0 else 0.0) for key in raw_scores}
    return {
        key: round((value - min_s) / (max_s - min_s), 4)
        for key, value in raw_scores.items()
    }


def apply_count_criterion_normalization(
    *,
    artifact_scores: dict[str, dict[str, float]],
    ranking_weights: dict[str, float],
) -> dict[str, dict[str, float]]:
    normalized = {artifact_id: dict(scores) for artifact_id, scores in artifact_scores.items()}
    for criterion_id in COUNT_BASED_RANKING_CRITERIA:
        if criterion_id not in ranking_weights or ranking_weights[criterion_id] <= 0:
            continue
        raw = {
            artifact_id: scores.get(criterion_id, 0.0)
            for artifact_id, scores in artifact_scores.items()
            if criterion_id in scores
        }
        scaled = normalize_candidate_count_scores(raw)
        for artifact_id, value in scaled.items():
            normalized[artifact_id][criterion_id] = value
    return normalized


def normalize_bm25_scores(scores: list[float]) -> list[float]:
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        return [1.0 for _ in scores]
    return [(max_s - s) / (max_s - min_s) for s in scores]
