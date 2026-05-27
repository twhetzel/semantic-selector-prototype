from __future__ import annotations

import re
from typing import Any

from semantic_selector.extractors.normalization import normalize_label

MATCH_TIER_ORDER: dict[str, int] = {
    "curie_exact": 0,
    "preferred_label_exact": 1,
    "synonym_exact": 2,
    "preferred_label_prefix": 3,
    "preferred_label_word": 4,
    "synonym_text_match": 5,
    "preferred_label_text_match": 6,
    "definition_text_match": 7,
    "unknown": 99,
}


def obo_id_from_term_iri(term_iri: str) -> str | None:
    if "/obo/" not in term_iri:
        return None
    local = term_iri.rsplit("/", 1)[-1]
    if "_" not in local:
        return None
    prefix, rest = local.split("_", 1)
    return f"{prefix}:{rest}"


def curie_to_obo_iri(query: str) -> str | None:
    candidate = query.strip()
    if not re.fullmatch(r"[\w-]+:[\w-]+", candidate, flags=re.IGNORECASE):
        return None
    prefix, local = candidate.split(":", 1)
    return f"http://purl.obolibrary.org/obo/{prefix.upper()}_{local}"


def is_curie_query(query: str) -> bool:
    return curie_to_obo_iri(query) is not None


def _split_synonyms(synonyms_text: str) -> list[str]:
    return [part.strip() for part in synonyms_text.split(" | ") if part.strip()]


def _label_tokens(text: str) -> list[str]:
    return re.findall(r"\w+", normalize_label(text), flags=re.UNICODE)


def classify_term_match(row: dict[str, Any], query: str) -> str:
    query_norm = normalize_label(query)
    if not query_norm:
        return "unknown"

    term_iri = str(row.get("term_iri") or "")
    obo_id = obo_id_from_term_iri(term_iri)
    if obo_id and query_norm == normalize_label(obo_id):
        return "curie_exact"

    preferred = row.get("preferred_label") or ""
    preferred_norm = normalize_label(preferred)
    synonyms = _split_synonyms(row.get("synonyms_text") or "")
    definitions = _split_synonyms(row.get("definitions_text") or "")

    if preferred_norm == query_norm:
        return "preferred_label_exact"

    for synonym in synonyms:
        if normalize_label(synonym) == query_norm:
            return "synonym_exact"

    if preferred_norm.startswith(f"{query_norm} "):
        return "preferred_label_prefix"

    if query_norm in _label_tokens(preferred):
        return "preferred_label_word"

    for synonym in synonyms:
        synonym_norm = normalize_label(synonym)
        if query_norm in synonym_norm and query_norm != synonym_norm:
            return "synonym_text_match"

    if query_norm in preferred_norm:
        return "preferred_label_text_match"

    definitions_norm = normalize_label(" | ".join(definitions))
    if query_norm in definitions_norm:
        return "definition_text_match"

    return "unknown"


def term_match_sort_key(
    row: dict[str, Any],
    *,
    query: str,
    ontology_score: float = 0.0,
    bm25_score: float = 0.0,
) -> tuple[int, float, float, str]:
    match_type = classify_term_match(row, query)
    tier = MATCH_TIER_ORDER.get(match_type, MATCH_TIER_ORDER["unknown"])
    return (
        tier,
        -ontology_score,
        bm25_score,
        str(row.get("term_iri") or ""),
    )


def rank_term_rows(
    rows: list[dict[str, Any]],
    *,
    query: str,
    bm25_scores: list[float],
    ontology_scores: dict[str, float] | None = None,
) -> list[tuple[dict[str, Any], float, str]]:
    score_lookup = ontology_scores or {}
    ranked: list[tuple[dict[str, Any], float, str, tuple[int, float, float, str]]] = []
    for row, bm25_score in zip(rows, bm25_scores, strict=True):
        match_type = classify_term_match(row, query)
        artifact_id = str(row.get("artifact_id") or "")
        sort_key = term_match_sort_key(
            row,
            query=query,
            ontology_score=score_lookup.get(artifact_id, 0.0),
            bm25_score=bm25_score,
        )
        ranked.append((row, bm25_score, match_type, sort_key))
    ranked.sort(key=lambda item: item[3])
    return [(row, bm25, match_type) for row, bm25, match_type, _ in ranked]


def compute_lexical_text_scores(count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [1.0]
    return [round(1.0 - (index / (count - 1)), 4) for index in range(count)]
